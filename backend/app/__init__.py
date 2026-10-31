"""Flask application factory.

`create_app()` builds a fresh app. Gunicorn (production), `flask run` (local dev) and the
tests all call it, so there is exactly one place where the app is wired together.
"""

from flask import Flask

from app import auth, errors
from app.config import Config
from app.routes import api


def create_app(config: Config | None = None) -> Flask:
    config = config or Config.from_env()

    app = Flask(__name__)
    app.config["APP_CONFIG"] = config
    # Phase 3 limit: reject bodies over 25 MB before reading them.
    app.config["MAX_CONTENT_LENGTH"] = config.max_upload_bytes

    auth.init_firebase(config)
    errors.register(app)
    app.register_blueprint(api)

    @app.after_request
    def no_store(response):
        # API responses contain private log data: never let a browser or proxy cache them.
        response.headers["Cache-Control"] = "private, no-store"
        return response

    return app
