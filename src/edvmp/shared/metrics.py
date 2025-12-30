from __future__ import annotations

from prometheus_client import Counter, Histogram


def api_metrics(namespace: str) -> tuple[Counter, Histogram]:
    requests_total = Counter(
        f"{namespace}_api_requests_total",
        "API requests",
        labelnames=("method", "path", "status"),
    )
    latency = Histogram(
        f"{namespace}_api_request_latency_seconds",
        "API request latency (seconds)",
        labelnames=("method", "path"),
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
    )
    return requests_total, latency


worker_jobs_total = Counter(
    "edvmp_worker_jobs_total",
    "Worker job outcomes",
    labelnames=("status",),
)
worker_job_duration = Histogram(
    "edvmp_worker_job_duration_seconds",
    "Worker job duration (seconds)",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)
dlq_messages_total = Counter(
    "edvmp_dlq_messages_total",
    "DLQ messages produced",
    labelnames=("category",),
)

