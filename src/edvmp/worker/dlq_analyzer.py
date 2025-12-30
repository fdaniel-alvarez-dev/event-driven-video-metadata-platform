from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from edvmp.shared.aws_sqs_queue import SqsDlq
from edvmp.shared.backends import get_dlq
from edvmp.shared.config import Settings
from edvmp.shared.logging import configure_logging
from edvmp.shared.metrics import dlq_messages_total
from edvmp.shared.queue import RedisDlq
from edvmp.worker.classifier import classify_failure

logger = logging.getLogger("edvmp.dlq_analyzer")


def analyze_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, int] = {}
    samples: dict[str, dict[str, Any]] = {}
    for m in messages:
        err_msg = m.get("error_message") or "unknown"
        classification = classify_failure(RuntimeError(err_msg), context=m)
        by_category[classification.category] = by_category.get(classification.category, 0) + 1
        dlq_messages_total.labels(category=classification.category).inc()
        samples.setdefault(
            classification.category,
            {
                "example_job_id": m.get("job_id"),
                "example_error": err_msg,
                "recommendation": classification.recommendation,
            },
        )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_messages": len(messages),
        "categories": by_category,
        "samples": samples,
    }


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)

    dlq = get_dlq(settings)
    messages: list[dict[str, Any]]
    if isinstance(dlq, RedisDlq):
        messages = dlq.drain(max_items=1000)
    elif isinstance(dlq, SqsDlq):
        received = dlq.receive(wait_time_s=2, max_messages=10)
        messages = []
        for rcv in received:
            raw = rcv.message.payload
            messages.append(raw)
            dlq.delete(rcv.receipt_handle)
    else:
        raise RuntimeError("Unsupported DLQ backend")
    report = analyze_messages(messages)

    out_dir = Path("incidents")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"incident-{int(datetime.now(UTC).timestamp())}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info("dlq_incident_report_written", extra={"path": str(out_path), "report": report})


if __name__ == "__main__":
    main()
