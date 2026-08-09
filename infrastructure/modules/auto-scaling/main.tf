###############################################################################
# Auto Scaling Module
#
# Configures ECS Application Auto Scaling with:
# - Target tracking policy (CPU utilisation)
# - Step scaling policy (ALB RequestCountPerTarget)
# - Scheduled scaling (scale to zero outside demo hours)
###############################################################################

# -----------------------------------------------------------------------------
# Scalable Target
# -----------------------------------------------------------------------------

resource "aws_appautoscaling_target" "ecs" {
  max_capacity       = var.max_capacity
  min_capacity       = var.min_capacity
  resource_id        = "service/${var.ecs_cluster_name}/${var.ecs_service_name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# -----------------------------------------------------------------------------
# Target Tracking Policy — CPU Utilisation
# -----------------------------------------------------------------------------

resource "aws_appautoscaling_policy" "cpu_target_tracking" {
  name               = "${var.ecs_service_name}-cpu-target-tracking"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }

    target_value       = var.cpu_target
    scale_out_cooldown = var.scale_out_cooldown
    scale_in_cooldown  = var.scale_in_cooldown
  }
}

# -----------------------------------------------------------------------------
# Step Scaling Policy — ALB Request Count Per Target
# -----------------------------------------------------------------------------

resource "aws_appautoscaling_policy" "request_count_step" {
  name               = "${var.ecs_service_name}-request-count-step"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = var.scale_out_cooldown
    metric_aggregation_type = "Average"

    # Moderate load: 1000-2000 requests per target → add 1 task
    step_adjustment {
      metric_interval_lower_bound = 0
      metric_interval_upper_bound = var.request_count_threshold_high - var.request_count_threshold_moderate
      scaling_adjustment          = 1
    }

    # High load: 2000+ requests per target → add 2 tasks
    step_adjustment {
      metric_interval_lower_bound = var.request_count_threshold_high - var.request_count_threshold_moderate
      scaling_adjustment          = 2
    }
  }
}

# CloudWatch Alarm to trigger step scaling policy
resource "aws_cloudwatch_metric_alarm" "request_count_high" {
  alarm_name          = "${var.ecs_service_name}-request-count-high"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "RequestCountPerTarget"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = var.request_count_threshold_moderate

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }

  alarm_actions = [aws_appautoscaling_policy.request_count_step.arn]

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Scheduled Scaling — Scale to zero outside demo hours
# -----------------------------------------------------------------------------

resource "aws_appautoscaling_scheduled_action" "scale_up" {
  count = var.enable_scheduled_scaling ? 1 : 0

  name               = "${var.ecs_service_name}-scheduled-scale-up"
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  schedule           = var.demo_schedule_start

  scalable_target_action {
    min_capacity = var.min_capacity
    max_capacity = var.max_capacity
  }
}

resource "aws_appautoscaling_scheduled_action" "scale_down" {
  count = var.enable_scheduled_scaling ? 1 : 0

  name               = "${var.ecs_service_name}-scheduled-scale-down"
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  schedule           = var.demo_schedule_end

  scalable_target_action {
    min_capacity = 0
    max_capacity = 0
  }
}
