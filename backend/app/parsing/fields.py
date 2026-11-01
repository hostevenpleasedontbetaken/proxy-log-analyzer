"""One small converter per field: raw string → typed value.

Every converter returns `(value, warning)`. A bad field becomes `None` plus a warning
(e.g. "bad_ip"); it never rejects the whole line, because the rest of the line is still
evidence. Warnings are counted per upload and shown in the data-quality panel.
"""

import base64
import binascii
import ipaddress
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

Converted = tuple[Any, str | None]
Converter = Callable[[Any], Converted]

# Zscaler writes these instead of leaving a value empty. Compared case-insensitively.
PLACEHOLDERS = frozenset({"", "none", "na", "n/a", "-", "null"})
TEXT_CAP = 1_024
URL_CAP = 8_192


def is_missing(raw: Any) -> bool:
    return raw is None or (isinstance(raw, str) and raw.strip().lower() in PLACEHOLDERS)


def text(raw: Any, cap: int = TEXT_CAP) -> Converted:
    """Any value as a string, cut to `cap` characters (one 50 KB user agent shouldn't bloat
    the database).

    NUL characters are removed here as well as in the reader: JSON usually writes them
    escaped (\\u0000), so they only appear after decoding, and Postgres refuses to store them.
    """
    if is_missing(raw):
        return None, None
    value = str(raw).replace("\x00", "")
    if len(value) > cap:
        return value[:cap], "truncated_field"
    return value, None


def integer(lowest: int, highest: int) -> Converter:
    """A converter for whole numbers in a range. Accepts "1300" and 1300 alike."""

    def convert(raw: Any) -> Converted:
        if is_missing(raw):
            return None, None
        try:
            value = int(str(raw).strip())
        except ValueError:
            return None, "bad_number"
        if not lowest <= value <= highest:
            return None, "number_out_of_range"
        return value, None

    return convert


def ip(raw: Any) -> Converted:
    """IPv4 or IPv6, validated (the column is Postgres `inet`, which would reject junk and
    fail the whole insert)."""
    if is_missing(raw):
        return None, None
    try:
        return str(ipaddress.ip_address(str(raw).strip())), None
    except ValueError:
        return None, "bad_ip"


def severity_label(raw: Any) -> Converted:
    """ "Critical (90–100)" → "Critical": keep the label, drop the score range."""
    value, warning = text(raw)
    if value:
        value = value.split("(")[0].strip() or value
    return value, warning


def b64_url(raw: Any) -> Converted:
    """Zscaler's `b64url` field: base64 of "host/path". Tolerates missing padding and the
    URL-safe alphabet (- and _ instead of + and /)."""
    if is_missing(raw):
        return None, None
    encoded = str(raw).strip().replace("-", "+").replace("_", "/")
    encoded += "=" * (-len(encoded) % 4)
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None, "bad_b64url"
    return text(decoded, cap=URL_CAP)


def plain_url(raw: Any) -> Converted:
    return text(raw, cap=URL_CAP)


SMALLINT_MAX = 32_767
BIGINT_MAX = 2**63 - 1

# column in log_entries → (key in the Zscaler event, converter)
COLUMNS: dict[str, tuple[str, Converter]] = {
    "record_id": ("recordid", integer(0, BIGINT_MAX)),
    "tz": ("tz", text),
    "login": ("login", text),
    "dept": ("dept", text),
    "location": ("location", text),
    "devicehostname": ("devicehostname", text),
    "cltip": ("cltip", ip),
    "serverip": ("serverip", ip),
    "dstip_country": ("dstip_country", text),
    "host": ("host", text),
    "url": ("b64url", b64_url),
    "reqmethod": ("reqmethod", text),
    "respcode": ("respcode", integer(0, 999)),
    "proto": ("proto", text),
    "useragent": ("useragent", text),
    "refererhost": ("refererhost", text),
    "contenttype": ("contenttype", text),
    "reqsize": ("reqsize", integer(0, BIGINT_MAX)),
    "respsize": ("respsize", integer(0, BIGINT_MAX)),
    "action": ("action", text),
    "reason": ("reason", text),
    "rulelabel": ("rulelabel", text),
    "ruletype": ("ruletype", text),
    "urlsubcat": ("urlsubcat", text),
    "urlsupercat": ("urlsupercat", text),
    "urlclass": ("urlclass", text),
    "appname": ("appname", text),
    "appclass": ("appclass", text),
    "threatname": ("threatname", text),
    "threatseverity": ("threatseverity", severity_label),
    "malwarecategory": ("malwarecategory", text),
    "malwareclass": ("malwareclass", text),
    "riskscore": ("riskscore", integer(0, 100)),
    "filename": ("filename", text),
    "filetype": ("filetype", text),
    "upload_filename": ("upload_filename", text),
    "sha256": ("sha256", text),
}

# --- time ------------------------------------------------------------------------------------

EARLIEST_PLAUSIBLE = datetime(2000, 1, 1, tzinfo=UTC)
MISMATCH_TOLERANCE = timedelta(seconds=60)
TIME_FORMAT = "%a %b %d %H:%M:%S %Y"  # "Tue Oct 20 09:14:03 2026"
UTC_NAMES = frozenset({"gmt", "utc", "z"})
OFFSET = re.compile(r"^(?:gmt|utc)?\s*([+-])(\d{1,2}):?(\d{2})?$", re.IGNORECASE)


def timestamp(event: dict[str, Any], now: datetime) -> tuple[datetime | None, list[str]]:
    """When the request happened, in UTC.

    `epochtime` (seconds since 1970) is the source of truth: it has no time-zone ambiguity.
    If it's missing or implausible (before 2000, or after tomorrow), fall back to `time` +
    `tz`. If both exist and disagree by more than a minute, keep epochtime and warn; even
    Elastic's published Zscaler sample has the two fields years apart.
    """
    warnings: list[str] = []
    latest = now + timedelta(days=1)

    from_epoch = _from_epoch(event.get("epochtime"))
    if from_epoch is not None and not EARLIEST_PLAUSIBLE <= from_epoch <= latest:
        from_epoch = None
        warnings.append("implausible_epochtime")

    from_text, tz_warning = _from_text(event.get("time"), event.get("tz"))
    if tz_warning:
        warnings.append(tz_warning)
    if from_text is not None and not EARLIEST_PLAUSIBLE <= from_text <= latest:
        from_text = None

    if from_epoch and from_text and abs(from_epoch - from_text) > MISMATCH_TOLERANCE:
        warnings.append("time_mismatch")
    return from_epoch or from_text, warnings


def _from_epoch(raw: Any) -> datetime | None:
    if is_missing(raw):
        return None
    try:
        return datetime.fromtimestamp(float(str(raw).strip()), UTC)
    except (ValueError, OverflowError, OSError):
        return None


def _from_text(raw_time: Any, raw_tz: Any) -> tuple[datetime | None, str | None]:
    if is_missing(raw_time):
        return None, None
    try:
        naive = datetime.strptime(str(raw_time).strip(), TIME_FORMAT)
    except ValueError:
        return None, None
    zone, warning = _zone(raw_tz)
    return naive.replace(tzinfo=zone).astimezone(UTC), warning


def _zone(raw_tz: Any) -> tuple[timezone, str | None]:
    """ "GMT", "UTC", "+05:30", "GMT-0700" → a time zone. Anything else is assumed UTC, with a
    warning (abbreviations like "PST" are ambiguous worldwide)."""
    if is_missing(raw_tz) or str(raw_tz).strip().lower() in UTC_NAMES:
        return UTC, None
    match = OFFSET.match(str(raw_tz).strip())
    if not match:
        return UTC, "unknown_timezone"
    sign, hours, minutes = match.groups()
    offset = timedelta(hours=int(hours), minutes=int(minutes or 0))
    return timezone(offset if sign == "+" else -offset), None
