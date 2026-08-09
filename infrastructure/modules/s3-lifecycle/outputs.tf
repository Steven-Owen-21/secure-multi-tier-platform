###############################################################################
# S3 Lifecycle Management Module - Outputs
###############################################################################

output "bucket_arns" {
  description = "List of all managed S3 bucket ARNs"
  value = [
    aws_s3_bucket.waf_logs.arn,
    aws_s3_bucket.flow_logs.arn,
    aws_s3_bucket.application_data.arn,
    aws_s3_bucket.audit_logs.arn,
  ]
}

output "bucket_names" {
  description = "List of all managed S3 bucket names"
  value = [
    aws_s3_bucket.waf_logs.id,
    aws_s3_bucket.flow_logs.id,
    aws_s3_bucket.application_data.id,
    aws_s3_bucket.audit_logs.id,
  ]
}

output "waf_logs_bucket_arn" {
  description = "ARN of the WAF logs bucket"
  value       = aws_s3_bucket.waf_logs.arn
}

output "waf_logs_bucket_name" {
  description = "Name of the WAF logs bucket"
  value       = aws_s3_bucket.waf_logs.id
}

output "flow_logs_bucket_arn" {
  description = "ARN of the VPC Flow Logs bucket"
  value       = aws_s3_bucket.flow_logs.arn
}

output "flow_logs_bucket_name" {
  description = "Name of the VPC Flow Logs bucket"
  value       = aws_s3_bucket.flow_logs.id
}

output "application_data_bucket_arn" {
  description = "ARN of the Application Data bucket"
  value       = aws_s3_bucket.application_data.arn
}

output "application_data_bucket_name" {
  description = "Name of the Application Data bucket"
  value       = aws_s3_bucket.application_data.id
}

output "audit_logs_bucket_arn" {
  description = "ARN of the Audit Logs bucket"
  value       = aws_s3_bucket.audit_logs.arn
}

output "audit_logs_bucket_name" {
  description = "Name of the Audit Logs bucket"
  value       = aws_s3_bucket.audit_logs.id
}
