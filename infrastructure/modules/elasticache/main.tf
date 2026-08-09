###############################################################################
# ElastiCache Redis Module
#
# Defines a Redis replication group with:
#   - Primary + replica across different AZs with automatic failover
#   - Encryption at rest (KMS CMK) and in transit (TLS)
#   - Deployment in private subnets via ElastiCache subnet group
#   - Custom parameter group (allkeys-lru, timeout, keyspace events)
#   - KMS grant scoped to ElastiCache with encryption context
#
# Requirements: 4.1, 4.2, 4.3, 4.4, 24.3
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  name_prefix       = "${var.project}-${var.environment}"
  replication_group = "${local.name_prefix}-redis"
}

# -----------------------------------------------------------------------------
# ElastiCache Subnet Group
# Deploys Redis nodes in private subnets across multiple AZs
# (Requirement 4.3)
# -----------------------------------------------------------------------------

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name_prefix}-redis-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = merge(
    {
      Name        = "${local.name_prefix}-redis-subnet-group"
      Project     = var.project
      Environment = var.environment
      Component   = "cache"
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# -----------------------------------------------------------------------------
# Custom Redis Parameter Group
# (Requirement 4.4)
#   - maxmemory-policy: allkeys-lru (evict least-recently-used keys)
#   - timeout: 300 seconds (close idle connections)
#   - notify-keyspace-events: enabled for cache invalidation
# -----------------------------------------------------------------------------

resource "aws_elasticache_parameter_group" "redis" {
  name        = "${local.name_prefix}-redis-params"
  family      = "redis7"
  description = "Custom parameter group for ${var.project} Redis cluster"

  parameter {
    name  = "maxmemory-policy"
    value = var.maxmemory_policy
  }

  parameter {
    name  = "timeout"
    value = tostring(var.timeout)
  }

  parameter {
    name  = "notify-keyspace-events"
    value = var.notify_keyspace_events
  }

  tags = merge(
    {
      Name        = "${local.name_prefix}-redis-params"
      Project     = var.project
      Environment = var.environment
      Component   = "cache"
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# -----------------------------------------------------------------------------
# KMS Grant for ElastiCache Encryption
# (Requirement 24.3)
# Scoped to the ElastiCache service principal with encryption context
# restricting usage to this project's cache component.
# -----------------------------------------------------------------------------

resource "aws_kms_grant" "elasticache" {
  name              = "${local.name_prefix}-elasticache-grant"
  key_id            = var.kms_key_arn
  grantee_principal = "elasticache.${data.aws_region.current.name}.amazonaws.com"

  operations = [
    "Encrypt",
    "Decrypt",
    "GenerateDataKey",
    "ReEncryptFrom",
    "ReEncryptTo",
    "DescribeKey",
    "CreateGrant",
  ]

  constraints {
    encryption_context_equals = {
      Project   = var.project
      Component = "cache"
    }
  }
}

# -----------------------------------------------------------------------------
# ElastiCache Redis Replication Group
# (Requirements 4.1, 4.2)
#   - Primary + replica in different AZs
#   - Automatic failover enabled
#   - Encryption at rest (KMS CMK) and in transit (TLS)
# -----------------------------------------------------------------------------

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = local.replication_group
  description          = "Redis replication group for ${var.project} platform caching and session management"

  # Engine configuration
  engine               = "redis"
  engine_version       = var.engine_version
  node_type            = var.node_type
  port                 = var.port
  parameter_group_name = aws_elasticache_parameter_group.redis.name

  # Multi-AZ and failover (Requirement 4.1)
  num_cache_clusters   = var.num_cache_clusters
  automatic_failover_enabled = true
  multi_az_enabled           = true

  # Network — deploy in private subnets (Requirement 4.3)
  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [var.cache_sg_id]

  # Encryption at rest — KMS CMK (Requirement 4.2)
  at_rest_encryption_enabled = true
  kms_key_id                 = var.kms_key_arn

  # Encryption in transit — TLS (Requirement 4.2)
  transit_encryption_enabled = true

  # Maintenance and snapshots
  maintenance_window       = var.maintenance_window
  snapshot_retention_limit = var.snapshot_retention_days
  snapshot_window          = var.snapshot_window

  # Operational settings
  auto_minor_version_upgrade = true
  apply_immediately          = false

  tags = merge(
    {
      Name        = local.replication_group
      Project     = var.project
      Environment = var.environment
      Component   = "cache"
      ManagedBy   = "terraform"
    },
    var.tags
  )

  depends_on = [aws_kms_grant.elasticache]
}
