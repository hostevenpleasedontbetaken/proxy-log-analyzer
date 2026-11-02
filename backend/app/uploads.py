"""What happens when a file is uploaded, and the ownership rule for every upload lookup.

    check duplicate + quota ─► parse (in memory) ─► stats ─► ONE transaction:
        uploads row + upload_files (original, gzipped) + log_entries (bulk COPY)

Parsing happens before anything is written, so a bad file stores nothing, and the single
transaction means a crash halfway leaves no half-saved upload behind. Detection (M5) slots in
between stats and saving.
"""

import gzip
import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Upload, UploadFile
from app.parsing import PARSER_VERSION, ParseFailure, parse_upload
from app.parsing.fields import COLUMNS
from app.parsing.reader import GZIP_MAGIC
from app.stats import compute_stats, to_frame

MAX_UPLOADS_PER_USER = 10  # Neon's free tier has 1 GB; this keeps us well inside it
MAX_FILENAME_CHARS = 255

# log_entries columns filled by the parser, in the order COPY sends them.
ENTRY_COLUMNS = ["upload_id", "line_no", "ts", *COLUMNS]


def owned_upload_or_404(session: Session, upload_id: uuid.UUID, owner_uid: str) -> Upload:
    """The only way routes load an upload. Someone else's upload gives the same 404 as a
    missing one, so ids can't be probed to discover what exists (IDOR protection)."""
    upload = session.get(Upload, upload_id)
    if upload is None or upload.owner_uid != owner_uid:
        raise ApiError(404, "not_found", "Upload not found.")
    return upload


def create_upload(session: Session, *, owner_uid: str, filename: str, data: bytes) -> Upload:
    """Validate, parse and store one upload. The caller commits (or rolls back on error)."""
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

    try:
        parsed = parse_upload(data)
    except ParseFailure as failure:
        raise ApiError(422, failure.code, failure.message) from None
    stats = compute_stats(
        to_frame(parsed.rows),
        line_count=parsed.line_count,
        error_count=parsed.error_count,
        warnings=parsed.warnings,
    )

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
    return upload


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
