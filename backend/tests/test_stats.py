import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.parsing import parse_upload
from app.stats import choose_bucket, compute_stats, to_frame

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
START = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)


def row(**overrides) -> dict:
    values = {
        "line_no": 1, "ts": START, "login": "alice@acme.example", "cltip": "10.0.0.1",
        "devicehostname": "LT-1", "host": "mail.example", "dstip_country": "United States",
        "urlsubcat": "Web Mail", "urlclass": "Business Use", "action": "Allowed",
        "reason": "Allowed", "respcode": 200, "reqsize": 100, "respsize": 1_000,
        "riskscore": 0, "threatname": None,
    }  # fmt: skip
    return {**values, **overrides}


def stats(rows: list[dict]) -> dict:
    return compute_stats(to_frame(rows), line_count=len(rows), error_count=0, warnings={})


def test_totals():
    s = stats([
        row(),
        row(login="bob@acme.example", action="Blocked", reqsize=50, riskscore=90),
        row(threatname="Trojan.X", respsize=None),
    ])["totals"]  # fmt: skip
    assert s["requests"] == 3
    assert s["users"] == 2
    assert s["blocked"] == 1
    assert s["threat_hits"] == 1
    assert s["high_risk"] == 1
    assert s["bytes_out"] == 250
    assert s["bytes_in"] == 2_000  # a missing size counts as nothing, not an error


def test_top_lists_keep_ten_and_total_the_rest():
    rows = [row(login=f"user{i:02d}") for i in range(12) for _ in range(12 - i)]
    users = stats(rows)["top"]["users_by_requests"]
    assert [item["key"] for item in users["items"]] == [f"user{i:02d}" for i in range(10)]
    assert users["items"][0]["value"] == 12
    assert users["other"] == 2 + 1  # user10 and user11


def test_top_by_bytes_and_unknown_users():
    rows = [row(login="small", reqsize=10), row(login="big", reqsize=5_000), row(login=None)]
    items = stats(rows)["top"]["users_by_bytes_out"]["items"]
    assert items[0] == {"key": "big", "value": 5_000}
    assert {"key": "(unknown)", "value": 100} in items


def test_status_codes_are_grouped_by_class():
    rows = [row(respcode=200), row(respcode=204), row(respcode=404), row(respcode=None)]
    assert stats(rows)["breakdown"]["respcode_class"] == {"2xx": 2, "4xx": 1, "(unknown)": 1}


@pytest.mark.parametrize(
    ("span", "bucket"),
    [
        (timedelta(0), 60),
        (timedelta(hours=2), 60),
        (timedelta(hours=10), 300),
        (timedelta(days=1), 900),
        (timedelta(days=7), 3_600),
        (timedelta(days=30), 21_600),
        (timedelta(days=120), 86_400),
    ],
)
def test_bucket_size_keeps_the_chart_at_200_bars_or_fewer(span, bucket):
    assert choose_bucket(span.total_seconds()) == bucket


def test_timeline_fills_quiet_periods_with_zeros():
    rows = [row(ts=START), row(ts=START + timedelta(hours=3), action="Blocked")]
    timeline = stats(rows)["timeline"]
    buckets = timeline["buckets"]
    assert timeline["bucket_seconds"] == 60
    assert len(buckets) == 3 * 60 + 1  # every minute from 09:00 to 12:00, inclusive
    assert buckets[0] == {
        "t": "2026-10-20T09:00:00Z", "allowed": 1, "blocked": 0, "threats": 0, "flagged": 0,
        "bytes_out": 100,
    }  # fmt: skip
    assert buckets[-1]["blocked"] == 1
    assert sum(b["allowed"] + b["blocked"] for b in buckets[1:-1]) == 0


def test_flagged_lines_are_counted_per_bucket():
    rows = [row(line_no=1), row(line_no=2), row(line_no=3, ts=START + timedelta(minutes=5))]
    s = compute_stats(
        to_frame(rows), line_count=3, error_count=0, warnings={}, flagged_lines=[2, 3]
    )
    assert s["totals"]["flagged"] == 2
    assert [b["flagged"] for b in s["timeline"]["buckets"]] == [1, 0, 0, 0, 0, 1]


def test_stats_are_plain_json():
    # Stored in a JSONB column: no numpy numbers or timestamps may leak through.
    s = stats([row(), row(threatname="Trojan.X")])
    assert json.loads(json.dumps(s)) == s


def test_day_sample_overview():
    parsed = parse_upload((SAMPLES / "acme-web-day.ndjson.gz").read_bytes())
    s = compute_stats(
        to_frame(parsed.rows), line_count=parsed.line_count, error_count=0, warnings={}
    )
    timeline = s["timeline"]
    assert s["totals"]["requests"] == 18_654
    assert (timeline["bucket_seconds"], len(timeline["buckets"])) == (900, 96)
    assert sum(b["allowed"] + b["blocked"] for b in timeline["buckets"]) == 18_654
    assert s["top"]["threats"]["items"] == [{"key": "Trojan.Win32.Emotet", "value": 2}]
    # The exfiltration user already stands out on volume alone (next to the benign uploader).
    key = json.loads((SAMPLES / "acme-web-day.ground_truth.json").read_text())
    exfil_user = next(a for a in key["attacks"] if a["name"] == "data_exfiltration")["users"][0]
    top_uploaders = [i["key"] for i in s["top"]["users_by_bytes_out"]["items"][:2]]
    assert exfil_user in top_uploaders
