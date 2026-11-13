"""Response shapes (Pydantic). Each model lists exactly which fields leave the API, so adding a
column to a table never leaks it by accident. `model_dump(mode="json")` turns UUIDs and
datetimes into JSON strings (ISO 8601, UTC)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress


class UploadSummary(BaseModel):
    """One row of the uploads list."""

    model_config = ConfigDict(from_attributes=True)  # can be built straight from an Upload

    id: UUID
    filename: str
    size_bytes: int
    status: str
    line_count: int | None
    parsed_count: int | None
    error_count: int | None
    time_start: datetime | None
    time_end: datetime | None
    created_at: datetime
    is_sample: bool = False  # the shared sample analysis (read-only for everyone)


class UploadDetail(UploadSummary):
    """One upload with everything the Overview needs."""

    parse_errors: list[dict[str, Any]] | None
    stats: dict[str, Any] | None
    parser_version: str | None
    detector_version: str | None
    processed_at: datetime | None


# --- query parameters --------------------------------------------------------------------


class EntryQuery(BaseModel):
    """Filters and paging for GET /uploads/<id>/entries. Unknown parameters are rejected so a
    typo (e.g. `?usr=`) gives a clear 400 instead of silently returning everything."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    page: int = Field(1, ge=1)
    page_size: int = Field(100, ge=1, le=200)
    from_: datetime | None = Field(None, alias="from")  # `from` is a Python keyword
    to: datetime | None = None  # exclusive
    user: str | None = None  # exact login
    action: str | None = None  # Allowed | Blocked
    host: str | None = None  # exact host
    q: str | None = Field(None, max_length=200)  # substring of host or URL
    flagged: bool | None = None  # only rows some anomaly covers
    min_confidence: float | None = Field(None, ge=0, le=1)
    incident_id: int | None = None
    anomaly_id: int | None = None


class AnomalyQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detector: str | None = None  # rule | statistical | ml
    min_confidence: float | None = Field(None, ge=0, le=1)


# --- entries, anomalies, incidents -------------------------------------------------------


class EntrySummary(BaseModel):
    """One row of the log table: the columns shown, not all ~40."""

    model_config = ConfigDict(from_attributes=True)

    line_no: int
    ts: datetime
    login: str | None
    dept: str | None
    devicehostname: str | None
    cltip: IPvAnyAddress | None
    host: str | None
    url: str | None
    reqmethod: str | None
    respcode: int | None
    action: str | None
    urlsubcat: str | None
    reqsize: int | None
    respsize: int | None
    riskscore: int | None
    threatname: str | None
    anomaly_confidence: float | None
    max_severity: int | None


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int | None
    detector: str
    kind: str
    subject_type: str
    subject: str
    title: str
    explanation: str
    confidence: float
    severity: int
    start_ts: datetime
    end_ts: datetime
    entry_count: int
    evidence: dict[str, Any] | None


class EntryDetail(EntrySummary):
    """Every stored field of one entry, plus the anomalies it belongs to ("why flagged")."""

    record_id: int | None
    tz: str | None
    location: str | None
    serverip: IPvAnyAddress | None
    dstip_country: str | None
    proto: str | None
    useragent: str | None
    refererhost: str | None
    contenttype: str | None
    reason: str | None
    rulelabel: str | None
    ruletype: str | None
    urlsupercat: str | None
    urlclass: str | None
    appname: str | None
    appclass: str | None
    threatseverity: str | None
    malwarecategory: str | None
    malwareclass: str | None
    filename: str | None
    filetype: str | None
    upload_filename: str | None
    sha256: str | None
    anomalies: list[AnomalyOut] = []


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_type: str
    subject: str
    title: str
    summary: str | None
    severity: int
    confidence: float
    start_ts: datetime
    end_ts: datetime
    anomalies: list[AnomalyOut] = []
