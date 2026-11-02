"""Layer 1, rules: things Zscaler itself already marked as bad, plus simple, near-certain
patterns. Deterministic and easy to explain; each returns a list of Findings.

Every function receives the upload's DataFrame with two extra columns added by the runner:
`subject_type` ("user", or "ip" when there's no login) and `subject`.
"""

from datetime import timedelta

import pandas as pd

from app.detection.findings import (
    CRITICAL,
    HIGH,
    KNOWN_BAD,
    LOW,
    MEDIUM,
    POLICY,
    TOOLING,
    Finding,
    ramp,
)

RULE = "rule"
SEVERITY_LABELS = {"critical": CRITICAL, "high": HIGH, "medium": MEDIUM, "low": LOW}
# URL categories that are risky to visit at all: (confidence, severity, title)
RISKY_CATEGORIES = {
    "Phishing": (0.85, HIGH, "Visited a phishing site"),
    "Malware Sites": (0.85, HIGH, "Visited a known malware site"),
    "Spyware/Adware": (0.7, MEDIUM, "Visited a spyware/adware site"),
    "Anonymizer": (None, MEDIUM, "Tried to reach anonymizer / VPN sites"),  # scales with count
}
SCRIPT_CLIENTS = (
    "curl",
    "python-requests",
    "wget",
    "go-http-client",
    "python-urllib",
    "powershell",
)
PHISHING_POST_WINDOW = timedelta(minutes=5)
BLOCK_BURST_GAP = timedelta(minutes=10)
BLOCK_BURST_MIN = 10


def finding(rows: pd.DataFrame, **fields) -> Finding:
    """Build a Finding about `rows`, filling in subject, time span and line numbers."""
    first = rows.iloc[0]
    return Finding(
        layer=RULE,
        subject_type=first["subject_type"],
        subject=first["subject"],
        line_nos=rows["line_no"].astype(int).tolist(),
        start_ts=rows["ts"].min().to_pydatetime(),
        end_ts=rows["ts"].max().to_pydatetime(),
        **fields,
    )


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def known_threat(df: pd.DataFrame) -> list[Finding]:
    """Zscaler named a threat (virus, trojan, …) in the traffic."""
    hits = df[df["threatname"].notna() | df["malwarecategory"].notna()]
    findings = []
    for (_, _, threat), rows in hits.groupby(
        ["subject_type", "subject", hits["threatname"].fillna("unnamed threat")]
    ):
        label = (
            str(rows["threatseverity"].dropna().iloc[0])
            if rows["threatseverity"].notna().any()
            else ""
        )
        severity = SEVERITY_LABELS.get(label.lower(), HIGH)
        blocked = int(rows["action"].eq("Blocked").sum())
        outcome = "all blocked" if blocked == len(rows) else f"{len(rows) - blocked} allowed"
        hosts = ", ".join(sorted(rows["host"].dropna().unique()))
        files = ", ".join(sorted(rows["filename"].dropna().unique()))
        findings.append(finding(
            rows, detector="known_threat", family=KNOWN_BAD, confidence=0.95, severity=severity,
            title=f"Known threat: {threat}",
            explanation=(
                f"Zscaler identified {threat} ({label or 'severity unknown'}) in "
                f"{plural(len(rows), 'request')} from {rows.iloc[0]['subject']} to {hosts}"
                f"{f' ({files})' if files else ''}; {outcome}."
            ),
            evidence={"threat": threat, "severity_label": label, "requests": len(rows),
                      "blocked": blocked, "hosts": hosts, "files": files},
        ))  # fmt: skip
    return findings


def high_risk_score(df: pd.DataFrame) -> list[Finding]:
    """Zscaler's page risk score (0-100) of 75 or more. Confidence rises with the score."""
    risky = df[df["riskscore"] >= 75]
    findings = []
    for (_, _, host), rows in risky.groupby(["subject_type", "subject", "host"]):
        score = int(rows["riskscore"].max())
        findings.append(finding(
            rows, detector="high_risk_score", family=KNOWN_BAD,
            confidence=round(ramp(score, 75, 0.5, 100, 0.9), 3),
            severity=HIGH if score >= 90 else MEDIUM,
            title="High-risk destination",
            explanation=(
                f"{rows.iloc[0]['subject']} reached {host} {plural(len(rows), 'time')}; "
                f"Zscaler rated it {score}/100 risk."
            ),
            evidence={"host": host, "max_riskscore": score, "requests": len(rows)},
        ))  # fmt: skip
    return findings


def risky_category(df: pd.DataFrame) -> list[Finding]:
    """Visits to URL categories that are risky to visit at all (phishing, malware, anonymizers)."""
    risky = df[df["urlsubcat"].isin(RISKY_CATEGORIES)]
    findings = []
    for (_, _, category), rows in risky.groupby(["subject_type", "subject", "urlsubcat"]):
        confidence, severity, title = RISKY_CATEGORIES[category]
        hosts = sorted(rows["host"].dropna().unique())
        blocked = int(rows["action"].eq("Blocked").sum())
        if confidence is None:  # anonymizers: one attempt is curiosity, many is evasion
            confidence = round(ramp(len(rows), 1, 0.4, 10, 0.7), 3)
        findings.append(finding(
            rows, detector="risky_category", family=KNOWN_BAD, confidence=confidence,
            severity=severity, title=title,
            explanation=(
                f"{rows.iloc[0]['subject']} made {plural(len(rows), 'request')} to "
                f"{plural(len(hosts), 'site')} in the {category} category ({', '.join(hosts)}); "
                f"{blocked} blocked, {len(rows) - blocked} allowed."
            ),
            evidence={"category": category, "hosts": hosts, "requests": len(rows),
                      "blocked": blocked},
        ))  # fmt: skip
    return findings


def phishing_post(df: pd.DataFrame) -> list[Finding]:
    """A phishing page was opened and then a form was sent to the same host within 5 minutes:
    the user probably typed their password into it."""
    phishing = df[df["urlsubcat"].eq("Phishing")].sort_values("ts")
    findings = []
    for (_, _, host), rows in phishing.groupby(["subject_type", "subject", "host"]):
        posts = rows[rows["reqmethod"].eq("POST")]
        gets = rows[rows["reqmethod"].eq("GET")]
        if posts.empty or gets.empty:
            continue
        first_visit, post = gets["ts"].min(), posts.iloc[0]
        delay = post["ts"] - first_visit
        if timedelta(0) <= delay <= PHISHING_POST_WINDOW:
            findings.append(finding(
                rows, detector="phishing_post", family=KNOWN_BAD, confidence=0.9,
                severity=CRITICAL, title="Possible credential submission to a phishing page",
                explanation=(
                    f"{post['subject']} opened {host} (Phishing) and sent a form to it "
                    f"{int(delay.total_seconds())} s later ({int(post['reqsize'])} bytes); "
                    f"credentials were likely entered."
                ),
                evidence={"host": host, "seconds_to_post": int(delay.total_seconds()),
                          "post_bytes": int(post["reqsize"])},
            ))  # fmt: skip
    return findings


def script_user_agent(df: pd.DataFrame) -> list[Finding]:
    """Traffic from command-line tools instead of a browser. Common in legitimate IT work too,
    so it's Low on its own; it mainly strengthens other findings about the same subject."""
    client = df["useragent"].fillna("").str.split("/").str[0].str.lower()
    scripted = df[client.isin(SCRIPT_CLIENTS)]
    findings = []
    for (_, _, agent), rows in scripted.groupby(
        ["subject_type", "subject", scripted["useragent"].str.split("/").str[0]]
    ):
        hosts = rows["host"].nunique()
        findings.append(finding(
            rows, detector="script_user_agent", family=TOOLING, confidence=0.35, severity=LOW,
            title="Scripted client instead of a browser",
            explanation=(
                f"{plural(len(rows), 'request')} from {rows.iloc[0]['subject']} used {agent} "
                f"(to {plural(hosts, 'host')})."
            ),
            evidence={"client": agent, "requests": len(rows), "hosts": hosts},
        ))  # fmt: skip
    return findings


def repeated_blocks(df: pd.DataFrame) -> list[Finding]:
    """10+ blocked requests in a burst (each within 10 minutes of the previous): someone
    keeps trying to get past the web filter."""
    blocked = df[df["action"].eq("Blocked")].sort_values("ts")
    findings = []
    for _, rows in blocked.groupby(["subject_type", "subject"]):
        burst_id = (rows["ts"].diff() > BLOCK_BURST_GAP).cumsum()  # new burst after a long gap
        for _, burst in rows.groupby(burst_id):
            if len(burst) < BLOCK_BURST_MIN:
                continue
            minutes = max(1, round((burst["ts"].max() - burst["ts"].min()).total_seconds() / 60))
            categories = ", ".join(burst["urlsubcat"].dropna().value_counts().index[:3])
            findings.append(finding(
                burst, detector="repeated_blocks", family=POLICY,
                confidence=round(ramp(len(burst), 10, 0.6, 25, 0.85), 3), severity=MEDIUM,
                title="Repeated blocked requests",
                explanation=(
                    f"{burst.iloc[0]['subject']} had {len(burst)} requests blocked in "
                    f"{plural(minutes, 'minute')} ({categories or 'various categories'})."
                ),
                evidence={"blocked": len(burst), "minutes": minutes, "categories": categories},
            ))  # fmt: skip
    return findings


RULES = [known_threat, high_risk_score, risky_category, phishing_post, script_user_agent,
         repeated_blocks]  # fmt: skip
