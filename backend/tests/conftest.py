import pytest

from app import create_app
from app.config import Config


@pytest.fixture
def app():
    config = Config(
        database_url="postgresql://unused:unused@localhost:1/unused",
        firebase_project_id="demo-tenex",
    )
    return create_app(config)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def fake_firebase(monkeypatch):
    """Replace token verification: the token string "good-<uid>" is valid, anything else isn't."""
    from firebase_admin import auth as firebase_auth

    def verify(token, clock_skew_seconds=0):
        if token.startswith("good-"):
            uid = token.removeprefix("good-")
            return {"uid": uid, "email": f"{uid}@example.com"}
        raise firebase_auth.InvalidIdTokenError("bad token")

    monkeypatch.setattr(firebase_auth, "verify_id_token", verify)
