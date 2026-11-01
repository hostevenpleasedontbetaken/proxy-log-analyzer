"""Create the core tables: uploads, upload_files, log_entries, incidents, anomalies,
anomaly_entries (Phase 2 design; see app/models.py).

Revision ID: 148e82d85688
Revises:
Create Date: 2026-11-01 22:01:20.714765
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "148e82d85688"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "uploads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_uid", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("line_count", sa.Integer(), nullable=True),
        sa.Column("parsed_count", sa.Integer(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=True),
        sa.Column("parse_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("time_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("parser_version", sa.Text(), nullable=True),
        sa.Column("detector_version", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('processing', 'ready', 'failed')", name=op.f("ck_uploads_status_valid")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploads")),
        sa.UniqueConstraint("owner_uid", "sha256", name=op.f("uq_uploads_owner_uid_sha256")),
    )
    op.create_index(
        "ix_uploads_owner_newest_first",
        "uploads",
        ["owner_uid", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_table(
        "incidents",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("severity", sa.SmallInteger(), nullable=False),
        sa.Column("confidence", sa.REAL(), nullable=False),
        sa.Column("start_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_ts", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_incidents_confidence_range")
        ),
        sa.CheckConstraint("severity BETWEEN 1 AND 4", name=op.f("ck_incidents_severity_range")),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["uploads.id"],
            name=op.f("fk_incidents_upload_id_uploads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
    )
    op.create_index(
        op.f("ix_incidents_upload_id_start_ts"),
        "incidents",
        ["upload_id", "start_ts"],
        unique=False,
    )
    op.create_table(
        "log_entries",
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("record_id", sa.BigInteger(), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tz", sa.Text(), nullable=True),
        sa.Column("login", sa.Text(), nullable=True),
        sa.Column("dept", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("devicehostname", sa.Text(), nullable=True),
        sa.Column("cltip", postgresql.INET(), nullable=True),
        sa.Column("serverip", postgresql.INET(), nullable=True),
        sa.Column("dstip_country", sa.Text(), nullable=True),
        sa.Column("host", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("reqmethod", sa.Text(), nullable=True),
        sa.Column("respcode", sa.SmallInteger(), nullable=True),
        sa.Column("proto", sa.Text(), nullable=True),
        sa.Column("useragent", sa.Text(), nullable=True),
        sa.Column("refererhost", sa.Text(), nullable=True),
        sa.Column("contenttype", sa.Text(), nullable=True),
        sa.Column("reqsize", sa.BigInteger(), nullable=True),
        sa.Column("respsize", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("rulelabel", sa.Text(), nullable=True),
        sa.Column("ruletype", sa.Text(), nullable=True),
        sa.Column("urlsubcat", sa.Text(), nullable=True),
        sa.Column("urlsupercat", sa.Text(), nullable=True),
        sa.Column("urlclass", sa.Text(), nullable=True),
        sa.Column("appname", sa.Text(), nullable=True),
        sa.Column("appclass", sa.Text(), nullable=True),
        sa.Column("threatname", sa.Text(), nullable=True),
        sa.Column("threatseverity", sa.Text(), nullable=True),
        sa.Column("malwarecategory", sa.Text(), nullable=True),
        sa.Column("malwareclass", sa.Text(), nullable=True),
        sa.Column("riskscore", sa.SmallInteger(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("filetype", sa.Text(), nullable=True),
        sa.Column("upload_filename", sa.Text(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("anomaly_confidence", sa.REAL(), nullable=True),
        sa.Column("max_severity", sa.SmallInteger(), nullable=True),
        sa.CheckConstraint(
            "max_severity BETWEEN 1 AND 4", name=op.f("ck_log_entries_max_severity_range")
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["uploads.id"],
            name=op.f("fk_log_entries_upload_id_uploads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("upload_id", "line_no", name=op.f("pk_log_entries")),
    )
    op.create_index(
        "ix_log_entries_flagged",
        "log_entries",
        ["upload_id", sa.literal_column("anomaly_confidence DESC")],
        unique=False,
        postgresql_where=sa.text("anomaly_confidence IS NOT NULL"),
    )
    op.create_index(
        op.f("ix_log_entries_upload_id_cltip"), "log_entries", ["upload_id", "cltip"], unique=False
    )
    op.create_index(
        op.f("ix_log_entries_upload_id_login"), "log_entries", ["upload_id", "login"], unique=False
    )
    op.create_index(
        op.f("ix_log_entries_upload_id_ts_line_no"),
        "log_entries",
        ["upload_id", "ts", "line_no"],
        unique=False,
    )
    op.create_table(
        "upload_files",
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("raw_gz", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["uploads.id"],
            name=op.f("fk_upload_files_upload_id_uploads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("upload_id", name=op.f("pk_upload_files")),
    )
    # The file is already gzipped: tell Postgres to store it out of line without compressing
    # it again (autogenerate can't express this, so it's written by hand).
    op.execute("ALTER TABLE upload_files ALTER COLUMN raw_gz SET STORAGE EXTERNAL")
    op.create_table(
        "anomalies",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.BigInteger(), nullable=True),
        sa.Column("detector", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("confidence", sa.REAL(), nullable=False),
        sa.Column("severity", sa.SmallInteger(), nullable=False),
        sa.Column("start_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "detector IN ('rule', 'statistical', 'ml')", name=op.f("ck_anomalies_detector_valid")
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_anomalies_confidence_range")
        ),
        sa.CheckConstraint("severity BETWEEN 1 AND 4", name=op.f("ck_anomalies_severity_range")),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_anomalies_incident_id_incidents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["uploads.id"],
            name=op.f("fk_anomalies_upload_id_uploads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anomalies")),
    )
    op.create_index(
        "ix_anomalies_by_confidence",
        "anomalies",
        ["upload_id", sa.literal_column("confidence DESC")],
        unique=False,
    )
    op.create_index(op.f("ix_anomalies_incident_id"), "anomalies", ["incident_id"], unique=False)
    op.create_table(
        "anomaly_entries",
        sa.Column("anomaly_id", sa.BigInteger(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["anomaly_id"],
            ["anomalies.id"],
            name=op.f("fk_anomaly_entries_anomaly_id_anomalies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["upload_id", "line_no"],
            ["log_entries.upload_id", "log_entries.line_no"],
            name=op.f("fk_anomaly_entries_upload_id_line_no_log_entries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("anomaly_id", "line_no", name=op.f("pk_anomaly_entries")),
    )
    op.create_index(
        op.f("ix_anomaly_entries_upload_id_line_no"),
        "anomaly_entries",
        ["upload_id", "line_no"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_anomaly_entries_upload_id_line_no"), table_name="anomaly_entries")
    op.drop_table("anomaly_entries")
    op.drop_index(op.f("ix_anomalies_incident_id"), table_name="anomalies")
    op.drop_index("ix_anomalies_by_confidence", table_name="anomalies")
    op.drop_table("anomalies")
    op.drop_table("upload_files")
    op.drop_index(op.f("ix_log_entries_upload_id_ts_line_no"), table_name="log_entries")
    op.drop_index(op.f("ix_log_entries_upload_id_login"), table_name="log_entries")
    op.drop_index(op.f("ix_log_entries_upload_id_cltip"), table_name="log_entries")
    op.drop_index(
        "ix_log_entries_flagged",
        table_name="log_entries",
        postgresql_where=sa.text("anomaly_confidence IS NOT NULL"),
    )
    op.drop_table("log_entries")
    op.drop_index(op.f("ix_incidents_upload_id_start_ts"), table_name="incidents")
    op.drop_table("incidents")
    op.drop_index("ix_uploads_owner_newest_first", table_name="uploads")
    op.drop_table("uploads")
