"""Read queries for one upload's entries, anomalies and incidents. Every function takes an
upload the caller already checked with owned_upload_or_404, and filters by its id."""

import uuid
from collections import defaultdict

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import Anomaly, AnomalyEntry, Incident, LogEntry
from app.schemas import EntryQuery


def entries_page(
    session: Session, upload_id: uuid.UUID, query: EntryQuery
) -> tuple[list[LogEntry], int]:
    """One page of entries in time order, plus how many entries match in total."""
    filtered = _filter_entries(select(LogEntry), upload_id, query)
    total = session.scalar(select(func.count()).select_from(filtered.subquery()))
    page = session.scalars(
        filtered.order_by(LogEntry.ts, LogEntry.line_no)
        .offset((query.page - 1) * query.page_size)  # page 3 of 100s → skip the first 200
        .limit(query.page_size)
    ).all()
    return list(page), total


def _filter_entries(stmt: Select, upload_id: uuid.UUID, query: EntryQuery) -> Select:
    """Add a WHERE condition for each filter that was given."""
    stmt = stmt.where(LogEntry.upload_id == upload_id)
    if query.from_:
        stmt = stmt.where(LogEntry.ts >= query.from_)
    if query.to:
        stmt = stmt.where(LogEntry.ts < query.to)
    if query.user:
        stmt = stmt.where(LogEntry.login == query.user)
    if query.action:
        stmt = stmt.where(LogEntry.action == query.action)
    if query.host:
        stmt = stmt.where(LogEntry.host == query.host)
    if query.q:
        pattern = f"%{_escape_like(query.q)}%"
        stmt = stmt.where(
            or_(LogEntry.host.ilike(pattern, escape="\\"), LogEntry.url.ilike(pattern, escape="\\"))
        )
    if query.flagged is not None:
        flagged = LogEntry.anomaly_confidence.is_not(None)
        stmt = stmt.where(flagged if query.flagged else ~flagged)
    if query.min_confidence is not None:
        stmt = stmt.where(LogEntry.anomaly_confidence >= query.min_confidence)
    if query.anomaly_id is not None or query.incident_id is not None:
        linked = select(AnomalyEntry.line_no).where(AnomalyEntry.upload_id == upload_id)
        if query.anomaly_id is not None:
            linked = linked.where(AnomalyEntry.anomaly_id == query.anomaly_id)
        if query.incident_id is not None:
            linked = linked.join(Anomaly, Anomaly.id == AnomalyEntry.anomaly_id).where(
                Anomaly.incident_id == query.incident_id
            )
        stmt = stmt.where(LogEntry.line_no.in_(linked))
    return stmt


def _escape_like(text: str) -> str:
    """User text inside a LIKE pattern: % and _ are wildcards, so escape them to match literally
    (searching for "%" must not match every row)."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def entry_with_anomalies(
    session: Session, upload_id: uuid.UUID, line_no: int
) -> tuple[LogEntry | None, list[Anomaly]]:
    entry = session.get(LogEntry, (upload_id, line_no))
    if entry is None:
        return None, []
    anomalies = session.scalars(
        select(Anomaly)
        .join(AnomalyEntry, AnomalyEntry.anomaly_id == Anomaly.id)
        .where(AnomalyEntry.upload_id == upload_id, AnomalyEntry.line_no == line_no)
        .order_by(Anomaly.confidence.desc(), Anomaly.id)
    ).all()
    return entry, list(anomalies)


def anomalies_for(
    session: Session, upload_id: uuid.UUID, *, detector: str | None, min_confidence: float | None
) -> list[Anomaly]:
    stmt = select(Anomaly).where(Anomaly.upload_id == upload_id)
    if detector:
        stmt = stmt.where(Anomaly.detector == detector)
    if min_confidence is not None:
        stmt = stmt.where(Anomaly.confidence >= min_confidence)
    return list(session.scalars(stmt.order_by(Anomaly.confidence.desc(), Anomaly.id)))


def incidents_with_anomalies(
    session: Session, upload_id: uuid.UUID
) -> list[tuple[Incident, list[Anomaly]]]:
    """Most severe first (then most confident, then earliest), each with its anomalies.
    Two queries in total, not one per incident."""
    incidents = session.scalars(
        select(Incident)
        .where(Incident.upload_id == upload_id)
        .order_by(Incident.severity.desc(), Incident.confidence.desc(), Incident.start_ts)
    ).all()
    by_incident: dict[int, list[Anomaly]] = defaultdict(list)
    for anomaly in session.scalars(
        select(Anomaly)
        .where(Anomaly.upload_id == upload_id, Anomaly.incident_id.is_not(None))
        .order_by(Anomaly.confidence.desc(), Anomaly.id)
    ):
        by_incident[anomaly.incident_id].append(anomaly)
    return [(incident, by_incident[incident.id]) for incident in incidents]
