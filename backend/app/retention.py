"""Uploads are deleted after RETENTION_DAYS. The shared sample analysis is kept.

This is a demo that anyone can sign up to, so nothing stays around: it bounds the storage
used and means a stranger's data doesn't sit in the database. The rows' dependants (entries,
incidents, anomalies, the stored file) go with them through ON DELETE CASCADE.

It runs in two places: on every new upload (so a full database frees itself), and after each
deploy's migrations (`python -m app.retention`).
"""

import logging
import os
from datetime import timedelta

from sqlalchemy import delete, func

from app.db import new_session
from app.models import DEMO_OWNER_UID, Upload

RETENTION_DAYS = 7


def delete_expired(session) -> int:
    """Delete uploads older than the retention period. The caller commits. Returns how many."""
    result = session.execute(
        delete(Upload).where(
            Upload.owner_uid != DEMO_OWNER_UID,
            Upload.created_at < func.now() - timedelta(days=RETENTION_DAYS),
        )
    )
    return result.rowcount


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with new_session(os.environ["DATABASE_URL"]) as session, session.begin():
        count = delete_expired(session)
    logging.info("Deleted %d expired upload(s)", count)


if __name__ == "__main__":
    main()
