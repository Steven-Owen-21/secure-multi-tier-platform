# -----------------------------------------------------------------------------
# API Gateway Module — Input Variables
# -----------------------------------------------------------------------------

variable "alb_dns_name" {
  description = "DNS name of the Application Load Balancer used as the backend integration endpoint."
  type        = string
}

variable "cognito_user_pool_arn" {
  description = "ARN of the Cognito user pool for API Gateway authorizer."
  type        = string
}

variable "environment" {
  description = "Deployment environment name (used for resource naming and stage creation)."
  type        = string
  default     = "demo"
}

variable "project_name" {
  description = "Project name used in resource naming."
  type        = string
  default     = "secure-multi-tier-platform"
}

variable "custom_domain_name" {
  description = "Custom domain name for the API Gateway endpoint (e.g., api.example.com)."
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "ARN of the ACM certificate for the custom domain. Required when custom_domain_name is set."
  type        = string
  default     = ""
}

variable "stages" {
  description = "List of API Gateway stage names to create."
  type        = list(string)
  default     = ["development", "staging", "production"]

  validation {
    condition     = length(var.stages) > 0
    error_message = "At least one stage must be defined."
  }
}

# -----------------------------------------------------------------------------
# Usage Plan Configuration
# -----------------------------------------------------------------------------

variable "free_tier_daily_limit" {
  description = "Daily request quota for the free usage plan."
  type        = number
  default     = 100

  validation {
    condition     = var.free_tier_daily_limit > 0
    error_message = "free_tier_daily_limit must be a positive integer."
  }
}

variable "free_tier_burst_limit" {
  description = "Burst limit (requests per second) for the free usage plan."
  type        = number
  default     = 10

  validation {
    condition     = var.free_tier_burst_limit > 0
    error_message = "free_tier_burst_limit must be a positive integer."
  }
}

variable "free_tier_rate_limit" {
  description = "Steady-state rate limit (requests per second) for the free usage plan."
  type        = number
  default     = 5
}

variable "standard_tier_daily_limit" {
  description = "Daily request quota for the standard usage plan."
  type        = number
  default     = 10000

  validation {
    condition     = var.standard_tier_daily_limit > 0
    error_message = "standard_tier_daily_limit must be a positive integer."
  }
}

variable "standard_tier_burst_limit" {
  description = "Burst limit (requests per second) for the standard usage plan."
  type        = number
  default     = 50

  validation {
    condition     = var.standard_tier_burst_limit > 0
    error_message = "standard_tier_burst_limit must be a positive integer."
  }
}

variable "standard_tier_rate_limit" {
  description = "Steady-state rate limit (requests per second) for the standard usage plan."
  type        = number
  default     = 25
}

variable "premium_tier_daily_limit" {
  description = "Daily request quota for the premium usage plan."
  type        = number
  default     = 100000

  validation {
    condition     = var.premium_tier_daily_limit > 0
    error_message = "premium_tier_daily_limit must be a positive integer."
  }
}

variable "premium_tier_burst_limit" {
  description = "Burst limit (requests per second) for the premium usage plan."
  type        = number
  default     = 200

  validation {
    condition     = var.premium_tier_burst_limit > 0
    error_message = "premium_tier_burst_limit must be a positive integer."
  }
}

variable "premium_tier_rate_limit" {
  description = "Steady-state rate limit (requests per second) for the premium usage plan."
  type        = number
  default     = 100
}

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------

variable "access_log_retention_days" {
  description = "Number of days to retain API Gateway access logs in CloudWatch."
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.access_log_retention_days)
    error_message = "access_log_retention_days must be a valid CloudWatch Logs retention period."
  }
}

variable "enable_detailed_metrics" {
  description = "Whether to enable detailed CloudWatch metrics for API Gateway."
  type        = bool
  default     = true
}
