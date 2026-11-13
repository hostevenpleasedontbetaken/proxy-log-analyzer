"""What happens when a file is uploaded, and the ownership rule for every upload lookup.

    check duplicate + quota ─► parse ─► detect ─► stats   (all in memory)
        ─► ONE transaction: uploads row + upload_files (original, gzipped)
                            + log_entries (bulk COPY) + incidents + anomalies + links

Everything is computed before anything is written, so a bad file stores nothing, and the
single transaction means a crash halfway leaves no half-saved upload behind.
"""

import gzip
import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.detection import DETECTOR_VERSION, Detection, detect
from app.detection.findings import band
from app.detection.ml import MIN_USER_HOURS
from app.errors import ApiError
from app.models import DEMO_OWNER_UID, Anomaly, Incident, Upload, UploadFile
from app.parsing import PARSER_VERSION, ParseFailure, parse_upload
from app.parsing.fields import COLUMNS
from app.parsing.reader import GZIP_MAGIC
from app.retention import delete_expired
from app.stats import compute_stats, to_frame

MAX_UPLOADS_PER_USER = 3  # per person
# Across everyone's uploads (the shared sample is exempt). Measured: 18,654 entries take about
# 13 MB (rows plus indexes), so 400k entries is roughly 280 MB: well inside Neon's free storage,
# so open sign-up can't fill the database.
MAX_STORED_ENTRIES = 400_000
MAX_FILENAME_CHARS = 255

# log_entries columns, in the order COPY sends them: parser fields + detection's highlight.
ENTRY_COLUMNS = ["upload_id", "line_no", "ts", *COLUMNS, "anomaly_confidence", "max_severity"]
SEVERITY_NAMES = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}


def owned_upload_or_404(session: Session, upload_id: uuid.UUID, owner_uid: str) -> Upload:
    """The only way routes load an upload. Someone else's upload gives the same 404 as a
    missing one, so ids can't be probed to discover what exists (IDOR protection)."""
    upload = session.get(Upload, upload_id)
    if upload is None or upload.owner_uid != owner_uid:
        raise ApiError(404, "not_found", "Upload not found.")
    return upload


def readable_upload_or_404(session: Session, upload_id: uuid.UUID, uid: str) -> Upload:
    """For routes that only READ an upload: your own, or the shared sample analysis. Anything
    else is the same 404 as a missing id. Routes that change data use owned_upload_or_404, so
    the sample can't be deleted by anyone."""
    upload = session.get(Upload, upload_id)
    if upload is None or upload.owner_uid not in (uid, DEMO_OWNER_UID):
        raise ApiError(404, "not_found", "Upload not found.")
    return upload


def _stored_entries(session: Session) -> int:
    """Log entries stored for everyone except the shared sample."""
    total = session.scalar(
        select(func.coalesce(func.sum(Upload.parsed_count), 0)).where(
            Upload.owner_uid != DEMO_OWNER_UID
        )
    )
    return int(total)


def _storage_full() -> ApiError:
    return ApiError(
        503,
        "storage_full",
        "The demo's free storage is full right now. Delete one of your uploads or try again later.",
    )


def create_upload(session: Session, *, owner_uid: str, filename: str, data: bytes) -> Upload:
    """Validate, parse and store one upload. The caller commits (or rolls back on error)."""
    capped = owner_uid != DEMO_OWNER_UID  # the shared sample has no caps and never expires
    if capped:
        delete_expired(session)  # first, so an expired upload neither counts nor blocks a re-upload
    sha256 = hashlib.sha256(data).hexdigest()
    existing = session.scalar(
        select(Upload).where(Upload.owner_uid == owner_uid, Upload.sha256 == sha256)
    )
    if existing:
        raise ApiError(
            409,
            "duplicate_upload",
            "You already uploaded this file.",
            existing_upload_id=str(existing.id),
        )
    owned = session.scalar(select(func.count()).where(Upload.owner_uid == owner_uid))
    if owned >= MAX_UPLOADS_PER_USER:
        raise ApiError(
            409,
            "upload_quota_exceeded",
            f"You can keep up to {MAX_UPLOADS_PER_USER} uploads. Delete one to add another.",
        )
    stored = _stored_entries(session) if capped else 0
    if capped and stored >= MAX_STORED_ENTRIES:
        raise _storage_full()

    try:
        parsed = parse_upload(data)
    except ParseFailure as failure:
        raise ApiError(422, failure.code, failure.message) from None
    if capped and stored + len(parsed.rows) > MAX_STORED_ENTRIES:
        raise _storage_full()
    df = to_frame(parsed.rows)
    detection = detect(df)
    stats = compute_stats(
        df,
        line_count=parsed.line_count,
        error_count=parsed.error_count,
        warnings=parsed.warnings,
        flagged_lines=detection.entry_scores.keys(),
    )
    stats["detection"] = detection_summary(detection)
    for row in parsed.rows:  # copy each entry's score onto it, for highlighting
        confidence, severity = detection.entry_scores.get(row["line_no"], (None, None))
        row["anomaly_confidence"], row["max_severity"] = confidence, severity

    now = datetime.now(UTC)
    upload = Upload(
        owner_uid=owner_uid,
        filename=filename[:MAX_FILENAME_CHARS],
        size_bytes=len(data),
        sha256=sha256,
        status="ready",
        line_count=parsed.line_count,
        parsed_count=parsed.parsed_count,
        error_count=parsed.error_count,
        parse_errors=parsed.parse_errors,
        time_start=parsed.time_start,
        time_end=parsed.time_end,
        stats=stats,
        parser_version=PARSER_VERSION,
        detector_version=DETECTOR_VERSION,
        created_at=now,
        processed_at=now,
    )
    session.add(upload)
    session.flush()  # sends the INSERT so upload.id can be used below

    # Keep the original as evidence (and for reprocessing). Already-gzipped uploads are kept
    # as they are; plain ones are gzipped.
    raw_gz = data if data.startswith(GZIP_MAGIC) else gzip.compress(data, compresslevel=6)
    session.add(UploadFile(upload_id=upload.id, raw_gz=raw_gz))
    copy_entries(session, upload.id, parsed.rows)
    save_detection(session, upload.id, detection)
    return upload


def detection_summary(detection: Detection) -> dict:
    """Counts for the Overview cards: incidents by confidence band and by severity."""
    by_band: dict[str, int] = {"High": 0, "Medium": 0, "Low": 0}
    by_severity: dict[str, int] = {name: 0 for name in SEVERITY_NAMES.values()}
    for incident in detection.incidents:
        by_band[band(incident.confidence)] += 1
        by_severity[SEVERITY_NAMES[incident.severity]] += 1
    return {
        "incidents": len(detection.incidents),
        "anomalies": len(detection.findings),
        "incidents_by_band": by_band,
        "incidents_by_severity": by_severity,
        # Isolation Forest needs enough active user-hours to learn what's normal.
        "ml": {
            "ran": detection.ml_ran,
            "active_user_hours": detection.ml_user_hours,
            "required_user_hours": MIN_USER_HOURS,
        },
    }


def save_detection(session: Session, upload_id: uuid.UUID, detection: Detection) -> None:
    """Incidents first (anomalies point at them), then anomalies, then which entries each
    anomaly covers (bulk COPY: beaconing alone can cover a thousand entries)."""
    links: list[tuple[int, int]] = []  # (anomaly id, line_no)
    for draft in detection.incidents:
        incident = Incident(
            upload_id=upload_id,
            subject_type=draft.subject_type,
            subject=draft.subject,
            title=draft.title,
            summary=draft.summary,
            severity=draft.severity,
            confidence=draft.confidence,
            start_ts=draft.start_ts,
            end_ts=draft.end_ts,
        )
        session.add(incident)
        session.flush()  # gives incident.id
        for finding in draft.findings:
            anomaly = Anomaly(
                upload_id=upload_id,
                incident_id=incident.id,
                detector=finding.layer,
                kind=finding.detector,
                subject_type=finding.subject_type,
                subject=finding.subject,
                title=finding.title,
                explanation=finding.explanation,
                confidence=finding.confidence,
                severity=finding.severity,
                start_ts=finding.start_ts,
                end_ts=finding.end_ts,
                entry_count=len(finding.line_nos),
                evidence={"family": finding.family, **finding.evidence},
            )
            session.add(anomaly)
            session.flush()  # gives anomaly.id
            links += [(anomaly.id, line_no) for line_no in finding.line_nos]

    psycopg_conn = session.connection().connection.driver_connection
    with (
        psycopg_conn.cursor() as cursor,
        cursor.copy("COPY anomaly_entries (anomaly_id, upload_id, line_no) FROM STDIN") as copy,
    ):
        for anomaly_id, line_no in links:
            copy.write_row([anomaly_id, upload_id, line_no])


def copy_entries(session: Session, upload_id: uuid.UUID, rows: list[dict]) -> None:
    """Bulk-insert entries with Postgres COPY: one streamed command instead of thousands of
    INSERTs (10-50x faster). It goes through the raw psycopg connection underneath SQLAlchemy,
    inside the same transaction, so it commits or rolls back with everything else."""
    session.flush()  # make sure the uploads row is sent before rows that reference it
    columns = ", ".join(ENTRY_COLUMNS)
    psycopg_conn = session.connection().connection.driver_connection
    with (
        psycopg_conn.cursor() as cursor,
        cursor.copy(f"COPY log_entries ({columns}) FROM STDIN") as copy,
    ):
        for row in rows:
            copy.write_row([upload_id, *(row[column] for column in ENTRY_COLUMNS[1:])])
