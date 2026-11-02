"""Statistical detectors: each one fires on its attack pattern and stays quiet on the benign
look-alike designed to resemble it. Then the whole pipeline on the committed samples."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from app.detection import detect, with_subject
from app.detection.findings import band
from app.detection.statistics import (
    beaconing,
    burst,
    entropy,
    exfil_volume,
    new_device,
    off_hours,
    random_domains,
)
from app.parsing import parse_upload
from app.stats import to_frame

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
DAY = datetime(2026, 10, 20, tzinfo=UTC)
BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131"
_line = iter(range(1, 10_000_000))


def row(at: timedelta, user="alice", **overrides) -> dict:
    values = {
        "line_no": next(_line), "ts": DAY + at, "login": f"{user}@acme.example",
        "cltip": "10.0.0.1", "devicehostname": f"LT-{user}", "location": "London HQ",
        "host": "mail.example", "reqmethod": "GET", "respcode": 200, "action": "Allowed",
        "urlsubcat": "Web Mail", "urlclass": "Business Use", "reqsize": 500, "respsize": 5_000,
        "serverip": "192.0.2.10", "upload_filename": None, "useragent": BROWSER,
    }  # fmt: skip
    return {**values, **overrides}


def workday(user="alice", start=9, end=17, per_hour=30, **overrides) -> list[dict]:
    """Ordinary browsing: `per_hour` requests every hour from start to end."""
    return [
        row(timedelta(hours=h, minutes=i * 60 / per_hour), user, **overrides)
        for h in range(start, end)
        for i in range(per_hour)
    ]


def frame(rows: list[dict]) -> pd.DataFrame:
    return with_subject(to_frame(rows))


def everyone(n=4, **overrides) -> list[dict]:
    return [r for i in range(n) for r in workday(f"user{i}", **overrides)]


# --- beaconing ---------------------------------------------------------------------------


def timer(user: str, host: str, every_s: float, hours: float, jitter=0.02) -> list[dict]:
    """Requests every `every_s` seconds, each gap alternately 2% longer or shorter."""
    rows, at = [], timedelta(hours=2)
    for i in range(int(hours * 3600 / every_s)):
        rows.append(row(at, user, host=host, reqsize=380, respsize=140, urlclass="General Surfing"))
        at += timedelta(seconds=every_s * (1 + jitter * (-1) ** i))
    return rows


def test_beaconing_flags_one_device_on_a_timer():
    rows = everyone() + timer("user0", "x9fq2kd7wz.example", 60, hours=3)
    found = beaconing(frame(rows))
    assert [f.evidence["host"] for f in found] == ["x9fq2kd7wz.example"]
    assert band(found[0].confidence) == "High"


def test_beaconing_ignores_software_every_laptop_runs():
    heartbeats = [r for i in range(4) for r in timer(f"user{i}", "agent.edr.example", 1800, 20)]
    assert beaconing(frame(everyone() + heartbeats)) == []


def test_beaconing_ignores_irregular_visits():
    irregular = [row(timedelta(hours=2, minutes=m), "user0", host="news.example")
                 for m in (0, 3, 17, 18, 40, 95, 96, 150, 151, 152, 200, 260, 261, 300, 301,
                           302, 330, 400, 401, 470, 520)]  # fmt: skip
    assert beaconing(frame(everyone() + irregular)) == []


# --- exfiltration ------------------------------------------------------------------------


def uploads(user: str, host: str, hour: int, urlclass: str, mb=12, n=10) -> list[dict]:
    return [
        row(timedelta(hours=hour, minutes=i * 2), user, host=host, reqmethod="POST",
            reqsize=mb * 1_000_000, respsize=300, urlclass=urlclass,
            urlsubcat="File Host", upload_filename="payroll.xlsx")
        for i in range(n)
    ]  # fmt: skip


def test_exfil_to_an_outside_site_is_high():
    rows = workday() + uploads("alice", "dropbin.example", 23, "Privacy Risk")
    found = exfil_volume(frame(rows))
    assert len(found) == 1
    assert band(found[0].confidence) == "High" and found[0].severity == 3
    assert "payroll.xlsx" in found[0].explanation


def test_big_upload_to_company_storage_stays_low():
    rows = workday() + uploads("alice", "files.officesuite.example", 15, "Business Use")
    found = exfil_volume(frame(rows))
    assert band(found[0].confidence) == "Low" and found[0].severity == 1


def test_normal_uploads_are_not_exfiltration():
    assert exfil_volume(frame(workday(reqsize=2_000))) == []


# --- bursts ------------------------------------------------------------------------------


def test_scanning_burst_with_404s():
    scan = [row(timedelta(hours=14, seconds=i * 0.25), "user0", host="portal.example",
                respcode=404, useragent="python-requests/2.31") for i in range(500)]  # fmt: skip
    found = burst(frame(everyone() + scan))
    assert len(found) == 1
    assert found[0].severity == 3 and band(found[0].confidence) == "High"


def test_it_script_rate_is_not_a_burst():
    script = [row(timedelta(hours=2, seconds=i * 3), "user0", host="api.cloud.example",
                  useragent="python-requests/2.32") for i in range(40)]  # fmt: skip
    assert burst(frame(everyone() + script)) == []


# --- off-hours ---------------------------------------------------------------------------


def test_off_hours_flags_a_late_session_but_not_lunch_or_late_finishes():
    day = workday(start=8, end=12) + workday(start=13, end=17)  # quiet lunch
    late_finish = [row(timedelta(hours=18, minutes=m)) for m in range(0, 45, 3)]
    session = [row(timedelta(hours=23, minutes=m)) for m in range(0, 30, 2)]
    found = off_hours(frame(day + late_finish + session))
    assert [f.start_ts.hour for f in found] == [23]
    assert found[0].severity == 1


def test_off_hours_ignores_background_software_at_night():
    agent = [row(timedelta(hours=3, minutes=m), useragent="EDR-Agent/4.2") for m in range(60)]
    assert off_hours(frame(workday() + agent)) == []


# --- new device --------------------------------------------------------------------------


def test_login_from_a_second_device():
    attacker = [row(timedelta(hours=3, minutes=m), devicehostname="DESKTOP-7Q2K9LM",
                    cltip="10.88.14.201", location="Remote", useragent="Mozilla/5.0 Firefox/132")
                for m in range(20)]  # fmt: skip
    found = new_device(frame(workday() + attacker))
    assert len(found) == 1
    assert found[0].evidence["differences"] == ["IP", "browser", "location"]
    assert band(found[0].confidence) == "Medium"  # High needs another family to agree


# --- random domains ----------------------------------------------------------------------


def test_entropy():
    assert entropy("aaaa") == 0
    assert entropy("mail") < 2.1 < entropy("x9fq2kd7wz")


def test_dga_search_then_success_is_one_finding():
    lookups = [row(timedelta(hours=3, seconds=i * 3), "user0", host=f"{name}.example",
                   serverip=None, respcode=502)
               for i, name in enumerate(f"k{i:02d}q7zx9vbm" for i in range(40))]  # fmt: skip
    found_server = timer("user0", "x9fq2kd7wz.example", 60, hours=2)  # many successful calls
    found = random_domains(frame(everyone() + lookups + found_server))
    assert len(found) == 1
    assert found[0].evidence["domains"] >= 40


def test_a_few_odd_cdn_names_are_not_dga():
    cdn = [row(timedelta(hours=10, minutes=i), "user0", host=f"d{i}x7k2qzm.cloudcdn.example")
           for i in range(4)]  # fmt: skip
    assert random_domains(frame(everyone() + cdn)) == []


# --- the committed samples, end to end ---------------------------------------------------


def detect_sample(name: str):
    path = next(SAMPLES.glob(f"{name}.ndjson*"))
    df = to_frame(parse_upload(path.read_bytes()).rows)
    key = json.loads((SAMPLES / f"{name}.ground_truth.json").read_text())
    line_of = dict(zip(df["record_id"], df["line_no"], strict=True))
    return detect(df), key, line_of


@pytest.mark.parametrize("name", ["acme-web-day", "acme-web-small"])
def test_every_planted_attack_is_in_a_high_incident(name):
    detection, key, line_of = detect_sample(name)
    high_lines = {
        line
        for incident in detection.incidents
        if band(incident.confidence) == "High"
        for finding in incident.findings
        for line in finding.line_nos
    }
    for attack in key["attacks"]:
        lines = {line_of[int(rid)] for rid in attack["recordids"]}
        assert lines & high_lines, f"{attack['name']} is not in any High incident"


@pytest.mark.parametrize("name", ["acme-web-day", "acme-web-small", "acme-web-clean"])
def test_no_benign_lookalike_reaches_high(name):
    detection, key, line_of = detect_sample(name)
    lookalike_lines = {
        line_of[int(rid)] for item in key["benign_lookalikes"] for rid in item["recordids"]
    }
    for line, (confidence, _) in detection.entry_scores.items():
        if line in lookalike_lines:
            assert band(confidence) != "High", f"look-alike line {line} scored {confidence}"


def test_the_clean_file_has_nothing_above_low():
    detection, _, _ = detect_sample("acme-web-clean")
    assert {band(i.confidence) for i in detection.incidents} <= {"Low"}
