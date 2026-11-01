"""Bytes → numbered text lines, lazily (one line at a time), with the file-level limits.

Line numbers are physical: blank lines still count, so "line 812" matches what an analyst
sees when they open the file in an editor.
"""

import gzip
import io
import zlib
from collections.abc import Iterator

from app.parsing.errors import ParseFailure

GZIP_MAGIC = b"\x1f\x8b"  # every gzip file starts with these two bytes
MAX_UNZIPPED_BYTES = 50 * 1024 * 1024
MAX_LINES = 100_000
UTF8_BOM = "﻿"


def decompress(data: bytes, max_bytes: int = MAX_UNZIPPED_BYTES) -> bytes:
    """Unzip if the bytes are gzip (detected by content, not file name).

    Reads at most `max_bytes + 1` so a "gzip bomb" (a tiny file that unzips to gigabytes)
    is rejected without ever being fully expanded in memory.
    """
    if not data.startswith(GZIP_MAGIC):
        if len(data) > max_bytes:
            raise ParseFailure("file_too_large", "The file is larger than 50 MB.")
        return data
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
            out = gz.read(max_bytes + 1)
    except (OSError, EOFError, zlib.error):
        raise ParseFailure("bad_gzip", "The file looks gzipped but couldn't be unzipped.") from None
    if len(out) > max_bytes:
        raise ParseFailure("file_too_large", "The file unzips to more than 50 MB.")
    return out


def iter_lines(data: bytes, max_lines: int = MAX_LINES) -> Iterator[tuple[int, str]]:
    """Yield (line number, text) for each non-blank line.

    Normalizes what real exports contain: a UTF-8 byte-order mark, Windows line endings,
    invalid UTF-8 (replaced, not fatal) and NUL characters, which Postgres refuses to store
    in text and which would otherwise fail the whole insert.
    """
    count = 0
    for line_no, raw in enumerate(io.BytesIO(data), start=1):
        text = raw.decode("utf-8", errors="replace").rstrip("\r\n").replace("\x00", "")
        if line_no == 1:
            text = text.removeprefix(UTF8_BOM)
        if not text.strip():
            continue
        count += 1
        if count > max_lines:
            raise ParseFailure("too_many_lines", f"The file has more than {max_lines:,} lines.")
        yield line_no, text


def strip_syslog_prefix(line: str) -> str:
    """NSS ships logs over syslog, so exported lines may start with a header such as
    `<134>Oct 16 22:55:48 nss zscaler: {...}`. The JSON starts at the first `{`."""
    if line.startswith("{"):
        return line
    start = line.find("{")
    return line[start:] if start != -1 else line
