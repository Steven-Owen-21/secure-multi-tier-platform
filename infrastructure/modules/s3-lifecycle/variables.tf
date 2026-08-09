###############################################################################
# S3 Lifecycle Management Module - Variables
###############################################################################

variable "project" {
  description = "Project name used for bucket naming and tagging"
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
  description = "ARN of the KMS customer-managed key used for server-side encryption on all buckets"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:kms:", var.kms_key_arn))
    error_message = "KMS key ARN must be a valid ARN starting with 'arn:aws:kms:'."
  }
}

variable "waf_log_retention_days" {
  description = "Number of days before WAF log objects expire (final expiration)"
  type        = number
  default     = 365

  validation {
    condition     = var.waf_log_retention_days > 90
    error_message = "WAF log retention must be greater than 90 days to allow Glacier transition."
  }
}

variable "waf_log_ia_transition_days" {
  description = "Number of days before WAF log objects transition to Infrequent Access"
  type        = number
  default     = 30

  validation {
    condition     = var.waf_log_ia_transition_days >= 30
    error_message = "IA transition must be at least 30 days."
  }
}

variable "waf_log_glacier_transition_days" {
  description = "Number of days before WAF log objects transition to Glacier"
  type        = number
  default     = 90

  validation {
    condition     = var.waf_log_glacier_transition_days >= 60
    error_message = "Glacier transition must be at least 60 days."
  }
}

variable "flow_log_retention_days" {
  description = "Number of days before VPC Flow Log objects expire"
  type        = number
  default     = 90

  validation {
    condition     = var.flow_log_retention_days >= 1 && var.flow_log_retention_days <= 365
    error_message = "Flow log retention must be between 1 and 365 days."
  }
}

variable "noncurrent_version_expiration_days" {
  description = "Number of days before non-current object versions are expired on versioned buckets"
  type        = number
  default     = 30

  validation {
    condition     = var.noncurrent_version_expiration_days >= 1
    error_message = "Non-current version expiration must be at least 1 day."
  }
}

variable "intelligent_tiering_archive_days" {
  description = "Number of days of no access before objects move to the archive access tier (application data bucket)"
  type        = number
  default     = 90

  validation {
    condition     = var.intelligent_tiering_archive_days >= 90
    error_message = "Archive access tier must be at least 90 days."
  }
}

variable "audit_log_retention_days" {
  description = "Number of days before audit log objects expire"
  type        = number
  default     = 365

  validation {
    condition     = var.audit_log_retention_days > 90
    error_message = "Audit log retention must be greater than 90 days to allow Glacier transition."
  }
}

variable "audit_log_ia_transition_days" {
  description = "Number of days before audit log objects transition to Infrequent Access"
  type        = number
  default     = 30
}

variable "audit_log_glacier_transition_days" {
  description = "Number of days before audit log objects transition to Glacier"
  type        = number
  default     = 90
}

variable "object_lock_retention_days" {
  description = "Number of days for Object Lock governance mode retention on audit log buckets"
  type        = number
  default     = 365

  validation {
    condition     = var.object_lock_retention_days >= 1
    error_message = "Object Lock retention must be at least 1 day."
  }
}

variable "tags" {
  description = "Additional tags to apply to all S3 resources"
  type        = map(string)
  default     = {}
}
