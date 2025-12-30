# Rollback Runbook

## Goal
Restore service quickly if a deployment causes regressions.

## API Rollback (ECS)
1. Identify previous stable image tag.
2. Update Terraform `image_tag` to the stable tag.
3. `make deploy` (Terraform applies new task definition revision).

## Worker Rollback
Same approach as API: pin the image tag and redeploy.

## Data Safety
- Jobs and results are append/update-only.
- Re-running a job is protected by idempotency keys.

