from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from edvmp.api.auth import LoginRequest, TokenResponse, issue_token, make_get_current_user
from edvmp.shared.backends import get_store
from edvmp.shared.config import Settings
from edvmp.shared.http import prometheus_metrics_response
from edvmp.shared.logging import configure_logging
from edvmp.shared.metrics import api_metrics
from edvmp.shared.models import JobStatus
from edvmp.shared.s3 import ensure_bucket_exists, presign_put_url, s3_client

logger = logging.getLogger("edvmp.api")


class CreateJobRequest(BaseModel):
    filename: str = Field(min_length=1)
    content_type: str | None = None


class CreateJobResponse(BaseModel):
    job_id: str
    s3_bucket: str
    s3_key: str
    upload_url: str
    expires_in: int


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings.log_level)

    store = get_store(settings)

    s3_internal = s3_client(
        region_name=settings.s3_region,
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    ensure_bucket_exists(s3_internal, settings.s3_bucket)

    presign_endpoint = settings.s3_public_endpoint_url or settings.s3_endpoint_url
    s3_presign = s3_client(
        region_name=settings.s3_region,
        endpoint_url=presign_endpoint,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

    requests_total, latency = api_metrics(settings.prometheus_namespace)

    app = FastAPI(title="event-driven-video-metadata-platform", version="0.1.0")
    get_current_user = make_get_current_user(settings)

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start = time.time()
        try:
            response = await call_next(request)
        except Exception:
            requests_total.labels(method=request.method, path=request.url.path, status="500").inc()
            raise
        finally:
            latency.labels(method=request.method, path=request.url.path).observe(time.time() - start)
        requests_total.labels(
            method=request.method, path=request.url.path, status=str(response.status_code)
        ).inc()
        return response

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "env": settings.app_env, "ts": datetime.now(UTC).isoformat()}

    @app.get("/metrics")
    def metrics():
        return prometheus_metrics_response()

    @app.post("/auth/login", response_model=TokenResponse)
    def login(req: LoginRequest):
        if req.username != settings.auth_username or req.password != settings.auth_password:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return issue_token(settings, subject=req.username)

    @app.post("/jobs", response_model=CreateJobResponse)
    def create_job(req: CreateJobRequest, user: str = Depends(get_current_user)):
        job_id = str(uuid.uuid4())
        key = f"uploads/{job_id}/{req.filename}"
        expires_in = 900
        url = presign_put_url(s3_presign, settings.s3_bucket, key, expires_in=expires_in)

        store.create_job_if_missing(
            job_id=job_id, bucket=settings.s3_bucket, key=key, status=JobStatus.awaiting_upload
        )
        logger.info("job_created", extra={"job_id": job_id, "user": user, "s3_key": key})
        return CreateJobResponse(
            job_id=job_id,
            s3_bucket=settings.s3_bucket,
            s3_key=key,
            upload_url=url,
            expires_in=expires_in,
        )

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str, _: str = Depends(get_current_user)):
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job.model_dump(mode="json")

    @app.get("/jobs/{job_id}/result")
    def get_result(job_id: str, _: str = Depends(get_current_user)):
        result = store.get_result(job_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Result not found")
        return result.model_dump(mode="json")

    @app.get("/history")
    def history(limit: int = 50, _: str = Depends(get_current_user)):
        limit = max(1, min(200, limit))
        jobs = store.list_jobs(limit=limit)
        return {"items": [j.model_dump(mode="json") for j in jobs]}

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(_: Request, exc: RuntimeError):
        logger.exception("runtime_error", extra={"error": str(exc)})
        return JSONResponse(status_code=500, content={"detail": "Internal error"})

    return app


def main() -> None:
    settings = Settings()
    app = create_app()
    import uvicorn

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
