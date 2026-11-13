"""Upload endpoints against a real Postgres: POST/GET/DELETE /api/uploads."""

import gzip
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import create_app
from app.config import Config
from app.models import LogEntry, Upload, UploadFile
from tests.conftest import TEST_DATABASE_URL, Api

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
SMALL = (SAMPLES / "acme-web-small.ndjson").read_bytes()


def count(db_engine, model, **where) -> int:
    query = select(func.count()).select_from(model).filter_by(**where)
    with Session(db_engine) as session:
        return session.scalar(query)


def test_upload_parses_and_stores_everything(api, db_engine):
    res = api.upload("alice", SMALL, filename="acme-web-small.ndjson")
    assert res.status_code == 201
    body = res.json
    assert body["filename"] == "acme-web-small.ndjson"
    assert body["status"] == "ready"
    assert (body["line_count"], body["parsed_count"], body["error_count"]) == (1934, 1934, 0)
    assert body["stats"]["totals"]["requests"] == 1934
    assert body["time_start"].startswith("2026-10-20T00:")
    assert count(db_engine, LogEntry, upload_id=body["id"]) == 1934
    with Session(db_engine) as session:
        stored = session.get(UploadFile, body["id"]).raw_gz
    assert gzip.decompress(stored) == SMALL  # the original, kept as evidence


def test_gzipped_upload_is_stored_as_is(api, db_engine):
    day = (SAMPLES / "acme-web-day.ndjson.gz").read_bytes()
    res = api.upload("alice", day, filename="acme-web-day.ndjson.gz")
    assert res.status_code == 201
    assert res.json["parsed_count"] == 18_654
    with Session(db_engine) as session:
        assert session.get(UploadFile, res.json["id"]).raw_gz == day


def test_same_file_twice_returns_the_existing_upload(api):
    first = api.upload("alice", SMALL).json
    again = api.upload("alice", SMALL)
    assert again.status_code == 409
    assert again.json["error"]["code"] == "duplicate_upload"
    assert again.json["error"]["existing_upload_id"] == first["id"]
    assert api.upload("bob", SMALL).status_code == 201  # another user may upload it


def test_wrong_kind_of_file_is_rejected_and_nothing_is_stored(api, db_engine):
    res = api.upload("alice", (SAMPLES / "not-zscaler.log").read_bytes(), "access.log")
    assert res.status_code == 422
    assert res.json["error"]["code"] == "not_zscaler_web"
    assert count(db_engine, Upload) == 0


def test_missing_file_field(api):
    res = api.client.post("/api/uploads", headers=Api.auth("alice"))
    assert res.status_code == 400
    assert res.json["error"]["code"] == "missing_file"


def test_body_over_the_size_limit_is_rejected(db_engine, fake_firebase):
    small_limit = Config(
        database_url=TEST_DATABASE_URL, firebase_project_id="demo-proxylog", max_upload_bytes=1_000
    )
    res = Api(create_app(small_limit).test_client()).upload("alice", SMALL)
    assert res.status_code == 413
    assert res.json["error"]["code"] == "file_too_large"


def test_upload_quota(api, db_engine):
    with Session(db_engine) as session, session.begin():
        session.add_all(
            Upload(owner_uid="alice", filename=f"f{i}", size_bytes=1, sha256=str(i), status="ready")
            for i in range(10)
        )
    res = api.upload("alice", SMALL)
    assert res.status_code == 409
    assert res.json["error"]["code"] == "upload_quota_exceeded"


def test_list_shows_only_my_uploads_newest_first(api):
    a1 = api.upload("alice", SMALL, "first.ndjson").json
    a2 = api.upload("alice", SMALL + b"\n", "second.ndjson").json  # different bytes, new file
    api.upload("bob", SMALL, "bobs.ndjson")
    uploads = api.get("alice", "/api/uploads").json["uploads"]
    assert [u["id"] for u in uploads] == [a2["id"], a1["id"]]
    assert "stats" not in uploads[0]  # the list stays light; details come from GET /uploads/<id>


def test_someone_elses_upload_looks_like_it_does_not_exist(api):
    upload_id = api.upload("alice", SMALL).json["id"]
    assert api.get("alice", f"/api/uploads/{upload_id}").status_code == 200
    for res in (
        api.get("bob", f"/api/uploads/{upload_id}"),
        api.delete("bob", f"/api/uploads/{upload_id}"),
        api.get("alice", "/api/uploads/00000000-0000-0000-0000-000000000000"),
        api.get("alice", "/api/uploads/not-a-uuid"),
    ):
        assert res.status_code == 404
        assert res.json["error"]["code"] == "not_found"


def test_delete_removes_the_upload_and_its_rows(api, db_engine):
    upload_id = api.upload("alice", SMALL).json["id"]
    assert api.delete("alice", f"/api/uploads/{upload_id}").status_code == 204
    assert api.get("alice", f"/api/uploads/{upload_id}").status_code == 404
    assert count(db_engine, LogEntry) == 0
    assert count(db_engine, UploadFile) == 0
    assert api.upload("alice", SMALL).status_code == 201  # and the file can be uploaded again


def test_uploads_require_a_token(api):
    assert api.client.get("/api/uploads").status_code == 401
