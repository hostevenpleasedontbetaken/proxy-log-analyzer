"""Isolation Forest: features, the minimum-data rule, determinism, explanations, and what it
finds on the day sample without any rules."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from app.detection import detect, with_subject
from app.detection.findings import RATE, VOLUME
from app.detection.ml import (
    MIN_USER_HOURS,
    active_user_hours,
    isolation_forest,
    rows_behind,
    user_hour_features,
    with_flags,
)
from app.parsing import parse_upload
from app.stats import to_frame

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
T0 = datetime(2026, 10, 20, 9, tzinfo=UTC)


def frame(rows: list[dict]) -> pd.DataFrame:
    return with_subject(to_frame(rows))


def row(minute: float, **overrides) -> dict:
    values = {
        "line_no": 0, "ts": T0 + timedelta(minutes=minute), "login": "alice@acme.example",
        "cltip": "10.0.0.1", "host": "mail.example", "reqmethod": "GET", "respcode": 200,
        "action": "Allowed", "reqsize": 500, "respsize": 5_000, "useragent": "Mozilla/5.0",
    }  # fmt: skip
    return {**values, **overrides}


@pytest.fixture(scope="module")
def day() -> pd.DataFrame:
    rows = parse_upload((SAMPLES / "acme-web-day.ndjson.gz").read_bytes()).rows
    return with_subject(to_frame(rows))


def test_features_are_one_row_per_user_hour_with_smoothed_ratios():
    rows = [row(i, line_no=i, action="Blocked" if i == 0 else "Allowed") for i in range(4)]
    features = user_hour_features(frame(rows))
    assert len(features) == 1
    assert features["requests"].iloc[0] == 4
    # 1 blocked of 4: smoothed to 1 / (4 + 10), not a jumpy 25%
    assert features["blocked_ratio"].iloc[0] == pytest.approx(1 / 14)


def test_ml_does_not_run_without_enough_active_hours():
    rows = parse_upload((SAMPLES / "acme-web-small.ndjson").read_bytes()).rows
    df = with_subject(to_frame(rows))
    assert len(active_user_hours(df)) < MIN_USER_HOURS
    assert isolation_forest(df) == []
    assert detect(to_frame(rows)).ml_ran is False


def test_same_file_gives_the_same_result(day):
    first, second = isolation_forest(day), isolation_forest(day)
    assert [(f.subject, f.start_ts, f.confidence) for f in first] == [
        (f.subject, f.start_ts, f.confidence) for f in second
    ]


def test_finds_attack_hours_without_any_rules(day):
    found = {(f.subject, f.start_ts.hour) for f in isolation_forest(day)}
    assert ("vera.tanaka@acme.example", 14) in found  # scanning
    assert ("yusuf.zhang@acme.example", 23) in found  # exfiltration
    assert ("carla.evans@acme.example", 3) in found  # DGA search + first C2 check-ins


def test_findings_explain_themselves_and_stay_below_high(day):
    findings = isolation_forest(day)
    assert findings and all(f.confidence <= 0.7 for f in findings)
    exfil = next(f for f in findings if f.subject == "yusuf.zhang@acme.example")
    assert "bytes uploaded 145.7 MB" in exfil.explanation
    assert exfil.family == VOLUME  # counted with exfil_volume, not on top of it
    assert len(exfil.evidence["top_features"]) == 3
    scan = next(f for f in findings if f.subject == "vera.tanaka@acme.example")
    assert scan.family == RATE


def test_rows_behind_point_at_the_evidence():
    rows = with_flags(frame([row(0, respcode=404), row(1), row(2, respcode=500)]))
    assert len(rows_behind("error_ratio", rows)) == 2
    assert len(rows_behind("blocked_ratio", rows)) == 3  # nothing blocked → whole hour


def test_upload_summary_reports_whether_ml_ran(api):
    upload = api.upload("alice", (SAMPLES / "acme-web-small.ndjson").read_bytes()).json
    ml = upload["stats"]["detection"]["ml"]
    assert ml == {"ran": False, "active_user_hours": ml["active_user_hours"],
                  "required_user_hours": 200}  # fmt: skip
