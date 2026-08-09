output "scaling_policy_arns" {
  description = "ARNs of all auto scaling policies"
  value = {
    cpu_target_tracking = aws_appautoscaling_policy.cpu_target_tracking.arn
    request_count_step  = aws_appautoscaling_policy.request_count_step.arn
  }
}

output "scalable_target_id" {
  description = "The ID of the Application Auto Scaling scalable target"
  value       = aws_appautoscaling_target.ecs.id
}

output "request_count_alarm_arn" {
  description = "ARN of the CloudWatch alarm triggering step scaling"
  value       = aws_cloudwatch_metric_alarm.request_count_high.arn
}

output "scheduled_action_arns" {
  description = "ARNs of scheduled scaling actions (empty if disabled)"
  value = var.enable_scheduled_scaling ? {
    scale_up   = aws_appautoscaling_scheduled_action.scale_up[0].arn
    scale_down = aws_appautoscaling_scheduled_action.scale_down[0].arn
  } : {}
}
