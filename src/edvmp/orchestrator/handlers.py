from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from edvmp.shared.models import JobCompletedEvent, JobStatus, ObjectCreatedEvent
from edvmp.shared.queue import QueueMessage
from edvmp.shared.store import LocalSqliteStore


def job_id_from_s3_key(key: str) -> str | None:
    parts = key.split("/")
    if len(parts) >= 3 and parts[0] == "uploads":
        return parts[1]
    return None


@dataclass(frozen=True)
class OrchestratorDecision:
    action: str
    job_id: str
    idempotency_key: str


class QueueWriter(Protocol):
    def enqueue(self, message: QueueMessage) -> None: ...


def handle_object_created(
    *,
    store: LocalSqliteStore,
    queue: QueueWriter,
    event: ObjectCreatedEvent,
) -> OrchestratorDecision:
    job_id = job_id_from_s3_key(event.key) or f"job-{int(time.time() * 1000)}"
    idempotency_key = f"s3://{event.bucket}/{event.key}"

    claimed = store.try_claim_idempotency(idempotency_key=idempotency_key, job_id=job_id)
    if not claimed:
        return OrchestratorDecision(action="skip_duplicate", job_id=job_id, idempotency_key=idempotency_key)

    store.create_job_if_missing(job_id=job_id, bucket=event.bucket, key=event.key, status=JobStatus.submitted)
    store.update_job(job_id=job_id, status=JobStatus.processing)

    queue.enqueue(
        QueueMessage(
            message_type="ProcessVideo",
            payload={"job_id": job_id, "bucket": event.bucket, "key": event.key},
        )
    )
    return OrchestratorDecision(action="enqueued", job_id=job_id, idempotency_key=idempotency_key)


def handle_job_completed(*, store: LocalSqliteStore, event: JobCompletedEvent) -> None:
    store.update_job(
        job_id=event.job_id,
        status=event.status,
        error_code=event.error_code,
        error_message=event.error_message,
    )
