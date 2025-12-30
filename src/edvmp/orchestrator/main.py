from __future__ import annotations

import logging
import os
import socket
import time

import redis

from edvmp.orchestrator.handlers import handle_job_completed, handle_object_created
from edvmp.shared.config import Settings
from edvmp.shared.events import RedisEventStream
from edvmp.shared.logging import configure_logging
from edvmp.shared.models import JobCompletedEvent, ObjectCreatedEvent
from edvmp.shared.queue import RedisQueue
from edvmp.shared.store import LocalSqliteStore

logger = logging.getLogger("edvmp.orchestrator")


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)

    consumer_name = os.getenv("HOSTNAME") or socket.gethostname()
    group_name = "orchestrator"

    r = redis.Redis.from_url(settings.redis_url)
    stream = RedisEventStream(r, settings.redis_events_stream)
    stream.ensure_consumer_group(group_name)

    store = LocalSqliteStore(settings.db_path)
    queue = RedisQueue(r, settings.redis_jobs_queue)

    logger.info(
        "orchestrator_started",
        extra={
            "env": settings.app_env,
            "stream": settings.redis_events_stream,
            "queue": settings.redis_jobs_queue,
            "db_path": settings.db_path,
            "consumer": consumer_name,
        },
    )

    while True:
        try:
            messages = stream.read_group(group_name=group_name, consumer_name=consumer_name)
            if not messages:
                continue
            for message_id, event in messages:
                try:
                    event_type = event.get("event_type")
                    if event_type == "ObjectCreated":
                        decision = handle_object_created(
                            store=store, queue=queue, event=ObjectCreatedEvent.model_validate(event)
                        )
                        logger.info(
                            "object_created_handled",
                            extra={
                                "action": decision.action,
                                "job_id": decision.job_id,
                                "idempotency_key": decision.idempotency_key,
                            },
                        )

                    elif event_type == "JobCompleted":
                        completed = JobCompletedEvent.model_validate(event)
                        handle_job_completed(store=store, event=completed)
                        logger.info("job_status_updated", extra=completed.model_dump(mode="json"))
                    else:
                        logger.warning("unknown_event_type", extra={"event_type": event_type, "event": event})

                    stream.ack(group_name, message_id)
                except Exception:
                    logger.exception(
                        "orchestrator_event_failed",
                        extra={"message_id": message_id, "event": event},
                    )
        except Exception:
            logger.exception("orchestrator_loop_failed")
            time.sleep(1)


if __name__ == "__main__":
    main()
