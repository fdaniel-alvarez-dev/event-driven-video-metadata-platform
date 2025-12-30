# On-Call Runbook

## Primary Signals
- API error rate (5xx) and latency (P95)
- Worker failures and DLQ growth
- DynamoDB throttles

## First 5 Minutes
1. Confirm impact: failing uploads vs failing processing vs API auth issues.
2. Check dashboard (Grafana) and recent logs.
3. If failures spike, look at DLQ analyzer output and classify.

## Common Issues
- **Bad media / codec**: reject early; update allowlist/validation rules.
- **Dependency outage**: S3/Dynamo/SQS/Bedrock transient issues → check AWS Health + retries.
- **Worker saturation**: increase worker count or task size; verify queue depth alarms.

