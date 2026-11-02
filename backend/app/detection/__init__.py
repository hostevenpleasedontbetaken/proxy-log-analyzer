"""Threat detection. Pure Python on the upload's DataFrame: no database, no network.

rows ─┬─ rules (layer 1)        "Zscaler already says it's bad" + near-certain patterns
      ├─ statistics (layer 2)   unusual compared with this user's normal
      └─ Isolation Forest (3)   the odd one out across many numbers at once
         │
         ├─► findings   (explanation, confidence, severity, which rows)
         ├─► incidents  (findings about the same subject within 30 minutes)
         └─► per-entry score: combined confidence + worst severity, for highlighting
"""

from dataclasses import dataclass

import pandas as pd

from app.detection.findings import NOISE_FLOOR, Finding, combine
from app.detection.incidents import IncidentDraft, group_incidents
from app.detection.ml import MACHINE_LEARNING, MIN_USER_HOURS, active_user_hours
from app.detection.rules import RULES
from app.detection.statistics import STATISTICS

DETECTOR_VERSION = "1"  # stored on each upload; bump when detection logic changes
DETECTORS = [*RULES, *STATISTICS, *MACHINE_LEARNING]


@dataclass
class Detection:
    findings: list[Finding]
    incidents: list[IncidentDraft]
    entry_scores: dict[int, tuple[float, int]]  # line_no → (combined confidence, worst severity)
    ml_user_hours: int = 0  # active user-hours available to Isolation Forest

    @property
    def ml_ran(self) -> bool:
        return self.ml_user_hours >= MIN_USER_HOURS


def detect(df: pd.DataFrame) -> Detection:
    df = with_subject(df)
    findings = [
        finding
        for detector in DETECTORS
        for finding in detector(df)
        if finding.confidence >= NOISE_FLOOR
    ]
    return Detection(
        findings,
        group_incidents(findings),
        score_entries(findings),
        ml_user_hours=len(active_user_hours(df)),
    )


def with_subject(df: pd.DataFrame) -> pd.DataFrame:
    """Who each row is about: the user's login, or the client IP when there's no login."""
    has_login = df["login"].notna()
    return df.assign(
        subject_type=has_login.map({True: "user", False: "ip"}),
        subject=df["login"].where(has_login, df["cltip"].astype(str)),
    )


def score_entries(findings: list[Finding]) -> dict[int, tuple[float, int]]:
    """For each flagged entry: the combined confidence of every finding that covers it, and
    the worst severity among them. Copied onto log_entries for row highlighting."""
    covering: dict[int, list[Finding]] = {}
    for finding in findings:
        for line_no in finding.line_nos:
            covering.setdefault(line_no, []).append(finding)
    return {
        line_no: (combine(items), max(f.severity for f in items))
        for line_no, items in covering.items()
    }


__all__ = ["DETECTOR_VERSION", "Detection", "Finding", "IncidentDraft", "detect"]
