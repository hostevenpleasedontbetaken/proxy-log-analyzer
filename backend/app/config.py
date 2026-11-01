"""Settings read from environment variables (set by docker compose locally, Cloud Run in prod)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url: str
    firebase_project_id: str
    # Set only when running against the local Firebase Auth emulator.
    auth_emulator_host: str | None = None
    # Cloud Run sets K_SERVICE on every container; we use it to detect production.
    running_on_cloud_run: bool = False
    max_upload_bytes: int = 25 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            database_url=os.environ["DATABASE_URL"],
            firebase_project_id=os.environ["FIREBASE_PROJECT_ID"],
            auth_emulator_host=os.environ.get("FIREBASE_AUTH_EMULATOR_HOST") or None,
            running_on_cloud_run="K_SERVICE" in os.environ,
        )
