# -----------------------------------------------------------------------------
# VPC Endpoints Module — Input Variables
# -----------------------------------------------------------------------------

variable "vpc_id" {
  description = "ID of the VPC where endpoints will be created."
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for Interface endpoint placement."
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_ids) >= 1
    error_message = "At least one private subnet ID must be provided."
  }
}

variable "route_table_ids" {
  description = "List of private route table IDs for Gateway endpoint route entries."
  type        = list(string)

  validation {
    condition     = length(var.route_table_ids) >= 1
    error_message = "At least one route table ID must be provided."
  }
}

variable "endpoint_sg_id" {
  description = "ID of the security group for Interface VPC endpoints (inbound HTTPS from App SG)."
  type        = string
}

variable "platform_bucket_arns" {
  description = "List of S3 bucket ARNs that the S3 Gateway endpoint policy restricts access to. If empty, no bucket restriction is applied."
  type        = list(string)
  default     = []
}

variable "environment" {
  description = "Deployment environment name (used for resource naming)."
  type        = string
  default     = "demo"
}

variable "project_name" {
  description = "Project name used in resource naming and tagging."
  type        = string
  default     = "secure-multi-tier-platform"
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}
