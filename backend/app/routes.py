"""HTTP routes. Everything under /api except /api/health requires a Firebase user.

Routes stay thin: read the request, call the logic in app/uploads.py, shape the response with
app/schemas.py. Every upload lookup goes through owned_upload_or_404.
"""

import uuid

from flask import Blueprint, current_app, g, request
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_firebase_user
from app.db import get_engine, new_session
from app.errors import ApiError
from app.models import Upload
from app.schemas import UploadDetail, UploadSummary
from app.uploads import create_upload, owned_upload_or_404

api = Blueprint("api", __name__, url_prefix="/api")

# Routes listed here skip the auth check. Keep this list tiny.
PUBLIC_ENDPOINTS = {"api.health"}


@api.before_request
def authenticate():
    if request.endpoint not in PUBLIC_ENDPOINTS:
        require_firebase_user()


def _session() -> Session:
    return new_session(current_app.config["APP_CONFIG"].database_url)


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


@api.post("/uploads")
def upload_log():
    """Multipart form with the log in a field named "file" (plain or gzipped).
    201 + the upload; 409 duplicate / quota; 413 too large; 422 not a usable Zscaler log."""
    file = request.files.get("file")
    if file is None or not file.filename:
        raise ApiError(400, "missing_file", 'Send the log as a form field named "file".')
    data = file.read()
    try:
        with _session() as session, session.begin():
            upload = create_upload(session, owner_uid=g.uid, filename=file.filename, data=data)
            body = UploadDetail.model_validate(upload).model_dump(mode="json")
    except IntegrityError:
        # Two identical uploads at the same moment: the database's unique rule caught it.
        raise ApiError(409, "duplicate_upload", "You already uploaded this file.") from None
    return body, 201


@api.get("/uploads")
def list_uploads():
    """My uploads, newest first."""
    with _session() as session:
        uploads = session.scalars(
            select(Upload).where(Upload.owner_uid == g.uid).order_by(Upload.created_at.desc())
        )
        return {
            "uploads": [UploadSummary.model_validate(u).model_dump(mode="json") for u in uploads]
        }


@api.get("/uploads/<uuid:upload_id>")
def get_upload(upload_id: uuid.UUID):
    with _session() as session:
        upload = owned_upload_or_404(session, upload_id, g.uid)
        return UploadDetail.model_validate(upload).model_dump(mode="json")


@api.delete("/uploads/<uuid:upload_id>")
def delete_upload(upload_id: uuid.UUID):
    """Deletes the upload and, through ON DELETE CASCADE, everything derived from it."""
    with _session() as session, session.begin():
        session.delete(owned_upload_or_404(session, upload_id, g.uid))
    return "", 204
