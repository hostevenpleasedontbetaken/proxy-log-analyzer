"""Detection framework and rule detectors: the confidence math, each rule on hand-made rows
(fires on the pattern, stays quiet on the benign version), incident grouping, and the upload
flow storing incidents."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.detection import detect
from app.detection.findings import ML, Finding, band, combine, ramp
from app.detection.incidents import group_incidents
from app.stats import to_frame

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
T0 = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
_line = iter(range(1, 1_000_000))


def row(seconds: float = 0, **overrides) -> dict:
    values = {
        "line_no": next(_line), "ts": T0 + timedelta(seconds=seconds),
        "login": "alice@acme.example", "cltip": "10.0.0.1", "host": "mail.example",
        "reqmethod": "GET", "respcode": 200, "action": "Allowed", "urlsubcat": "Web Mail",
        "reqsize": 500, "respsize": 5_000, "riskscore": 0, "threatname": None,
        "threatseverity": None, "malwarecategory": None, "filename": None,
        "useragent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131",
    }  # fmt: skip
    return {**values, **overrides}


def run(rows: list[dict]):
    return detect(to_frame(rows))


def detectors(result) -> set[str]:
    return {f.detector for f in result.findings}


def fake(family: str, confidence: float, subject="alice", start=T0, severity=2) -> Finding:
    return Finding(
        detector="x", layer="rule", family=family, subject_type="user", subject=subject,
        title="t", explanation="e", confidence=confidence, severity=severity, line_nos=[1],
        start_ts=start, end_ts=start,
    )  # fmt: skip


# --- confidence math ---------------------------------------------------------------------


def test_combine_adds_evidence_across_families_but_not_within_one():
    assert combine([fake("known_bad", 0.9), fake("volume", 0.6)]) == pytest.approx(0.96)
    assert combine([fake("volume", 0.9), fake("volume", 0.6)]) == pytest.approx(0.9)
    assert combine([]) == 0


def test_ml_alone_never_reaches_high():
    assert combine([fake(ML, 0.95)]) == 0.75
    assert combine([fake(ML, 0.95), fake("timing", 0.5)]) > 0.8  # unless something agrees


def test_ramp_and_bands():
    assert [ramp(x, 75, 0.5, 100, 0.9) for x in (60, 75, 87.5, 100, 120)] == pytest.approx(
        [0.5, 0.5, 0.7, 0.9, 0.9]
    )
    assert [band(c) for c in (0.95, 0.8, 0.6, 0.49)] == ["High", "High", "Medium", "Low"]


# --- rules -------------------------------------------------------------------------------


def test_known_threat():
    malware = row(threatname="Trojan.X", threatseverity="Critical", action="Blocked",
                  filename="invoice.exe", host="dl.bad.example")  # fmt: skip
    result = run([row(), malware])
    finding = next(f for f in result.findings if f.detector == "known_threat")
    assert (finding.confidence, finding.severity, finding.line_nos) == (
        0.95,
        4,
        [malware["line_no"]],
    )
    assert "Trojan.X" in finding.explanation and "all blocked" in finding.explanation
    assert detectors(run([row(), row()])) == set()


def test_high_risk_score_scales_with_the_score():
    result = run([row(riskscore=80, host="a.example"), row(riskscore=100, host="b.example")])
    by_host = {f.evidence["host"]: f for f in result.findings if f.detector == "high_risk_score"}
    assert by_host["a.example"].confidence < by_host["b.example"].confidence == 0.9
    assert detectors(run([row(riskscore=74)])) == set()


def test_phishing_visit_then_form_post():
    visit = row(0, host="login-fake.example", urlsubcat="Phishing", riskscore=88)
    post = row(20, host="login-fake.example", urlsubcat="Phishing", reqmethod="POST", reqsize=1400)
    result = run([visit, post])
    assert {"risky_category", "phishing_post"} <= detectors(result)
    assert max(f.severity for f in result.findings) == 4
    late = row(600, host="login-fake.example", urlsubcat="Phishing", reqmethod="POST")
    assert "phishing_post" not in detectors(run([visit, late]))  # > 5 minutes later


def test_anonymizer_attempts_scale_with_count():
    def tries(n):
        rows = [row(i * 30, host="vpn.example", urlsubcat="Anonymizer", action="Blocked")
                for i in range(n)]  # fmt: skip
        return next(f for f in run(rows).findings if f.detector == "risky_category").confidence

    assert tries(1) < tries(5) < tries(12) == 0.7


def test_repeated_blocks_needs_a_burst():
    burst = [row(i * 40, action="Blocked", urlsubcat="Anonymizer") for i in range(12)]
    spread = [row(i * 3_600, action="Blocked", urlsubcat="Social Networking") for i in range(12)]
    assert "repeated_blocks" in detectors(run(burst))
    assert "repeated_blocks" not in detectors(run(spread))  # one an hour isn't probing


def test_script_user_agent_is_low_on_its_own():
    result = run([row(useragent="curl/8.7.1"), row(useragent="python-requests/2.32")])
    assert detectors(result) == {"script_user_agent"}
    assert {f.severity for f in result.findings} == {1}
    assert all(band(f.confidence) == "Low" for f in result.findings)


def test_rows_without_a_login_are_grouped_by_ip():
    result = run([row(login=None, cltip="10.9.9.9", threatname="Trojan.X")])
    assert (result.findings[0].subject_type, result.findings[0].subject) == ("ip", "10.9.9.9")


# --- incidents and entry scores ----------------------------------------------------------


def test_incidents_group_by_subject_within_30_minutes():
    incidents = group_incidents([
        fake("known_bad", 0.9, start=T0),
        fake("policy", 0.6, start=T0 + timedelta(minutes=20)),
        fake("tooling", 0.4, start=T0 + timedelta(hours=2)),
        fake("known_bad", 0.9, subject="bob", start=T0),
    ])  # fmt: skip
    sizes = sorted((i.subject, len(i.findings)) for i in incidents)
    assert sizes == [("alice", 1), ("alice", 2), ("bob", 1)]
    merged = next(i for i in incidents if len(i.findings) == 2)
    assert merged.confidence == pytest.approx(0.96)


def test_entry_scores_combine_every_finding_covering_the_entry():
    visit = row(0, host="login-fake.example", urlsubcat="Phishing", riskscore=88)
    post = row(20, host="login-fake.example", urlsubcat="Phishing", reqmethod="POST")
    result = run([row(), visit, post])
    confidence, severity = result.entry_scores[post["line_no"]]
    assert severity == 4 and confidence >= 0.9
    assert len(result.entry_scores) == 2  # the ordinary row isn't flagged


# --- the upload flow ---------------------------------------------------------------------


def test_upload_stores_incidents_and_highlights_entries(api):
    upload = api.upload("alice", (SAMPLES / "acme-web-small.ndjson").read_bytes()).json
    assert upload["detector_version"] == "1"
    assert upload["stats"]["detection"]["incidents_by_severity"]["Critical"] >= 2
    assert upload["stats"]["totals"]["flagged"] > 0

    incidents = api.get("alice", f"/api/uploads/{upload['id']}/incidents").json["incidents"]
    # The two Critical incidents (malware download, phishing form) come first.
    assert {i["title"] for i in incidents[:2]} == {
        "Known threat: Trojan.Win32.Emotet",
        "Possible credential submission to a phishing page",
    }
    phishing = next(i for i in incidents if "phishing" in i["title"])
    assert {a["kind"] for a in phishing["anomalies"]} >= {"phishing_post", "risky_category"}

    flagged = api.get("alice", f"/api/uploads/{upload['id']}/entries?flagged=true").json
    assert flagged["total"] == upload["stats"]["totals"]["flagged"]
    assert all(e["anomaly_confidence"] >= 0.3 for e in flagged["entries"])
