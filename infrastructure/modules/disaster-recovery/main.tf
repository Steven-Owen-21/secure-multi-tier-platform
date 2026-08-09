# -----------------------------------------------------------------------------
# Disaster Recovery Module — Main Resources
# -----------------------------------------------------------------------------
# Implements cross-region disaster recovery with:
#   - Aurora PostgreSQL cross-region read replica (secondary region)
#   - S3 cross-region replication with 15-minute RTC SLA
#   - Route53 health checks on primary ALB (failure threshold 3, interval 30s)
#   - Route53 failover routing policies (primary → secondary on failure)
#
# Architecture:
#   Primary Region (eu-west-2): ALB + Aurora writer + S3 buckets
#   Secondary Region (eu-west-1): Aurora read replica + S3 replicated buckets
#   Route53: health check → failover routing
#
# Requirements: 9.2, 9.3, 9.4, 9.5
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = ">= 5.0"
      configuration_aliases = [aws.secondary]
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  name_prefix = "${var.project}-${var.environment}"
  common_tags = merge(
    {
      Project     = var.project
      Environment = var.environment
      Component   = "disaster-recovery"
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# =============================================================================
# CROSS-REGION AURORA READ REPLICA (Requirement 9.2)
# =============================================================================
# A cross-region Aurora read replica in the secondary region that can be
# promoted to a standalone cluster during a regional failure.
# Uses an RDS Global Cluster to manage cross-region replication.
# =============================================================================

resource "aws_rds_global_cluster" "main" {
  global_cluster_identifier    = "${local.name_prefix}-global-cluster"
  source_db_cluster_identifier = var.rds_cluster_arn
  force_destroy                = var.environment == "demo" ? true : false
}

resource "aws_rds_cluster" "dr_replica" {
  provider = aws.secondary

  cluster_identifier        = "${local.name_prefix}-aurora-dr-replica"
  engine                    = "aurora-postgresql"
  engine_mode               = "provisioned"
  global_cluster_identifier = aws_rds_global_cluster.main.id

  # Network — private subnets in secondary region
  db_subnet_group_name   = aws_db_subnet_group.dr.name
  vpc_security_group_ids = var.dr_vpc_security_group_ids

  # Encryption at rest with secondary region KMS key
  storage_encrypted = true
  kms_key_id        = var.dr_kms_key_arn

  # Backup configuration for replica (enables point-in-time recovery after promotion)
  backup_retention_period = 7

  # Deletion protection — disabled for demo
  deletion_protection       = var.environment == "demo" ? false : true
  skip_final_snapshot       = var.environment == "demo" ? true : false
  final_snapshot_identifier = var.environment == "demo" ? null : "${local.name_prefix}-dr-final-snapshot"

  # Secondary cluster must not specify master credentials
  lifecycle {
    ignore_changes = [engine_version]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-aurora-dr-replica"
    Role = "dr-replica"
  })

  depends_on = [aws_db_subnet_group.dr, aws_rds_global_cluster.main]
}

resource "aws_db_subnet_group" "dr" {
  provider = aws.secondary

  name        = "${local.name_prefix}-aurora-dr-subnet-group"
  description = "DB subnet group for Aurora DR replica in secondary region"
  subnet_ids  = var.dr_subnet_ids

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-aurora-dr-subnet-group"
  })
}

resource "aws_rds_cluster_instance" "dr_replica" {
  provider = aws.secondary

  identifier         = "${local.name_prefix}-aurora-dr-reader-1"
  cluster_identifier = aws_rds_cluster.dr_replica.id
  instance_class     = var.dr_instance_class
  engine             = aws_rds_cluster.dr_replica.engine
  engine_version     = aws_rds_cluster.dr_replica.engine_version

  publicly_accessible = false

  # Performance Insights
  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  performance_insights_kms_key_id       = var.dr_kms_key_arn

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-aurora-dr-reader-1"
    Role = "dr-replica-instance"
  })
}

# =============================================================================
# S3 CROSS-REGION REPLICATION (Requirement 9.3)
# =============================================================================
# Replicates critical S3 data to the secondary region with Replication Time
# Control (RTC) enforcing a 15-minute SLA for replication completion.
# =============================================================================

# IAM role for S3 replication
resource "aws_iam_role" "s3_replication" {
  name = "${local.name_prefix}-s3-crr-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-s3-crr-role"
  })
}

resource "aws_iam_role_policy" "s3_replication" {
  name = "${local.name_prefix}-s3-crr-policy"
  role = aws_iam_role.s3_replication.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Resource = var.s3_bucket_arns
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Resource = [for arn in var.s3_bucket_arns : "${arn}/*"]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Resource = [for i, arn in var.s3_bucket_arns : "${aws_s3_bucket.dr_replica[i].arn}/*"]
      }
    ]
  })
}

# Destination buckets in the secondary region
resource "aws_s3_bucket" "dr_replica" {
  provider = aws.secondary
  count    = length(var.s3_bucket_arns)

  bucket = "${var.s3_bucket_ids[count.index]}-dr-replica"

  tags = merge(local.common_tags, {
    Name = "${var.s3_bucket_ids[count.index]}-dr-replica"
    Role = "dr-replica"
  })
}

resource "aws_s3_bucket_versioning" "dr_replica" {
  provider = aws.secondary
  count    = length(var.s3_bucket_arns)

  bucket = aws_s3_bucket.dr_replica[count.index].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "dr_replica" {
  provider = aws.secondary
  count    = length(var.s3_bucket_arns)

  bucket = aws_s3_bucket.dr_replica[count.index].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Replication configuration on source buckets with RTC (15-minute SLA)
resource "aws_s3_bucket_replication_configuration" "source" {
  count = length(var.s3_bucket_arns)

  role   = aws_iam_role.s3_replication.arn
  bucket = var.s3_bucket_ids[count.index]

  rule {
    id     = "dr-replication-${count.index}"
    status = "Enabled"

    destination {
      bucket        = aws_s3_bucket.dr_replica[count.index].arn
      storage_class = "STANDARD"

      # Replication Time Control — 15-minute SLA
      replication_time {
        status = "Enabled"
        time {
          minutes = var.replication_time_minutes
        }
      }

      # Replication metrics for monitoring
      metrics {
        status = "Enabled"
        event_threshold {
          minutes = var.replication_time_minutes
        }
      }
    }

    # Replicate all objects
    filter {}
  }

  depends_on = [
    aws_s3_bucket_versioning.dr_replica
  ]
}

# =============================================================================
# ROUTE53 HEALTH CHECKS (Requirement 9.4)
# =============================================================================
# Monitors the primary region ALB endpoint. Failure threshold of 3 consecutive
# checks at 30-second intervals triggers failover routing.
# =============================================================================

resource "aws_route53_health_check" "primary_alb" {
  fqdn              = var.alb_dns_name
  port              = var.health_check_port
  type              = var.health_check_protocol
  resource_path     = var.health_check_path
  failure_threshold = var.health_check_failure_threshold
  request_interval  = var.health_check_interval

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-primary-alb-health-check"
  })
}

# =============================================================================
# ROUTE53 FAILOVER ROUTING (Requirement 9.5)
# =============================================================================
# Failover routing policy: primary record → secondary record when health check
# fails. Uses alias records to the ALB in each region.
# =============================================================================

resource "aws_route53_record" "primary" {
  count = var.domain_name != "" && var.hosted_zone_id != "" ? 1 : 0

  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  failover_routing_policy {
    type = "PRIMARY"
  }

  set_identifier  = "primary"
  health_check_id = aws_route53_health_check.primary_alb.id

  alias {
    name                   = var.alb_dns_name
    zone_id                = var.primary_alb_zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "secondary" {
  count = var.domain_name != "" && var.hosted_zone_id != "" ? 1 : 0

  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  failover_routing_policy {
    type = "SECONDARY"
  }

  set_identifier = "secondary"

  alias {
    name                   = var.secondary_alb_dns_name
    zone_id                = var.secondary_alb_zone_id
    evaluate_target_health = true
  }
}
