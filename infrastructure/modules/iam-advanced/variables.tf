###############################################################################
# IAM Advanced Module - Variables
#
# Inputs for permission boundaries, role chaining, session policies,
# IAM Access Analyzer, and least-privilege application policies.
###############################################################################

variable "project" {
  description = "Project name used for resource naming and tag-based scoping"
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

variable "ecs_task_role_arn" {
  description = "ARN of the ECS task role to attach the permission boundary and session policy to"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:iam::\\d{12}:role/.+", var.ecs_task_role_arn))
    error_message = "ECS task role ARN must be a valid IAM role ARN."
  }
}

variable "pipeline_role_arn" {
  description = "ARN of the GitHub Actions Pipeline role (OIDC-federated) that initiates the role chain"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:iam::\\d{12}:role/.+", var.pipeline_role_arn))
    error_message = "Pipeline role ARN must be a valid IAM role ARN."
  }
}

variable "resource_tag_value" {
  description = "Value of the Project tag used for session policy resource scoping"
  type        = string
  default     = "secure-multi-tier-platform"

  validation {
    condition     = length(var.resource_tag_value) > 0
    error_message = "Resource tag value must not be empty."
  }
}

variable "deployment_role_external_id" {
  description = "External ID required when Pipeline role assumes Deployment role (prevents confused deputy)"
  type        = string
  default     = "secure-platform-deploy-ext-id"

  validation {
    condition     = length(var.deployment_role_external_id) >= 10
    error_message = "External ID must be at least 10 characters for security."
  }
}

variable "allowed_services" {
  description = "List of AWS service prefixes allowed by the permission boundary (e.g., s3, rds, elasticache)"
  type        = list(string)
  default = [
    "s3",
    "rds",
    "rds-db",
    "elasticache",
    "ecs",
    "ecr",
    "logs",
    "cloudwatch",
    "secretsmanager",
    "kms",
    "sns",
    "sqs",
    "dynamodb",
    "cognito-idp",
    "execute-api",
    "ssmmessages",
    "xray",
  ]

  validation {
    condition     = length(var.allowed_services) > 0
    error_message = "At least one service must be allowed by the permission boundary."
  }
}

variable "application_s3_bucket_arns" {
  description = "List of S3 bucket ARNs the Application_Service is permitted to access"
  type        = list(string)
  default     = []
}

variable "application_dynamodb_table_arns" {
  description = "List of DynamoDB table ARNs the Application_Service is permitted to access"
  type        = list(string)
  default     = []
}

variable "application_secrets_arns" {
  description = "List of Secrets Manager secret ARNs the Application_Service is permitted to read"
  type        = list(string)
  default     = []
}

variable "application_sns_topic_arns" {
  description = "List of SNS topic ARNs the Application_Service is permitted to publish to"
  type        = list(string)
  default     = []
}

variable "application_kms_key_arns" {
  description = "List of KMS key ARNs the Application_Service is permitted to use for encrypt/decrypt"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags to apply to IAM resources"
  type        = map(string)
  default     = {}
}
