from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import unquote_plus

import redis
from fastapi import FastAPI, Request

from edvmp.shared.config import Settings
from edvmp.shared.events import RedisEventStream
from edvmp.shared.http import prometheus_metrics_response
from edvmp.shared.logging import configure_logging
from edvmp.shared.models import JobCompletedEvent, ObjectCreatedEvent

logger = logging.getLogger("edvmp.eventbus")


def _parse_minio_webhook(payload: dict[str, Any]) -> list[ObjectCreatedEvent]:
    records = payload.get("Records") or []
    out: list[ObjectCreatedEvent] = []
    for r in records:
        s3 = r.get("s3", {})
        bucket = (s3.get("bucket") or {}).get("name")
        key = (s3.get("object") or {}).get("key")
        if not bucket or not key:
            continue
        key = unquote_plus(key)
        obj = s3.get("object") or {}
        etag = obj.get("eTag") or obj.get("etag")
        size = obj.get("size")
        out.append(
            ObjectCreatedEvent(
                bucket=bucket,
                key=key,
                etag=etag,
                size=size,
                event_time=datetime.utcnow(),
            )
        )
    return out


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings.log_level)

    r = redis.Redis.from_url(settings.redis_url)
    stream = RedisEventStream(r, settings.redis_events_stream)

    app = FastAPI(title="edvmp-eventbus", version="0.1.0")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics():
        return prometheus_metrics_response()

    @app.post("/minio/webhook")
    async def minio_webhook(request: Request):
        payload = await request.json()
        events = _parse_minio_webhook(payload)
        published = 0
        for event in events:
            stream.publish(event.model_dump(mode="json"))
            published += 1
        logger.info("minio_webhook_published", extra={"count": published})
        return {"published": published}

    @app.post("/events/job-completed")
    async def job_completed(event: JobCompletedEvent):
        stream.publish(event.model_dump(mode="json"))
        return {"published": 1}

    return app


def main() -> None:
    settings = Settings()
    app = create_app()
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
