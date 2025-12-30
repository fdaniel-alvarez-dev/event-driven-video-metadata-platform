from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.example"), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Auth
    auth_username: str = Field(default="demo", alias="AUTH_USERNAME")
    auth_password: str = Field(default="demo", alias="AUTH_PASSWORD")
    jwt_secret: str = Field(default="change-me-in-prod", alias="JWT_SECRET")
    jwt_issuer: str = Field(default="edvmp", alias="JWT_ISSUER")

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # Storage
    s3_endpoint_url: str | None = Field(default=None, alias="S3_ENDPOINT_URL")
    s3_public_endpoint_url: str | None = Field(default=None, alias="S3_PUBLIC_ENDPOINT_URL")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
    s3_bucket: str = Field(default="videos", alias="S3_BUCKET")

    # AWS credentials (also used for MinIO in local mode)
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")

    # Event bus + queues (Redis)
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_events_stream: str = Field(default="events", alias="REDIS_EVENTS_STREAM")
    redis_jobs_queue: str = Field(default="jobs", alias="REDIS_JOBS_QUEUE")
    redis_dlq: str = Field(default="dlq", alias="REDIS_DLQ")

    # Local persistence
    db_path: str = Field(default="data/app.db", alias="DB_PATH")

    # Backend switches (local mock vs AWS)
    store_backend: str = Field(default="sqlite", alias="STORE_BACKEND")  # sqlite|dynamodb
    queue_backend: str = Field(default="redis", alias="QUEUE_BACKEND")  # redis|sqs

    # DynamoDB (AWS mode)
    ddb_jobs_table: str | None = Field(default=None, alias="DDB_JOBS_TABLE")
    ddb_results_table: str | None = Field(default=None, alias="DDB_RESULTS_TABLE")
    ddb_idempotency_table: str | None = Field(default=None, alias="DDB_IDEMPOTENCY_TABLE")

    # SQS (AWS mode)
    sqs_jobs_queue_url: str | None = Field(default=None, alias="SQS_JOBS_QUEUE_URL")
    sqs_dlq_url: str | None = Field(default=None, alias="SQS_DLQ_URL")

    # EventBridge (AWS mode)
    eventbridge_bus_name: str = Field(default="default", alias="EVENTBRIDGE_BUS_NAME")

    # Worker
    worker_concurrency: int = Field(default=1, alias="WORKER_CONCURRENCY")
    worker_max_attempts: int = Field(default=3, alias="WORKER_MAX_ATTEMPTS")
    worker_backoff_seconds: float = Field(default=1.0, alias="WORKER_BACKOFF_SECONDS")
    worker_metrics_port: int = Field(default=9100, alias="WORKER_METRICS_PORT")

    # Bedrock
    bedrock_mode: str = Field(default="mock", alias="BEDROCK_MODE")  # mock|aws
    bedrock_model_id: str = Field(
        default="anthropic.claude-3-sonnet-20240229-v1:0", alias="BEDROCK_MODEL_ID"
    )

    # Observability
    prometheus_namespace: str = Field(default="edvmp", alias="PROMETHEUS_NAMESPACE")

    # Service URLs (local)
    eventbus_url: str | None = Field(default=None, alias="EVENTBUS_URL")
