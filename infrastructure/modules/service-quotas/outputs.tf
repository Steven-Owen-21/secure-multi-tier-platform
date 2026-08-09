output "alarm_arns" {
  description = "Map of quota alarm ARNs keyed by service-quotacode"
  value       = { for key, alarm in aws_cloudwatch_metric_alarm.quota_usage : key => alarm.arn }
}

output "alarm_names" {
  description = "Map of quota alarm names keyed by service-quotacode"
  value       = { for key, alarm in aws_cloudwatch_metric_alarm.quota_usage : key => alarm.alarm_name }
}

output "lambda_function_arn" {
  description = "ARN of the quota alert formatter Lambda function"
  value       = aws_lambda_function.quota_alert_formatter.arn
}

output "lambda_function_name" {
  description = "Name of the quota alert formatter Lambda function"
  value       = aws_lambda_function.quota_alert_formatter.function_name
}

output "trusted_advisor_rule_arns" {
  description = "ARNs of the Trusted Advisor EventBridge rules (empty if Trusted Advisor is disabled)"
  value = var.enable_trusted_advisor ? {
    cost_optimisation = aws_cloudwatch_event_rule.trusted_advisor_cost[0].arn
    security          = aws_cloudwatch_event_rule.trusted_advisor_security[0].arn
    fault_tolerance   = aws_cloudwatch_event_rule.trusted_advisor_fault_tolerance[0].arn
    performance       = aws_cloudwatch_event_rule.trusted_advisor_performance[0].arn
  } : {}
}

output "sns_subscription_arn" {
  description = "ARN of the SNS subscription for quota alerts"
  value       = aws_sns_topic_subscription.quota_alerts.arn
}
