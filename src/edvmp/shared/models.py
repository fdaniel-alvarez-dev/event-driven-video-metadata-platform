from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    awaiting_upload = "AWAITING_UPLOAD"
    submitted = "SUBMITTED"
    processing = "PROCESSING"
    succeeded = "SUCCEEDED"
    failed = "FAILED"


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    s3_bucket: str
    s3_key: str
    error_code: str | None = None
    error_message: str | None = None


class JobResult(BaseModel):
    job_id: str
    metadata: dict[str, Any]
    summary: str


class ObjectCreatedEvent(BaseModel):
    event_type: str = Field(default="ObjectCreated", frozen=True)
    bucket: str
    key: str
    size: int | None = None
    etag: str | None = None
    event_time: datetime = Field(default_factory=lambda: datetime.now(UTC))


class JobCompletedEvent(BaseModel):
    event_type: str = Field(default="JobCompleted", frozen=True)
    job_id: str
    status: JobStatus
    event_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error_code: str | None = None
    error_message: str | None = None
