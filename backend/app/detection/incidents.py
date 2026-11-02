"""Group findings into incidents: same subject, each finding starting within 30 minutes of the
incident so far. Like a chat app threading notifications from the same person."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.detection.findings import Finding, combine

GROUPING_GAP = timedelta(minutes=30)


@dataclass
class IncidentDraft:
    subject_type: str
    subject: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def start_ts(self) -> datetime:
        return min(f.start_ts for f in self.findings)

    @property
    def end_ts(self) -> datetime:
        return max(f.end_ts for f in self.findings)

    @property
    def severity(self) -> int:
        return max(f.severity for f in self.findings)

    @property
    def confidence(self) -> float:
        return combine(self.findings)

    @property
    def lead(self) -> Finding:
        """The most serious finding (then the most confident) names the incident."""
        return max(self.findings, key=lambda f: (f.severity, f.confidence))

    @property
    def title(self) -> str:
        return self.lead.title

    @property
    def summary(self) -> str:
        ordered = sorted(self.findings, key=lambda f: (-f.severity, -f.confidence))
        return " ".join(f.explanation for f in ordered)


def group_incidents(findings: list[Finding]) -> list[IncidentDraft]:
    incidents: list[IncidentDraft] = []
    for item in sorted(findings, key=lambda f: (f.subject_type, f.subject, f.start_ts)):
        current = incidents[-1] if incidents else None
        same_subject = current is not None and (current.subject_type, current.subject) == (
            item.subject_type,
            item.subject,
        )
        if same_subject and item.start_ts <= current.end_ts + GROUPING_GAP:
            current.findings.append(item)
        else:
            incidents.append(IncidentDraft(item.subject_type, item.subject, [item]))
    return incidents
