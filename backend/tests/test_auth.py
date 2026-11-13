import pytest

from app import create_app
from app.config import Config


def test_missing_token_is_401_with_error_envelope(client):
    res = client.get("/api/me")
    assert res.status_code == 401
    assert res.json == {"error": {"code": "unauthenticated", "message": "Missing bearer token"}}


def test_invalid_token_is_401(client, fake_firebase):
    res = client.get("/api/me", headers={"Authorization": "Bearer forged"})
    assert res.status_code == 401
    assert res.json["error"]["code"] == "unauthenticated"


def test_wrong_scheme_is_401(client, fake_firebase):
    res = client.get("/api/me", headers={"Authorization": "Basic good-alice"})
    assert res.status_code == 401


def test_valid_token_sets_uid(client, fake_firebase):
    res = client.get("/api/me", headers={"Authorization": "Bearer good-alice"})
    assert res.status_code == 200
    assert res.json == {"uid": "alice", "email": "alice@example.com"}


def test_responses_are_never_cached(client, fake_firebase):
    res = client.get("/api/me", headers={"Authorization": "Bearer good-alice"})
    assert res.headers["Cache-Control"] == "private, no-store"


def test_unknown_route_uses_error_envelope(client, fake_firebase):
    res = client.get("/api/nope", headers={"Authorization": "Bearer good-alice"})
    assert res.status_code == 404
    assert res.json["error"]["code"] == "not_found"


def test_refuses_to_start_with_emulator_on_cloud_run():
    config = Config(
        database_url="postgresql://x",
        firebase_project_id="demo-proxylog",
        auth_emulator_host="auth:9099",
        running_on_cloud_run=True,
    )
    with pytest.raises(RuntimeError, match="never be set on Cloud Run"):
        create_app(config)
