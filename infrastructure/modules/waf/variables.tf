# -----------------------------------------------------------------------------
# WAF Module — Input Variables
# -----------------------------------------------------------------------------

variable "alb_arn" {
  description = "ARN of the Application Load Balancer to associate the WAF Web ACL with."
  type        = string
}

variable "rate_limit" {
  description = "Maximum number of requests allowed per 5-minute window per source IP before rate-based blocking applies."
  type        = number
  default     = 2000

  validation {
    condition     = var.rate_limit >= 100 && var.rate_limit <= 20000000
    error_message = "rate_limit must be between 100 and 20,000,000 requests per 5-minute window."
  }
}

variable "body_size_limit" {
  description = "Maximum allowed request body size in bytes. Requests with bodies exceeding this limit are blocked."
  type        = number
  default     = 8192

  validation {
    condition     = var.body_size_limit >= 1024 && var.body_size_limit <= 65536
    error_message = "body_size_limit must be between 1024 and 65536 bytes."
  }
}

variable "environment" {
  description = "Deployment environment name (used for resource naming and tagging)."
  type        = string
  default     = "demo"
}

variable "project_name" {
  description = "Project name used in resource naming."
  type        = string
  default     = "secure-multi-tier-platform"
}

variable "enable_waf_logging" {
  description = "Whether to enable WAF logging to S3."
  type        = bool
  default     = true
}

variable "waf_log_retention_days" {
  description = "Number of days to retain WAF logs in the S3 bucket before expiration."
  type        = number
  default     = 365

  validation {
    condition     = var.waf_log_retention_days >= 1 && var.waf_log_retention_days <= 3650
    error_message = "waf_log_retention_days must be between 1 and 3650."
  }
}
