#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"
USERNAME="${AUTH_USERNAME:-demo}"
PASSWORD="${AUTH_PASSWORD:-demo}"

echo "[1/6] Starting local stack..."
docker compose up -d --build

echo "[2/6] Waiting for API..."
until curl -fsS "$API_BASE/healthz" >/dev/null; do
  sleep 1
done

echo "[3/6] Creating sample video..."
bash scripts/generate_sample_video.sh samples/sample.mp4

echo "[4/6] Logging in..."
TOKEN="$(curl -fsS -X POST "$API_BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')"

echo "[5/6] Creating job..."
JOB_JSON="$(curl -fsS -X POST "$API_BASE/jobs" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"filename":"sample.mp4","content_type":"video/mp4"}')"
JOB_ID="$(python -c 'import sys,json; print(json.load(sys.stdin)["job_id"])' <<<"$JOB_JSON")"
JOB_ID="$(python3 -c 'import sys,json; print(json.load(sys.stdin)["job_id"])' <<<"$JOB_JSON")"
UPLOAD_URL="$(python3 -c 'import sys,json; print(json.load(sys.stdin)["upload_url"])' <<<"$JOB_JSON")"
echo "Job: $JOB_ID"

echo "[6/6] Uploading and waiting for completion..."
curl -fsS -X PUT "$UPLOAD_URL" --upload-file samples/sample.mp4 >/dev/null

for i in {1..60}; do
  STATUS="$(curl -fsS "$API_BASE/jobs/$JOB_ID" -H "Authorization: Bearer $TOKEN" | python -c 'import sys,json; print(json.load(sys.stdin)["status"])')"
  echo "Status: $STATUS"
  if [[ "$STATUS" == "SUCCEEDED" ]]; then
    echo "Result:"
    curl -fsS "$API_BASE/jobs/$JOB_ID/result" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
    echo "History:"
    curl -fsS "$API_BASE/history?limit=5" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
    exit 0
  fi
  if [[ "$STATUS" == "FAILED" ]]; then
    echo "Job failed. DLQ analyzer output:"
    docker compose exec -T worker python -m edvmp.worker.dlq_analyzer || true
    exit 1
  fi
  sleep 2
done

echo "Timed out waiting for job completion"
exit 1
