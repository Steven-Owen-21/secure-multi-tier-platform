###############################################################################
# KMS Encryption Governance Module - Variables
###############################################################################

variable "project" {
  description = "Project name used for key alias and encryption context"
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

variable "key_administrator_arns" {
  description = "List of IAM principal ARNs granted key administration permissions (e.g., Pipeline role)"
  type        = list(string)

  validation {
    condition     = length(var.key_administrator_arns) > 0
    error_message = "At least one key administrator ARN must be provided."
  }
}

variable "key_user_arns" {
  description = "List of IAM principal ARNs granted key usage (encrypt/decrypt) permissions (e.g., ECS task role, RDS service)"
  type        = list(string)

  validation {
    condition     = length(var.key_user_arns) > 0
    error_message = "At least one key user ARN must be provided."
  }
}

variable "grant_creator_arns" {
  description = "List of IAM principal ARNs granted permission to create/manage KMS grants (e.g., Deployment role)"
  type        = list(string)

  validation {
    condition     = length(var.grant_creator_arns) > 0
    error_message = "At least one grant creator ARN must be provided."
  }
}

variable "allowed_via_services" {
  description = "List of AWS service identifiers allowed to use the key via kms:ViaService condition (e.g., rds.eu-west-2.amazonaws.com)"
  type        = list(string)
  default = [
    "rds.eu-west-2.amazonaws.com",
    "elasticache.eu-west-2.amazonaws.com",
    "s3.eu-west-2.amazonaws.com",
    "backup.eu-west-2.amazonaws.com"
  ]
}

variable "deletion_window_in_days" {
  description = "Number of days before a key scheduled for deletion is permanently deleted (7-30)"
  type        = number
  default     = 30

  validation {
    condition     = var.deletion_window_in_days >= 7 && var.deletion_window_in_days <= 30
    error_message = "Deletion window must be between 7 and 30 days."
  }
}

variable "tags" {
  description = "Additional tags to apply to the KMS key and alias"
  type        = map(string)
  default     = {}
}
