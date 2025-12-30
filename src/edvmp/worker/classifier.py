from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edvmp.worker.ffprobe import MediaProbeError


@dataclass(frozen=True)
class Classification:
    category: str
    recommendation: str


def classify_failure(error: Exception, context: dict[str, Any] | None = None) -> Classification:
    msg = str(error).lower()
    if isinstance(error, MediaProbeError) or "ffprobe" in msg or "codec" in msg or "moov" in msg:
        return Classification(
            category="bad_media",
            recommendation="Validate media format; reject unsupported codecs early and surface clear errors to users.",
        )
    if "timeout" in msg or "timed out" in msg:
        return Classification(
            category="timeout",
            recommendation="Increase worker timeout or split extraction into smaller steps; verify ECS task CPU/memory sizing.",
        )
    if "bedrock" in msg or "throttl" in msg or "model" in msg:
        return Classification(
            category="provider_error",
            recommendation="Enable provider retries with jitter, add circuit breaker, and fall back to mock summary when upstream is degraded.",
        )
    if "redis" in msg or "s3" in msg or "endpoint" in msg or "connection" in msg:
        return Classification(
            category="dependency_unavailable",
            recommendation="Check dependent services health and network; add readiness checks and alerting on dependency latency.",
        )
    return Classification(
        category="unexpected_exception",
        recommendation="Capture stack traces and inputs; add regression tests and consider DLQ replay tooling.",
    )
