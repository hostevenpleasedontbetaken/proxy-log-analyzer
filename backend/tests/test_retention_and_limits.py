"""Uploads expire after a week, and uploading is rate limited."""

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import routes
from app.demo import seed_demo
from app.models import DEMO_OWNER_UID, LogEntry, Upload
from app.ratelimit import RateLimiter
from app.retention import RETENTION_DAYS

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
SMALL = (SAMPLES / "acme-web-small.ndjson").read_bytes()
CLEAN = (SAMPLES / "acme-web-clean.ndjson").read_bytes()


def age(db_engine, upload_id, days):
    with Session(db_engine) as session, session.begin():
        session.execute(
            update(Upload)
            .where(Upload.id == upload_id)
            .values(created_at=func.now() - timedelta(days=days))
        )


def test_old_uploads_are_deleted_with_everything_derived_from_them(api, db_engine):
    old = api.upload("alice", SMALL).json["id"]
    age(db_engine, old, RETENTION_DAYS + 1)
    api.upload("bob", CLEAN)  # any new upload clears out the expired ones first
    with Session(db_engine) as session:
        assert session.get(Upload, old) is None
        assert session.scalar(select(func.count()).where(LogEntry.upload_id == old)) == 0


def test_recent_uploads_are_kept(api, db_engine):
    recent = api.upload("alice", SMALL).json["id"]
    age(db_engine, recent, RETENTION_DAYS - 1)
    api.upload("bob", CLEAN)
    with Session(db_engine) as session:
        assert session.get(Upload, recent) is not None


def test_the_shared_sample_never_expires(api, db_engine):
    with Session(db_engine) as session, session.begin():
        seed_demo(session, SMALL)
        sample = session.scalar(select(Upload.id).where(Upload.owner_uid == DEMO_OWNER_UID))
    age(db_engine, sample, 365)
    api.upload("alice", CLEAN)
    with Session(db_engine) as session:
        assert session.get(Upload, sample) is not None


def test_an_expired_upload_can_be_uploaded_again(api, db_engine):
    old = api.upload("alice", SMALL).json["id"]
    age(db_engine, old, RETENTION_DAYS + 1)
    assert api.upload("alice", SMALL).status_code == 201  # not a duplicate any more


def test_limiter_counts_a_sliding_window():
    limiter = RateLimiter()
    assert limiter.allow("k", 2, 60, now=0)
    assert limiter.allow("k", 2, 60, now=10)
    assert not limiter.allow("k", 2, 60, now=20)  # third hit inside the minute
    assert limiter.allow("k", 2, 60, now=61)  # the first hit has aged out
    assert limiter.allow("other", 2, 60, now=20)  # keys are independent


def test_uploads_are_rate_limited_per_person(api, monkeypatch):
    monkeypatch.setattr(routes, "UPLOADS_PER_USER_PER_HOUR", 1)
    assert api.upload("alice", SMALL).status_code == 201
    res = api.upload("alice", CLEAN)
    assert res.status_code == 429
    assert res.json["error"]["code"] == "rate_limited"
    assert api.upload("bob", CLEAN).status_code == 201  # someone else is unaffected


def test_uploads_are_rate_limited_overall(api, monkeypatch):
    monkeypatch.setattr(routes, "UPLOADS_PER_HOUR_OVERALL", 1)
    assert api.upload("alice", SMALL).status_code == 201
    assert api.upload("bob", CLEAN).status_code == 429


@pytest.mark.parametrize("uid", ["alice"])
def test_reading_is_not_rate_limited(api, uid, monkeypatch):
    monkeypatch.setattr(routes, "UPLOADS_PER_USER_PER_HOUR", 1)
    for _ in range(5):
        assert api.get(uid, "/api/uploads").status_code == 200
