# -----------------------------------------------------------------------------
# ECS Fargate Module — Main Resources
# -----------------------------------------------------------------------------
# Creates an ECS Fargate service with:
# - ECS Cluster with Container Insights enabled
# - Task definition for Application_Service container
# - Service with minimum 2 tasks distributed across different AZs
# - Deployment configuration: min healthy 100%, max 200% (zero-downtime)
# - Integration with ALB target group for health-checked traffic routing
# - CloudWatch log group for container logs
# - IAM roles: task execution role (pull images, fetch secrets) and task role (app permissions)
# - Environment variables and secrets from Secrets Manager
#
# Requirements: 10.3, 10.4, 10.5
# -----------------------------------------------------------------------------

locals {
  name_prefix    = "${var.project_name}-${var.environment}"
  container_name = "${local.name_prefix}-app"
}

# -----------------------------------------------------------------------------
# ECS Cluster
# -----------------------------------------------------------------------------

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name      = "${local.name_prefix}-cluster"
    Component = "compute"
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Log Group for container logs
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${local.name_prefix}"
  retention_in_days = var.log_retention_days

  tags = {
    Name      = "${local.name_prefix}-ecs-logs"
    Component = "compute"
  }
}

# -----------------------------------------------------------------------------
# IAM — Task Execution Role
# Allows ECS agent to pull images from ECR, fetch secrets, and write logs.
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "ecs_task_execution_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "${local.name_prefix}-ecs-exec-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume.json

  tags = {
    Name      = "${local.name_prefix}-ecs-exec-role"
    Component = "compute"
  }
}

resource "aws_iam_role_policy_attachment" "task_execution_managed" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow the execution role to fetch secrets from Secrets Manager
data "aws_iam_policy_document" "secrets_access" {
  count = length(var.secrets) > 0 ? 1 : 0

  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
    ]
    resources = values(var.secrets)
  }
}

resource "aws_iam_role_policy" "secrets_access" {
  count = length(var.secrets) > 0 ? 1 : 0

  name   = "${local.name_prefix}-secrets-access"
  role   = aws_iam_role.task_execution.id
  policy = data.aws_iam_policy_document.secrets_access[0].json
}

# -----------------------------------------------------------------------------
# IAM — Task Role
# Role assumed by the application container at runtime.
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "ecs_task_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task" {
  name               = "${local.name_prefix}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json

  tags = {
    Name      = "${local.name_prefix}-ecs-task-role"
    Component = "compute"
  }
}

# Enable ECS Exec (SSM) when requested
data "aws_iam_policy_document" "ecs_exec" {
  count = var.enable_execute_command ? 1 : 0

  statement {
    effect = "Allow"
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "ecs_exec" {
  count = var.enable_execute_command ? 1 : 0

  name   = "${local.name_prefix}-ecs-exec"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.ecs_exec[0].json
}

# -----------------------------------------------------------------------------
# ECS Task Definition
# -----------------------------------------------------------------------------

resource "aws_ecs_task_definition" "app" {
  family                   = "${local.name_prefix}-app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = local.container_name
      image     = var.ecr_image_uri
      essential = true

      portMappings = [
        {
          containerPort = var.app_port
          protocol      = "tcp"
        }
      ]

      environment = [
        for key, value in merge(
          {
            ENVIRONMENT = var.environment
            PORT        = tostring(var.app_port)
          },
          var.environment_variables
          ) : {
          name  = key
          value = value
        }
      ]

      secrets = [
        for key, arn in var.secrets : {
          name      = key
          valueFrom = arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "app"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:${var.app_port}/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name      = "${local.name_prefix}-task-def"
    Component = "compute"
  }
}

# -----------------------------------------------------------------------------
# ECS Service — Fargate with ALB Integration
# - Minimum 2 tasks across different AZs (via subnet placement)
# - Deployment: min healthy 100%, max 200% for zero-downtime rolling updates
# - Wired to ALB target group for load balancing and health checking
# -----------------------------------------------------------------------------

resource "aws_ecs_service" "app" {
  name            = "${local.name_prefix}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  # Zero-downtime deployment: keep all existing tasks running while deploying new ones
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  # Grace period before ALB health checks start counting against new tasks
  health_check_grace_period_seconds = var.health_check_grace_period

  # Enable ECS Exec for debugging when requested
  enable_execute_command = var.enable_execute_command

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.app_sg_id]
    assign_public_ip = var.assign_public_ip
  }

  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = local.container_name
    container_port   = var.app_port
  }

  # Ensure ECS distributes tasks across AZs for high availability
  # Fargate automatically spreads tasks across available AZs when multiple subnets are provided

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  # Ignore desired_count changes from auto-scaling
  lifecycle {
    ignore_changes = [desired_count]
  }

  tags = {
    Name      = "${local.name_prefix}-service"
    Component = "compute"
  }

  depends_on = [
    aws_iam_role_policy_attachment.task_execution_managed,
  ]
}
