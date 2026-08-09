# -----------------------------------------------------------------------------
# Monitoring Module — Outputs
# -----------------------------------------------------------------------------

output "guardduty_detector_id" {
  description = "ID of the GuardDuty detector"
  value       = aws_guardduty_detector.main.id
}

output "guardduty_detector_arn" {
  description = "ARN of the GuardDuty detector"
  value       = aws_guardduty_detector.main.arn
}

output "config_recorder_id" {
  description = "ID of the AWS Config configuration recorder"
  value       = aws_config_configuration_recorder.main.id
}

output "config_recorder_name" {
  description = "Name of the AWS Config configuration recorder"
  value       = aws_config_configuration_recorder.main.name
}

output "security_hub_arn" {
  description = "ARN of the Security Hub account subscription"
  value       = aws_securityhub_account.main.arn
}

output "config_rules" {
  description = "Map of AWS Config rule names to their ARNs"
  value = {
    encrypted_volumes = aws_config_config_rule.encrypted_volumes.arn
    rds_encryption    = aws_config_config_rule.rds_encryption_enabled.arn
    s3_sse            = aws_config_config_rule.s3_bucket_sse_enabled.arn
    vpc_flow_logs     = aws_config_config_rule.vpc_flow_logs_enabled.arn
    iam_user_policies = aws_config_config_rule.iam_user_no_policies.arn
  }
}

output "config_logs_bucket" {
  description = "Name of the S3 bucket used for AWS Config delivery"
  value       = aws_s3_bucket.config_logs.id
}

output "config_logs_bucket_arn" {
  description = "ARN of the S3 bucket used for AWS Config delivery"
  value       = aws_s3_bucket.config_logs.arn
}

output "guardduty_event_rule_arn" {
  description = "ARN of the EventBridge rule for GuardDuty HIGH/CRITICAL findings"
  value       = aws_cloudwatch_event_rule.guardduty_high_critical.arn
}

output "config_event_rule_arn" {
  description = "ARN of the EventBridge rule for Config non-compliance events"
  value       = aws_cloudwatch_event_rule.config_non_compliance.arn
}

output "securityhub_event_rule_arn" {
  description = "ARN of the EventBridge rule for Security Hub HIGH/CRITICAL findings"
  value       = aws_cloudwatch_event_rule.securityhub_high_critical.arn
}
