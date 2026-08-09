###############################################################################
# ElastiCache Redis Module - Variables
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

variable "private_subnet_ids" {
  description = "List of private subnet IDs across multiple AZs for the ElastiCache subnet group"
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "At least 2 private subnet IDs are required for multi-AZ deployment."
  }
}

variable "cache_sg_id" {
  description = "Security group ID permitting inbound Redis traffic (port 6379) from the application tier"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS customer-managed key for encryption at rest"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:kms:", var.kms_key_arn))
    error_message = "KMS key ARN must be a valid ARN starting with 'arn:aws:kms:'."
  }
}

variable "node_type" {
  description = "ElastiCache node instance type"
  type        = string
  default     = "cache.t3.micro"
}

variable "engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.1"
}

variable "num_cache_clusters" {
  description = "Number of cache clusters (primary + replicas) in the replication group"
  type        = number
  default     = 2

  validation {
    condition     = var.num_cache_clusters >= 2 && var.num_cache_clusters <= 6
    error_message = "Number of cache clusters must be between 2 and 6 (primary + at least 1 replica)."
  }
}

variable "port" {
  description = "Port number for the Redis cluster"
  type        = number
  default     = 6379
}

variable "maintenance_window" {
  description = "Weekly maintenance window (UTC) for the replication group"
  type        = string
  default     = "sun:03:00-sun:04:00"
}

variable "snapshot_retention_days" {
  description = "Number of days to retain automatic snapshots (0 to disable)"
  type        = number
  default     = 7

  validation {
    condition     = var.snapshot_retention_days >= 0 && var.snapshot_retention_days <= 35
    error_message = "Snapshot retention must be between 0 and 35 days."
  }
}

variable "snapshot_window" {
  description = "Daily time range for automatic snapshots (UTC)"
  type        = string
  default     = "02:00-03:00"
}

variable "maxmemory_policy" {
  description = "Redis maxmemory eviction policy"
  type        = string
  default     = "allkeys-lru"

  validation {
    condition = contains([
      "allkeys-lru", "allkeys-lfu", "allkeys-random",
      "volatile-lru", "volatile-lfu", "volatile-random", "volatile-ttl",
      "noeviction"
    ], var.maxmemory_policy)
    error_message = "Invalid maxmemory policy. Must be a valid Redis eviction policy."
  }
}

variable "timeout" {
  description = "Idle connection timeout in seconds (0 to disable)"
  type        = number
  default     = 300

  validation {
    condition     = var.timeout >= 0 && var.timeout <= 86400
    error_message = "Timeout must be between 0 and 86400 seconds."
  }
}

variable "notify_keyspace_events" {
  description = "Redis keyspace event notification configuration string"
  type        = string
  default     = "Ex"
}

variable "tags" {
  description = "Additional tags to apply to all resources in this module"
  type        = map(string)
  default     = {}
}
