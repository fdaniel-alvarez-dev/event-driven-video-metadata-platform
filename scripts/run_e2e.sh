#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"

docker compose up -d --build

cleanup() {
  docker compose down -v
}
trap cleanup EXIT

until curl -fsS "$API_BASE/healthz" >/dev/null; do
  sleep 1
done

python3 -m pytest -q tests/e2e
