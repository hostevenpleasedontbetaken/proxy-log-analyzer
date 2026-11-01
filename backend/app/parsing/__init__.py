"""Turns an uploaded Zscaler NSS web log into clean, typed rows for `log_entries`.

    bytes ─► unzip? ─► lines ─► strip syslog prefix ─► JSON ─► unwrap envelope ─► convert fields

reader.py  bytes → numbered lines (gzip, size and line limits, BOM, CRLF, NUL)
fields.py  one small converter per field: string → int / IP / text / timestamp
parser.py  ties it together: per-line errors, warnings, the "is this Zscaler?" sniff test
"""

from app.parsing.errors import ParseFailure
from app.parsing.parser import PARSER_VERSION, ParseResult, parse_upload

__all__ = ["PARSER_VERSION", "ParseFailure", "ParseResult", "parse_upload"]
