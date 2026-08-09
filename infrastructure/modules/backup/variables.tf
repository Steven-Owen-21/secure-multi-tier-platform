###############################################################################
# AWS Backup Module - Variables
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

variable "kms_key_arn" {
  description = "ARN of the KMS customer-managed key for encrypting backup vaults"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:kms:", var.kms_key_arn))
    error_message = "KMS key ARN must be a valid ARN starting with arn:aws:kms:."
  }
}

variable "secondary_region" {
  description = "Secondary AWS region for cross-region backup replication"
  type        = string
  default     = "eu-west-1"
}

variable "backup_tag_key" {
  description = "Tag key used for backup resource selection"
  type        = string
  default     = "BackupEnabled"
}

variable "backup_tag_value" {
  description = "Tag value used for backup resource selection"
  type        = string
  default     = "true"
}

variable "aurora_retention_days" {
  description = "Number of days to retain Aurora backups (1-365)"
  type        = number
  default     = 7

  validation {
    condition     = var.aurora_retention_days >= 1 && var.aurora_retention_days <= 365
    error_message = "Aurora retention must be between 1 and 365 days."
  }
}

variable "ebs_retention_days" {
  description = "Number of days to retain EBS volume backups (1-365)"
  type        = number
  default     = 14

  validation {
    condition     = var.ebs_retention_days >= 1 && var.ebs_retention_days <= 365
    error_message = "EBS retention must be between 1 and 365 days."
  }
}

variable "s3_retention_days" {
  description = "Number of days to retain S3 backups (1-365)"
  type        = number
  default     = 30

  validation {
    condition     = var.s3_retention_days >= 1 && var.s3_retention_days <= 365
    error_message = "S3 retention must be between 1 and 365 days."
  }
}

variable "aurora_schedule" {
  description = "Cron expression for Aurora backup schedule (AWS Backup cron format)"
  type        = string
  default     = "cron(0 3 * * ? *)"
}

variable "ebs_schedule" {
  description = "Cron expression for EBS backup schedule (AWS Backup cron format)"
  type        = string
  default     = "cron(0 4 * * ? *)"
}

variable "s3_schedule" {
  description = "Cron expression for S3 backup schedule (AWS Backup cron format)"
  type        = string
  default     = "cron(0 5 ? * SUN *)"
}

variable "vault_lock_changeable_days" {
  description = "Number of days before vault lock policy becomes immutable (governance mode cooling-off period)"
  type        = number
  default     = 3

  validation {
    condition     = var.vault_lock_changeable_days >= 3
    error_message = "Vault lock changeable period must be at least 3 days."
  }
}

variable "vault_lock_min_retention_days" {
  description = "Minimum retention period enforced by vault lock (days)"
  type        = number
  default     = 7

  validation {
    condition     = var.vault_lock_min_retention_days >= 1
    error_message = "Minimum retention days must be at least 1."
  }
}

variable "vault_lock_max_retention_days" {
  description = "Maximum retention period enforced by vault lock (days)"
  type        = number
  default     = 365

  validation {
    condition     = var.vault_lock_max_retention_days >= 1
    error_message = "Maximum retention days must be at least 1."
  }
}

variable "tags" {
  description = "Additional tags to apply to backup resources"
  type        = map(string)
  default     = {}
}
