"""Layer 2, statistics: "unusual compared with normal", where normal is learned from the same
file. Each detector returns Findings, like the rules.

There's no history to learn from and the attack is inside the data, so baselines use the
median (and MAD, the median distance from the median) instead of the mean: one huge upload
barely moves a median but drags an average far up.

Every detector also has to leave the benign look-alikes alone, so each one names what
separates the attack from its harmless twin.
"""

import math
from collections import Counter
from datetime import timedelta

import pandas as pd

from app.detection.findings import (
    DESTINATION,
    HIGH,
    IDENTITY,
    LOW,
    MEDIUM,
    RATE,
    TIMING,
    VOLUME,
    Finding,
    ramp,
)

STATISTICAL = "statistical"
FLEET_SHARE = 0.5  # a host more than half the users contact is company-wide software/SaaS
MB = 1_000_000


def finding(rows: pd.DataFrame, **fields) -> Finding:
    first = rows.iloc[0]
    return Finding(
        layer=STATISTICAL,
        subject_type=first["subject_type"],
        subject=first["subject"],
        line_nos=rows["line_no"].astype(int).tolist(),
        start_ts=rows["ts"].min().to_pydatetime(),
        end_ts=rows["ts"].max().to_pydatetime(),
        **fields,
    )


def fleet_hosts(df: pd.DataFrame) -> set[str]:
    """Hosts most of the company talks to (mail, chat, the security agent, updates…)."""
    users_per_host = df.groupby("host")["subject"].nunique()
    return set(users_per_host[users_per_host > FLEET_SHARE * df["subject"].nunique()].index)


def mad(values: pd.Series) -> float:
    """Median absolute deviation: the typical distance from the median."""
    return float((values - values.median()).abs().median())


def clock(ts: pd.Timestamp) -> str:
    return ts.strftime("%H:%M")


# --- beaconing ---------------------------------------------------------------------------


def beaconing(df: pd.DataFrame) -> list[Finding]:
    """One user's device calling one host on a near-fixed timer with near-identical sizes:
    malware checking in with its command server.

    vs the look-alike: the security agent and update checks also run on a timer, but on
    every laptop, to a host most of the company uses. Those are skipped.
    """
    fleet = fleet_hosts(df)
    findings = []
    candidates = df[~df["host"].isin(fleet) & df["action"].eq("Allowed")].sort_values("ts")
    for (_, _, host), rows in candidates.groupby(["subject_type", "subject", "host"]):
        if len(rows) < 20:
            continue
        gaps = rows["ts"].diff().dt.total_seconds().dropna()
        span = rows["ts"].max() - rows["ts"].min()
        if gaps.median() < 30 or span < timedelta(minutes=30):
            continue  # page loads and bursts aren't a timer
        gap_cv = gaps.std() / gaps.mean()  # coefficient of variation: 0 = perfectly regular
        size_cv = rows["reqsize"].std() / max(rows["reqsize"].mean(), 1)
        if gap_cv > 0.3 or size_cv > 0.3:
            continue
        confidence = ramp(gap_cv, 0.05, 0.85, 0.3, 0.45)  # more regular → more confident
        findings.append(finding(
            rows, detector="beaconing", family=TIMING, confidence=round(confidence, 3),
            severity=HIGH, title="Regular check-ins to an unusual host (possible C2 beaconing)",
            explanation=(
                f"{rows.iloc[0]['subject']} contacted {host} {len(rows)} times from "
                f"{clock(rows['ts'].min())} to {clock(rows['ts'].max())}, every "
                f"{gaps.median():.0f} s (±{gap_cv:.0%}) with near-identical sizes "
                f"(~{rows['reqsize'].median():.0f} bytes out); no other user contacts this host "
                f"regularly."
            ),
            evidence={"host": host, "requests": len(rows), "median_gap_s": round(gaps.median(), 1),
                      "gap_cv": round(gap_cv, 3), "size_cv": round(size_cv, 3)},
        ))  # fmt: skip
    return findings


# --- data exfiltration -------------------------------------------------------------------


def exfil_volume(df: pd.DataFrame) -> list[Finding]:
    """An hour in which a user uploaded far more than their usual hour (robust z-score on
    their own hourly uploads), mostly to one destination.

    vs the look-alike: a big upload to the company's own storage (a "Business Use" app) is
    expected work, so confidence is halved; uploads to personal file sharing are not.
    """
    hourly = df.assign(hour=df["ts"].dt.floor("h"))
    per_hour = hourly.groupby(["subject_type", "subject", "hour"])["reqsize"].sum()
    findings = []
    for (_, subject), hours in per_hour.groupby(level=[0, 1]):
        baseline = hours.median()
        spread = max(mad(hours), 1.0)
        for (_, _, hour), uploaded in hours.items():
            if uploaded < 20 * MB or uploaded < 10 * max(baseline, 1):
                continue
            robust_z = (uploaded - baseline) / (1.4826 * spread)  # 1.4826 makes MAD ≈ std
            in_hour = hourly[(hourly["subject"] == subject) & (hourly["hour"] == hour)]
            by_host = in_hour.groupby("host")["reqsize"].sum()
            host = by_host.idxmax()
            rows = in_hour[in_hour["host"] == host]
            sanctioned = rows["urlclass"].eq("Business Use").all()
            confidence = ramp(uploaded / MB, 20, 0.6, 100, 0.9) * (0.5 if sanctioned else 1)
            files = sorted(rows["upload_filename"].dropna().unique())
            category = (
                rows["urlsubcat"].dropna().iloc[0] if rows["urlsubcat"].notna().any() else "?"
            )
            findings.append(finding(
                rows, detector="exfil_volume", family=VOLUME, confidence=round(confidence, 3),
                severity=LOW if sanctioned else HIGH,
                title="Large upload to company storage" if sanctioned
                else "Large upload to an outside site (possible data exfiltration)",
                explanation=(
                    f"{subject} uploaded {uploaded / MB:.0f} MB in the {clock(hour)} hour, "
                    f"{uploaded / max(baseline, 1):,.0f}× their typical hour; "
                    f"{by_host.max() / MB:.0f} MB went to {host} ({category})"
                    f"{': ' + ', '.join(files[:5]) if files else ''}."
                ),
                evidence={"bytes_out": int(uploaded), "typical_hour_bytes": int(baseline),
                          "robust_z": round(float(robust_z), 1), "host": host,
                          "sanctioned": bool(sanctioned), "files": files[:10]},
            ))  # fmt: skip
    return findings


# --- bursts / scanning -------------------------------------------------------------------


def burst(df: pd.DataFrame) -> list[Finding]:
    """Far more requests per minute than anyone normally makes, usually from a script. A high
    share of 404s means it's probing for pages that might exist: scanning.

    vs the look-alike: the IT admin's scripts make ~20 requests a minute that all succeed.
    """
    minute = df["ts"].dt.floor("min")
    per_minute = df.groupby(["subject_type", "subject", minute]).size()
    typical = max(per_minute.median(), 1)
    threshold = max(60, 10 * typical)
    findings = []
    for (_, subject), minutes in per_minute.groupby(level=[0, 1]):
        busy = minutes[minutes >= threshold]
        if busy.empty:
            continue
        busy_minutes = {m for (_, _, m) in busy.index}
        rows = df[(df["subject"] == subject) & minute.isin(busy_minutes)]
        not_found = rows["respcode"].eq(404).mean()
        confidence = ramp(int(busy.max()), 60, 0.5, 200, 0.8) + (0.1 if not_found >= 0.5 else 0)
        host = rows["host"].mode().iloc[0]
        findings.append(finding(
            rows, detector="burst", family=RATE, confidence=round(confidence, 3),
            severity=HIGH if not_found >= 0.5 else MEDIUM,
            title="Scanning: bursts of requests, mostly 404" if not_found >= 0.5
            else "Unusual burst of requests",
            explanation=(
                f"{subject} made {len(rows)} requests in {len(busy_minutes)} minute(s) "
                f"(peak {int(busy.max())}/min vs a typical {typical:.0f}/min), mostly to {host}; "
                f"{not_found:.0%} returned 404 Not Found."
            ),
            evidence={"requests": len(rows), "peak_per_minute": int(busy.max()),
                      "typical_per_minute": float(typical),
                      "not_found_share": round(float(not_found), 3), "host": host},
        ))  # fmt: skip
    return findings


# --- off-hours activity ------------------------------------------------------------------


def off_hours(df: pd.DataFrame) -> list[Finding]:
    """Interactive browsing well outside this user's workday, learned from the file.

    The workday is the biggest cluster of busy hours (10+ requests), where hours up to 3 apart
    still belong together (a quiet lunch doesn't split the day), widened by 2 hours each side
    so early starts and late finishes are fine. An isolated 3 a.m. or 11 p.m. session forms
    its own small cluster, so it can't make itself look "usual".

    Only real browsers count (user agents with a browser engine, like AppleWebKit or Gecko):
    the security agent, update checks and IT scripts run at night by design, and malware
    check-ins are beaconing's job. Low severity on its own: people do work late.
    """
    browsing = df[df["useragent"].fillna("").str.contains("AppleWebKit|Gecko/", regex=True)]
    hour = browsing["ts"].dt.floor("h")
    per_hour = browsing.groupby(["subject_type", "subject", hour]).size()
    findings = []
    for (_, subject), hours in per_hour.groupby(level=[0, 1]):
        by_hour_of_day = hours.groupby(lambda key: key[2].hour).sum()
        busy = by_hour_of_day[by_hour_of_day >= 10]
        if len(busy) < 3:
            continue  # not enough to know this user's routine
        workday = _biggest_cluster(busy)
        start, end = workday[0] - WORKDAY_SLACK, workday[-1] + WORKDAY_SLACK
        for (_, _, odd_hour), count in hours.items():
            if start <= odd_hour.hour <= end or count < 10:
                continue
            rows = browsing[(browsing["subject"] == subject) & (hour == odd_hour)]
            findings.append(finding(
                rows, detector="off_hours", family=TIMING,
                confidence=round(ramp(count, 10, 0.45, 60, 0.6), 3), severity=LOW,
                title="Browsing outside usual hours",
                explanation=(
                    f"{subject} made {count} browser requests in the {clock(odd_hour)} hour; "
                    f"their workday in this file is {workday[0]:02d}:00–{workday[-1] + 1:02d}:00."
                ),
                evidence={"requests": int(count), "workday": [workday[0], workday[-1] + 1]},
            ))  # fmt: skip
    return findings


WORKDAY_SLACK = 2  # hours either side of the workday that still count as normal


def _biggest_cluster(busy: pd.Series) -> list[int]:
    """Busy hours of the day → the cluster with the most requests, allowing gaps of up to
    3 hours. E.g. {8: 40, 9: 50, 10: 45, 14: 40, 15: 38, 23: 15} → [8, 9, 10, 14, 15]."""
    clusters: list[list[int]] = []
    for h in sorted(busy.index):
        if clusters and h - clusters[-1][-1] <= MAX_GAP_HOURS:
            clusters[-1].append(h)
        else:
            clusters.append([h])
    return max(clusters, key=lambda cluster: busy[cluster].sum())


MAX_GAP_HOURS = 3


# --- new device or location --------------------------------------------------------------


def new_device(df: pd.DataFrame) -> list[Finding]:
    """A user's login appearing from a device that accounts for a minority of their activity,
    alongside their usual one: often stolen credentials used elsewhere."""
    findings = []
    for (_, subject), rows in df.groupby(["subject_type", "subject"]):
        devices = rows["devicehostname"].value_counts()
        if len(devices) < 2:
            continue
        usual = devices.index[0]
        usual_rows = rows[rows["devicehostname"] == usual]
        for device in devices.index[1:]:
            odd = rows[rows["devicehostname"] == device]
            differences = [
                name for name, column in (("IP", "cltip"), ("browser", "useragent"),
                                          ("location", "location"))
                if not set(odd[column].dropna()) & set(usual_rows[column].dropna())
            ]  # fmt: skip
            # Each difference (new IP, browser, place) adds weight, but alone this stays
            # Medium: people do get new laptops. Off-hours or other signals push it to High.
            confidence = 0.5 + 0.08 * len(differences)
            findings.append(finding(
                odd, detector="new_device", family=IDENTITY, confidence=round(confidence, 3),
                severity=MEDIUM, title="Account used from a new device",
                explanation=(
                    f"{subject} was used from {device} ({len(odd)} requests, "
                    f"{clock(odd['ts'].min())}–{clock(odd['ts'].max())}) besides their usual "
                    f"{usual}; different {', '.join(differences) or 'nothing else'}."
                ),
                evidence={"device": device, "usual_device": usual, "requests": len(odd),
                          "differences": differences},
            ))  # fmt: skip
    return findings


# --- random-looking domains --------------------------------------------------------------


def entropy(text: str) -> float:
    """How random a string looks, in bits per character: "mail" ≈ 1.5, "x9fq2kd7wz" ≈ 3.3."""
    counts = Counter(text)
    return -sum(n / len(text) * math.log2(n / len(text)) for n in counts.values())


def random_domains(df: pd.DataFrame) -> list[Finding]:
    """Many never-seen, random-looking host names tried within minutes, most of them failing:
    malware generating domain names (DGA) to find its command server.

    Random-looking names alone aren't enough (some CDNs have them), so it takes 10+ distinct
    names that only this user contacts, first tried within 10 minutes of each other, mostly
    unanswered. It works per name, not per request: once the malware finds its server it may
    call it a thousand times, and those successful calls mustn't hide the failed search.
    """
    users_per_host = df.groupby("host")["subject"].nunique()
    only_one_user = set(users_per_host[users_per_host == 1].index)
    label = df["host"].fillna("").str.split(".").str[0]
    odd = df[
        df["host"].isin(only_one_user) & (label.str.len() >= 8) & (label.map(entropy) >= 2.5)
    ].assign(failed=lambda d: d["serverip"].isna() | (d["respcode"] >= 500))
    names = (
        odd.groupby(["subject_type", "subject", "host"])
        .agg(first_tried=("ts", "min"), never_answered=("failed", "all"))
        .reset_index()
        .sort_values("first_tried")
    )
    findings = []
    for _, tried in names.groupby(["subject_type", "subject"]):
        search_id = (tried["first_tried"].diff() > timedelta(minutes=10)).cumsum()
        for _, search in tried.groupby(search_id):
            failed_share = search["never_answered"].mean()
            if len(search) < 10 or failed_share < 0.5:
                continue
            end = search["first_tried"].max() + timedelta(minutes=1)
            rows = odd[odd["host"].isin(search["host"]) & (odd["ts"] <= end)]
            answered = sorted(search.loc[~search["never_answered"], "host"])
            minutes = (
                search["first_tried"].max() - search["first_tried"].min()
            ).total_seconds() / 60
            findings.append(finding(
                rows, detector="random_domains", family=DESTINATION,
                confidence=round(ramp(len(search), 10, 0.6, 50, 0.9), 3), severity=HIGH,
                title="Many random-looking domains tried (possible malware DGA)",
                explanation=(
                    f"{rows.iloc[0]['subject']} tried {len(search)} never-seen, random-looking "
                    f"domains in {minutes:.0f} minutes ({failed_share:.0%} never answered); "
                    f"{len(answered)} answered: {', '.join(answered[:3])}."
                ),
                evidence={"domains": len(search), "failed_share": round(float(failed_share), 3),
                          "answered": answered},
            ))  # fmt: skip
    return findings


STATISTICS = [beaconing, exfil_volume, burst, off_hours, new_device, random_domains]
