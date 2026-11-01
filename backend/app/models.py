"""Database tables (Phase 2 design). Each class is one table; each attribute is one column.

    uploads ─┬─ upload_files      1:1   the original file, gzipped (evidence; reprocessing)
             ├─ log_entries       1:N   one row per parsed log line
             ├─ incidents         1:N   related anomalies grouped into one story
             └─ anomalies         1:N   one detection, linked to the entries it covers
                    └─ anomaly_entries  N:M  which entries each anomaly covers

Deleting an upload deletes everything below it (ON DELETE CASCADE in the database).
There's no users table: Firebase owns identity, and uploads store the Firebase `owner_uid`.
"""

import uuid
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Any

from sqlalchemy import (
    REAL,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

IP = IPv4Address | IPv6Address
UPLOAD_STATUSES = ("processing", "ready", "failed")
DETECTORS = ("rule", "statistical", "ml")


def _severity_check() -> CheckConstraint:
    # 1 Low, 2 Medium, 3 High, 4 Critical: numbers sort correctly, words wouldn't.
    return CheckConstraint("severity BETWEEN 1 AND 4", name="severity_range")


def _confidence_check() -> CheckConstraint:
    return CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range")


class Upload(Base):
    __tablename__ = "uploads"
    __table_args__ = (
        # Uploading the exact same file twice returns the existing analysis.
        UniqueConstraint("owner_uid", "sha256"),
        CheckConstraint(f"status IN {UPLOAD_STATUSES}", name="status_valid"),
        # The uploads page: my uploads, newest first.
        Index("ix_uploads_owner_newest_first", "owner_uid", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_uid: Mapped[str] = mapped_column(Text)  # Firebase user id
    filename: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(Text)  # hex digest of the uploaded bytes
    status: Mapped[str] = mapped_column(Text, default="processing")
    error_message: Mapped[str | None] = mapped_column(Text)
    line_count: Mapped[int | None] = mapped_column(Integer)
    parsed_count: Mapped[int | None] = mapped_column(Integer)
    error_count: Mapped[int | None] = mapped_column(Integer)
    parse_errors: Mapped[list[Any] | None] = mapped_column(JSONB)  # first 20 bad lines
    time_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Totals, timeline buckets and top-10 lists, computed once when the upload is processed.
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    parser_version: Mapped[str | None] = mapped_column(Text)
    detector_version: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UploadFile(Base):
    """The original upload, gzipped. Kept in its own table so loading an `Upload` never drags
    a few MB of bytes along by accident."""

    __tablename__ = "upload_files"

    upload_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("uploads.id", ondelete="CASCADE"), primary_key=True
    )
    raw_gz: Mapped[bytes] = mapped_column(LargeBinary)


class LogEntry(Base):
    """One parsed log line. Field names follow the Zscaler template where one exists."""

    __tablename__ = "log_entries"
    __table_args__ = (
        Index(None, "upload_id", "ts", "line_no"),  # the log table, in time order
        Index(None, "upload_id", "login"),
        Index(None, "upload_id", "cltip"),
        # "Flagged only", most suspicious first. Partial: only flagged rows are indexed.
        Index(
            "ix_log_entries_flagged",
            "upload_id",
            text("anomaly_confidence DESC"),
            postgresql_where=text("anomaly_confidence IS NOT NULL"),
        ),
        CheckConstraint("max_severity BETWEEN 1 AND 4", name="max_severity_range"),
    )

    # The line's position in the file: unique within an upload, known before inserting, so
    # entries can be bulk-loaded with COPY and linked to anomalies without fetching ids back.
    upload_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("uploads.id", ondelete="CASCADE"), primary_key=True
    )
    line_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int | None] = mapped_column(BigInteger)  # Zscaler's recordid
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tz: Mapped[str | None] = mapped_column(Text)
    # Who
    login: Mapped[str | None] = mapped_column(Text)
    dept: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    devicehostname: Mapped[str | None] = mapped_column(Text)
    # Network (inet: Postgres validates the address and supports subnet queries)
    cltip: Mapped[IP | None] = mapped_column(INET)
    serverip: Mapped[IP | None] = mapped_column(INET)
    dstip_country: Mapped[str | None] = mapped_column(Text)
    # Request
    host: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)  # decoded from b64url
    reqmethod: Mapped[str | None] = mapped_column(Text)
    respcode: Mapped[int | None] = mapped_column(SmallInteger)
    proto: Mapped[str | None] = mapped_column(Text)
    useragent: Mapped[str | None] = mapped_column(Text)
    refererhost: Mapped[str | None] = mapped_column(Text)
    contenttype: Mapped[str | None] = mapped_column(Text)
    reqsize: Mapped[int | None] = mapped_column(BigInteger)
    respsize: Mapped[int | None] = mapped_column(BigInteger)
    # Policy verdict
    action: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    rulelabel: Mapped[str | None] = mapped_column(Text)
    ruletype: Mapped[str | None] = mapped_column(Text)
    urlsubcat: Mapped[str | None] = mapped_column(Text)
    urlsupercat: Mapped[str | None] = mapped_column(Text)
    urlclass: Mapped[str | None] = mapped_column(Text)
    appname: Mapped[str | None] = mapped_column(Text)
    appclass: Mapped[str | None] = mapped_column(Text)
    # Threat
    threatname: Mapped[str | None] = mapped_column(Text)
    threatseverity: Mapped[str | None] = mapped_column(Text)
    malwarecategory: Mapped[str | None] = mapped_column(Text)
    malwareclass: Mapped[str | None] = mapped_column(Text)
    riskscore: Mapped[int | None] = mapped_column(SmallInteger)
    # Files
    filename: Mapped[str | None] = mapped_column(Text)
    filetype: Mapped[str | None] = mapped_column(Text)
    upload_filename: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)
    # Copied from the anomalies this entry belongs to (entries never change after processing),
    # so highlighting and "flagged only" need no join.
    anomaly_confidence: Mapped[float | None] = mapped_column(REAL)
    max_severity: Mapped[int | None] = mapped_column(SmallInteger)


class Incident(Base):
    """Related anomalies about the same subject (user, device, IP) close together in time."""

    __tablename__ = "incidents"
    __table_args__ = (
        _severity_check(),
        _confidence_check(),
        Index(None, "upload_id", "start_ts"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    upload_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("uploads.id", ondelete="CASCADE"))
    subject_type: Mapped[str] = mapped_column(Text)  # user | device | ip
    subject: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[int] = mapped_column(SmallInteger)
    confidence: Mapped[float] = mapped_column(REAL)
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Anomaly(Base):
    """One detection: what was found, why, how sure, and which entries it covers."""

    __tablename__ = "anomalies"
    __table_args__ = (
        _severity_check(),
        _confidence_check(),
        CheckConstraint(f"detector IN {DETECTORS}", name="detector_valid"),
        Index("ix_anomalies_by_confidence", "upload_id", text("confidence DESC")),
        Index(None, "incident_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    upload_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("uploads.id", ondelete="CASCADE"))
    # SET NULL: anomalies don't have to belong to an incident.
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"))
    detector: Mapped[str] = mapped_column(Text)  # rule | statistical | ml
    kind: Mapped[str] = mapped_column(Text)  # e.g. beaconing, burst, exfiltration
    subject_type: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(REAL)
    severity: Mapped[int] = mapped_column(SmallInteger)
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_count: Mapped[int] = mapped_column(Integer)
    # Detector-specific numbers that differ in shape per detector and are only displayed,
    # e.g. beaconing {"interval_mean": 60.2, "cv": 0.03}.
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class AnomalyEntry(Base):
    """Join table: one row per (anomaly, log entry) pair. Many-to-many because one burst
    covers hundreds of entries, and one entry can be in several anomalies."""

    __tablename__ = "anomaly_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["upload_id", "line_no"],
            ["log_entries.upload_id", "log_entries.line_no"],
            ondelete="CASCADE",
        ),
        Index(None, "upload_id", "line_no"),  # "which anomalies is this entry in?"
    )

    anomaly_id: Mapped[int] = mapped_column(
        ForeignKey("anomalies.id", ondelete="CASCADE"), primary_key=True
    )
    upload_id: Mapped[uuid.UUID] = mapped_column()
    line_no: Mapped[int] = mapped_column(Integer, primary_key=True)
