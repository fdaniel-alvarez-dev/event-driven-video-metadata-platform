resource "aws_cloudwatch_event_rule" "s3_object_created" {
  name        = "${local.name}-s3-created"
  description = "Start Step Functions when a video is uploaded"
  event_pattern = jsonencode({
    source      = ["aws.s3"]
    "detail-type" = ["Object Created"]
    detail = {
      bucket = { name = [aws_s3_bucket.uploads.bucket] }
      object = { key = [{ prefix = "uploads/" }] }
    }
  })
}

resource "aws_cloudwatch_event_target" "s3_to_sfn" {
  rule      = aws_cloudwatch_event_rule.s3_object_created.name
  arn       = aws_sfn_state_machine.this.arn
  role_arn  = aws_iam_role.eventbridge_invoke_sfn.arn
}

data "aws_iam_policy_document" "eventbridge_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eventbridge_invoke_sfn" {
  name               = "${local.name}-events-sfn"
  assume_role_policy = data.aws_iam_policy_document.eventbridge_assume.json
}

data "aws_iam_policy_document" "eventbridge_invoke_sfn" {
  statement {
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.this.arn]
  }
}

resource "aws_iam_role_policy" "eventbridge_invoke_sfn" {
  name   = "${local.name}-events-sfn"
  role   = aws_iam_role.eventbridge_invoke_sfn.id
  policy = data.aws_iam_policy_document.eventbridge_invoke_sfn.json
}

