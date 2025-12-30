from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from prometheus_client import start_http_server
from tenacity import retry, stop_after_attempt, wait_exponential

from edvmp.shared.aws_sqs_queue import SqsDlq, SqsQueue
from edvmp.shared.backends import get_dlq, get_queue, get_store
from edvmp.shared.bedrock import BedrockClient
from edvmp.shared.config import Settings
from edvmp.shared.eventbridge import put_event
from edvmp.shared.logging import configure_logging
from edvmp.shared.metrics import worker_job_duration, worker_jobs_total
from edvmp.shared.models import JobStatus
from edvmp.shared.queue import QueueMessage, RedisDlq, RedisQueue
from edvmp.shared.s3 import ensure_bucket_exists, s3_client
from edvmp.worker.classifier import classify_failure
from edvmp.worker.ffprobe import MediaProbeError, ffprobe

logger = logging.getLogger("edvmp.worker")


@retry(wait=wait_exponential(multiplier=1, min=0.5, max=10), stop=stop_after_attempt(3))
def _download(s3, bucket: str, key: str, dest: Path) -> None:
    s3.download_file(bucket, key, str(dest))


def _post_job_completed(eventbus_url: str, payload: dict[str, Any]) -> None:
    with httpx.Client(timeout=5) as client:
        client.post(f"{eventbus_url}/events/job-completed", json=payload).raise_for_status()


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)

    start_http_server(settings.worker_metrics_port)

    queue = get_queue(settings)
    dlq = get_dlq(settings)

    store = get_store(settings)

    s3 = s3_client(
        region_name=settings.s3_region,
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    ensure_bucket_exists(s3, settings.s3_bucket)

    bedrock = BedrockClient(
        mode=settings.bedrock_mode,
        model_id=settings.bedrock_model_id,
        region_name=settings.s3_region,
    )

    eventbus_url = settings.eventbus_url or os.environ.get("EVENTBUS_URL") or ""

    logger.info(
        "worker_started",
        extra={
            "env": settings.app_env,
            "queue": settings.redis_jobs_queue,
            "dlq": settings.sqs_dlq_url if settings.queue_backend == "sqs" else settings.redis_dlq,
            "metrics_port": settings.worker_metrics_port,
            "bedrock_mode": settings.bedrock_mode,
        },
    )

    while True:
        msg: QueueMessage | None = None
        ack: Callable[[], None]
        if isinstance(queue, RedisQueue):
            msg = queue.dequeue_blocking(timeout_s=5)
            def ack_noop() -> None:
                return None

            ack = ack_noop
        elif isinstance(queue, SqsQueue):
            received = queue.receive(wait_time_s=10, max_messages=1)
            if not received:
                continue
            msg = received[0].message
            receipt_handle = received[0].receipt_handle

            def ack_sqs(receipt_handle: str = receipt_handle) -> None:
                queue.delete(receipt_handle)

            ack = ack_sqs
        else:
            raise RuntimeError("Unsupported queue backend")

        if msg is None:
            continue
        if msg.message_type != "ProcessVideo":
            logger.warning("unknown_message_type", extra={"message_type": msg.message_type})
            continue

        job_id = str(msg.payload["job_id"])
        bucket = str(msg.payload["bucket"])
        key = str(msg.payload["key"])

        store.update_job(job_id=job_id, status=JobStatus.processing)

        start = time.time()
        last_error: Exception | None = None
        for attempt in range(settings.worker_max_attempts):
            try:
                with tempfile.TemporaryDirectory() as td:
                    path = Path(td) / "input"
                    _download(s3, bucket=bucket, key=key, dest=path)
                    metadata = ffprobe(path)
                    summary = bedrock.summarize(metadata=metadata)
                    store.store_result(job_id=job_id, metadata=metadata, summary=summary)
                store.update_job(job_id=job_id, status=JobStatus.succeeded)

                worker_jobs_total.labels(status="succeeded").inc()
                duration = time.time() - start
                worker_job_duration.observe(duration)

                if eventbus_url:
                    _post_job_completed(
                        eventbus_url,
                        {
                            "event_type": "JobCompleted",
                            "job_id": job_id,
                            "status": "SUCCEEDED",
                        },
                    )
                if not eventbus_url and settings.app_env == "aws":
                    put_event(
                        region_name=settings.s3_region,
                        bus_name=settings.eventbridge_bus_name,
                        source="edvmp.worker",
                        detail_type="JobCompleted",
                        detail=json.dumps({"job_id": job_id, "status": "SUCCEEDED"}),
                    )
                logger.info("job_succeeded", extra={"job_id": job_id, "duration_s": duration})
                ack()
                last_error = None
                break
            except Exception as e:
                last_error = e
                sleep_s = settings.worker_backoff_seconds * (2**attempt)
                logger.warning(
                    "job_attempt_failed",
                    extra={"job_id": job_id, "attempt": attempt + 1, "sleep_s": sleep_s, "error": str(e)},
                )
                time.sleep(sleep_s)

        if last_error is not None:
            _handle_failure(settings, store, dlq, eventbus_url, job_id, bucket, key, last_error)
            ack()


def _handle_failure(
    settings: Settings,
    store,
    dlq: RedisDlq | SqsDlq,
    eventbus_url: str,
    job_id: str,
    bucket: str,
    key: str,
    error: Exception,
) -> None:
    classification = classify_failure(error, context={"job_id": job_id, "bucket": bucket, "key": key})
    error_code = classification.category
    error_message = str(error)

    worker_jobs_total.labels(status="failed").inc()

    store.update_job(job_id=job_id, status=JobStatus.failed, error_code=error_code, error_message=error_message)

    dlq_payload = {
        "job_id": job_id,
        "bucket": bucket,
        "key": key,
        "error_code": error_code,
        "error_message": error_message,
        "recommendation": classification.recommendation,
    }
    if isinstance(dlq, RedisDlq):
        dlq.push(dlq_payload)
    elif isinstance(dlq, SqsDlq):
        dlq.enqueue(QueueMessage(message_type="DLQ", payload=dlq_payload))
    else:
        raise RuntimeError("Unsupported DLQ backend")
    try:
        if eventbus_url:
            _post_job_completed(
                eventbus_url,
                {
                    "event_type": "JobCompleted",
                    "job_id": job_id,
                    "status": "FAILED",
                    "error_code": error_code,
                    "error_message": error_message,
                },
            )
        elif settings.app_env == "aws":
            put_event(
                region_name=settings.s3_region,
                bus_name=settings.eventbridge_bus_name,
                source="edvmp.worker",
                detail_type="JobCompleted",
                detail=json.dumps(
                    {
                        "job_id": job_id,
                        "status": "FAILED",
                        "error_code": error_code,
                        "error_message": error_message,
                    }
                ),
            )
    except Exception:
        logger.exception("failed_to_publish_job_completed", extra={"job_id": job_id})

    if isinstance(error, MediaProbeError):
        logger.warning("job_failed_media", extra={"job_id": job_id, "error": error_message})
    else:
        logger.exception("job_failed", extra={"job_id": job_id, "error_code": error_code, "error": error_message})


if __name__ == "__main__":
    main()
