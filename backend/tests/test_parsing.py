"""Parser tests: one per messy-input case from the Phase 4 design, plus the real sample files
checked against their answer keys (the generator shares no code with the parser, so this
catches field-mapping mistakes)."""

import base64
import gzip
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.parsing import ParseFailure, parse_upload
from app.parsing.fields import b64_url, integer, ip, severity_label, text

SAMPLES = Path(__file__).resolve().parents[2] / "samples"  # /samples in docker compose
NOW = datetime(2026, 11, 1, tzinfo=UTC)
EPOCH = 1_792_493_089  # 2026-10-20 10:44:49 UTC
TIME = "Tue Oct 20 10:44:49 2026"


def event(**overrides) -> dict:
    """A valid Zscaler web event with every value as a string, like real NSS output."""
    values = {
        "time": TIME, "tz": "GMT", "epochtime": str(EPOCH), "recordid": "123456789",
        "login": "jdoe@acme.example", "dept": "Sales", "cltip": "10.20.1.12",
        "serverip": "192.0.2.10", "host": "mail.officesuite.example",
        "b64url": base64.b64encode(b"mail.officesuite.example/inbox").decode(),
        "reqmethod": "GET", "respcode": "200", "reqsize": "1300", "respsize": "10500",
        "action": "Allowed", "riskscore": "5", "threatseverity": "None",
    }  # fmt: skip
    return {**values, **overrides}


def line(evt: dict | None = None, **overrides) -> str:
    envelope = {"version": "v12", "sourcetype": "zscalernss-web", "event": evt or event()}
    envelope["event"] = {**envelope["event"], **overrides}
    return json.dumps(envelope)


def parse(*lines: str, **options):
    return parse_upload("\n".join(lines).encode(), now=NOW, **options)


# --- happy path --------------------------------------------------------------------------


def test_a_valid_line_becomes_a_typed_row():
    row = parse(line()).rows[0]
    assert row["line_no"] == 1
    assert row["ts"] == datetime(2026, 10, 20, 10, 44, 49, tzinfo=UTC)
    assert row["url"] == "mail.officesuite.example/inbox"  # decoded from b64url
    assert (row["reqsize"], row["respcode"], row["riskscore"]) == (1300, 200, 5)
    assert row["cltip"] == "10.20.1.12"
    assert row["threatseverity"] is None  # "None" is a placeholder, not text


def test_elastic_style_sample_quirks():
    # Modelled on Elastic's published Zscaler sample: the two time fields are years apart.
    row_line = line(
        epochtime="1578128400", time="Mon Oct 16 22:55:48 2023", reqmethod="invalid",
        threatseverity="Critical (90–100)",
        b64url="d3d3LnRyeXRoaXNlbmNvZGV1cmwuY29tL2luZGV4",
    )  # fmt: skip
    result = parse(row_line)
    row = result.rows[0]
    assert row["ts"] == datetime(2020, 1, 4, 9, 0, tzinfo=UTC)  # epochtime wins
    assert result.warnings["time_mismatch"] == 1
    assert row["url"] == "www.trythisencodeurl.com/index"
    assert row["threatseverity"] == "Critical"
    assert row["reqmethod"] == "invalid"  # kept as evidence


def test_bare_event_and_syslog_prefix_are_accepted():
    bare = json.dumps(event())
    syslog = "<134>Oct 20 10:44:49 nss zscaler: " + line()
    assert parse(bare, syslog).parsed_count == 2


def test_plain_url_field_is_used_when_there_is_no_b64url():
    evt = {k: v for k, v in event().items() if k != "b64url"}
    row = parse(line(evt, url="example.com/plain")).rows[0]
    assert row["url"] == "example.com/plain"


def test_epochtime_missing_or_implausible_falls_back_to_time_and_tz():
    for bad in ("0", "None", "4102444800"):  # 1970, missing, year 2100
        row = parse(line(epochtime=bad, time="Tue Oct 20 05:44:49 2026", tz="-05:00")).rows[0]
        assert row["ts"] == datetime(2026, 10, 20, 10, 44, 49, tzinfo=UTC), bad


# --- messy files -------------------------------------------------------------------------


def test_bom_crlf_and_blank_lines_keep_physical_line_numbers():
    data = ("﻿" + line() + "\r\n\r\n" + line() + "\r\n").encode()
    rows = parse_upload(data, now=NOW).rows
    assert [r["line_no"] for r in rows] == [1, 3]


def test_nul_characters_are_removed():
    row = parse(line(useragent="Mozilla\u0000/5.0")).rows[0]
    assert row["useragent"] == "Mozilla/5.0"


def test_a_truncated_last_line_is_skipped_and_reported():
    good = [line() for _ in range(9)]
    result = parse(*good, line()[:-40])
    assert (result.parsed_count, result.error_count) == (9, 1)
    assert result.parse_errors == [
        {"line": 10, "reason": "invalid_json", "excerpt": line()[:-40][:120]}
    ]


def test_other_log_types_mixed_in_are_skipped():
    firewall = json.dumps({"sourcetype": "zscalernss-fw", "event": {"action": "Allow"}})
    result = parse(*[line()] * 9, firewall)
    assert result.parse_errors[0]["reason"] == "wrong_sourcetype"
    assert result.parsed_count == 9


def test_only_the_first_20_errors_are_stored():
    result = parse(*[line()] * 60, *["garbage"] * 30)
    assert result.error_count == 30
    assert len(result.parse_errors) == 20


def test_bad_fields_become_none_with_a_warning_and_the_line_is_kept():
    result = parse(line(cltip="999.1.1.1", reqsize="lots", riskscore="250", b64url="%%%"))
    row = result.rows[0]
    assert (row["cltip"], row["reqsize"], row["riskscore"], row["url"]) == (None,) * 4
    assert result.warnings == {
        "bad_ip": 1, "bad_number": 1, "number_out_of_range": 1, "bad_b64url": 1,
    }  # fmt: skip


def test_huge_fields_are_capped():
    result = parse(line(useragent="A" * 50_000))
    assert len(result.rows[0]["useragent"]) == 1_024
    assert result.warnings["truncated_field"] == 1


def test_duplicate_record_ids_are_counted():
    assert parse(line(), line()).warnings["duplicate_recordid"] == 1


# --- rejected files ----------------------------------------------------------------------


def test_wrong_kind_of_file_is_rejected():
    apache = (SAMPLES / "not-zscaler.log").read_bytes()
    with pytest.raises(ParseFailure) as err:
        parse_upload(apache, now=NOW)
    assert err.value.code == "not_zscaler_web"


def test_sniff_runs_on_the_first_50_lines_of_a_big_file():
    with pytest.raises(ParseFailure) as err:
        parse(*["not json"] * 50, *[line()] * 1_000)
    assert err.value.code == "not_zscaler_web"


def test_more_than_half_bad_lines_is_rejected():
    with pytest.raises(ParseFailure) as err:
        parse(*[line()] * 50, *["not json"] * 60)
    assert err.value.code == "too_many_errors"


def test_empty_file_is_rejected():
    with pytest.raises(ParseFailure) as err:
        parse_upload(b"\n\n  \n", now=NOW)
    assert err.value.code == "empty_file"


def test_too_many_lines_is_rejected():
    with pytest.raises(ParseFailure) as err:
        parse(*[line()] * 11, max_lines=10)
    assert err.value.code == "too_many_lines"


def test_gzip_is_detected_by_content():
    data = gzip.compress((line() + "\n").encode())
    assert parse_upload(data, now=NOW).parsed_count == 1


def test_gzip_bomb_is_rejected_without_unzipping_it_all():
    bomb = gzip.compress(b"\n" * (2 * 1024 * 1024))  # ~2 KB that unzips to 2 MB
    with pytest.raises(ParseFailure) as err:
        parse_upload(bomb, max_bytes=1024 * 1024, now=NOW)
    assert err.value.code == "file_too_large"


def test_corrupt_gzip_is_rejected():
    with pytest.raises(ParseFailure) as err:
        parse_upload(b"\x1f\x8b" + b"definitely not gzip", now=NOW)
    assert err.value.code == "bad_gzip"


# --- converters --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("convert", "raw", "expected"),
    [
        (text, "NA", (None, None)),
        (text, "-", (None, None)),
        (integer(0, 10), 7, (7, None)),  # real numbers are accepted too
        (integer(0, 10), " 7 ", (7, None)),
        (ip, "2001:db8::1", ("2001:db8::1", None)),
        (severity_label, "High (75–89)", ("High", None)),
        (b64_url, "ZXhhbXBsZS5jb20vYQ", ("example.com/a", None)),  # padding missing
        (b64_url, "ZXhhbXBsZS5jb20vPz8-", ("example.com/??>", None)),  # URL-safe alphabet
    ],
)
def test_converters(convert, raw, expected):
    assert convert(raw) == expected


# --- the committed sample files ----------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["acme-web-day.ndjson.gz", "acme-web-small.ndjson", "acme-web-clean.ndjson"]
)
def test_sample_files_parse_completely(name):
    result = parse_upload((SAMPLES / name).read_bytes(), now=NOW)
    assert result.error_count == 0
    assert result.warnings == {}
    assert result.parsed_count == result.line_count


def test_parsed_rows_match_the_answer_key():
    result = parse_upload((SAMPLES / "acme-web-day.ndjson.gz").read_bytes(), now=NOW)
    by_id = {r["record_id"]: r for r in result.rows}
    key = json.loads((SAMPLES / "acme-web-day.ground_truth.json").read_text())
    expected_hosts = {
        "phishing": {"officesuite-login.example"},
        "data_exfiltration": {"www.dropbin.example"},
        "c2_beaconing": {"x9fq2kd7wz.example"},
        "scanning": {"portal.partnerhub.example"},
    }
    for attack in key["attacks"]:
        rows = [by_id[int(rid)] for rid in attack["recordids"]]
        assert {r["login"] for r in rows} == set(attack["users"]), attack["name"]
        if attack["name"] in expected_hosts:
            assert {r["host"] for r in rows} == expected_hosts[attack["name"]]
    exfil = next(a for a in key["attacks"] if a["name"] == "data_exfiltration")
    uploads = [
        by_id[int(rid)] for rid in exfil["recordids"] if by_id[int(rid)]["reqmethod"] == "POST"
    ]
    assert all(r["upload_filename"] and r["reqsize"] > 1_000_000 for r in uploads)


def test_a_50_mb_file_parses_well_within_the_time_budget():
    # Phase 4 budget: 50 MB in under 20 s (the whole request must fit in 60 s).
    day = gzip.decompress((SAMPLES / "acme-web-day.ndjson.gz").read_bytes())
    big = (day * 3)[: 50 * 1024 * 1024]
    big = big[: big.rfind(b"\n") + 1]  # whole lines only
    started = time.perf_counter()
    result = parse_upload(big, now=NOW)
    assert result.parsed_count > 45_000
    assert time.perf_counter() - started < 20
