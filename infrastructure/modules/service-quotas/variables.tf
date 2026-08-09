variable "project_name" {
  description = "Project name used in resource naming"
  type        = string
  default     = "secure-multi-tier-platform"
}

variable "environment" {
  description = "Deployment environment (local, demo)"
  type        = string
}

variable "monitored_services" {
  description = "Map of AWS services and their quotas to monitor. Each entry contains the service code and a list of quota objects with quota_code, quota_name, and quota_value (current limit)."
  type = map(object({
    service_code = string
    quotas = list(object({
      quota_code = string
      quota_name = string
      quota_value = number
    }))
  }))
  default = {
    vpc = {
      service_code = "vpc"
      quotas = [
        {
          quota_code  = "L-407747CB"
          quota_name  = "Subnets per VPC"
          quota_value = 200
        },
        {
          quota_code  = "L-2AFB9258"
          quota_name  = "Security groups per network interface"
          quota_value = 5
        }
      ]
    }
    ecs = {
      service_code = "ecs"
      quotas = [
        {
          quota_code  = "L-9095DEDB"
          quota_name  = "Tasks per service"
          quota_value = 5000
        }
      ]
    }
    rds = {
      service_code = "rds"
      quotas = [
        {
          quota_code  = "L-952B80B8"
          quota_name  = "DB instances per cluster"
          quota_value = 16
        }
      ]
    }
    lambda = {
      service_code = "lambda"
      quotas = [
        {
          quota_code  = "L-B99A9384"
          quota_name  = "Concurrent executions"
          quota_value = 1000
        }
      ]
    }
  }
}

variable "alarm_threshold_percent" {
  description = "Percentage of quota limit at which CloudWatch alarms trigger (0-100)"
  type        = number
  default     = 80

  validation {
    condition     = var.alarm_threshold_percent > 0 && var.alarm_threshold_percent <= 100
    error_message = "Alarm threshold must be between 1 and 100."
  }
}

variable "sns_topic_arn" {
  description = "ARN of the SNS topic for quota alarm notifications"
  type        = string
}

variable "alarm_evaluation_periods" {
  description = "Number of evaluation periods before alarm triggers"
  type        = number
  default     = 1
}

variable "alarm_period_seconds" {
  description = "Period in seconds for alarm metric evaluation"
  type        = number
  default     = 300
}

variable "enable_trusted_advisor" {
  description = "Whether to enable Trusted Advisor check monitoring (requires Business or Enterprise support plan)"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to resources that support tagging"
  type        = map(string)
  default     = {}
}
