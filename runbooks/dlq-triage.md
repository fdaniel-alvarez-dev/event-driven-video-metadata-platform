# DLQ Triage

## What to Look For
- Category distribution: bad_media vs timeout vs provider_error vs dependency_unavailable
- Top failing job IDs and their object keys

## Actions
- bad_media: add validation at job creation and provide actionable client errors
- timeout: tune task resources/timeouts and consider splitting steps
- provider_error: add circuit breaker; keep Bedrock mock fallback enabled
- dependency_unavailable: verify service health + network and increase retries with jitter

## Local Mode
Run:
```bash
docker compose exec -T worker python -m edvmp.worker.dlq_analyzer
```

## AWS Mode
DLQ analyzer runs on a schedule (EventBridge). Inspect CloudWatch logs for the incident JSON.

