# -----------------------------------------------------------------------------
# ECS Fargate Module — Input Variables
# -----------------------------------------------------------------------------

variable "private_subnet_ids" {
  description = "List of private subnet IDs for ECS task placement (minimum 2 AZs required)."
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "At least 2 private subnet IDs are required for multi-AZ ECS deployment."
  }
}

variable "app_sg_id" {
  description = "Security group ID to attach to ECS tasks."
  type        = string
}

variable "target_group_arn" {
  description = "ARN of the ALB target group for ECS service registration."
  type        = string
}

variable "ecr_image_uri" {
  description = "Full ECR image URI including tag (e.g. 123456789.dkr.ecr.eu-west-2.amazonaws.com/app:latest)."
  type        = string
}

variable "environment" {
  description = "Deployment environment name (used for resource naming and environment variables)."
  type        = string
  default     = "demo"
}

variable "project_name" {
  description = "Project name used in resource naming."
  type        = string
  default     = "secure-multi-tier-platform"
}

variable "app_port" {
  description = "Port on which the application container listens."
  type        = number
  default     = 8000

  validation {
    condition     = var.app_port > 0 && var.app_port <= 65535
    error_message = "app_port must be between 1 and 65535."
  }
}

variable "desired_count" {
  description = "Desired number of ECS tasks. Minimum 2 for multi-AZ HA."
  type        = number
  default     = 2

  validation {
    condition     = var.desired_count >= 2
    error_message = "desired_count must be at least 2 for multi-AZ high availability."
  }
}

variable "cpu" {
  description = "CPU units for the Fargate task (256, 512, 1024, 2048, 4096)."
  type        = number
  default     = 256

  validation {
    condition     = contains([256, 512, 1024, 2048, 4096], var.cpu)
    error_message = "cpu must be one of: 256, 512, 1024, 2048, 4096."
  }
}

variable "memory" {
  description = "Memory in MiB for the Fargate task. Must be compatible with chosen CPU."
  type        = number
  default     = 512

  validation {
    condition     = var.memory >= 512 && var.memory <= 30720
    error_message = "memory must be between 512 and 30720 MiB."
  }
}

variable "environment_variables" {
  description = "Map of environment variables to inject into the application container."
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "Map of secret name to Secrets Manager ARN for sensitive environment variables."
  type        = map(string)
  default     = {}
}

variable "log_retention_days" {
  description = "CloudWatch log group retention period in days."
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.log_retention_days)
    error_message = "log_retention_days must be a valid CloudWatch Logs retention value."
  }
}

variable "assign_public_ip" {
  description = "Whether to assign a public IP to ECS tasks. Should be false in private subnets with NAT."
  type        = bool
  default     = false
}

variable "health_check_grace_period" {
  description = "Seconds to wait before the ECS service starts evaluating ALB health checks for a new task."
  type        = number
  default     = 60

  validation {
    condition     = var.health_check_grace_period >= 0 && var.health_check_grace_period <= 2147483647
    error_message = "health_check_grace_period must be a non-negative integer."
  }
}

variable "enable_execute_command" {
  description = "Whether to enable ECS Exec for debugging (allows shell access to running containers)."
  type        = bool
  default     = false
}

variable "aws_region" {
  description = "AWS region for CloudWatch Logs and ECR."
  type        = string
  default     = "eu-west-2"
}
