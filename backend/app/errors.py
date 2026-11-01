"""One JSON error shape for every failure: {"error": {"code": "...", "message": "..."}}.

The frontend maps `code` to friendly text, so codes are stable identifiers and messages are
for humans/debugging.
"""

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _envelope(status: int, code: str, message: str):
    return jsonify({"error": {"code": code, "message": message}}), status


def register(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return _envelope(err.status, err.code, err.message)

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
