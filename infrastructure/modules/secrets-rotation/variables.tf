###############################################################################
# Secrets Manager Rotation Module - Variables
###############################################################################

variable "project" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "secure-multi-tier-platform"

  validation {
    condition     = length(var.project) > 0 && length(var.project) <= 64
    error_message = "Project name must be between 1 and 64 characters."
  }
}

variable "environment" {
  description = "Deployment environment (local, demo)"
  type        = string
  default     = "demo"

  validation {
    condition     = contains(["local", "demo"], var.environment)
    error_message = "Environment must be 'local' or 'demo'."
  }
}

variable "db_cluster_endpoint" {
  description = "Aurora PostgreSQL cluster writer endpoint for the rotation Lambda to connect to"
  type        = string

  validation {
    condition     = length(var.db_cluster_endpoint) > 0
    error_message = "Database cluster endpoint must not be empty."
  }
}

variable "db_cluster_port" {
  description = "Port number for the Aurora PostgreSQL cluster"
  type        = number
  default     = 5432

  validation {
    condition     = var.db_cluster_port > 0 && var.db_cluster_port <= 65535
    error_message = "Port must be between 1 and 65535."
  }
}

variable "db_name" {
  description = "Name of the database for credential rotation"
  type        = string
  default     = "platform"

  validation {
    condition     = length(var.db_name) > 0 && length(var.db_name) <= 63
    error_message = "Database name must be between 1 and 63 characters."
  }
}

variable "db_master_username" {
  description = "Master username for the database (used in the initial secret value)"
  type        = string
  default     = "platform_admin"

  validation {
    condition     = length(var.db_master_username) > 0 && length(var.db_master_username) <= 63
    error_message = "Master username must be between 1 and 63 characters."
  }
}

variable "kms_key_arn" {
  description = "ARN of the KMS customer-managed key for encrypting secrets"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:kms:", var.kms_key_arn))
    error_message = "KMS key ARN must be a valid ARN starting with 'arn:aws:kms:'."
  }
}

variable "rotation_days" {
  description = "Number of days between automatic secret rotations"
  type        = number
  default     = 30

  validation {
    condition     = var.rotation_days >= 1 && var.rotation_days <= 365
    error_message = "Rotation days must be between 1 and 365."
  }
}

variable "vpc_id" {
  description = "VPC ID where the rotation Lambda will be deployed"
  type        = string

  validation {
    condition     = can(regex("^vpc-", var.vpc_id))
    error_message = "VPC ID must start with 'vpc-'."
  }
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for the rotation Lambda function"
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_ids) >= 1
    error_message = "At least one private subnet ID must be provided."
  }
}

variable "lambda_security_group_ids" {
  description = "List of security group IDs to attach to the rotation Lambda"
  type        = list(string)

  validation {
    condition     = length(var.lambda_security_group_ids) >= 1
    error_message = "At least one security group ID must be provided."
  }
}

variable "sns_topic_arn" {
  description = "ARN of the SNS topic for rotation failure notifications"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to apply to all resources in this module"
  type        = map(string)
  default     = {}
}
