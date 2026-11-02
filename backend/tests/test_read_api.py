"""Read endpoints against a real Postgres: entries (paging, filters), one entry, incidents,
anomalies. Detection doesn't exist yet (M5), so tests insert anomalies and incidents directly."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Anomaly, AnomalyEntry, Incident, LogEntry

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
SMALL = (SAMPLES / "acme-web-small.ndjson").read_bytes()  # 1,934 lines, includes 3 attacks
T0 = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)


@pytest.fixture
def upload_id(api):
    return api.upload("alice", SMALL).json["id"]


def entries(api, upload_id, query=""):
    res = api.get("alice", f"/api/uploads/{upload_id}/entries{query}")
    assert res.status_code == 200, res.json
    return res.json


def add_incident(db_engine, upload_id, line_nos, *, confidence=0.9, severity=3):
    """What detection will do in M5: an incident, one anomaly in it, links to entries, and the
    copied confidence/severity on those entries."""
    with Session(db_engine) as session, session.begin():
        incident = Incident(
            upload_id=upload_id, subject_type="user", subject="x", title="Phishing",
            severity=severity, confidence=confidence, start_ts=T0, end_ts=T0,
        )  # fmt: skip
        session.add(incident)
        session.flush()
        anomaly = Anomaly(
            upload_id=upload_id, incident_id=incident.id, detector="rule", kind="phishing",
            subject_type="user", subject="x", title="Phishing page", explanation="why",
            confidence=confidence, severity=severity, start_ts=T0, end_ts=T0,
            entry_count=len(line_nos), evidence={"category": "Phishing"},
        )  # fmt: skip
        session.add(anomaly)
        session.flush()
        session.add_all(
            AnomalyEntry(anomaly_id=anomaly.id, upload_id=upload_id, line_no=n) for n in line_nos
        )
        session.execute(
            update(LogEntry)
            .where(LogEntry.upload_id == upload_id, LogEntry.line_no.in_(line_nos))
            .values(anomaly_confidence=confidence, max_severity=severity)
        )
        return incident.id, anomaly.id


# --- entries -----------------------------------------------------------------------------


def test_first_page_in_time_order(api, upload_id):
    body = entries(api, upload_id)
    assert (body["page"], body["page_size"], body["total"], body["pages"]) == (1, 100, 1934, 20)
    times = [e["ts"] for e in body["entries"]]
    assert len(times) == 100 and times == sorted(times)
    assert set(body["entries"][0]) >= {"line_no", "ts", "login", "host", "action", "cltip"}


def test_paging(api, upload_id):
    first = entries(api, upload_id, "?page_size=200")["entries"]
    second = entries(api, upload_id, "?page=2&page_size=200")["entries"]
    last = entries(api, upload_id, "?page=10&page_size=200")["entries"]
    assert first[-1]["ts"] <= second[0]["ts"]
    assert len(last) == 1934 - 9 * 200
    assert entries(api, upload_id, "?page=11&page_size=200")["entries"] == []


@pytest.mark.parametrize("query", ["?page=0", "?page_size=500", "?min_confidence=2", "?usr=bob"])
def test_bad_parameters_are_rejected(api, upload_id, query):
    res = api.get("alice", f"/api/uploads/{upload_id}/entries{query}")
    assert res.status_code == 400
    assert res.json["error"]["code"] == "invalid_query"


def test_filters(api, upload_id):
    blocked = entries(api, upload_id, "?action=Blocked&page_size=200")
    assert blocked["total"] > 0
    assert {e["action"] for e in blocked["entries"]} == {"Blocked"}

    exfil = entries(api, upload_id, "?q=DROPBIN")  # case-insensitive host/URL search
    assert exfil["total"] == 15
    assert {e["host"] for e in exfil["entries"]} == {"www.dropbin.example"}

    user = exfil["entries"][0]["login"]
    mine = entries(api, upload_id, f"?user={user}&page_size=200")
    assert {e["login"] for e in mine["entries"]} == {user}

    window = entries(api, upload_id, "?from=2026-10-20T23:00:00Z&to=2026-10-21T00:00:00Z")
    assert all("2026-10-20T23:" in e["ts"] for e in window["entries"])


def test_search_treats_wildcards_literally(api, upload_id):
    assert entries(api, upload_id, "?q=%25")["total"] == 0  # "%" must not match everything


def test_flagged_and_incident_filters(api, db_engine, upload_id):
    incident_id, anomaly_id = add_incident(db_engine, upload_id, [5, 6, 7], confidence=0.9)
    add_incident(db_engine, upload_id, [100], confidence=0.4)

    assert entries(api, upload_id, "?flagged=true")["total"] == 4
    assert entries(api, upload_id, "?flagged=false")["total"] == 1930
    assert entries(api, upload_id, "?min_confidence=0.8")["total"] == 3
    by_incident = entries(api, upload_id, f"?incident_id={incident_id}")
    assert [e["line_no"] for e in by_incident["entries"]] == [5, 6, 7]
    assert entries(api, upload_id, f"?anomaly_id={anomaly_id}")["total"] == 3
    flagged_row = by_incident["entries"][0]
    assert (flagged_row["anomaly_confidence"], flagged_row["max_severity"]) == (0.9, 3)


# --- one entry ---------------------------------------------------------------------------


def test_entry_detail_includes_every_field_and_why_it_was_flagged(api, db_engine, upload_id):
    _, anomaly_id = add_incident(db_engine, upload_id, [5])
    res = api.get("alice", f"/api/uploads/{upload_id}/entries/5")
    assert res.status_code == 200
    detail = res.json
    assert detail["line_no"] == 5
    assert {"useragent", "serverip", "rulelabel", "urlclass", "record_id"} <= set(detail)
    assert [a["id"] for a in detail["anomalies"]] == [anomaly_id]
    assert detail["anomalies"][0]["explanation"] == "why"

    unflagged = api.get("alice", f"/api/uploads/{upload_id}/entries/6").json
    assert unflagged["anomalies"] == []


def test_missing_entry_and_someone_elses_upload(api, upload_id):
    assert api.get("alice", f"/api/uploads/{upload_id}/entries/99999").status_code == 404
    for path in ("entries", "entries/5", "incidents", "anomalies"):
        res = api.get("bob", f"/api/uploads/{upload_id}/{path}")
        assert res.status_code == 404, path


# --- incidents and anomalies -------------------------------------------------------------


def test_incidents_most_severe_first_with_their_anomalies(api, db_engine, upload_id):
    low, _ = add_incident(db_engine, upload_id, [1], confidence=0.5, severity=2)
    high, _ = add_incident(db_engine, upload_id, [2, 3], confidence=0.95, severity=4)
    incidents = api.get("alice", f"/api/uploads/{upload_id}/incidents").json["incidents"]
    assert [i["id"] for i in incidents] == [high, low]
    assert incidents[0]["anomalies"][0]["entry_count"] == 2
    assert incidents[0]["anomalies"][0]["evidence"] == {"category": "Phishing"}


def test_anomalies_most_confident_first_and_filters(api, db_engine, upload_id):
    add_incident(db_engine, upload_id, [1], confidence=0.5)
    add_incident(db_engine, upload_id, [2], confidence=0.95)
    path = f"/api/uploads/{upload_id}/anomalies"
    confidences = [a["confidence"] for a in api.get("alice", path).json["anomalies"]]
    assert confidences == [0.95, 0.5]
    assert len(api.get("alice", f"{path}?min_confidence=0.9").json["anomalies"]) == 1
    assert api.get("alice", f"{path}?detector=ml").json["anomalies"] == []


def test_no_detection_yet_means_empty_lists(api, upload_id):
    assert api.get("alice", f"/api/uploads/{upload_id}/incidents").json == {"incidents": []}
    assert api.get("alice", f"/api/uploads/{upload_id}/anomalies").json == {"anomalies": []}
