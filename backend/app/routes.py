"""HTTP routes. Everything under /api except /api/health requires a Firebase user.

Routes stay thin: read the request, call the logic in app/uploads.py, shape the response with
app/schemas.py. Every upload lookup goes through owned_upload_or_404 (changes) or
readable_upload_or_404 (reads: your own, or the shared sample analysis).
"""

import math
import uuid
from typing import Any

from flask import Blueprint, current_app, g, request
from pydantic import BaseModel, ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_firebase_user
from app.db import get_engine, new_session
from app.errors import ApiError
from app.models import DEMO_OWNER_UID, Upload
from app.queries import anomalies_for, entries_page, entry_with_anomalies, incidents_with_anomalies
from app.schemas import (
    AnomalyOut,
    AnomalyQuery,
    EntryDetail,
    EntryQuery,
    EntrySummary,
    IncidentOut,
    UploadDetail,
    UploadSummary,
)
from app.uploads import create_upload, owned_upload_or_404, readable_upload_or_404

api = Blueprint("api", __name__, url_prefix="/api")

# Routes listed here skip the auth check. Keep this list tiny.
PUBLIC_ENDPOINTS = {"api.health"}


@api.before_request
def authenticate():
    if request.endpoint not in PUBLIC_ENDPOINTS:
        require_firebase_user()


def _session() -> Session:
    return new_session(current_app.config["APP_CONFIG"].database_url)


def _query(model: type[BaseModel]) -> Any:
    """Validate the URL's query string with a Pydantic model (e.g. EntryQuery); returns the
    validated model. Problems become a 400 listing each bad parameter."""
    try:
        return model.model_validate(request.args.to_dict())
    except ValidationError as err:
        problems = "; ".join(
            f"{'.'.join(map(str, e['loc'])) or 'query'}: {e['msg']}" for e in err.errors()
        )
        raise ApiError(400, "invalid_query", problems) from None


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
    return {"uid": g.uid, "email": g.email, "is_guest": g.is_guest}


@api.post("/uploads")
def upload_log():
    """Multipart form with the log in a field named "file" (plain or gzipped).
    201 + the upload; 409 duplicate / quota; 413 too large; 422 not a usable Zscaler log."""
    if g.is_guest:
        raise ApiError(
            403, "guest_read_only", "Guests can browse the sample analysis. Sign in to upload logs."
        )
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
    """My uploads plus the shared sample analysis, newest first."""
    with _session() as session:
        uploads = session.scalars(
            select(Upload)
            .where(Upload.owner_uid.in_([g.uid, DEMO_OWNER_UID]))
            .order_by(Upload.created_at.desc())
        )
        return {
            "uploads": [UploadSummary.model_validate(u).model_dump(mode="json") for u in uploads]
        }


@api.get("/uploads/<uuid:upload_id>")
def get_upload(upload_id: uuid.UUID):
    with _session() as session:
        upload = readable_upload_or_404(session, upload_id, g.uid)
        return UploadDetail.model_validate(upload).model_dump(mode="json")


@api.delete("/uploads/<uuid:upload_id>")
def delete_upload(upload_id: uuid.UUID):
    """Deletes the upload and, through ON DELETE CASCADE, everything derived from it."""
    with _session() as session, session.begin():
        session.delete(owned_upload_or_404(session, upload_id, g.uid))
    return "", 204


@api.get("/uploads/<uuid:upload_id>/entries")
def list_entries(upload_id: uuid.UUID):
    """One page of the log table. Filters: from, to, user, action, host, q (host/URL search),
    flagged, min_confidence, incident_id, anomaly_id. Paging: page, page_size (max 200)."""
    query = _query(EntryQuery)
    with _session() as session:
        readable_upload_or_404(session, upload_id, g.uid)
        entries, total = entries_page(session, upload_id, query)
        return {
            "entries": [EntrySummary.model_validate(e).model_dump(mode="json") for e in entries],
            "page": query.page,
            "page_size": query.page_size,
            "total": total,
            "pages": max(1, math.ceil(total / query.page_size)),
        }


@api.get("/uploads/<uuid:upload_id>/entries/<int:line_no>")
def get_entry(upload_id: uuid.UUID, line_no: int):
    """Every field of one entry, plus the anomalies it belongs to ("why flagged")."""
    with _session() as session:
        readable_upload_or_404(session, upload_id, g.uid)
        entry, anomalies = entry_with_anomalies(session, upload_id, line_no)
        if entry is None:
            raise ApiError(404, "not_found", "Entry not found.")
        detail = EntryDetail.model_validate(entry)
        detail.anomalies = [AnomalyOut.model_validate(a) for a in anomalies]
        return detail.model_dump(mode="json")


@api.get("/uploads/<uuid:upload_id>/incidents")
def list_incidents(upload_id: uuid.UUID):
    """Incidents, most severe first, each with its anomalies."""
    with _session() as session:
        readable_upload_or_404(session, upload_id, g.uid)
        incidents = []
        for incident, anomalies in incidents_with_anomalies(session, upload_id):
            out = IncidentOut.model_validate(incident)
            out.anomalies = [AnomalyOut.model_validate(a) for a in anomalies]
            incidents.append(out.model_dump(mode="json"))
        return {"incidents": incidents}


@api.get("/uploads/<uuid:upload_id>/anomalies")
def list_anomalies(upload_id: uuid.UUID):
    """Every anomaly, most confident first. Filters: detector, min_confidence."""
    query = _query(AnomalyQuery)
    with _session() as session:
        readable_upload_or_404(session, upload_id, g.uid)
        anomalies = anomalies_for(
            session, upload_id, detector=query.detector, min_confidence=query.min_confidence
        )
        return {
            "anomalies": [AnomalyOut.model_validate(a).model_dump(mode="json") for a in anomalies]
        }
