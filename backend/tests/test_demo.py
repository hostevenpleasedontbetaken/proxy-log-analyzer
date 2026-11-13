"""Guest mode: the shared sample analysis is readable by everyone and changeable by no one."""

import io
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.demo import SAMPLE_PATH, seed_demo
from app.models import DEMO_OWNER_UID, Upload

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
SMALL = (SAMPLES / "acme-web-small.ndjson").read_bytes()
CLEAN = (SAMPLES / "acme-web-clean.ndjson").read_bytes()


@pytest.fixture
def sample_id(api, db_engine):
    """Seed the sample analysis (from the small log, to keep tests quick); returns its id."""
    with Session(db_engine) as session, session.begin():
        seed_demo(session, SMALL)
        return str(session.scalar(select(Upload.id).where(Upload.owner_uid == DEMO_OWNER_UID)))


def guest_get(api, uid, path):
    return api.client.get(path, headers=api.guest(uid))


def test_bundled_sample_matches_the_repo_sample():
    repo_copy = SAMPLES / "acme-web-day.ndjson.gz"
    if not repo_copy.exists():
        pytest.skip("needs the samples folder (run with make test-backend)")
    assert SAMPLE_PATH.read_bytes() == repo_copy.read_bytes()


def test_me_says_whether_the_user_is_a_guest(api):
    assert api.get("alice", "/api/me").json["is_guest"] is False
    assert guest_get(api, "visitor", "/api/me").json["is_guest"] is True


def test_guest_sees_only_the_sample_in_their_list(api, sample_id):
    api.upload("alice", CLEAN)  # someone else's private upload
    uploads = guest_get(api, "visitor", "/api/uploads").json["uploads"]
    assert [(u["id"], u["is_sample"]) for u in uploads] == [(sample_id, True)]


def test_signed_in_users_see_the_sample_next_to_their_own(api, sample_id):
    own = api.upload("alice", CLEAN).json["id"]
    uploads = {u["id"]: u["is_sample"] for u in api.get("alice", "/api/uploads").json["uploads"]}
    assert uploads == {sample_id: True, own: False}


@pytest.mark.parametrize("suffix", ["", "/entries", "/incidents", "/anomalies", "/entries/1"])
def test_guest_can_read_every_view_of_the_sample(api, sample_id, suffix):
    res = guest_get(api, "visitor", f"/api/uploads/{sample_id}{suffix}")
    assert res.status_code == 200


def test_guest_cannot_read_someone_elses_upload(api, sample_id):
    private = api.upload("alice", CLEAN).json["id"]
    for suffix in ["", "/entries", "/incidents", "/anomalies", "/entries/1"]:
        res = guest_get(api, "visitor", f"/api/uploads/{private}{suffix}")
        assert res.status_code == 404, suffix


def test_guest_cannot_upload(api):
    res = api.client.post(
        "/api/uploads",
        data={"file": (io.BytesIO(SMALL), "acme.ndjson")},
        headers=api.guest("visitor"),
        content_type="multipart/form-data",
    )
    assert res.status_code == 403
    assert res.json["error"]["code"] == "guest_read_only"


def test_nobody_can_delete_the_sample(api, db_engine, sample_id):
    assert api.delete("alice", f"/api/uploads/{sample_id}").status_code == 404
    res = api.client.delete(f"/api/uploads/{sample_id}", headers=api.guest("visitor"))
    assert res.status_code == 404
    with Session(db_engine) as session:
        assert session.get(Upload, sample_id) is not None


def test_seeding_is_idempotent_and_rebuilds_when_versions_change(db_engine):
    def run():
        with Session(db_engine) as session, session.begin():
            return seed_demo(session, SMALL)

    def sample_rows():
        with Session(db_engine) as session:
            return session.scalar(
                select(func.count()).select_from(Upload).where(Upload.owner_uid == DEMO_OWNER_UID)
            )

    assert run() == "created"
    assert run() == "unchanged"
    with Session(db_engine) as session, session.begin():  # pretend an older detector made it
        session.execute(
            Upload.__table__.update()
            .where(Upload.owner_uid == DEMO_OWNER_UID)
            .values(detector_version="old")
        )
    assert run() == "refreshed"
    assert run() == "unchanged"
    assert sample_rows() == 1
    with Session(db_engine) as session, session.begin():
        session.execute(Upload.__table__.delete())  # leave the tables empty for the next test
