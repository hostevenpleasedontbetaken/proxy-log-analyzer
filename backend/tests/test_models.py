"""Database tests: run against a real Postgres (the separate tenex_test database in docker
compose), because inet, JSONB, partial indexes and cascades are Postgres features.

Run with: make test-backend
"""

import os
import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.db import sqlalchemy_url
from app.models import Anomaly, AnomalyEntry, Incident, LogEntry, Upload, UploadFile

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="needs TEST_DATABASE_URL")

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def _alembic(url: str) -> Config:
    os.environ["DATABASE_URL"] = url  # migrations/env.py reads it
    return Config("alembic.ini")


@pytest.fixture(scope="module")
def engine():
    """Fresh schema from the migrations: drop everything, then upgrade to the latest."""
    previous = os.environ.get("DATABASE_URL")
    config = _alembic(TEST_DATABASE_URL)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    eng = create_engine(sqlalchemy_url(TEST_DATABASE_URL))
    yield eng
    eng.dispose()
    if previous is not None:
        os.environ["DATABASE_URL"] = previous


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s
        s.rollback()
    with engine.begin() as conn:  # leave the tables empty for the next test
        conn.execute(text("TRUNCATE uploads CASCADE"))


def make_upload(session: Session, owner: str = "alice", sha: str = "abc") -> Upload:
    upload = Upload(owner_uid=owner, filename="acme.ndjson", size_bytes=10, sha256=sha)
    session.add(upload)
    session.flush()  # sends the INSERT now so upload.id exists
    return upload


def make_anomaly(upload: Upload, **overrides) -> Anomaly:
    values = dict(
        upload_id=upload.id, detector="rule", kind="malware_download", subject_type="user",
        subject="alice", title="Malware blocked", explanation="Blocked .exe", confidence=0.9,
        severity=4, start_ts=NOW, end_ts=NOW, entry_count=1,
    )  # fmt: skip
    return Anomaly(**{**values, **overrides})


def test_migrations_match_the_models(engine):
    # Fails if someone changes app/models.py without generating a migration.
    command.check(_alembic(TEST_DATABASE_URL))


def test_deleting_an_upload_deletes_everything_under_it(session):
    upload = make_upload(session)
    session.add(UploadFile(upload_id=upload.id, raw_gz=b"\x1f\x8b..."))
    session.add_all([LogEntry(upload_id=upload.id, line_no=n, ts=NOW) for n in (1, 2)])
    incident = Incident(
        upload_id=upload.id, subject_type="user", subject="alice", title="Malware",
        severity=4, confidence=0.9, start_ts=NOW, end_ts=NOW,
    )  # fmt: skip
    session.add(incident)
    session.flush()
    anomaly = make_anomaly(upload, incident_id=incident.id)
    session.add(anomaly)
    session.flush()
    session.add(AnomalyEntry(anomaly_id=anomaly.id, upload_id=upload.id, line_no=2))
    session.commit()

    session.delete(upload)
    session.commit()

    for model in (UploadFile, LogEntry, Incident, Anomaly, AnomalyEntry):
        assert session.scalar(select(func.count()).select_from(model)) == 0, model.__name__


def test_same_file_twice_is_rejected_for_the_same_owner_only(session):
    make_upload(session, owner="alice", sha="same")
    make_upload(session, owner="bob", sha="same")  # a different user may upload it
    with pytest.raises(IntegrityError):
        make_upload(session, owner="alice", sha="same")


def test_ip_columns_reject_invalid_addresses(session):
    upload = make_upload(session)
    session.add(LogEntry(upload_id=upload.id, line_no=1, ts=NOW, cltip="10.20.1.12"))
    session.flush()
    session.add(LogEntry(upload_id=upload.id, line_no=2, ts=NOW, cltip="not-an-ip"))
    with pytest.raises(DataError):
        session.flush()


@pytest.mark.parametrize(
    "overrides",
    [{"severity": 5}, {"confidence": 1.5}, {"confidence": -0.1}, {"detector": "magic"}],
)
def test_anomaly_values_are_checked_by_the_database(session, overrides):
    upload = make_upload(session)
    session.add(make_anomaly(upload, **overrides))
    with pytest.raises(IntegrityError):
        session.flush()


def test_upload_status_must_be_known(session):
    upload = make_upload(session)
    upload.status = "done"
    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_an_incident_keeps_its_anomalies(session):
    upload = make_upload(session)
    incident = Incident(
        upload_id=upload.id, subject_type="user", subject="alice", title="x",
        severity=2, confidence=0.5, start_ts=NOW, end_ts=NOW,
    )  # fmt: skip
    session.add(incident)
    session.flush()
    anomaly = make_anomaly(upload, incident_id=incident.id)
    session.add(anomaly)
    session.commit()

    session.delete(incident)
    session.commit()
    session.refresh(anomaly)
    assert anomaly.incident_id is None


def test_raw_file_is_not_compressed_twice(session):
    storage = session.scalar(
        text(
            "SELECT attstorage FROM pg_attribute "
            "WHERE attrelid = 'upload_files'::regclass AND attname = 'raw_gz'"
        )
    )
    assert storage == "e"  # EXTERNAL: out of line, no Postgres compression


def test_new_uploads_get_an_id_status_and_timestamp(session):
    upload = make_upload(session, sha=uuid.uuid4().hex)
    session.commit()
    session.refresh(upload)
    assert isinstance(upload.id, uuid.UUID)
    assert upload.status == "processing"
    assert upload.created_at is not None
