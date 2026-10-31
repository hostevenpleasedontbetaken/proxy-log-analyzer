"""HTTP routes. Everything under /api except /api/health requires a Firebase user."""

from flask import Blueprint, current_app, g, request
from sqlalchemy import text

from app.auth import require_firebase_user
from app.db import get_engine
from app.errors import ApiError

api = Blueprint("api", __name__, url_prefix="/api")

# Routes listed here skip the auth check. Keep this list tiny.
PUBLIC_ENDPOINTS = {"api.health"}


@api.before_request
def authenticate():
    if request.endpoint not in PUBLIC_ENDPOINTS:
        require_firebase_user()


@api.get("/health")
def health():
    """Public. Also wakes the database, so the frontend can call it to warm up a cold start."""
    config = current_app.config["APP_CONFIG"]
    try:
        with get_engine(config.database_url).connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        current_app.logger.exception("Health check: database unreachable")
        raise ApiError(503, "db_unavailable", "Database unreachable") from None
    return {"status": "ok"}


@api.get("/me")
def me():
    """Who the token belongs to. Used by the frontend to confirm the login round-trip."""
    return {"uid": g.uid, "email": g.email}
