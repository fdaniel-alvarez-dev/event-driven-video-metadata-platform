data "aws_iam_policy_document" "sfn_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn" {
  name               = "${local.name}-sfn"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume.json
}

data "aws_iam_policy_document" "sfn" {
  statement {
    actions = ["dynamodb:PutItem"]
    resources = [
      aws_dynamodb_table.idempotency.arn
    ]
  }
  statement {
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.jobs.arn]
  }
}

resource "aws_iam_role_policy" "sfn" {
  name   = "${local.name}-sfn"
  role   = aws_iam_role.sfn.id
  policy = data.aws_iam_policy_document.sfn.json
}

locals {
  sfn_definition = jsonencode({
    Comment = "EDVMP: S3 event -> idempotency -> SQS"
    StartAt = "GenerateJobId"
    States = {
      GenerateJobId = {
        Type = "Pass"
        Parameters = {
          "job_id.$" = "States.ArrayGetItem(States.StringSplit($.detail.object.key, '/'), 1)"
          "detail.$" = "$.detail"
          "message" = {
            message_type = "ProcessVideo"
            payload = {
              "job_id.$" = "$.job_id"
              "bucket.$" = "$.detail.bucket.name"
              "key.$"    = "$.detail.object.key"
            }
          }
        }
        Next = "Idempotency"
      }
      Idempotency = {
        Type     = "Task"
        Resource = "arn:aws:states:::dynamodb:putItem"
        Parameters = {
          TableName = aws_dynamodb_table.idempotency.name
          Item = {
            idempotency_key = { "S.$" = "States.Format('s3://{}/{}', $.detail.bucket.name, $.detail.object.key)" }
            job_id          = { "S.$" = "$.job_id" }
            created_at      = { "S.$" = "$$.Execution.StartTime" }
          }
          ConditionExpression = "attribute_not_exists(idempotency_key)"
        }
        ResultPath = "$.idempotency"
        Catch = [
          {
            ErrorEquals = ["DynamoDB.ConditionalCheckFailedException"]
            Next        = "DoneDuplicate"
          }
        ]
        Next = "Enqueue"
      }
      Enqueue = {
        Type     = "Task"
        Resource = "arn:aws:states:::sqs:sendMessage"
        Parameters = {
          QueueUrl = aws_sqs_queue.jobs.id
          "MessageBody.$" = "States.JsonToString($.message)"
        }
        Retry = [
          {
            ErrorEquals     = ["States.ALL"]
            IntervalSeconds = 1
            BackoffRate     = 2.0
            MaxAttempts     = 6
          }
        ]
        End = true
      }
      DoneDuplicate = { Type = "Succeed" }
    }
  })
}

resource "aws_sfn_state_machine" "this" {
  name     = "${local.name}-pipeline"
  role_arn = aws_iam_role.sfn.arn
  definition = local.sfn_definition
}
