"""The parsing pipeline: uploaded bytes → a list of rows ready for `log_entries`.

Rules for bad input (Phase 4 decisions):
- a bad field  → that field is None, a warning is counted, the line is kept
- a bad line   → skipped and counted; the first 20 are kept with line number and reason
- the file     → rejected only if it isn't Zscaler web logs (sniff test on the first 50
                 lines) or more than half its lines are unreadable
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.parsing.errors import ParseFailure
from app.parsing.fields import COLUMNS, plain_url, timestamp
from app.parsing.reader import (
    MAX_LINES,
    MAX_UNZIPPED_BYTES,
    decompress,
    iter_lines,
    strip_syslog_prefix,
)

PARSER_VERSION = "1"  # stored on each upload; bump when parsing rules change
SNIFF_LINES = 50
SNIFF_MIN_GOOD_SHARE = 0.8
MAX_BAD_SHARE = 0.5
MAX_STORED_ERRORS = 20
EXCERPT_CHARS = 120
WEB_SOURCETYPE = "zscalernss-web"


class LineError(Exception):
    """This line can't be used; `reason` is a short code like "invalid_json"."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class ParseResult:
    rows: list[dict[str, Any]]  # one per good line: {"line_no": 12, "ts": ..., "login": ...}
    line_count: int  # non-blank lines read
    error_count: int  # lines skipped
    parse_errors: list[dict[str, Any]]  # the first 20: {"line", "reason", "excerpt"}
    warnings: Counter[str] = field(default_factory=Counter)  # bad fields, by kind

    @property
    def parsed_count(self) -> int:
        return len(self.rows)

    @property
    def time_start(self) -> datetime | None:
        return min((r["ts"] for r in self.rows), default=None)

    @property
    def time_end(self) -> datetime | None:
        return max((r["ts"] for r in self.rows), default=None)


def parse_upload(
    data: bytes,
    *,
    max_lines: int = MAX_LINES,
    max_bytes: int = MAX_UNZIPPED_BYTES,
    now: datetime | None = None,
) -> ParseResult:
    """Parse a whole upload (plain or gzipped). Raises ParseFailure if the file is rejected."""
    now = now or datetime.now(UTC)
    result = ParseResult(rows=[], line_count=0, error_count=0, parse_errors=[])

    for line_no, line in iter_lines(decompress(data, max_bytes), max_lines):
        result.line_count += 1
        try:
            row, warnings = to_row(parse_event(line), line_no, now)
        except LineError as err:
            result.error_count += 1
            if len(result.parse_errors) < MAX_STORED_ERRORS:
                excerpt = line[:EXCERPT_CHARS]
                result.parse_errors.append(
                    {"line": line_no, "reason": err.reason, "excerpt": excerpt}
                )
        else:
            result.rows.append(row)
            result.warnings.update(warnings)
        if result.line_count == SNIFF_LINES:
            _sniff(result)  # fail fast: don't parse 100k lines of the wrong kind of log

    if result.line_count == 0:
        raise ParseFailure("empty_file", "The file has no log lines.")
    if result.line_count < SNIFF_LINES:
        _sniff(result)
    if result.error_count > MAX_BAD_SHARE * result.line_count:
        raise ParseFailure(
            "too_many_errors",
            f"{result.error_count:,} of {result.line_count:,} lines couldn't be read.",
        )

    duplicates = len(result.rows) - len({r["record_id"] for r in result.rows})
    if duplicates:
        result.warnings["duplicate_recordid"] += duplicates
    return result


def parse_event(line: str) -> dict[str, Any]:
    """One line → the Zscaler event object. Accepts the v12 envelope
    {"sourcetype": "zscalernss-web", "event": {...}}, a bare event, and a syslog prefix."""
    try:
        obj = json.loads(strip_syslog_prefix(line))
    except json.JSONDecodeError:
        raise LineError("invalid_json") from None  # often a line cut off mid-write
    if not isinstance(obj, dict):
        raise LineError("not_an_object")
    if "event" in obj:
        if obj.get("sourcetype", WEB_SOURCETYPE) != WEB_SOURCETYPE:
            raise LineError("wrong_sourcetype")  # e.g. firewall or DNS logs mixed in
        obj = obj["event"]
        if not isinstance(obj, dict):
            raise LineError("not_an_object")
    has_destination = any(key in obj for key in ("host", "b64url", "url"))
    has_time = "epochtime" in obj or "time" in obj
    if not (has_destination and has_time):
        raise LineError("not_a_web_event")
    return obj


def to_row(event: dict[str, Any], line_no: int, now: datetime) -> tuple[dict, list[str]]:
    """Convert every field. Returns the row and the warnings it produced."""
    ts, warnings = timestamp(event, now)
    if ts is None:
        raise LineError("no_valid_time")

    row: dict[str, Any] = {"line_no": line_no, "ts": ts}
    for column, (key, convert) in COLUMNS.items():
        value, warning = convert(event.get(key))
        row[column] = value
        if warning:
            warnings.append(warning)

    if row["url"] is None and "url" in event:  # some exports have a plain `url` instead
        row["url"], warning = plain_url(event["url"])
        if warning:
            warnings.append(warning)
    return row, warnings


def _sniff(result: ParseResult) -> None:
    good = result.line_count - result.error_count
    if good < SNIFF_MIN_GOOD_SHARE * result.line_count:
        raise ParseFailure(
            "not_zscaler_web",
            "This doesn't look like a Zscaler web log: only "
            f"{good} of the first {result.line_count} lines are Zscaler web events.",
        )
