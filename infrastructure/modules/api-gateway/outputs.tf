# -----------------------------------------------------------------------------
# API Gateway Module — Outputs
# -----------------------------------------------------------------------------

output "api_endpoint" {
  description = "Invoke URL of the API Gateway REST API (production stage)"
  value       = aws_api_gateway_stage.stages["production"].invoke_url
}

output "api_id" {
  description = "ID of the REST API"
  value       = aws_api_gateway_rest_api.main.id
}

output "api_arn" {
  description = "ARN of the REST API"
  value       = aws_api_gateway_rest_api.main.arn
}

output "api_execution_arn" {
  description = "Execution ARN of the REST API (for IAM permissions)"
  value       = aws_api_gateway_rest_api.main.execution_arn
}

output "api_key_ids" {
  description = "Map of usage plan tier to API key IDs"
  value = {
    free     = aws_api_gateway_api_key.free.id
    standard = aws_api_gateway_api_key.standard.id
    premium  = aws_api_gateway_api_key.premium.id
  }
}

output "api_key_values" {
  description = "Map of usage plan tier to API key values (sensitive)"
  sensitive   = true
  value = {
    free     = aws_api_gateway_api_key.free.value
    standard = aws_api_gateway_api_key.standard.value
    premium  = aws_api_gateway_api_key.premium.value
  }
}

output "usage_plan_ids" {
  description = "Map of usage plan tier to usage plan IDs"
  value = {
    free     = aws_api_gateway_usage_plan.free.id
    standard = aws_api_gateway_usage_plan.standard.id
    premium  = aws_api_gateway_usage_plan.premium.id
  }
}

output "stage_invoke_urls" {
  description = "Map of stage name to invoke URL"
  value = {
    for stage_name, stage in aws_api_gateway_stage.stages :
    stage_name => stage.invoke_url
  }
}

output "stage_arns" {
  description = "Map of stage name to stage ARN"
  value = {
    for stage_name, stage in aws_api_gateway_stage.stages :
    stage_name => stage.arn
  }
}

output "cloudwatch_log_group_arns" {
  description = "Map of stage name to CloudWatch log group ARN for access logs"
  value = {
    for stage_name, log_group in aws_cloudwatch_log_group.api_access_logs :
    stage_name => log_group.arn
  }
}

output "custom_domain_name" {
  description = "Custom domain name (empty if not configured)"
  value       = var.custom_domain_name != "" ? aws_api_gateway_domain_name.custom[0].domain_name : ""
}

output "custom_domain_regional_domain_name" {
  description = "Regional domain name of the custom domain (for DNS CNAME/alias records)"
  value       = var.custom_domain_name != "" ? aws_api_gateway_domain_name.custom[0].regional_domain_name : ""
}

output "custom_domain_regional_zone_id" {
  description = "Regional hosted zone ID of the custom domain (for Route53 alias records)"
  value       = var.custom_domain_name != "" ? aws_api_gateway_domain_name.custom[0].regional_zone_id : ""
}

output "authorizer_id" {
  description = "ID of the Cognito authorizer"
  value       = aws_api_gateway_authorizer.cognito.id
}
