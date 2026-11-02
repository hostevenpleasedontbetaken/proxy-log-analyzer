"""The upload summary behind the Overview tab: cards, top-10 lists, breakdowns and the
timeline. Computed once with pandas when an upload is processed and stored in `uploads.stats`
(the data never changes afterwards, so there's no reason to recompute it per page view).

pandas is Python's table library: a DataFrame is like an array of row objects that you can
filter, group and count in one call, e.g. `df.groupby("login")["reqsize"].sum()` is roughly
lodash's `_.mapValues(_.groupBy(rows, "login"), rs => _.sumBy(rs, "reqsize"))`.

Shape (abridged):
    {"version": 1,
     "totals":    {"requests": 18654, "users": 40, "blocked": 286, ...},
     "top":       {"users_by_bytes_out": {"items": [{"key": "...", "value": 191000000}, ...],
                                          "other": 1234}, ...},
     "breakdown": {"action": {"Allowed": 18368, "Blocked": 286}, ...},
     "timeline":  {"bucket_seconds": 900, "buckets": [{"t": "2026-10-20T00:00:00Z",
                   "allowed": 12, "blocked": 0, "threats": 0, "bytes_out": 9811}, ...]},
     "quality":   {"lines": 18654, "parsed": 18654, "errors": 0, "warnings": {}}}
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pandas as pd

STATS_VERSION = 1
TOP_N = 10
UNKNOWN = "(unknown)"
HIGH_RISK_SCORE = 75
# Timeline bar sizes to choose from: 1 min, 5 min, 15 min, 1 h, 6 h, 1 day.
BUCKET_SIZES = (60, 300, 900, 3_600, 21_600, 86_400)
MAX_BUCKETS = 200


def to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Parsed rows → a DataFrame (one column per field). Detection (M5) uses the same table."""
    df = pd.DataFrame.from_records(rows)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    for column in ("reqsize", "respsize", "respcode", "riskscore"):
        df[column] = pd.to_numeric(df[column], errors="coerce")  # None → NaN (missing)
    return df


def compute_stats(
    df: pd.DataFrame, *, line_count: int, error_count: int, warnings: Mapping[str, int]
) -> dict[str, Any]:
    blocked = df["action"].eq("Blocked")
    threat = df["threatname"].notna()
    return {
        "version": STATS_VERSION,
        # How much data, who, where, what got stopped, anything known to be bad?
        "totals": {
            "requests": len(df),
            "users": int(df["login"].nunique()),
            "client_ips": int(df["cltip"].nunique()),
            "devices": int(df["devicehostname"].nunique()),
            "hosts": int(df["host"].nunique()),
            "blocked": int(blocked.sum()),
            "threat_hits": int(threat.sum()),
            "high_risk": int((df["riskscore"] >= HIGH_RISK_SCORE).sum()),
            "bytes_out": int(df["reqsize"].sum()),  # uploaded by users
            "bytes_in": int(df["respsize"].sum()),  # downloaded by users
        },
        "top": {
            "users_by_requests": top(df["login"]),
            "users_by_bytes_out": top(df["login"], weights=df["reqsize"]),
            "hosts_by_requests": top(df["host"]),
            "hosts_by_bytes_out": top(df["host"], weights=df["reqsize"]),
            "countries": top(df["dstip_country"]),
            "categories": top(df["urlsubcat"]),
            "blocked_hosts": top(df.loc[blocked, "host"]),
            "block_reasons": top(df.loc[blocked, "reason"]),
            "threats": top(df.loc[threat, "threatname"]),
        },
        "breakdown": {
            "action": counts(df["action"]),
            "respcode_class": counts(status_class(df["respcode"])),
            "urlclass": counts(df["urlclass"]),
        },
        "timeline": timeline(df, blocked, threat),
        # Can I trust the data?
        "quality": {
            "lines": line_count,
            "parsed": len(df),
            "errors": error_count,
            "warnings": dict(sorted(warnings.items())),
        },
    }


def top(values: pd.Series, weights: pd.Series | None = None, n: int = TOP_N) -> dict[str, Any]:
    """The n biggest groups plus an "other" total, by row count or by summed `weights`.
    Missing keys are grouped as "(unknown)"; ties are ordered by name so output is stable."""
    keys = values.fillna(UNKNOWN)
    amounts = weights.fillna(0) if weights is not None else pd.Series(1, index=keys.index)
    totals = amounts.groupby(keys).sum()
    ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    return {
        "items": [{"key": key, "value": int(value)} for key, value in ranked[:n]],
        "other": int(sum(value for _, value in ranked[n:])),
    }


def counts(values: pd.Series) -> dict[str, int]:
    """Every distinct value and how often it appears (for short lists like Allowed/Blocked)."""
    return {
        str(key): int(n)
        for key, n in sorted(values.fillna(UNKNOWN).value_counts().items(), key=_by_count)
    }


def status_class(codes: pd.Series) -> pd.Series:
    """200 → "2xx", 404 → "4xx"; missing stays missing."""
    return (codes // 100).map(lambda c: f"{int(c)}xx", na_action="ignore")


def choose_bucket(span_seconds: float) -> int:
    """The smallest bar size that keeps the chart at 200 bars or fewer:
    2 hours → 1 min (120 bars), 1 day → 15 min (96), 1 week → 1 h (168)."""
    for size in BUCKET_SIZES:
        if span_seconds // size + 1 <= MAX_BUCKETS:
            return size
    return BUCKET_SIZES[-1]


def timeline(df: pd.DataFrame, blocked: pd.Series, threat: pd.Series) -> dict[str, Any]:
    """Requests per time bucket. Empty buckets are filled with zeros instead of skipped: in a
    SOC, a silent hour can mean log forwarding broke, so the gap has to be visible."""
    seconds = (df["ts"] - pd.Timestamp(0, tz=UTC)).dt.total_seconds()
    size = choose_bucket(seconds.max() - seconds.min())
    bucket = (seconds // size * size).astype("int64")
    every_bucket = range(int(bucket.min()), int(bucket.max()) + size, size)

    def per_bucket(values: pd.Series) -> pd.Series:
        return values.groupby(bucket).sum().reindex(every_bucket, fill_value=0)

    allowed = per_bucket(~blocked)
    blocked_n = per_bucket(blocked)
    threats = per_bucket(threat)
    bytes_out = per_bucket(df["reqsize"].fillna(0))
    return {
        "bucket_seconds": size,
        "buckets": [
            {
                "t": _iso(t),
                "allowed": int(allowed[t]),
                "blocked": int(blocked_n[t]),
                "threats": int(threats[t]),
                "bytes_out": int(bytes_out[t]),
            }
            for t in every_bucket
        ],
    }


def _by_count(item: tuple[Any, int]) -> tuple[int, str]:
    return (-item[1], str(item[0]))


def _iso(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
