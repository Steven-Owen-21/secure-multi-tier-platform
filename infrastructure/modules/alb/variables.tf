# -----------------------------------------------------------------------------
# ALB Module — Input Variables
# -----------------------------------------------------------------------------

variable "public_subnet_ids" {
  description = "List of public subnet IDs for ALB placement (minimum 2 AZs required)."
  type        = list(string)

  validation {
    condition     = length(var.public_subnet_ids) >= 2
    error_message = "At least 2 public subnet IDs are required for multi-AZ ALB deployment."
  }
}

variable "alb_sg_id" {
  description = "Security group ID to attach to the ALB."
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC where the ALB target group will be created."
  type        = string
}

variable "environment" {
  description = "Deployment environment name (used for resource naming)."
  type        = string
  default     = "demo"
}

variable "project_name" {
  description = "Project name used in resource naming."
  type        = string
  default     = "secure-multi-tier-platform"
}

variable "app_port" {
  description = "Port on which the application containers listen."
  type        = number
  default     = 8000

  validation {
    condition     = var.app_port > 0 && var.app_port <= 65535
    error_message = "app_port must be between 1 and 65535."
  }
}

variable "health_check_path" {
  description = "Path for ALB health checks against target instances."
  type        = string
  default     = "/health"
}

variable "health_check_healthy_threshold" {
  description = "Number of consecutive successful health checks before marking target healthy."
  type        = number
  default     = 2

  validation {
    condition     = var.health_check_healthy_threshold >= 2 && var.health_check_healthy_threshold <= 10
    error_message = "health_check_healthy_threshold must be between 2 and 10."
  }
}

variable "health_check_unhealthy_threshold" {
  description = "Number of consecutive failed health checks before marking target unhealthy."
  type        = number
  default     = 3

  validation {
    condition     = var.health_check_unhealthy_threshold >= 2 && var.health_check_unhealthy_threshold <= 10
    error_message = "health_check_unhealthy_threshold must be between 2 and 10."
  }
}

variable "health_check_interval" {
  description = "Time in seconds between health check attempts."
  type        = number
  default     = 30

  validation {
    condition     = var.health_check_interval >= 5 && var.health_check_interval <= 300
    error_message = "health_check_interval must be between 5 and 300 seconds."
  }
}

variable "health_check_timeout" {
  description = "Time in seconds to wait for a health check response before considering it failed."
  type        = number
  default     = 5

  validation {
    condition     = var.health_check_timeout >= 2 && var.health_check_timeout <= 120
    error_message = "health_check_timeout must be between 2 and 120 seconds."
  }
}

variable "enable_deletion_protection" {
  description = "Whether to enable deletion protection on the ALB. Set to true for production workloads."
  type        = bool
  default     = false
}

variable "enable_access_logging" {
  description = "Whether to enable access logging to an S3 bucket."
  type        = bool
  default     = false
}

variable "access_log_bucket_name" {
  description = "S3 bucket name for ALB access logs. Required when enable_access_logging is true."
  type        = string
  default     = ""
}

variable "access_log_prefix" {
  description = "S3 key prefix for ALB access logs."
  type        = string
  default     = "alb-logs"
}

variable "deregistration_delay" {
  description = "Time in seconds to wait before deregistering a target (allows in-flight requests to complete)."
  type        = number
  default     = 30

  validation {
    condition     = var.deregistration_delay >= 0 && var.deregistration_delay <= 3600
    error_message = "deregistration_delay must be between 0 and 3600 seconds."
  }
}
