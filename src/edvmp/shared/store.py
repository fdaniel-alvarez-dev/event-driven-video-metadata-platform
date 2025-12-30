from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from edvmp.shared.models import JobRecord, JobResult, JobStatus


def _utc_now() -> datetime:
    return datetime.now(UTC)


class LocalSqliteStore:
    def __init__(self, db_path: str):
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                  job_id TEXT PRIMARY KEY,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  s3_bucket TEXT NOT NULL,
                  s3_key TEXT NOT NULL,
                  error_code TEXT,
                  error_message TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS results (
                  job_id TEXT PRIMARY KEY,
                  metadata_json TEXT NOT NULL,
                  summary TEXT NOT NULL,
                  FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency (
                  idempotency_key TEXT PRIMARY KEY,
                  job_id TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);")

    def create_job_if_missing(self, *, job_id: str, bucket: str, key: str, status: JobStatus) -> None:
        now = _utc_now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO jobs(job_id, status, created_at, updated_at, s3_bucket, s3_key)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO NOTHING;
                """,
                (job_id, status.value, now, now, bucket, key),
            )

    def update_job(
        self,
        *,
        job_id: str,
        status: JobStatus,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        now = _utc_now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?, error_code = ?, error_message = ?
                WHERE job_id = ?;
                """,
                (status.value, now, error_code, error_message, job_id),
            )

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?;", (job_id,)).fetchone()
            if row is None:
                return None
            return JobRecord(
                job_id=row["job_id"],
                status=JobStatus(row["status"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                s3_bucket=row["s3_bucket"],
                s3_key=row["s3_key"],
                error_code=row["error_code"],
                error_message=row["error_message"],
            )

    def list_jobs(self, limit: int = 50) -> list[JobRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?;",
                (limit,),
            ).fetchall()
            return [
                JobRecord(
                    job_id=r["job_id"],
                    status=JobStatus(r["status"]),
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                    s3_bucket=r["s3_bucket"],
                    s3_key=r["s3_key"],
                    error_code=r["error_code"],
                    error_message=r["error_message"],
                )
                for r in rows
            ]

    def store_result(self, *, job_id: str, metadata: dict[str, Any], summary: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO results(job_id, metadata_json, summary)
                VALUES(?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                  metadata_json=excluded.metadata_json,
                  summary=excluded.summary;
                """,
                (job_id, json.dumps(metadata), summary),
            )

    def get_result(self, job_id: str) -> JobResult | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM results WHERE job_id = ?;", (job_id,)).fetchone()
            if row is None:
                return None
            return JobResult(job_id=row["job_id"], metadata=json.loads(row["metadata_json"]), summary=row["summary"])

    def try_claim_idempotency(self, *, idempotency_key: str, job_id: str) -> bool:
        now = _utc_now().isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO idempotency(idempotency_key, job_id, created_at)
                VALUES(?, ?, ?);
                """,
                (idempotency_key, job_id, now),
            )
            return cur.rowcount == 1
