# -----------------------------------------------------------------------------
# ALB Module — Main Resources
# -----------------------------------------------------------------------------
# Creates an Application Load Balancer with:
# - Internet-facing ALB across public subnets (minimum 2 AZs)
# - Cross-zone load balancing enabled
# - Target group for ECS Fargate tasks (target_type = "ip")
# - Health checks: /health path, healthy 2, unhealthy 3, interval 30s, timeout 5s
# - Optional access logging to S3
# - Optional deletion protection (default: false for demo/local)
# - HTTP listener on port 80 (redirects to HTTPS in production)
# -----------------------------------------------------------------------------

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# -----------------------------------------------------------------------------
# Application Load Balancer
# -----------------------------------------------------------------------------

resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_sg_id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection       = var.enable_deletion_protection
  enable_cross_zone_load_balancing = true

  dynamic "access_logs" {
    for_each = var.enable_access_logging ? [1] : []
    content {
      bucket  = var.access_log_bucket_name
      prefix  = var.access_log_prefix
      enabled = true
    }
  }

  tags = {
    Name      = "${local.name_prefix}-alb"
    Component = "load-balancing"
  }
}

# -----------------------------------------------------------------------------
# Target Group — ECS Fargate (IP-based targets)
# -----------------------------------------------------------------------------

resource "aws_lb_target_group" "app" {
  name        = "${local.name_prefix}-app-tg"
  port        = var.app_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  deregistration_delay = var.deregistration_delay

  health_check {
    enabled             = true
    path                = var.health_check_path
    protocol            = "HTTP"
    port                = "traffic-port"
    healthy_threshold   = var.health_check_healthy_threshold
    unhealthy_threshold = var.health_check_unhealthy_threshold
    interval            = var.health_check_interval
    timeout             = var.health_check_timeout
    matcher             = "200"
  }

  tags = {
    Name      = "${local.name_prefix}-app-tg"
    Component = "load-balancing"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# -----------------------------------------------------------------------------
# HTTP Listener (port 80)
# In production this would redirect to HTTPS (443). For demo/local purposes,
# it forwards directly to the target group.
# -----------------------------------------------------------------------------

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }

  tags = {
    Name      = "${local.name_prefix}-http-listener"
    Component = "load-balancing"
  }
}
