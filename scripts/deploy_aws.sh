#!/usr/bin/env bash
set -euo pipefail

TF_DIR="infra/terraform"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "Deploying (region=$AWS_REGION, image_tag=$IMAGE_TAG)"

terraform -chdir="$TF_DIR" init -upgrade

echo "[1/3] Provisioning base AWS resources (including ECR)..."
terraform -chdir="$TF_DIR" apply -auto-approve \
  -var "aws_region=$AWS_REGION" \
  -var "image_tag=$IMAGE_TAG" \
  -target aws_ecr_repository.api \
  -target aws_ecr_repository.worker \
  -target aws_dynamodb_table.jobs \
  -target aws_dynamodb_table.results \
  -target aws_dynamodb_table.idempotency \
  -target aws_sqs_queue.jobs \
  -target aws_sqs_queue.dlq \
  -target aws_s3_bucket.uploads \
  -target aws_cloudwatch_log_group.api \
  -target aws_cloudwatch_log_group.worker \
  -target aws_iam_role.task_execution \
  -target aws_iam_role.task_runtime

API_REPO="$(terraform -chdir="$TF_DIR" output -raw ecr_api_repo_url)"
WORKER_REPO="$(terraform -chdir="$TF_DIR" output -raw ecr_worker_repo_url)"

echo "[2/3] Building and pushing images to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${API_REPO%/*}"

docker build -f docker/Dockerfile.api -t "$API_REPO:$IMAGE_TAG" .
docker build -f docker/Dockerfile.worker -t "$WORKER_REPO:$IMAGE_TAG" .
docker push "$API_REPO:$IMAGE_TAG"
docker push "$WORKER_REPO:$IMAGE_TAG"

echo "[3/3] Applying full Terraform (ECS, Step Functions, EventBridge, ALB)..."
terraform -chdir="$TF_DIR" apply -auto-approve -var "aws_region=$AWS_REGION" -var "image_tag=$IMAGE_TAG"

echo "API URL: $(terraform -chdir="$TF_DIR" output -raw api_url)"
echo "Uploads bucket: $(terraform -chdir="$TF_DIR" output -raw uploads_bucket)"

