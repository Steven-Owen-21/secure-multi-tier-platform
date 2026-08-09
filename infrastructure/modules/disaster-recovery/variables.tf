# -----------------------------------------------------------------------------
# Disaster Recovery Module — Input Variables
# -----------------------------------------------------------------------------

variable "project" {
  description = "Project name used in resource naming."
  type        = string
  default     = "secure-multi-tier-platform"
}

variable "environment" {
  description = "Deployment environment name (used for resource naming)."
  type        = string
  default     = "demo"
}

variable "primary_region" {
  description = "Primary AWS region for the platform."
  type        = string
  default     = "eu-west-2"
}

variable "secondary_region" {
  description = "Secondary (DR) AWS region for failover resources."
  type        = string
  default     = "eu-west-1"
}

# -----------------------------------------------------------------------------
# Aurora Cross-Region Replica
# -----------------------------------------------------------------------------

variable "rds_cluster_arn" {
  description = "ARN of the primary Aurora PostgreSQL cluster to replicate."
  type        = string
}

variable "rds_cluster_identifier" {
  description = "Identifier of the primary Aurora cluster (used for naming the replica)."
  type        = string
  default     = "secure-multi-tier-platform-aurora-cluster"
}

variable "dr_instance_class" {
  description = "Instance class for the DR Aurora read replica."
  type        = string
  default     = "db.t3.medium"
}

variable "dr_kms_key_arn" {
  description = "KMS key ARN in the secondary region for encrypting the DR replica."
  type        = string
}

variable "dr_subnet_ids" {
  description = "List of subnet IDs in the secondary region for the DR Aurora replica."
  type        = list(string)

  validation {
    condition     = length(var.dr_subnet_ids) >= 2
    error_message = "At least 2 subnet IDs are required for multi-AZ DR Aurora deployment."
  }
}

variable "dr_vpc_security_group_ids" {
  description = "Security group IDs in the secondary region for the DR Aurora replica."
  type        = list(string)
  default     = []
}

# -----------------------------------------------------------------------------
# S3 Cross-Region Replication
# -----------------------------------------------------------------------------

variable "s3_bucket_arns" {
  description = "List of S3 bucket ARNs to configure cross-region replication on."
  type        = list(string)

  validation {
    condition     = length(var.s3_bucket_arns) > 0
    error_message = "At least one S3 bucket ARN is required for cross-region replication."
  }
}

variable "s3_bucket_ids" {
  description = "List of S3 bucket IDs (names) corresponding to s3_bucket_arns, used for naming replica buckets."
  type        = list(string)
}

variable "replication_time_minutes" {
  description = "S3 Replication Time Control (RTC) SLA in minutes."
  type        = number
  default     = 15

  validation {
    condition     = var.replication_time_minutes >= 15 && var.replication_time_minutes <= 60
    error_message = "replication_time_minutes must be between 15 and 60."
  }
}

# -----------------------------------------------------------------------------
# Route53 Health Checks and Failover
# -----------------------------------------------------------------------------

variable "alb_dns_name" {
  description = "DNS name of the primary region ALB to health-check."
  type        = string
}

variable "health_check_port" {
  description = "Port for Route53 health checks against the ALB."
  type        = number
  default     = 443

  validation {
    condition     = var.health_check_port > 0 && var.health_check_port <= 65535
    error_message = "health_check_port must be between 1 and 65535."
  }
}

variable "health_check_path" {
  description = "Path for Route53 HTTP/HTTPS health checks."
  type        = string
  default     = "/health"
}

variable "health_check_protocol" {
  description = "Protocol for Route53 health checks (HTTP or HTTPS)."
  type        = string
  default     = "HTTPS"

  validation {
    condition     = contains(["HTTP", "HTTPS"], var.health_check_protocol)
    error_message = "health_check_protocol must be HTTP or HTTPS."
  }
}

variable "health_check_failure_threshold" {
  description = "Number of consecutive health check failures before Route53 considers the endpoint unhealthy."
  type        = number
  default     = 3

  validation {
    condition     = var.health_check_failure_threshold >= 1 && var.health_check_failure_threshold <= 10
    error_message = "health_check_failure_threshold must be between 1 and 10."
  }
}

variable "health_check_interval" {
  description = "Time in seconds between Route53 health check requests (10 or 30)."
  type        = number
  default     = 30

  validation {
    condition     = contains([10, 30], var.health_check_interval)
    error_message = "health_check_interval must be 10 or 30 seconds."
  }
}

variable "domain_name" {
  description = "Domain name for Route53 failover routing records."
  type        = string
  default     = ""
}

variable "hosted_zone_id" {
  description = "Route53 hosted zone ID for failover routing records."
  type        = string
  default     = ""
}

variable "primary_alb_zone_id" {
  description = "Hosted zone ID of the primary ALB (for alias record targeting)."
  type        = string
  default     = ""
}

variable "secondary_alb_dns_name" {
  description = "DNS name of the secondary region ALB for failover target."
  type        = string
  default     = ""
}

variable "secondary_alb_zone_id" {
  description = "Hosted zone ID of the secondary region ALB."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}
