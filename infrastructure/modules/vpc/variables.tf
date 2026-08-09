# -----------------------------------------------------------------------------
# VPC Module — Input Variables
# -----------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the VPC. Must be a /16 network."
  type        = string

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0)) && endswith(var.vpc_cidr, "/16")
    error_message = "vpc_cidr must be a valid /16 CIDR block (e.g. 10.0.0.0/16)."
  }
}

variable "az_count" {
  description = "Number of Availability Zones to deploy subnets across (minimum 2)."
  type        = number
  default     = 2

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 4
    error_message = "az_count must be between 2 and 4."
  }
}

variable "subnet_bits" {
  description = "Number of additional bits to add to the VPC CIDR for subnet addressing. A value of 8 produces /24 subnets from a /16 VPC."
  type        = number
  default     = 8

  validation {
    condition     = var.subnet_bits >= 4 && var.subnet_bits <= 12
    error_message = "subnet_bits must be between 4 and 12."
  }
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

variable "flow_log_retention_days" {
  description = "Number of days to retain VPC Flow Logs in CloudWatch."
  type        = number
  default     = 30

  validation {
    condition     = var.flow_log_retention_days >= 1
    error_message = "flow_log_retention_days must be at least 1."
  }
}
