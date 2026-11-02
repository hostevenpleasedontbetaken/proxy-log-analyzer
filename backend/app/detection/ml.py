"""Layer 3, machine learning: an Isolation Forest finds user-hours that are odd in a
combination no single rule or statistic was written for (the "unknown unknowns").

How it works: it builds 200 random trees, each splitting the data with random yes/no
questions ("bytes out > 40 MB?"). Ordinary hours need many splits to be separated from the
crowd; odd hours are isolated after only a few. Like Guess Who?: a character with a unique
feature is found in two questions.

    log rows ─► one row per user per hour, ~10 numbers ─► IsolationForest ─► the oddest hours
             ─► explained by the 3 numbers furthest from typical ("bytes out 41× typical")

Unusual isn't the same as malicious, so on its own an ML finding stays below High; it raises
confidence when another detector agrees about the same person.
"""

import math
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.detection.findings import (
    DESTINATION,
    MEDIUM,
    POLICY,
    RATE,
    TOOLING,
    VOLUME,
    Finding,
    ramp,
)

MIN_USER_HOURS = 200  # fewer active user-hours than this and "normal" can't be learned
ACTIVE_HOUR_REQUESTS = 10  # an idle laptop (security agent, updates) makes ~3 an hour
# Below the 0.75 ML-alone cap on purpose: a weak agreeing signal (e.g. a script user agent at
# 0.35) shouldn't be enough to push an unusual-but-benign hour into High.
ML_TOP_CONFIDENCE = 0.7
TOP_SHARE = 0.01  # at most the oddest 1% of user-hours are reported
SMOOTHING = 10  # ratios are computed as count / (requests + 10), see user_hour_features
SCRIPT_CLIENTS = ("curl", "python-requests", "wget", "go-http-client", "python-urllib")

# feature → (how to describe it, which evidence family it belongs to). An ML finding is
# counted in the family of the number it found most unusual, so it can't double-count a fact
# another detector already reported (e.g. a huge upload is "volume" either way).
FEATURES = {
    "requests": ("requests", RATE),
    "log_bytes_out": ("bytes uploaded", VOLUME),
    "log_bytes_in": ("bytes downloaded", VOLUME),
    "distinct_hosts": ("distinct hosts", DESTINATION),
    "new_host_share": ("share of never-before-seen hosts", DESTINATION),
    "blocked_ratio": ("share of blocked requests", POLICY),
    "error_ratio": ("share of 4xx/5xx errors", RATE),
    "post_ratio": ("share of POST/PUT requests", VOLUME),
    "mean_host_entropy": ("randomness of host names", DESTINATION),
    "script_share": ("share of scripted (non-browser) requests", TOOLING),
}


def with_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Per-row yes/no columns the features are built from (and that pick the rows behind an
    explanation): blocked, error, post, scripted, new_host, plus host_entropy and hour."""
    df = df.assign(
        hour=df["ts"].dt.floor("h"),
        blocked=df["action"].eq("Blocked"),
        error=df["respcode"].ge(400),
        post=df["reqmethod"].isin(["POST", "PUT"]),
        scripted=df["useragent"].fillna("").str.split("/").str[0].str.lower().isin(SCRIPT_CLIENTS),
        host_entropy=df["host"].fillna("").str.split(".").str[0].map(_entropy),
    )
    # A host is "new" in an hour if this user had never contacted it in an earlier hour.
    first_seen = df.groupby(["subject", "host"])["hour"].transform("min")
    return df.assign(new_host=first_seen.eq(df["hour"]))


def user_hour_features(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (subject, hour) with the FEATURES columns.

    - Byte counts are log-scaled, so a 200 MB hour and a 2 MB hour differ by a few units,
      not by 200 million.
    - Ratios are smoothed: count / (requests + 10). Otherwise a quiet hour with 4 requests
      and 1 block is "25% blocked" and looks wild; with smoothing it's 7%, while a busy hour
      with 100 of 200 blocked still shows 48%.
    """
    df = with_flags(df)
    keys = ["subject_type", "subject", "hour"]
    grouped = df.groupby(keys)
    requests = grouped.size()
    hosts = grouped["host"].nunique()
    # Each (user, hour, host) once, then count how many of those hosts were new.
    new_hosts = df.drop_duplicates([*keys, "host"]).groupby(keys)["new_host"].sum()

    def smoothed(counts: pd.Series, total: pd.Series) -> pd.Series:
        return counts / (total + SMOOTHING)

    features = pd.DataFrame({
        "requests": requests,
        "log_bytes_out": np.log1p(grouped["reqsize"].sum()),
        "log_bytes_in": np.log1p(grouped["respsize"].sum()),
        "distinct_hosts": hosts,
        "new_host_share": smoothed(new_hosts, hosts),
        "blocked_ratio": smoothed(grouped["blocked"].sum(), requests),
        "error_ratio": smoothed(grouped["error"].sum(), requests),
        "post_ratio": smoothed(grouped["post"].sum(), requests),
        "mean_host_entropy": grouped["host_entropy"].mean(),
        "script_share": smoothed(grouped["scripted"].sum(), requests),
    })  # fmt: skip
    return features.fillna(0.0)


def active_user_hours(df: pd.DataFrame) -> pd.DataFrame:
    """Only hours where the person (or something on their laptop) was actually active.
    Most user-hours are idle laptops at night; training on them would make every ordinary
    working hour look unusual."""
    features = user_hour_features(df)
    return features[features["requests"] >= ACTIVE_HOUR_REQUESTS]


def isolation_forest(df: pd.DataFrame) -> list[Finding]:
    features = active_user_hours(df)
    if len(features) < MIN_USER_HOURS:
        return []  # not enough data; the upload summary says ML didn't run

    model = IsolationForest(
        n_estimators=200,  # number of random trees
        max_samples=min(256, len(features)),  # each tree sees a random sample of user-hours
        contamination="auto",  # sklearn's own outlier line (decision < 0)
        random_state=42,  # same file → same trees → same result, every time
    )
    model.fit(features)
    # decision_function: below 0 means past sklearn's outlier line; more negative = odder.
    decision = pd.Series(model.decision_function(features), index=features.index)

    top_n = max(1, math.ceil(TOP_SHARE * len(features)))
    oddest = decision[decision < 0].nsmallest(top_n)

    typical = features.median()
    # Typical spread: the MAD, or the standard deviation where the MAD is 0 (features that
    # are 0 for most hours, like blocked ratio), so a small non-zero value isn't "infinitely"
    # unusual.
    mad = (features - typical).abs().median()
    spread = mad.where(mad > 0, features.std()).replace(0, np.nan)
    flagged = with_flags(df)
    findings = []
    for (subject_type, subject, hour), score in oddest.items():
        row = features.loc[(subject_type, subject, hour)]
        top = _most_extreme(row, typical, spread)
        family = FEATURES[top[0]["feature"]][1]
        hour_rows = flagged[(flagged["subject"] == subject) & (flagged["hour"] == hour)]
        rows = rows_behind(top[0]["feature"], hour_rows)
        findings.append(Finding(
            detector="isolation_forest", layer="ml", family=family,
            subject_type=subject_type, subject=subject,
            title="Unusual hour of activity (machine learning)",
            explanation=(
                f"Isolation Forest ranked {subject}'s {hour:%H}:00 hour among the "
                f"{top_n} most unusual of {len(features):,} active user-hours: "
                f"{'; '.join(item['text'] for item in top)}."
            ),
            # Further past sklearn's line → more confident, but never High on its own.
            confidence=round(ramp(-score, 0.0, 0.4, 0.25, ML_TOP_CONFIDENCE), 3),
            severity=MEDIUM,
            line_nos=rows["line_no"].astype(int).tolist(),
            start_ts=rows["ts"].min().to_pydatetime(),
            end_ts=rows["ts"].max().to_pydatetime(),
            evidence={"anomaly_score": round(float(-score), 4), "user_hours": len(features),
                      "rank": int(oddest.index.get_loc((subject_type, subject, hour))) + 1,
                      "top_features": [{k: v for k, v in item.items() if k != "text"}
                                       for item in top]},
        ))  # fmt: skip
    return findings


def rows_behind(feature: str, rows: pd.DataFrame) -> pd.DataFrame:
    """The rows that explain the hour's most unusual number, so highlighting points at the
    evidence (the error responses, the big uploads…) rather than the whole hour."""
    if feature == "requests":
        picked = rows[rows["host"] == rows["host"].mode().iloc[0]]  # the busiest destination
    elif feature in ("distinct_hosts", "new_host_share"):
        picked = rows[rows["new_host"]]
    elif feature == "log_bytes_out":
        picked = rows[rows["reqsize"] >= 1_000_000]
    elif feature == "log_bytes_in":
        picked = rows[rows["respsize"] >= 1_000_000]
    elif feature == "mean_host_entropy":
        picked = rows[rows["host_entropy"] >= 3.0]
    else:  # blocked_ratio, error_ratio, post_ratio, script_share → their yes/no column
        column = {"blocked_ratio": "blocked", "error_ratio": "error", "post_ratio": "post",
                  "script_share": "scripted"}[feature]  # fmt: skip
        picked = rows[rows[column]]
    return picked if not picked.empty else rows


def _most_extreme(row: pd.Series, typical: pd.Series, spread: pd.Series) -> list[dict]:
    """The 3 features furthest from the typical user-hour (robust z-score), described in
    plain words. This is how an Isolation Forest result is made explainable."""
    distance = ((row - typical).abs() / spread).fillna(0.0)
    items = []
    for feature in distance.nlargest(3).index:
        value, normal = row[feature], typical[feature]
        items.append({"feature": feature, "value": round(float(value), 3),
                      "typical": round(float(normal), 3),
                      "text": _describe(feature, value, normal)})  # fmt: skip
    return items


def _describe(feature: str, value: float, typical: float) -> str:
    name = FEATURES[feature][0]
    if feature.startswith("log_bytes"):
        actual, normal = math.expm1(value), math.expm1(typical)
        return f"{name} {actual / 1e6:.1f} MB vs typical {normal / 1e6:.2f} MB"
    if feature.endswith(("ratio", "share")):
        return f"{name} {value:.0%} vs typical {typical:.0%}"
    return f"{name} {value:.1f} vs typical {typical:.1f}"


def _entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    return -sum(n / len(text) * math.log2(n / len(text)) for n in counts.values())


MACHINE_LEARNING = [isolation_forest]
