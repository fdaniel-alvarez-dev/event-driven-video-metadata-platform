from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from edvmp.shared.models import JobRecord, JobResult, JobStatus


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class AwsDynamoStore:
    def __init__(self, *, region_name: str, jobs_table: str, results_table: str, idempotency_table: str):
        self._ddb = boto3.client("dynamodb", region_name=region_name)
        self._jobs_table = jobs_table
        self._results_table = results_table
        self._idempotency_table = idempotency_table

    def create_job_if_missing(self, *, job_id: str, bucket: str, key: str, status: JobStatus) -> None:
        now = _utc_now_iso()
        item = {
            "job_id": {"S": job_id},
            "status": {"S": status.value},
            "created_at": {"S": now},
            "updated_at": {"S": now},
            "s3_bucket": {"S": bucket},
            "s3_key": {"S": key},
            "gsi1pk": {"S": "HISTORY"},
            "gsi1sk": {"S": now},
        }
        try:
            self._ddb.put_item(
                TableName=self._jobs_table,
                Item=item,
                ConditionExpression="attribute_not_exists(job_id)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return
            raise

    def update_job(
        self,
        *,
        job_id: str,
        status: JobStatus,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        now = _utc_now_iso()
        expr = "SET #s = :s, updated_at = :u, error_code = :ec, error_message = :em"
        self._ddb.update_item(
            TableName=self._jobs_table,
            Key={"job_id": {"S": job_id}},
            UpdateExpression=expr,
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": {"S": status.value},
                ":u": {"S": now},
                ":ec": {"S": error_code or ""},
                ":em": {"S": error_message or ""},
            },
        )

    def get_job(self, job_id: str) -> JobRecord | None:
        res = self._ddb.get_item(TableName=self._jobs_table, Key={"job_id": {"S": job_id}})
        item = res.get("Item")
        if not item:
            return None
        return JobRecord(
            job_id=item["job_id"]["S"],
            status=JobStatus(item["status"]["S"]),
            created_at=datetime.fromisoformat(item["created_at"]["S"]),
            updated_at=datetime.fromisoformat(item["updated_at"]["S"]),
            s3_bucket=item["s3_bucket"]["S"],
            s3_key=item["s3_key"]["S"],
            error_code=(item.get("error_code") or {}).get("S") or None,
            error_message=(item.get("error_message") or {}).get("S") or None,
        )

    def list_jobs(self, limit: int = 50) -> list[JobRecord]:
        res = self._ddb.query(
            TableName=self._jobs_table,
            IndexName="gsi1",
            KeyConditionExpression="gsi1pk = :pk",
            ExpressionAttributeValues={":pk": {"S": "HISTORY"}},
            ScanIndexForward=False,
            Limit=limit,
        )
        items = res.get("Items") or []
        out: list[JobRecord] = []
        for item in items:
            out.append(
                JobRecord(
                    job_id=item["job_id"]["S"],
                    status=JobStatus(item["status"]["S"]),
                    created_at=datetime.fromisoformat(item["created_at"]["S"]),
                    updated_at=datetime.fromisoformat(item["updated_at"]["S"]),
                    s3_bucket=item["s3_bucket"]["S"],
                    s3_key=item["s3_key"]["S"],
                    error_code=(item.get("error_code") or {}).get("S") or None,
                    error_message=(item.get("error_message") or {}).get("S") or None,
                )
            )
        return out

    def store_result(self, *, job_id: str, metadata: dict[str, Any], summary: str) -> None:
        self._ddb.put_item(
            TableName=self._results_table,
            Item={
                "job_id": {"S": job_id},
                "metadata_json": {"S": json_dumps(metadata)},
                "summary": {"S": summary},
            },
        )

    def get_result(self, job_id: str) -> JobResult | None:
        res = self._ddb.get_item(TableName=self._results_table, Key={"job_id": {"S": job_id}})
        item = res.get("Item")
        if not item:
            return None
        return JobResult(
            job_id=item["job_id"]["S"],
            metadata=json_loads(item["metadata_json"]["S"]),
            summary=item["summary"]["S"],
        )

    def try_claim_idempotency(self, *, idempotency_key: str, job_id: str) -> bool:
        try:
            self._ddb.put_item(
                TableName=self._idempotency_table,
                Item={
                    "idempotency_key": {"S": idempotency_key},
                    "job_id": {"S": job_id},
                    "created_at": {"S": _utc_now_iso()},
                },
                ConditionExpression="attribute_not_exists(idempotency_key)",
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise


def json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, separators=(",", ":"), sort_keys=True)


def json_loads(raw: str) -> Any:
    import json

    return json.loads(raw)
