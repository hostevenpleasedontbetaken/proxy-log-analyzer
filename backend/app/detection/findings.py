"""What every detector returns, and how confidences are combined.

Confidence ("how sure are we this is real?") and severity ("how bad would it be?") are separate,
like a forecast's "70% chance" vs "hurricane".
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Evidence that comes from the same underlying fact is one "family". Within a family we take
# the strongest signal; across families evidence adds up (noisy-OR). That stops, say, two
# volume-based detectors from double-counting the same big upload.
KNOWN_BAD = "known_bad"  # Zscaler itself says it's bad: threats, risky categories, risk scores
POLICY = "policy"  # behaviour against policy: repeated blocks
TOOLING = "tooling"  # how the traffic was made: script user agents
VOLUME = "volume"  # how many bytes went out
RATE = "rate"  # how many requests, how fast
TIMING = "timing"  # when, and how regularly
IDENTITY = "identity"
DESTINATION = "destination"
ML = "ml"

ML_ALONE_CAP = 0.75  # unusual isn't the same as malicious: ML alone can't reach High (0.8)
NOISE_FLOOR = 0.3  # findings below this are dropped

LOW, MEDIUM, HIGH, CRITICAL = 1, 2, 3, 4  # severity scale (stored as numbers so it sorts)


@dataclass
class Finding:
    """One thing a detector noticed, about one subject (usually a user), over some rows."""

    detector: str  # e.g. "known_threat"
    layer: str  # "rule" | "statistical" | "ml"
    family: str  # see the constants above
    subject_type: str  # "user" | "ip"
    subject: str
    title: str  # short, for lists: "Known threat blocked"
    explanation: str  # one plain-English sentence with the actual numbers
    confidence: float  # 0-1
    severity: int  # 1 Low … 4 Critical
    line_nos: list[int]  # the log entries this is about
    start_ts: datetime
    end_ts: datetime
    evidence: dict[str, Any] = field(default_factory=dict)  # the numbers behind it


def combine(findings: list[Finding]) -> float:
    """Combined confidence of several findings: strongest per family, then noisy-OR across
    families, i.e. 1 − (chance every family is a false alarm).

    Example: known_bad 0.9 and volume 0.6 → 1 − (0.1 × 0.4) = 0.96.
    """
    strongest: dict[str, float] = {}
    for finding in findings:
        strongest[finding.family] = max(strongest.get(finding.family, 0.0), finding.confidence)
    if not strongest:
        return 0.0
    all_false_alarms = 1.0
    for confidence in strongest.values():
        all_false_alarms *= 1 - confidence
    combined = 1 - all_false_alarms
    if set(strongest) == {ML}:
        combined = min(combined, ML_ALONE_CAP)
    return round(combined, 4)


def ramp(value: float, low: float, low_conf: float, high: float, high_conf: float) -> float:
    """A simple confidence curve: `low` or less → low_conf, `high` or more → high_conf, and a
    straight line in between. E.g. ramp(score, 75, 0.5, 100, 0.9): risk score 75 → 0.5,
    87.5 → 0.7, 100 → 0.9."""
    if value <= low:
        return low_conf
    if value >= high:
        return high_conf
    return low_conf + (value - low) / (high - low) * (high_conf - low_conf)


def band(confidence: float) -> str:
    """What the UI shows: High ≥ 0.8, Medium ≥ 0.5, Low below."""
    if confidence >= 0.8:
        return "High"
    if confidence >= 0.5:
        return "Medium"
    return "Low"
