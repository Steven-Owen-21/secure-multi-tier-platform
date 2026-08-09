# -----------------------------------------------------------------------------
# General
# -----------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region for resource deployment"
  type        = string
  default     = "eu-west-2"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-\\d$", var.aws_region))
    error_message = "aws_region must be a valid AWS region identifier (e.g. eu-west-2)."
  }
}

variable "environment" {
  description = "Deployment environment (local or demo)"
  type        = string
  default     = "local"

  validation {
    condition     = contains(["local", "demo"], var.environment)
    error_message = "environment must be either 'local' or 'demo'."
  }
}

variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "secure-multi-tier-platform"
}

# -----------------------------------------------------------------------------
# Networking
# -----------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the VPC (/16)"
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0)) && endswith(var.vpc_cidr, "/16")
    error_message = "vpc_cidr must be a valid /16 CIDR block."
  }
}

variable "az_count" {
  description = "Number of Availability Zones to deploy across (minimum 2)"
  type        = number
  default     = 2

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 4
    error_message = "az_count must be between 2 and 4."
  }
}

variable "subnet_bits" {
  description = "Number of additional bits for subnet addressing (8 produces /24 subnets from /16 VPC)"
  type        = number
  default     = 8

  validation {
    condition     = var.subnet_bits >= 4 && var.subnet_bits <= 12
    error_message = "subnet_bits must be between 4 and 12."
  }
}

# -----------------------------------------------------------------------------
# Compute
# -----------------------------------------------------------------------------

variable "app_port" {
  description = "Port the application service listens on"
  type        = number
  default     = 8000

  validation {
    condition     = var.app_port > 0 && var.app_port <= 65535
    error_message = "app_port must be between 1 and 65535."
  }
}

variable "ecr_image_uri" {
  description = "Full ECR image URI for the application container (e.g. 123456789.dkr.ecr.eu-west-2.amazonaws.com/app:latest)"
  type        = string
  default     = "placeholder.dkr.ecr.eu-west-2.amazonaws.com/app:latest"
}

variable "ecs_min_capacity" {
  description = "Minimum number of ECS tasks"
  type        = number
  default     = 2

  validation {
    condition     = var.ecs_min_capacity >= 1
    error_message = "ecs_min_capacity must be at least 1."
  }
}

variable "ecs_max_capacity" {
  description = "Maximum number of ECS tasks"
  type        = number
  default     = 10

  validation {
    condition     = var.ecs_max_capacity >= 2
    error_message = "ecs_max_capacity must be at least 2."
  }
}

variable "ecs_cpu_target" {
  description = "Target CPU utilisation percentage for auto scaling target tracking"
  type        = number
  default     = 70

  validation {
    condition     = var.ecs_cpu_target > 0 && var.ecs_cpu_target <= 100
    error_message = "ecs_cpu_target must be between 1 and 100."
  }
}

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------

variable "db_master_password" {
  description = "Master password for the Aurora PostgreSQL cluster"
  type        = string
  sensitive   = true
  default     = "CHANGE_ME_IN_SECRETS_MANAGER"
}

variable "db_backup_retention_days" {
  description = "Number of days to retain automated database backups"
  type        = number
  default     = 7

  validation {
    condition     = var.db_backup_retention_days >= 1 && var.db_backup_retention_days <= 35
    error_message = "db_backup_retention_days must be between 1 and 35."
  }
}

# -----------------------------------------------------------------------------
# Secrets Rotation
# -----------------------------------------------------------------------------

variable "secrets_rotation_days" {
  description = "Number of days between automatic secret rotations"
  type        = number
  default     = 30

  validation {
    condition     = var.secrets_rotation_days >= 1 && var.secrets_rotation_days <= 365
    error_message = "secrets_rotation_days must be between 1 and 365."
  }
}

# -----------------------------------------------------------------------------
# Authentication (Cognito)
# -----------------------------------------------------------------------------

variable "cognito_callback_urls" {
  description = "List of allowed OAuth2 callback URLs for the Cognito user pool client"
  type        = list(string)
  default     = ["http://localhost:3000/callback"]

  validation {
    condition     = length(var.cognito_callback_urls) > 0
    error_message = "At least one callback URL must be provided."
  }
}

variable "cognito_logout_urls" {
  description = "List of allowed logout URLs for the Cognito user pool client"
  type        = list(string)
  default     = ["http://localhost:3000/logout"]

  validation {
    condition     = length(var.cognito_logout_urls) > 0
    error_message = "At least one logout URL must be provided."
  }
}

# -----------------------------------------------------------------------------
# WAF
# -----------------------------------------------------------------------------

variable "waf_rate_limit" {
  description = "Maximum requests per 5-minute window per source IP"
  type        = number
  default     = 2000

  validation {
    condition     = var.waf_rate_limit >= 100 && var.waf_rate_limit <= 20000000
    error_message = "waf_rate_limit must be between 100 and 20,000,000."
  }
}

variable "waf_body_size_limit" {
  description = "Maximum request body size in bytes before WAF blocks"
  type        = number
  default     = 8192

  validation {
    condition     = var.waf_body_size_limit >= 1024 && var.waf_body_size_limit <= 65536
    error_message = "waf_body_size_limit must be between 1024 and 65536 bytes."
  }
}

variable "waf_log_retention_days" {
  description = "Number of days before WAF log objects expire"
  type        = number
  default     = 365

  validation {
    condition     = var.waf_log_retention_days > 90
    error_message = "WAF log retention must be greater than 90 days."
  }
}

# -----------------------------------------------------------------------------
# Storage Lifecycle
# -----------------------------------------------------------------------------

variable "flow_log_retention_days" {
  description = "Number of days before VPC Flow Log objects expire"
  type        = number
  default     = 90

  validation {
    condition     = var.flow_log_retention_days >= 1 && var.flow_log_retention_days <= 365
    error_message = "flow_log_retention_days must be between 1 and 365."
  }
}

# -----------------------------------------------------------------------------
# CloudFront
# -----------------------------------------------------------------------------

variable "cloudfront_geo_restrictions" {
  description = "List of ISO 3166-1 alpha-2 country codes allowed to access the CloudFront distribution"
  type        = list(string)
  default = [
    "GB", "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI",
    "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT",
    "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"
  ]

  validation {
    condition     = length(var.cloudfront_geo_restrictions) > 0
    error_message = "At least one country code must be specified."
  }
}

# -----------------------------------------------------------------------------
# KMS
# -----------------------------------------------------------------------------

variable "kms_key_administrator_arns" {
  description = "IAM principal ARNs granted KMS key administration permissions"
  type        = list(string)
  default     = ["arn:aws:iam::000000000000:root"]

  validation {
    condition     = length(var.kms_key_administrator_arns) > 0
    error_message = "At least one key administrator ARN must be provided."
  }
}

variable "kms_key_user_arns" {
  description = "IAM principal ARNs granted KMS key usage (encrypt/decrypt) permissions"
  type        = list(string)
  default     = ["arn:aws:iam::000000000000:root"]

  validation {
    condition     = length(var.kms_key_user_arns) > 0
    error_message = "At least one key user ARN must be provided."
  }
}

variable "kms_grant_creator_arns" {
  description = "IAM principal ARNs granted permission to create/manage KMS grants"
  type        = list(string)
  default     = ["arn:aws:iam::000000000000:root"]

  validation {
    condition     = length(var.kms_grant_creator_arns) > 0
    error_message = "At least one grant creator ARN must be provided."
  }
}

# -----------------------------------------------------------------------------
# IAM
# -----------------------------------------------------------------------------

variable "pipeline_role_arn" {
  description = "ARN of the GitHub Actions Pipeline role (OIDC-federated) for IAM role chain"
  type        = string
  default     = "arn:aws:iam::000000000000:role/github-actions-pipeline"

  validation {
    condition     = can(regex("^arn:aws:iam::\\d{12}:role/.+", var.pipeline_role_arn))
    error_message = "pipeline_role_arn must be a valid IAM role ARN."
  }
}

# -----------------------------------------------------------------------------
# Disaster Recovery
# -----------------------------------------------------------------------------

variable "dr_secondary_region" {
  description = "Secondary AWS region for disaster recovery resources"
  type        = string
  default     = "eu-west-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-\\d$", var.dr_secondary_region))
    error_message = "dr_secondary_region must be a valid AWS region identifier."
  }
}

variable "dr_kms_key_arn" {
  description = "KMS key ARN in the secondary region for encrypting DR Aurora replica"
  type        = string
  default     = "arn:aws:kms:eu-west-1:000000000000:key/placeholder"
}

variable "dr_subnet_ids" {
  description = "List of subnet IDs in the secondary region for DR Aurora replica placement"
  type        = list(string)
  default     = ["subnet-placeholder1", "subnet-placeholder2"]

  validation {
    condition     = length(var.dr_subnet_ids) >= 2
    error_message = "At least 2 DR subnet IDs are required for multi-AZ deployment."
  }
}

# -----------------------------------------------------------------------------
# Tagging
# -----------------------------------------------------------------------------

variable "owner" {
  description = "Owner tag value for resource cost allocation"
  type        = string
  default     = "platform-team"
}

variable "cost_centre" {
  description = "Cost centre tag for billing allocation"
  type        = string
  default     = "engineering"
}
