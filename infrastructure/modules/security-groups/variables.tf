###############################################################################
# Security Groups Module - Variables
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

variable "vpc_id" {
  description = "ID of the VPC in which to create security groups"
  type        = string

  validation {
    condition     = can(regex("^vpc-[a-f0-9]+$", var.vpc_id))
    error_message = "VPC ID must be a valid vpc-* identifier."
  }
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC, used for internal traffic rules"
  type        = string

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid CIDR block."
  }
}

variable "app_port" {
  description = "Port on which the Application Service listens (default 8000)"
  type        = number
  default     = 8000

  validation {
    condition     = var.app_port > 0 && var.app_port <= 65535
    error_message = "Application port must be between 1 and 65535."
  }
}

variable "tags" {
  description = "Additional tags to apply to all security group resources"
  type        = map(string)
  default     = {}
}
