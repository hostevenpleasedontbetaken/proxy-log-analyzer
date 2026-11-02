"""One JSON error shape for every failure: {"error": {"code": "...", "message": "..."}}.

The frontend maps `code` to friendly text, so codes are stable identifiers and messages are
for humans/debugging.
"""

from typing import Any

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge


class ApiError(Exception):
    """Raise anywhere in a request to send a JSON error. Extra keyword arguments are added to
    the error object, e.g. `existing_upload_id` on a duplicate upload."""

    def __init__(self, status: int, code: str, message: str, **details: Any):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def _envelope(status: int, code: str, message: str, **details: Any):
    return jsonify({"error": {"code": code, "message": message, **details}}), status


def register(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return _envelope(err.status, err.code, err.message, **err.details)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_too_large(err: RequestEntityTooLarge):
        # Flask rejects bodies over MAX_CONTENT_LENGTH before our code reads them.
        return _envelope(413, "file_too_large", "Uploads are limited to 25 MB; gzip larger logs.")

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        # Werkzeug's own errors (404 route not found, 405, 413 body too large, ...).
        code = (err.name or "error").lower().replace(" ", "_")
        return _envelope(err.code or 500, code, err.description or err.name)

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        app.logger.exception("Unhandled error")
        # Never leak stack traces or internals to the client.
        return _envelope(500, "internal_error", "Something went wrong")
