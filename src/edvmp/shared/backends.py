from __future__ import annotations

import redis

from edvmp.shared.aws_dynamo_store import AwsDynamoStore
from edvmp.shared.aws_sqs_queue import SqsDlq, SqsQueue
from edvmp.shared.config import Settings
from edvmp.shared.queue import RedisDlq, RedisQueue
from edvmp.shared.store import LocalSqliteStore


def get_store(settings: Settings):
    if settings.store_backend == "dynamodb":
        if not (settings.ddb_jobs_table and settings.ddb_results_table and settings.ddb_idempotency_table):
            raise RuntimeError("DynamoDB tables must be set (DDB_*_TABLE) when STORE_BACKEND=dynamodb")
        return AwsDynamoStore(
            region_name=settings.s3_region,
            jobs_table=settings.ddb_jobs_table,
            results_table=settings.ddb_results_table,
            idempotency_table=settings.ddb_idempotency_table,
        )
    return LocalSqliteStore(settings.db_path)


def get_queue(settings: Settings):
    if settings.queue_backend == "sqs":
        if not settings.sqs_jobs_queue_url:
            raise RuntimeError("SQS_JOBS_QUEUE_URL must be set when QUEUE_BACKEND=sqs")
        return SqsQueue(region_name=settings.s3_region, queue_url=settings.sqs_jobs_queue_url)
    r = redis.Redis.from_url(settings.redis_url)
    return RedisQueue(r, settings.redis_jobs_queue)


def get_dlq(settings: Settings):
    if settings.queue_backend == "sqs":
        if not settings.sqs_dlq_url:
            raise RuntimeError("SQS_DLQ_URL must be set when QUEUE_BACKEND=sqs")
        return SqsDlq(region_name=settings.s3_region, queue_url=settings.sqs_dlq_url)
    r = redis.Redis.from_url(settings.redis_url)
    return RedisDlq(r, settings.redis_dlq)
