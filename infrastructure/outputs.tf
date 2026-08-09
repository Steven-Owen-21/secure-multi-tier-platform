# -----------------------------------------------------------------------------
# Root Module Outputs
# -----------------------------------------------------------------------------

# --- General ---

output "aws_region" {
  description = "AWS region where resources are deployed"
  value       = var.aws_region
}

output "environment" {
  description = "Current deployment environment"
  value       = var.environment
}

output "project_name" {
  description = "Project name"
  value       = var.project_name
}

# --- Networking ---

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

# --- Compute ---

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.alb.alb_dns_name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = module.ecs.service_name
}

# --- Data Tier ---

output "rds_cluster_endpoint" {
  description = "Writer endpoint of the Aurora PostgreSQL cluster"
  value       = module.rds.cluster_endpoint
  sensitive   = true
}

output "rds_reader_endpoint" {
  description = "Reader endpoint of the Aurora PostgreSQL cluster"
  value       = module.rds.reader_endpoint
  sensitive   = true
}

output "redis_primary_endpoint" {
  description = "Primary endpoint of the ElastiCache Redis cluster"
  value       = module.elasticache.primary_endpoint
  sensitive   = true
}

# --- Auth & API ---

output "cognito_user_pool_id" {
  description = "Cognito user pool ID"
  value       = module.cognito.user_pool_id
}

output "api_gateway_endpoint" {
  description = "API Gateway invocation URL"
  value       = module.api_gateway.api_endpoint
}

# --- Security ---

output "kms_key_arn" {
  description = "ARN of the platform KMS customer-managed key"
  value       = module.kms.key_arn
}

output "waf_web_acl_arn" {
  description = "ARN of the WAF Web ACL"
  value       = module.waf.web_acl_arn
}

# --- CDN ---

output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = module.cloudfront.distribution_domain
}

# --- Observability ---

output "dashboard_arn" {
  description = "ARN of the CloudWatch operations dashboard"
  value       = module.observability.dashboard_arn
}

# --- Disaster Recovery ---

output "dr_aurora_arn" {
  description = "ARN of the cross-region DR Aurora replica"
  value       = module.disaster_recovery.dr_aurora_arn
}
