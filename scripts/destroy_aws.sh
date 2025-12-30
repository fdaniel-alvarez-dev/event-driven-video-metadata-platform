#!/usr/bin/env bash
set -euo pipefail

TF_DIR="infra/terraform"
AWS_REGION="${AWS_REGION:-us-east-1}"

terraform -chdir="$TF_DIR" init -upgrade
terraform -chdir="$TF_DIR" destroy -auto-approve -var "aws_region=$AWS_REGION"

