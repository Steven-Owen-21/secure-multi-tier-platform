output "composite_alarm_arn" {
  description = "ARN of the composite alarm (platform-degraded)"
  value       = aws_cloudwatch_composite_alarm.platform_degraded.arn
}

output "composite_alarm_name" {
  description = "Name of the composite alarm"
  value       = aws_cloudwatch_composite_alarm.platform_degraded.alarm_name
}

output "dashboard_arn" {
  description = "ARN of the CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.platform.dashboard_arn
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.platform.dashboard_name
}

output "child_alarm_arns" {
  description = "ARNs of the child alarms feeding the composite alarm"
  value = {
    alb_5xx_rate       = aws_cloudwatch_metric_alarm.alb_5xx_rate.arn
    ecs_cpu_high       = aws_cloudwatch_metric_alarm.ecs_cpu_high.arn
    db_connections_high = aws_cloudwatch_metric_alarm.db_connections_high.arn
  }
}

output "anomaly_detection_alarm_arn" {
  description = "ARN of the API Gateway p99 latency anomaly detection alarm"
  value       = aws_cloudwatch_metric_alarm.api_latency_anomaly.arn
}

output "logs_insights_query_ids" {
  description = "IDs of the saved CloudWatch Logs Insights queries"
  value = {
    slow_requests          = aws_cloudwatch_query_definition.slow_requests.query_definition_id
    auth_failures_by_ip    = aws_cloudwatch_query_definition.auth_failures_by_ip.query_definition_id
    cache_misses_by_endpoint = aws_cloudwatch_query_definition.cache_misses_by_endpoint.query_definition_id
  }
}

output "contributor_insights_rule_names" {
  description = "Names of the Contributor Insights rules"
  value = {
    top_callers       = "${var.project_name}-top-callers-by-request-count"
    top_error_sources = "${var.project_name}-top-error-sources-by-path"
  }
}

output "contributor_insights_stack_ids" {
  description = "CloudFormation stack IDs for Contributor Insights rules"
  value = {
    top_callers       = aws_cloudformation_stack.contributor_insights_top_callers.id
    top_error_sources = aws_cloudformation_stack.contributor_insights_top_errors.id
  }
}
