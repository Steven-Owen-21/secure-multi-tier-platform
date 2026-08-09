variable "ecs_service_name" {
  description = "Name of the ECS service to apply auto scaling to"
  type        = string
}

variable "ecs_cluster_name" {
  description = "Name of the ECS cluster containing the service"
  type        = string
}

variable "min_capacity" {
  description = "Minimum number of ECS tasks for the service"
  type        = number
  default     = 2

  validation {
    condition     = var.min_capacity >= 0
    error_message = "Minimum capacity must be zero or greater."
  }
}

variable "max_capacity" {
  description = "Maximum number of ECS tasks for the service"
  type        = number
  default     = 10

  validation {
    condition     = var.max_capacity >= 1
    error_message = "Maximum capacity must be at least 1."
  }
}

variable "cpu_target" {
  description = "Target CPU utilisation percentage for target tracking policy"
  type        = number
  default     = 70

  validation {
    condition     = var.cpu_target > 0 && var.cpu_target <= 100
    error_message = "CPU target must be between 1 and 100."
  }
}

variable "scale_out_cooldown" {
  description = "Cooldown period in seconds after a scale-out activity"
  type        = number
  default     = 60
}

variable "scale_in_cooldown" {
  description = "Cooldown period in seconds after a scale-in activity"
  type        = number
  default     = 300
}

variable "alb_arn_suffix" {
  description = "ARN suffix of the ALB for request count metrics"
  type        = string
}

variable "target_group_arn_suffix" {
  description = "ARN suffix of the ALB target group for request count metrics"
  type        = string
}

variable "request_count_threshold_moderate" {
  description = "RequestCountPerTarget threshold for moderate load (add 1 task)"
  type        = number
  default     = 1000
}

variable "request_count_threshold_high" {
  description = "RequestCountPerTarget threshold for high load (add 2 tasks)"
  type        = number
  default     = 2000
}

variable "demo_schedule_start" {
  description = "Cron expression for scaling up at start of demo hours (UTC)"
  type        = string
  default     = "cron(0 9 ? * MON-FRI *)"
}

variable "demo_schedule_end" {
  description = "Cron expression for scaling down at end of demo hours (UTC)"
  type        = string
  default     = "cron(0 18 ? * MON-FRI *)"
}

variable "enable_scheduled_scaling" {
  description = "Whether to enable scheduled scaling rules for cost safety"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to resources that support tagging"
  type        = map(string)
  default     = {}
}
