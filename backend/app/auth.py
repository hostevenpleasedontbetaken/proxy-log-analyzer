"""Firebase ID-token verification.

The browser signs in with Firebase and sends `Authorization: Bearer <ID token>` on every API
call. We verify the token's signature, expiry and audience with firebase-admin and put the
user's id in `g.uid`. There is no users table: Firebase owns identity, we only store `uid`s.
"""

import firebase_admin
from firebase_admin import auth as firebase_auth
from flask import g, request

from app.config import Config
from app.errors import ApiError

# Tolerate small clock differences between Google's servers and ours.
CLOCK_SKEW_SECONDS = 10


def init_firebase(config: Config) -> None:
    if config.auth_emulator_host and config.running_on_cloud_run:
        # Emulator tokens are unsigned. Accepting them in production would let anyone log in.
        raise RuntimeError("FIREBASE_AUTH_EMULATOR_HOST must never be set on Cloud Run")

    # firebase-admin keeps one global "default app"; tests call create_app() many times.
    if not firebase_admin._apps:
        # No service-account key needed: verifying tokens only requires the project id.
        firebase_admin.initialize_app(options={"projectId": config.firebase_project_id})


def require_firebase_user() -> None:
    """`before_request` hook for the protected blueprint. Sets `g.uid` or raises 401."""
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme != "Bearer" or not token:
        raise ApiError(401, "unauthenticated", "Missing bearer token")

    try:
        claims = firebase_auth.verify_id_token(token, clock_skew_seconds=CLOCK_SKEW_SECONDS)
    except (ValueError, firebase_auth.InvalidIdTokenError, firebase_auth.ExpiredIdTokenError):
        # Same message for every failure: don't tell an attacker *why* the token was rejected.
        raise ApiError(401, "unauthenticated", "Invalid or expired token") from None

    g.uid = claims["uid"]
    g.email = claims.get("email")
