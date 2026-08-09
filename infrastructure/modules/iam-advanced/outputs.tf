###############################################################################
# IAM Advanced Module - Outputs
###############################################################################

output "permission_boundary_arn" {
  description = "ARN of the permission boundary policy applied to application roles"
  value       = aws_iam_policy.permission_boundary.arn
}

output "permission_boundary_policy_json" {
  description = "JSON representation of the permission boundary policy (useful for validation and testing)"
  value       = data.aws_iam_policy_document.permission_boundary.json
}

output "session_policy_json" {
  description = "JSON representation of the session policy for restricting access to tagged resources"
  value       = data.aws_iam_policy_document.session_policy.json
}

output "deployment_role_arn" {
  description = "ARN of the Deployment role (assumed by Pipeline role)"
  value       = aws_iam_role.deployment.arn
}

output "deployment_role_name" {
  description = "Name of the Deployment role"
  value       = aws_iam_role.deployment.name
}

output "service_role_arn" {
  description = "ARN of the Service role (assumed by ECS tasks, bounded by permission boundary)"
  value       = aws_iam_role.service.arn
}

output "service_role_name" {
  description = "Name of the Service role"
  value       = aws_iam_role.service.name
}

output "analyzer_arn" {
  description = "ARN of the IAM Access Analyzer"
  value       = aws_accessanalyzer_analyzer.platform.arn
}

output "analyzer_id" {
  description = "ID of the IAM Access Analyzer"
  value       = aws_accessanalyzer_analyzer.platform.id
}

output "application_service_policy_arn" {
  description = "ARN of the least-privilege Application_Service custom policy"
  value       = aws_iam_policy.application_service.arn
}

output "application_service_policy_json" {
  description = "JSON representation of the Application_Service policy (useful for validation and testing)"
  value       = data.aws_iam_policy_document.application_service.json
}
