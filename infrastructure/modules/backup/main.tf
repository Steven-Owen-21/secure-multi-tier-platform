###############################################################################
# AWS Backup Module
#
# Implements centralised backup management with cross-region replication:
#   - Primary Backup Vault encrypted with platform KMS key
#   - Secondary Backup Vault in DR region for cross-region copies
#   - Backup plan with rules for Aurora (daily/7d), EBS (daily/14d), S3 (weekly/30d)
#   - Cross-region copy rule on all backup rules
#   - Vault Lock in governance mode on both vaults
#   - Tag-based resource selection (BackupEnabled=true)
#   - Minimum-privilege IAM role for backup operations
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

# -----------------------------------------------------------------------------
# Secondary Region Provider (for cross-region vault)
# -----------------------------------------------------------------------------

provider "aws" {
  alias  = "secondary"
  region = var.secondary_region
}

# -----------------------------------------------------------------------------
# Primary Backup Vault
# -----------------------------------------------------------------------------

resource "aws_backup_vault" "primary" {
  name        = "${var.project}-backup-vault"
  kms_key_arn = var.kms_key_arn

  tags = merge(
    {
      Name        = "${var.project}-backup-vault"
      Project     = var.project
      Environment = var.environment
      Component   = "backup"
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# -----------------------------------------------------------------------------
# Secondary Backup Vault (Cross-Region DR)
# -----------------------------------------------------------------------------

resource "aws_backup_vault" "secondary" {
  provider = aws.secondary

  name = "${var.project}-backup-vault-dr"

  tags = merge(
    {
      Name        = "${var.project}-backup-vault-dr"
      Project     = var.project
      Environment = var.environment
      Component   = "backup"
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# -----------------------------------------------------------------------------
# Vault Lock - Governance Mode (Primary)
# -----------------------------------------------------------------------------

resource "aws_backup_vault_lock_configuration" "primary" {
  backup_vault_name   = aws_backup_vault.primary.name
  changeable_for_days = var.vault_lock_changeable_days
  min_retention_days  = var.vault_lock_min_retention_days
  max_retention_days  = var.vault_lock_max_retention_days
}

# -----------------------------------------------------------------------------
# Vault Lock - Governance Mode (Secondary)
# -----------------------------------------------------------------------------

resource "aws_backup_vault_lock_configuration" "secondary" {
  provider = aws.secondary

  backup_vault_name   = aws_backup_vault.secondary.name
  changeable_for_days = var.vault_lock_changeable_days
  min_retention_days  = var.vault_lock_min_retention_days
  max_retention_days  = var.vault_lock_max_retention_days
}

# -----------------------------------------------------------------------------
# Backup Plan
# -----------------------------------------------------------------------------

resource "aws_backup_plan" "platform" {
  name = "${var.project}-backup-plan"

  # Aurora: Daily backups at 03:00 UTC, 7-day retention, cross-region copy
  rule {
    rule_name         = "aurora-daily"
    target_vault_name = aws_backup_vault.primary.name
    schedule          = var.aurora_schedule
    start_window      = 60
    completion_window = 180

    lifecycle {
      delete_after = var.aurora_retention_days
    }

    copy_action {
      destination_vault_arn = aws_backup_vault.secondary.arn

      lifecycle {
        delete_after = var.aurora_retention_days
      }
    }
  }

  # EBS: Daily backups at 04:00 UTC, 14-day retention, cross-region copy
  rule {
    rule_name         = "ebs-daily"
    target_vault_name = aws_backup_vault.primary.name
    schedule          = var.ebs_schedule
    start_window      = 60
    completion_window = 180

    lifecycle {
      delete_after = var.ebs_retention_days
    }

    copy_action {
      destination_vault_arn = aws_backup_vault.secondary.arn

      lifecycle {
        delete_after = var.ebs_retention_days
      }
    }
  }

  # S3: Weekly backups on Sunday at 05:00 UTC, 30-day retention, cross-region copy
  rule {
    rule_name         = "s3-weekly"
    target_vault_name = aws_backup_vault.primary.name
    schedule          = var.s3_schedule
    start_window      = 60
    completion_window = 480

    lifecycle {
      delete_after = var.s3_retention_days
    }

    copy_action {
      destination_vault_arn = aws_backup_vault.secondary.arn

      lifecycle {
        delete_after = var.s3_retention_days
      }
    }
  }

  tags = merge(
    {
      Name        = "${var.project}-backup-plan"
      Project     = var.project
      Environment = var.environment
      Component   = "backup"
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# -----------------------------------------------------------------------------
# IAM Role for AWS Backup (Minimum Permissions)
# -----------------------------------------------------------------------------

resource "aws_iam_role" "backup" {
  name = "${var.project}-backup-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    {
      Name        = "${var.project}-backup-role"
      Project     = var.project
      Environment = var.environment
      Component   = "backup"
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# Backup operations policy - scoped to tagged resources only
resource "aws_iam_role_policy" "backup_operations" {
  name = "${var.project}-backup-operations"
  role = aws_iam_role.backup.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BackupCreation"
        Effect = "Allow"
        Action = [
          "backup:CreateBackupPlan",
          "backup:CreateBackupSelection",
          "backup:StartBackupJob",
          "backup:StartCopyJob",
          "backup:StartRestoreJob",
          "backup:DescribeBackupJob",
          "backup:DescribeCopyJob",
          "backup:DescribeRestoreJob",
          "backup:ListBackupJobs",
          "backup:ListCopyJobs",
          "backup:ListRestoreJobs",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:ResourceTag/${var.backup_tag_key}" = var.backup_tag_value
          }
        }
      },
      {
        Sid    = "RDSBackupOperations"
        Effect = "Allow"
        Action = [
          "rds:CreateDBClusterSnapshot",
          "rds:DescribeDBClusters",
          "rds:DescribeDBClusterSnapshots",
          "rds:RestoreDBClusterFromSnapshot",
          "rds:AddTagsToResource",
          "rds:ListTagsForResource",
          "rds:CopyDBClusterSnapshot",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:ResourceTag/${var.backup_tag_key}" = var.backup_tag_value
          }
        }
      },
      {
        Sid    = "EBSBackupOperations"
        Effect = "Allow"
        Action = [
          "ec2:CreateSnapshot",
          "ec2:CreateTags",
          "ec2:DeleteSnapshot",
          "ec2:DescribeSnapshots",
          "ec2:DescribeVolumes",
          "ec2:DescribeTags",
          "ec2:CopySnapshot",
          "ec2:CreateVolume",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:ResourceTag/${var.backup_tag_key}" = var.backup_tag_value
          }
        }
      },
      {
        Sid    = "S3BackupOperations"
        Effect = "Allow"
        Action = [
          "s3:GetBucketTagging",
          "s3:GetInventoryConfiguration",
          "s3:PutInventoryConfiguration",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketVersioning",
          "s3:ListBucketVersions",
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:ResourceTag/${var.backup_tag_key}" = var.backup_tag_value
          }
        }
      },
      {
        Sid    = "KMSOperations"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:ReEncryptFrom",
          "kms:ReEncryptTo",
          "kms:DescribeKey",
          "kms:CreateGrant",
        ]
        Resource = [var.kms_key_arn]
      },
      {
        Sid    = "BackupVaultAccess"
        Effect = "Allow"
        Action = [
          "backup-storage:MountCapsule",
          "backup:TagResource",
          "backup:DescribeBackupVault",
        ]
        Resource = [
          aws_backup_vault.primary.arn,
          aws_backup_vault.secondary.arn,
        ]
      },
    ]
  })
}

# -----------------------------------------------------------------------------
# Backup Resource Selection (Tag-Based)
# -----------------------------------------------------------------------------

resource "aws_backup_selection" "tagged_resources" {
  name         = "${var.project}-tagged-resources"
  plan_id      = aws_backup_plan.platform.id
  iam_role_arn = aws_iam_role.backup.arn

  selection_tag {
    type  = "STRINGEQUALS"
    key   = var.backup_tag_key
    value = var.backup_tag_value
  }
}
