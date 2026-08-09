# -----------------------------------------------------------------------------
# WAF Module — Outputs
# -----------------------------------------------------------------------------

output "web_acl_arn" {
  description = "ARN of the WAF Web ACL"
  value       = aws_wafv2_web_acl.main.arn
}

output "web_acl_id" {
  description = "ID of the WAF Web ACL"
  value       = aws_wafv2_web_acl.main.id
}

output "web_acl_name" {
  description = "Name of the WAF Web ACL"
  value       = aws_wafv2_web_acl.main.name
}

output "waf_log_bucket" {
  description = "Name of the S3 bucket used for WAF logging"
  value       = var.enable_waf_logging ? aws_s3_bucket.waf_logs[0].id : null
}

output "waf_log_bucket_arn" {
  description = "ARN of the S3 bucket used for WAF logging"
  value       = var.enable_waf_logging ? aws_s3_bucket.waf_logs[0].arn : null
}

output "web_acl_capacity" {
  description = "WCU (Web ACL Capacity Units) consumed by this Web ACL"
  value       = aws_wafv2_web_acl.main.capacity
}
