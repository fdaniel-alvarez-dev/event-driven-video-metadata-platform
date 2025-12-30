from __future__ import annotations

from pathlib import Path

from edvmp.orchestrator.handlers import handle_job_completed, handle_object_created
from edvmp.shared.models import JobCompletedEvent, JobStatus, ObjectCreatedEvent
from edvmp.shared.queue import QueueMessage
from edvmp.shared.store import LocalSqliteStore


class FakeQueue:
    def __init__(self):
        self.items: list[QueueMessage] = []

    def enqueue(self, message: QueueMessage) -> None:
        self.items.append(message)


def test_object_created_enqueues_once(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    store = LocalSqliteStore(str(db))

    queue = FakeQueue()

    event = ObjectCreatedEvent(bucket="videos", key="uploads/abc/sample.mp4")
    d1 = handle_object_created(store=store, queue=queue, event=event)
    d2 = handle_object_created(store=store, queue=queue, event=event)

    assert d1.action == "enqueued"
    assert d2.action == "skip_duplicate"
    assert len(queue.items) == 1

    job = store.get_job("abc")
    assert job is not None
    assert job.status == JobStatus.processing


def test_job_completed_updates_status(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    store = LocalSqliteStore(str(db))
    store.create_job_if_missing(job_id="j1", bucket="videos", key="uploads/j1/a.mp4", status=JobStatus.processing)

    handle_job_completed(store=store, event=JobCompletedEvent(job_id="j1", status=JobStatus.succeeded))
    job = store.get_job("j1")
    assert job is not None
    assert job.status == JobStatus.succeeded
