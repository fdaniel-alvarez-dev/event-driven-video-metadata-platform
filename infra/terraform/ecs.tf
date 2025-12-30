resource "aws_ecs_cluster" "this" {
  name = "${local.name}-cluster"
}

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb-sg"
  description = "ALB SG"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs" {
  name        = "${local.name}-ecs-sg"
  description = "ECS tasks SG"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "api" {
  name               = "${local.name}-alb"
  load_balancer_type = "application"
  subnets            = data.aws_subnets.default.ids
  security_groups    = [aws_security_group.alb.id]
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"

  health_check {
    path = "/healthz"
  }
}

resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task_runtime.arn

  container_definitions = jsonencode([
    {
      name      = "api",
      image     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}",
      essential = true,
      portMappings = [
        { containerPort = 8000, hostPort = 8000, protocol = "tcp" }
      ],
      environment = [
        { name = "APP_ENV", value = "aws" },
        { name = "STORE_BACKEND", value = "dynamodb" },
        { name = "QUEUE_BACKEND", value = "sqs" },
        { name = "S3_BUCKET", value = aws_s3_bucket.uploads.bucket },
        { name = "S3_REGION", value = local.aws_region },
        { name = "AUTH_USERNAME", value = "demo" },
        { name = "AUTH_PASSWORD", value = random_password.auth_password.result },
        { name = "JWT_SECRET", value = random_password.jwt_secret.result },
        { name = "DDB_JOBS_TABLE", value = aws_dynamodb_table.jobs.name },
        { name = "DDB_RESULTS_TABLE", value = aws_dynamodb_table.results.name },
        { name = "DDB_IDEMPOTENCY_TABLE", value = aws_dynamodb_table.idempotency.name }
      ],
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name,
          awslogs-region        = local.aws_region,
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task_runtime.arn

  container_definitions = jsonencode([
    {
      name      = "worker",
      image     = "${aws_ecr_repository.worker.repository_url}:${var.image_tag}",
      essential = true,
      environment = [
        { name = "APP_ENV", value = "aws" },
        { name = "STORE_BACKEND", value = "dynamodb" },
        { name = "QUEUE_BACKEND", value = "sqs" },
        { name = "S3_BUCKET", value = aws_s3_bucket.uploads.bucket },
        { name = "S3_REGION", value = local.aws_region },
        { name = "DDB_JOBS_TABLE", value = aws_dynamodb_table.jobs.name },
        { name = "DDB_RESULTS_TABLE", value = aws_dynamodb_table.results.name },
        { name = "DDB_IDEMPOTENCY_TABLE", value = aws_dynamodb_table.idempotency.name },
        { name = "SQS_JOBS_QUEUE_URL", value = aws_sqs_queue.jobs.id },
        { name = "SQS_DLQ_URL", value = aws_sqs_queue.dlq.id },
        { name = "BEDROCK_MODE", value = "mock" }
      ],
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name,
          awslogs-region        = local.aws_region,
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "api" {
  name            = "${local.name}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = data.aws_subnets.default.ids
    security_groups = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.api]
}

resource "aws_ecs_service" "worker" {
  name            = "${local.name}-worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }
}

output "api_url" {
  value = "http://${aws_lb.api.dns_name}"
}
