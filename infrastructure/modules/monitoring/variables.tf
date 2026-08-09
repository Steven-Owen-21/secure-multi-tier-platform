# -----------------------------------------------------------------------------
# Monitoring Module — Input Variables
# -----------------------------------------------------------------------------

variable "sns_topic_arn" {
  description = "ARN of the SNS topic for security alert notifications (HIGH/CRITICAL findings from GuardDuty, Config, and Security Hub)."
  type        = string
}

variable "environment" {
  description = "Deployment environment name (used for resource naming and tagging)."
  type        = string
  default     = "demo"

  validation {
    condition     = contains(["local", "demo"], var.environment)
    error_message = "environment must be either 'local' or 'demo'."
  }
}

variable "project_name" {
  description = "Project name used in resource naming."
  type        = string
  default     = "secure-multi-tier-platform"
}

variable "enable_guardduty" {
  description = "Whether to enable GuardDuty threat detection. Set to false for LocalStack/local development."
  type        = bool
  default     = true
}

variable "enable_config" {
  description = "Whether to enable AWS Config compliance monitoring. Set to false for LocalStack/local development."
  type        = bool
  default     = true
}

variable "enable_security_hub" {
  description = "Whether to enable Security Hub for aggregated findings. Set to false for LocalStack/local development."
  type        = bool
  default     = true
}
