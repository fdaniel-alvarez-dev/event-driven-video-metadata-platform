# System Design

## Goals
- Event-driven ingestion from video uploads
- Clear separation of concerns: API vs orchestration vs workers
- Built-in reliability patterns: idempotency, retries, DLQ classification
- Switch Bedrock mock → real Bedrock via config only

## Sequence Diagrams

### Local Mode
```mermaid
sequenceDiagram
  autonumber
  participant U as User
  participant API as FastAPI
  participant S3 as MinIO
  participant EB as Mock EventBus
  participant ORCH as Orchestrator
  participant Q as Redis Queue
  participant W as Worker
  participant DB as SQLite

  U->>API: POST /auth/login
  API-->>U: Bearer token
  U->>API: POST /jobs
  API->>DB: Create job (AWAITING_UPLOAD)
  API-->>U: job_id + presigned PUT URL
  U->>S3: PUT object (uploads/{job_id}/file)
  S3->>EB: webhook ObjectCreated
  EB->>ORCH: publish event (Redis Stream)
  ORCH->>DB: conditional idempotency + set PROCESSING
  ORCH->>Q: enqueue ProcessVideo
  W->>Q: consume
  W->>S3: download video
  W->>W: ffprobe metadata
  W->>W: Bedrock mock summary
  W->>DB: store result + set SUCCEEDED
  W->>EB: JobCompleted event
  U->>API: GET /jobs/{job_id}/result
  API->>DB: fetch result
  API-->>U: metadata + summary
```

### AWS Mode
```mermaid
sequenceDiagram
  autonumber
  participant U as User
  participant API as FastAPI (ECS)
  participant S3 as S3
  participant EVB as EventBridge
  participant SFN as Step Functions
  participant DDB as DynamoDB (Idempotency)
  participant SQS as SQS
  participant W as Worker (ECS)
  participant J as DynamoDB (Jobs/Results)
  participant DLQ as SQS DLQ
  participant ANA as DLQ Analyzer

  U->>API: POST /jobs
  API->>J: create job (AWAITING_UPLOAD)
  API-->>U: presigned PUT URL
  U->>S3: PUT uploads/{job_id}/file
  S3->>EVB: Object Created event
  EVB->>SFN: StartExecution
  SFN->>DDB: PutItem with ConditionExpression
  alt duplicate
    SFN-->>SFN: Succeed (no-op)
  else first-seen
    SFN->>SQS: SendMessage(ProcessVideo)
  end
  W->>SQS: ReceiveMessage
  W->>S3: download
  W->>W: ffprobe + Bedrock(mock/real)
  W->>J: update status + store results
  alt failure after retries
    W->>DLQ: SendMessage(DLQ enriched)
  end
  ANA->>DLQ: Drain + classify
  ANA-->>ANA: Incident JSON report (CloudWatch logs)
```

## Scaling Strategy
- Scale worker count horizontally (ECS Service desired count / autoscaling on SQS depth).
- Keep API stateless behind ALB; scale on request rate.
- DynamoDB PAY_PER_REQUEST supports bursty workloads; add adaptive capacity and alarm on throttles.

## Cost Model (Order-of-Magnitude)
- Main cost drivers: S3 storage + data transfer, ECS compute time, DynamoDB reads/writes, Step Functions transitions.
- Control levers:
  - Batch small videos to reduce overhead.
  - Tune worker CPU/memory for ffprobe workloads.
  - Use SQS long polling to reduce empty receives.

## Security Model
- JWT auth for API (rotate secret; store in Secrets Manager in real deployments).
- Principle of least privilege IAM roles (task runtime role only needs S3/DDB/SQS).
- CI gates: Bandit, pip-audit, Trivy, OWASP ZAP baseline.
- No secrets committed; use `.env` locally and Terraform outputs for AWS demo creds.

