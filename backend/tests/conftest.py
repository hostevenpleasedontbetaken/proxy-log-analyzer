"""Shared test setup.

- `app` / `client`: the Flask app with no database (auth and error tests).
- `fake_firebase`: token "good-<uid>" is valid for <uid>, anything else is rejected.
- `db_engine`, `alembic_config`: a real Postgres (TEST_DATABASE_URL, the proxylog_test database
  in docker compose), migrated from empty once per test run. Tests using them are skipped
  when no test database is configured.
- `api`: the app wired to that database, plus helpers to call it as a given user.
"""

import io
import os

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text

from app import create_app
from app.config import Config
from app.db import sqlalchemy_url

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
def app():
    config = Config(
        database_url="postgresql://unused:unused@localhost:1/unused",
        firebase_project_id="demo-proxylog",
    )
    return create_app(config)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def fake_firebase(monkeypatch):
    """Replace token verification: "good-<uid>" is a signed-in user, "guest-<uid>" an anonymous
    one, anything else is rejected."""
    from firebase_admin import auth as firebase_auth

    def verify(token, clock_skew_seconds=0):
        if token.startswith("good-"):
            uid = token.removeprefix("good-")
            return {"uid": uid, "email": f"{uid}@example.com"}
        if token.startswith("guest-"):  # "Try the demo": an anonymous Firebase user, no email
            uid = token.removeprefix("guest-")
            return {"uid": uid, "firebase": {"sign_in_provider": "anonymous"}}
        raise firebase_auth.InvalidIdTokenError("bad token")

    monkeypatch.setattr(firebase_auth, "verify_id_token", verify)


# --- database ----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def alembic_config():
    if not TEST_DATABASE_URL:
        pytest.skip("needs TEST_DATABASE_URL (run with make test-backend)")
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL  # migrations/env.py reads it
    return AlembicConfig("alembic.ini")


@pytest.fixture(scope="session")
def db_engine(alembic_config):
    """Fresh schema from the migrations: drop everything, then upgrade to the latest."""
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    engine = create_engine(sqlalchemy_url(TEST_DATABASE_URL))
    yield engine
    engine.dispose()


class Api:
    """The test client plus shortcuts for calling the API as a particular user."""

    def __init__(self, client):
        self.client = client

    @staticmethod
    def auth(uid: str) -> dict:
        return {"Authorization": f"Bearer good-{uid}"}

    @staticmethod
    def guest(uid: str) -> dict:
        return {"Authorization": f"Bearer guest-{uid}"}

    def upload(self, uid: str, data: bytes, filename: str = "acme.ndjson"):
        return self.client.post(
            "/api/uploads",
            data={"file": (io.BytesIO(data), filename)},
            headers=self.auth(uid),
            content_type="multipart/form-data",
        )

    def get(self, uid: str, path: str):
        return self.client.get(path, headers=self.auth(uid))

    def delete(self, uid: str, path: str):
        return self.client.delete(path, headers=self.auth(uid))


@pytest.fixture
def api(db_engine, fake_firebase):
    app = create_app(Config(database_url=TEST_DATABASE_URL, firebase_project_id="demo-proxylog"))
    yield Api(app.test_client())
    with db_engine.begin() as conn:  # leave the tables empty for the next test
        conn.execute(text("TRUNCATE uploads CASCADE"))
