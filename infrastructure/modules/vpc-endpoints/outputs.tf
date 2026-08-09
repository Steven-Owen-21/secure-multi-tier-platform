# -----------------------------------------------------------------------------
# VPC Endpoints Module — Outputs
# -----------------------------------------------------------------------------

output "endpoint_ids" {
  description = "Map of endpoint service names to their VPC endpoint IDs"
  value = {
    s3             = aws_vpc_endpoint.s3.id
    dynamodb       = aws_vpc_endpoint.dynamodb.id
    logs           = aws_vpc_endpoint.logs.id
    secretsmanager = aws_vpc_endpoint.secretsmanager.id
    ecr_api        = aws_vpc_endpoint.ecr_api.id
    ecr_dkr        = aws_vpc_endpoint.ecr_dkr.id
  }
}

output "s3_endpoint_id" {
  description = "ID of the S3 Gateway VPC endpoint"
  value       = aws_vpc_endpoint.s3.id
}

output "dynamodb_endpoint_id" {
  description = "ID of the DynamoDB Gateway VPC endpoint"
  value       = aws_vpc_endpoint.dynamodb.id
}

output "logs_endpoint_id" {
  description = "ID of the CloudWatch Logs Interface VPC endpoint"
  value       = aws_vpc_endpoint.logs.id
}

output "secretsmanager_endpoint_id" {
  description = "ID of the Secrets Manager Interface VPC endpoint"
  value       = aws_vpc_endpoint.secretsmanager.id
}

output "ecr_api_endpoint_id" {
  description = "ID of the ECR API Interface VPC endpoint"
  value       = aws_vpc_endpoint.ecr_api.id
}

output "ecr_dkr_endpoint_id" {
  description = "ID of the ECR Docker Interface VPC endpoint"
  value       = aws_vpc_endpoint.ecr_dkr.id
}

output "s3_endpoint_prefix_list_id" {
  description = "Prefix list ID for the S3 Gateway endpoint (useful for security group rules)"
  value       = aws_vpc_endpoint.s3.prefix_list_id
}

output "dynamodb_endpoint_prefix_list_id" {
  description = "Prefix list ID for the DynamoDB Gateway endpoint (useful for security group rules)"
  value       = aws_vpc_endpoint.dynamodb.prefix_list_id
}
