resource "aws_ecs_task_definition" "dlq_analyzer" {
  family                   = "${local.name}-dlq-analyzer"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task_runtime.arn

  container_definitions = jsonencode([
    {
      name      = "dlq-analyzer",
      image     = "${aws_ecr_repository.worker.repository_url}:${var.image_tag}",
      essential = true,
      command   = ["python", "-m", "edvmp.worker.dlq_analyzer"],
      environment = [
        { name = "APP_ENV", value = "aws" },
        { name = "STORE_BACKEND", value = "dynamodb" },
        { name = "QUEUE_BACKEND", value = "sqs" },
        { name = "DDB_JOBS_TABLE", value = aws_dynamodb_table.jobs.name },
        { name = "DDB_RESULTS_TABLE", value = aws_dynamodb_table.results.name },
        { name = "DDB_IDEMPOTENCY_TABLE", value = aws_dynamodb_table.idempotency.name },
        { name = "SQS_DLQ_URL", value = aws_sqs_queue.dlq.id }
      ],
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name,
          awslogs-region        = local.aws_region,
          awslogs-stream-prefix = "dlq"
        }
      }
    }
  ])
}

resource "aws_cloudwatch_event_rule" "dlq_analyzer_schedule" {
  name                = "${local.name}-dlq-analyzer"
  schedule_expression = "rate(15 minutes)"
}

data "aws_iam_policy_document" "events_run_task_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "events_run_task" {
  name               = "${local.name}-events-run-task"
  assume_role_policy = data.aws_iam_policy_document.events_run_task_assume.json
}

data "aws_iam_policy_document" "events_run_task" {
  statement {
    actions = ["ecs:RunTask"]
    resources = [aws_ecs_task_definition.dlq_analyzer.arn]
  }
  statement {
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.task_execution.arn, aws_iam_role.task_runtime.arn]
  }
}

resource "aws_iam_role_policy" "events_run_task" {
  name   = "${local.name}-events-run-task"
  role   = aws_iam_role.events_run_task.id
  policy = data.aws_iam_policy_document.events_run_task.json
}

resource "aws_cloudwatch_event_target" "dlq_analyzer" {
  rule     = aws_cloudwatch_event_rule.dlq_analyzer_schedule.name
  arn      = aws_ecs_cluster.this.arn
  role_arn = aws_iam_role.events_run_task.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.dlq_analyzer.arn
    launch_type         = "FARGATE"
    platform_version    = "LATEST"
    network_configuration {
      subnets          = data.aws_subnets.default.ids
      security_groups  = [aws_security_group.ecs.id]
      assign_public_ip = true
    }
  }
}

