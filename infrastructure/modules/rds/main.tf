###############################################################################
# RDS Aurora PostgreSQL Module
#
# Defines an Aurora PostgreSQL 15 cluster with:
#   - Writer + reader instance(s) in different Availability Zones
#   - Encryption at rest using KMS customer-managed key
#   - Automated backups with 7-day retention (off-hours window)
#   - Custom DB parameter group (connections, logging, performance)
#   - Private subnet deployment via DB subnet group (no public access)
#   - IAM database authentication enabled
#   - Performance Insights (7-day retention)
#   - KMS grant for Aurora encryption with encryption context
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
  cluster_identifier = "${var.project}-aurora-cluster"
  common_tags = merge(
    {
      Project     = var.project
      Environment = var.environment
      Component   = "database"
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# -----------------------------------------------------------------------------
# DB Subnet Group — deploy cluster in private subnets only
# -----------------------------------------------------------------------------

resource "aws_db_subnet_group" "aurora" {
  name        = "${var.project}-aurora-subnet-group"
  description = "Subnet group for Aurora PostgreSQL cluster - private subnets only"
  subnet_ids  = var.private_subnet_ids

  tags = merge(local.common_tags, {
    Name = "${var.project}-aurora-subnet-group"
  })
}

# -----------------------------------------------------------------------------
# Custom Cluster Parameter Group
# -----------------------------------------------------------------------------

resource "aws_rds_cluster_parameter_group" "aurora" {
  name        = "${var.project}-aurora-cluster-params"
  family      = "aurora-postgresql15"
  description = "Custom cluster parameters for ${var.project} Aurora PostgreSQL 15"

  # Logging: log statements with modifications (DDL + DML)
  parameter {
    name  = "log_statement"
    value = var.log_statement
  }

  # Logging: log queries taking longer than 1000ms
  parameter {
    name  = "log_min_duration_statement"
    value = tostring(var.log_min_duration_statement)
  }

  tags = merge(local.common_tags, {
    Name = "${var.project}-aurora-cluster-params"
  })
}

# -----------------------------------------------------------------------------
# Custom DB Parameter Group (instance-level)
# -----------------------------------------------------------------------------

resource "aws_db_parameter_group" "aurora" {
  name        = "${var.project}-aurora-instance-params"
  family      = "aurora-postgresql15"
  description = "Custom instance parameters for ${var.project} Aurora PostgreSQL 15"

  # Connection pooling: maximum connections allowed
  parameter {
    name  = "max_connections"
    value = tostring(var.max_connections)
  }

  # Performance: shared buffer pool size
  parameter {
    name  = "shared_buffers"
    value = var.shared_buffers
  }

  # Performance: work memory per operation
  parameter {
    name  = "work_mem"
    value = var.work_mem
  }

  tags = merge(local.common_tags, {
    Name = "${var.project}-aurora-instance-params"
  })
}

# -----------------------------------------------------------------------------
# KMS Grant — scoped Aurora encryption with encryption context
# -----------------------------------------------------------------------------

resource "aws_kms_grant" "aurora_encryption" {
  name              = "${var.project}-aurora-encryption-grant"
  key_id            = var.kms_key_arn
  grantee_principal = "rds.${data.aws_region.current.name}.amazonaws.com"

  operations = [
    "Encrypt",
    "Decrypt",
    "GenerateDataKey",
    "GenerateDataKeyWithoutPlaintext",
    "ReEncryptFrom",
    "ReEncryptTo",
    "DescribeKey",
    "CreateGrant",
  ]

  constraints {
    encryption_context_equals = {
      "Project"   = var.project
      "Component" = "database"
    }
  }

  retiring_principal = "rds.${data.aws_region.current.name}.amazonaws.com"
}

# -----------------------------------------------------------------------------
# Aurora PostgreSQL Cluster
# -----------------------------------------------------------------------------

resource "aws_rds_cluster" "aurora" {
  cluster_identifier = local.cluster_identifier
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = var.engine_version
  database_name      = var.database_name
  master_username    = var.master_username
  master_password    = var.master_password

  # Network — private subnets, no public access
  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [var.db_sg_id]

  # Encryption at rest with KMS customer-managed key
  storage_encrypted = true
  kms_key_id        = var.kms_key_arn

  # IAM database authentication
  iam_database_authentication_enabled = true

  # Backup configuration — off-hours window, 7-day retention
  backup_retention_period      = var.backup_retention_period
  preferred_backup_window      = var.preferred_backup_window
  preferred_maintenance_window = var.preferred_maintenance_window
  copy_tags_to_snapshot        = true

  # Cluster parameter group
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.aurora.name

  # Deletion protection for production workloads
  deletion_protection       = var.environment == "demo" ? false : true
  skip_final_snapshot       = var.environment == "demo" ? true : false
  final_snapshot_identifier = var.environment == "demo" ? null : "${local.cluster_identifier}-final-snapshot"

  # Enable CloudWatch log exports
  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = merge(local.common_tags, {
    Name          = local.cluster_identifier
    BackupEnabled = "true"
  })

  depends_on = [aws_kms_grant.aurora_encryption]
}

# -----------------------------------------------------------------------------
# Aurora Writer Instance
# -----------------------------------------------------------------------------

resource "aws_rds_cluster_instance" "writer" {
  identifier         = "${local.cluster_identifier}-writer"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = var.instance_class
  engine             = aws_rds_cluster.aurora.engine
  engine_version     = aws_rds_cluster.aurora.engine_version

  # Instance-level parameter group
  db_parameter_group_name = aws_db_parameter_group.aurora.name

  # No public access — deployed in private subnets
  publicly_accessible = false

  # Performance Insights — 7-day retention
  performance_insights_enabled          = true
  performance_insights_retention_period = var.performance_insights_retention_period
  performance_insights_kms_key_id       = var.kms_key_arn

  # Monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn

  # Auto minor version upgrade
  auto_minor_version_upgrade = true

  tags = merge(local.common_tags, {
    Name = "${local.cluster_identifier}-writer"
    Role = "writer"
  })
}

# -----------------------------------------------------------------------------
# Aurora Reader Instance(s) — deployed in different AZ from writer
# -----------------------------------------------------------------------------

resource "aws_rds_cluster_instance" "reader" {
  count = var.reader_count

  identifier         = "${local.cluster_identifier}-reader-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = var.instance_class
  engine             = aws_rds_cluster.aurora.engine
  engine_version     = aws_rds_cluster.aurora.engine_version

  # Instance-level parameter group
  db_parameter_group_name = aws_db_parameter_group.aurora.name

  # No public access — deployed in private subnets
  publicly_accessible = false

  # Performance Insights — 7-day retention
  performance_insights_enabled          = true
  performance_insights_retention_period = var.performance_insights_retention_period
  performance_insights_kms_key_id       = var.kms_key_arn

  # Monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn

  # Promotion tier — readers have lower priority than writer
  promotion_tier = count.index + 1

  # Auto minor version upgrade
  auto_minor_version_upgrade = true

  tags = merge(local.common_tags, {
    Name = "${local.cluster_identifier}-reader-${count.index + 1}"
    Role = "reader"
  })
}

# -----------------------------------------------------------------------------
# IAM Role for Enhanced Monitoring
# -----------------------------------------------------------------------------

resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "${var.project}-rds-enhanced-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${var.project}-rds-enhanced-monitoring"
  })
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  role       = aws_iam_role.rds_enhanced_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
