variable "project_name" {
  description = "Project name used in resource naming"
  type        = string
  default     = "secure-multi-tier-platform"
}

variable "environment" {
  description = "Deployment environment (local, demo)"
  type        = string
}

variable "alb_arn_suffix" {
  description = "ARN suffix of the Application Load Balancer for metric dimensions"
  type        = string
}

variable "alb_full_name" {
  description = "Full name of the ALB for CloudWatch metrics (e.g. app/my-alb/50dc6c495c0c9188)"
  type        = string
}

variable "ecs_service_name" {
  description = "Name of the ECS service for metric dimensions"
  type        = string
}

variable "ecs_cluster_name" {
  description = "Name of the ECS cluster for metric dimensions"
  type        = string
}

variable "rds_cluster_identifier" {
  description = "Identifier of the RDS Aurora cluster for metric dimensions"
  type        = string
}

variable "rds_max_connections" {
  description = "Maximum number of connections configured on the RDS cluster"
  type        = number
  default     = 100
}

variable "api_gateway_name" {
  description = "Name of the API Gateway REST API for metric dimensions"
  type        = string
}

variable "api_gateway_stage" {
  description = "API Gateway stage name for metric dimensions"
  type        = string
  default     = "production"
}

variable "elasticache_cluster_id" {
  description = "ElastiCache Redis replication group ID for metric dimensions"
  type        = string
}

variable "sns_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications"
  type        = string
}

variable "log_group_name" {
  description = "CloudWatch Logs group name for application logs (used in Logs Insights queries)"
  type        = string
  default     = "/ecs/secure-multi-tier-platform"
}

variable "api_gateway_log_group_name" {
  description = "CloudWatch Logs group name for API Gateway access logs"
  type        = string
  default     = "/aws/apigateway/secure-multi-tier-platform"
}

variable "alb_5xx_threshold" {
  description = "Percentage threshold for ALB 5xx error rate alarm"
  type        = number
  default     = 5

  validation {
    condition     = var.alb_5xx_threshold > 0 && var.alb_5xx_threshold <= 100
    error_message = "ALB 5xx threshold must be between 1 and 100."
  }
}

variable "ecs_cpu_threshold" {
  description = "Percentage threshold for ECS CPU utilisation alarm"
  type        = number
  default     = 80

  validation {
    condition     = var.ecs_cpu_threshold > 0 && var.ecs_cpu_threshold <= 100
    error_message = "ECS CPU threshold must be between 1 and 100."
  }
}

variable "db_connections_threshold_percent" {
  description = "Percentage of max_connections that triggers the DB connections alarm"
  type        = number
  default     = 80

  validation {
    condition     = var.db_connections_threshold_percent > 0 && var.db_connections_threshold_percent <= 100
    error_message = "DB connections threshold must be between 1 and 100."
  }
}

variable "anomaly_detection_band" {
  description = "Number of standard deviations for anomaly detection band on p99 latency"
  type        = number
  default     = 2
}

variable "tags" {
  description = "Tags to apply to resources that support tagging"
  type        = map(string)
  default     = {}
}
