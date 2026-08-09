# -----------------------------------------------------------------------------
# Secure Multi-Tier Platform — Root Module
# -----------------------------------------------------------------------------
# This root module composes all child modules, passing outputs from upstream
# modules as inputs to downstream modules to enforce dependency ordering.
#
# Module dependency order:
#   kms → tagging → vpc → security-groups → vpc-endpoints → alb → rds →
#   elasticache → secrets-rotation → cognito → ecs → auto-scaling →
#   iam-advanced → waf → api-gateway → cloudfront → s3-lifecycle →
#   observability → monitoring → backup → service-quotas → disaster-recovery
# -----------------------------------------------------------------------------

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      Owner       = var.owner
      CostCentre  = var.cost_centre
      ManagedBy   = "terraform"
    }
  }
}

# Secondary region provider for disaster recovery resources
provider "aws" {
  alias  = "secondary"
  region = var.dr_secondary_region
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

# -----------------------------------------------------------------------------
# SNS Topic for Alerts (shared across monitoring, observability, service-quotas)
# -----------------------------------------------------------------------------

resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-${var.environment}-alerts"
}

# =============================================================================
# Foundational Modules (no upstream dependencies)
# =============================================================================

# --- KMS ---
module "kms" {
  source = "./modules/kms"

  project                = var.project_name
  environment            = var.environment
  key_administrator_arns = var.kms_key_administrator_arns
  key_user_arns          = var.kms_key_user_arns
  grant_creator_arns     = var.kms_grant_creator_arns
  tags                   = module.tagging.tags_map
}

# --- Tagging ---
module "tagging" {
  source = "./modules/tagging"

  environment = var.environment
  component   = "platform"
  owner       = var.owner
  project     = var.project_name
  cost_centre = var.cost_centre
}

# =============================================================================
# Networking Modules
# =============================================================================

# --- VPC ---
module "vpc" {
  source = "./modules/vpc"

  vpc_cidr     = var.vpc_cidr
  az_count     = var.az_count
  subnet_bits  = var.subnet_bits
  environment  = var.environment
  project_name = var.project_name
}

# --- Security Groups ---
module "security_groups" {
  source = "./modules/security-groups"

  vpc_id      = module.vpc.vpc_id
  vpc_cidr    = var.vpc_cidr
  app_port    = var.app_port
  project     = var.project_name
  environment = var.environment
  tags        = module.tagging.tags_map
}

# --- VPC Endpoints ---
module "vpc_endpoints" {
  source = "./modules/vpc-endpoints"

  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  route_table_ids    = module.vpc.private_route_table_ids
  endpoint_sg_id     = module.security_groups.endpoint_sg_id
  environment        = var.environment
  project_name       = var.project_name
  tags               = module.tagging.tags_map
}

# =============================================================================
# Load Balancer
# =============================================================================

# --- ALB ---
module "alb" {
  source = "./modules/alb"

  public_subnet_ids = module.vpc.public_subnet_ids
  alb_sg_id         = module.security_groups.alb_sg_id
  vpc_id            = module.vpc.vpc_id
  environment       = var.environment
  project_name      = var.project_name
  app_port          = var.app_port
}

# =============================================================================
# Data Tier Modules
# =============================================================================

# --- RDS Aurora PostgreSQL ---
module "rds" {
  source = "./modules/rds"

  private_subnet_ids      = module.vpc.private_subnet_ids
  db_sg_id                = module.security_groups.db_sg_id
  kms_key_arn             = module.kms.key_arn
  project                 = var.project_name
  environment             = var.environment
  master_password         = var.db_master_password
  backup_retention_period = var.db_backup_retention_days
  tags                    = module.tagging.tags_map
}

# --- ElastiCache Redis ---
module "elasticache" {
  source = "./modules/elasticache"

  private_subnet_ids = module.vpc.private_subnet_ids
  cache_sg_id        = module.security_groups.cache_sg_id
  kms_key_arn        = module.kms.key_arn
  project            = var.project_name
  environment        = var.environment
  tags               = module.tagging.tags_map
}

# =============================================================================
# Secrets Rotation
# =============================================================================

module "secrets_rotation" {
  source = "./modules/secrets-rotation"

  db_cluster_endpoint       = module.rds.cluster_endpoint
  kms_key_arn               = module.kms.key_arn
  rotation_days             = var.secrets_rotation_days
  vpc_id                    = module.vpc.vpc_id
  private_subnet_ids        = module.vpc.private_subnet_ids
  lambda_security_group_ids = [module.security_groups.app_sg_id]
  project                   = var.project_name
  environment               = var.environment
  sns_topic_arn             = aws_sns_topic.alerts.arn
  tags                      = module.tagging.tags_map
}

# =============================================================================
# Authentication
# =============================================================================

# --- Cognito ---
module "cognito" {
  source = "./modules/cognito"

  callback_urls = var.cognito_callback_urls
  logout_urls   = var.cognito_logout_urls
  environment   = var.environment
  project_name  = var.project_name
}

# =============================================================================
# Compute Modules
# =============================================================================

# --- ECS Fargate ---
module "ecs" {
  source = "./modules/ecs"

  private_subnet_ids = module.vpc.private_subnet_ids
  app_sg_id          = module.security_groups.app_sg_id
  target_group_arn   = module.alb.target_group_arn
  ecr_image_uri      = var.ecr_image_uri
  environment        = var.environment
  project_name       = var.project_name
  app_port           = var.app_port
  aws_region         = var.aws_region
}

# --- Auto Scaling ---
module "auto_scaling" {
  source = "./modules/auto-scaling"

  ecs_service_name        = module.ecs.service_name
  ecs_cluster_name        = module.ecs.cluster_name
  min_capacity            = var.ecs_min_capacity
  max_capacity            = var.ecs_max_capacity
  cpu_target              = var.ecs_cpu_target
  alb_arn_suffix          = module.alb.alb_arn
  target_group_arn_suffix = module.alb.target_group_arn
  tags                    = module.tagging.tags_map
}

# =============================================================================
# IAM Governance
# =============================================================================

# --- IAM Advanced ---
module "iam_advanced" {
  source = "./modules/iam-advanced"

  ecs_task_role_arn      = module.ecs.task_role_arn
  pipeline_role_arn      = var.pipeline_role_arn
  resource_tag_value     = var.project_name
  project                = var.project_name
  environment            = var.environment
  application_kms_key_arns = [module.kms.key_arn]
  tags                   = module.tagging.tags_map
}

# =============================================================================
# Security Modules
# =============================================================================

# --- WAF ---
module "waf" {
  source = "./modules/waf"

  alb_arn         = module.alb.alb_arn
  rate_limit      = var.waf_rate_limit
  body_size_limit = var.waf_body_size_limit
  environment     = var.environment
  project_name    = var.project_name
}

# =============================================================================
# API Management
# =============================================================================

# --- API Gateway ---
module "api_gateway" {
  source = "./modules/api-gateway"

  alb_dns_name          = module.alb.alb_dns_name
  cognito_user_pool_arn = module.cognito.user_pool_arn
  environment           = var.environment
  project_name          = var.project_name
}

# =============================================================================
# CDN
# =============================================================================

# --- CloudFront ---
module "cloudfront" {
  source = "./modules/cloudfront"

  api_gateway_endpoint = module.api_gateway.api_endpoint
  s3_static_bucket     = "${var.project_name}-${var.environment}-static"
  geo_restrictions     = var.cloudfront_geo_restrictions
  environment          = var.environment
  project_name         = var.project_name
  tags                 = module.tagging.tags_map
}

# =============================================================================
# Storage Lifecycle
# =============================================================================

# --- S3 Lifecycle ---
module "s3_lifecycle" {
  source = "./modules/s3-lifecycle"

  kms_key_arn            = module.kms.key_arn
  waf_log_retention_days  = var.waf_log_retention_days
  flow_log_retention_days = var.flow_log_retention_days
  project                = var.project_name
  environment            = var.environment
  tags                   = module.tagging.tags_map
}

# =============================================================================
# Observability
# =============================================================================

module "observability" {
  source = "./modules/observability"

  alb_arn_suffix         = module.alb.alb_arn
  alb_full_name          = module.alb.alb_dns_name
  ecs_service_name       = module.ecs.service_name
  ecs_cluster_name       = module.ecs.cluster_name
  rds_cluster_identifier = module.rds.cluster_identifier
  elasticache_cluster_id = module.elasticache.replication_group_id
  api_gateway_name       = "${var.project_name}-${var.environment}"
  sns_topic_arn          = aws_sns_topic.alerts.arn
  project_name           = var.project_name
  environment            = var.environment
  tags                   = module.tagging.tags_map
}

# =============================================================================
# Security Monitoring
# =============================================================================

# --- Monitoring (GuardDuty, Config, Security Hub) ---
module "monitoring" {
  source = "./modules/monitoring"

  sns_topic_arn = aws_sns_topic.alerts.arn
  environment   = var.environment
  project_name  = var.project_name
}

# =============================================================================
# Backup & Recovery
# =============================================================================

# --- Backup ---
module "backup" {
  source = "./modules/backup"

  kms_key_arn = module.kms.key_arn
  project     = var.project_name
  environment = var.environment
  tags        = module.tagging.tags_map
}

# =============================================================================
# Service Quotas
# =============================================================================

module "service_quotas" {
  source = "./modules/service-quotas"

  sns_topic_arn  = aws_sns_topic.alerts.arn
  project_name   = var.project_name
  environment    = var.environment
  tags           = module.tagging.tags_map
}

# =============================================================================
# Disaster Recovery
# =============================================================================

module "disaster_recovery" {
  source = "./modules/disaster-recovery"

  providers = {
    aws           = aws
    aws.secondary = aws.secondary
  }

  rds_cluster_arn = module.rds.cluster_arn
  s3_bucket_arns  = module.s3_lifecycle.bucket_arns
  s3_bucket_ids   = module.s3_lifecycle.bucket_names
  alb_dns_name    = module.alb.alb_dns_name
  project         = var.project_name
  environment     = var.environment
  dr_kms_key_arn  = var.dr_kms_key_arn
  dr_subnet_ids   = var.dr_subnet_ids
  tags            = module.tagging.tags_map
}
