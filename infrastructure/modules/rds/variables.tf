###############################################################################
# RDS Aurora PostgreSQL Module - Variables
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

# -----------------------------------------------------------------------------
# Network Inputs
# -----------------------------------------------------------------------------

variable "private_subnet_ids" {
  description = "List of private subnet IDs for the DB subnet group (minimum 2 across different AZs)"
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "At least 2 private subnet IDs are required for Multi-AZ deployment."
  }
}

variable "db_sg_id" {
  description = "ID of the database security group (permits inbound PostgreSQL from application tier)"
  type        = string
}

# -----------------------------------------------------------------------------
# Encryption
# -----------------------------------------------------------------------------

variable "kms_key_arn" {
  description = "ARN of the KMS customer-managed key for encryption at rest"
  type        = string
}

# -----------------------------------------------------------------------------
# Database Configuration
# -----------------------------------------------------------------------------

variable "engine_version" {
  description = "Aurora PostgreSQL engine version"
  type        = string
  default     = "15.4"
}

variable "instance_class" {
  description = "DB instance class for cluster instances"
  type        = string
  default     = "db.t3.medium"
}

variable "database_name" {
  description = "Name of the default database to create"
  type        = string
  default     = "platform"

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]{0,62}$", var.database_name))
    error_message = "Database name must start with a letter and contain only alphanumeric characters and underscores (max 63 chars)."
  }
}

variable "master_username" {
  description = "Master username for the database cluster"
  type        = string
  default     = "platform_admin"
  sensitive   = true
}

variable "master_password" {
  description = "Master password for the database cluster (should be sourced from Secrets Manager in production)"
  type        = string
  sensitive   = true
}

# -----------------------------------------------------------------------------
# Backup Configuration
# -----------------------------------------------------------------------------

variable "backup_retention_period" {
  description = "Number of days to retain automated backups"
  type        = number
  default     = 7

  validation {
    condition     = var.backup_retention_period >= 1 && var.backup_retention_period <= 35
    error_message = "Backup retention period must be between 1 and 35 days."
  }
}

variable "preferred_backup_window" {
  description = "Daily time range for automated backups (UTC, format: hh:mm-hh:mm, outside business hours)"
  type        = string
  default     = "02:00-03:00"
}

variable "preferred_maintenance_window" {
  description = "Weekly maintenance window (UTC, format: ddd:hh:mm-ddd:hh:mm)"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

# -----------------------------------------------------------------------------
# Performance and Parameters
# -----------------------------------------------------------------------------

variable "max_connections" {
  description = "Maximum number of database connections"
  type        = number
  default     = 200
}

variable "shared_buffers" {
  description = "Shared buffers parameter (in 8KB pages, e.g. 32768 = 256MB)"
  type        = string
  default     = "{DBInstanceClassMemory/32768}"
}

variable "work_mem" {
  description = "Work memory per operation in KB"
  type        = string
  default     = "65536"
}

variable "log_statement" {
  description = "Controls which SQL statements are logged (none, ddl, mod, all)"
  type        = string
  default     = "mod"

  validation {
    condition     = contains(["none", "ddl", "mod", "all"], var.log_statement)
    error_message = "log_statement must be one of: none, ddl, mod, all."
  }
}

variable "log_min_duration_statement" {
  description = "Minimum statement duration (ms) before it is logged (-1 to disable)"
  type        = number
  default     = 1000
}

# -----------------------------------------------------------------------------
# Performance Insights
# -----------------------------------------------------------------------------

variable "performance_insights_retention_period" {
  description = "Number of days to retain Performance Insights data (7 or 731)"
  type        = number
  default     = 7

  validation {
    condition     = contains([7, 731], var.performance_insights_retention_period)
    error_message = "Performance Insights retention must be 7 (free tier) or 731 days."
  }
}

# -----------------------------------------------------------------------------
# Scaling
# -----------------------------------------------------------------------------

variable "reader_count" {
  description = "Number of reader instances to create"
  type        = number
  default     = 1

  validation {
    condition     = var.reader_count >= 1 && var.reader_count <= 15
    error_message = "Reader count must be between 1 and 15."
  }
}

# -----------------------------------------------------------------------------
# Tagging
# -----------------------------------------------------------------------------

variable "tags" {
  description = "Additional tags to apply to all RDS resources"
  type        = map(string)
  default     = {}
}
