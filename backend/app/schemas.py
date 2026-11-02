"""Response shapes (Pydantic). Each model lists exactly which fields leave the API, so adding a
column to a table never leaks it by accident. `model_dump(mode="json")` turns UUIDs and
datetimes into JSON strings (ISO 8601, UTC)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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


class UploadDetail(UploadSummary):
    """One upload with everything the Overview needs."""

    parse_errors: list[dict[str, Any]] | None
    stats: dict[str, Any] | None
    parser_version: str | None
    detector_version: str | None
    processed_at: datetime | None
