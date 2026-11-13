"""The shared sample analysis shown to guests ("Try the demo").

`python -m app.demo` loads the bundled sample log through the normal upload pipeline under a
fixed owner (DEMO_OWNER_UID). It runs after the migrations, locally (docker compose) and in
production (the Cloud Run migrate job), so it is safe to run on every deploy: it does nothing
when the sample is already there and was produced by the current parser and detectors, and
rebuilds it when either changed.
"""

import hashlib
import logging
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import new_session
from app.detection import DETECTOR_VERSION
from app.models import DEMO_OWNER_UID, Upload
from app.parsing import PARSER_VERSION
from app.uploads import create_upload

# A copy of samples/acme-web-day.ndjson.gz: the Docker image only contains backend/. A test
# checks the two files stay identical.
SAMPLE_PATH = Path(__file__).resolve().parent.parent / "demo" / "acme-web-day.ndjson.gz"
SAMPLE_FILENAME = "acme-web-day.ndjson.gz"


def seed_demo(session: Session, data: bytes | None = None) -> str:
    """Make sure exactly one up-to-date sample analysis exists. The caller commits.
    Returns "created", "refreshed" (rebuilt) or "unchanged"."""
    data = SAMPLE_PATH.read_bytes() if data is None else data
    sha256 = hashlib.sha256(data).hexdigest()
    current = session.scalars(select(Upload).where(Upload.owner_uid == DEMO_OWNER_UID)).all()

    if (
        len(current) == 1
        and current[0].sha256 == sha256
        and current[0].parser_version == PARSER_VERSION
        and current[0].detector_version == DETECTOR_VERSION
    ):
        return "unchanged"

    for old in current:
        session.delete(old)  # cascades to its entries, incidents and anomalies
    session.flush()
    create_upload(session, owner_uid=DEMO_OWNER_UID, filename=SAMPLE_FILENAME, data=data)
    return "refreshed" if current else "created"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with new_session(os.environ["DATABASE_URL"]) as session, session.begin():
        outcome = seed_demo(session)
    logging.info("Sample analysis: %s", outcome)


if __name__ == "__main__":
    main()
