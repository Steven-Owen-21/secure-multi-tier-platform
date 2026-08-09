###############################################################################
# KMS Encryption Governance Module
#
# Defines a single customer-managed KMS key with a structured key policy
# implementing three principal categories:
#   - Key Administrators (Pipeline role): full key management
#   - Key Users (ECS task role, RDS service): encrypt/decrypt operations
#   - Grant Creators (Deployment role): grant lifecycle management
#
# Enables automatic annual key rotation and restricts usage via condition
# keys (encryption context and ViaService).
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
# KMS Key Policy Document
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "key_policy" {
  # Root account statement - required for key policy to function correctly
  statement {
    sid    = "EnableRootAccountAccess"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }

  # Key Administrators - Pipeline role
  statement {
    sid    = "KeyAdministrators"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = var.key_administrator_arns
    }

    actions = [
      "kms:Create*",
      "kms:Describe*",
      "kms:Enable*",
      "kms:List*",
      "kms:Put*",
      "kms:Update*",
      "kms:Revoke*",
      "kms:Disable*",
      "kms:Delete*",
      "kms:TagResource",
      "kms:ScheduleKeyDeletion",
      "kms:CancelKeyDeletion",
    ]

    resources = ["*"]
  }

  # Key Users - ECS task role, RDS service
  # Restricted by encryption context and ViaService conditions
  statement {
    sid    = "KeyUsers"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = var.key_user_arns
    }

    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
    ]

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:EncryptionContext:Project"
      values   = [var.project]
    }

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = var.allowed_via_services
    }
  }

  # Grant Creators - Deployment role
  # Restricted to grants that are for AWS resources only
  statement {
    sid    = "GrantCreators"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = var.grant_creator_arns
    }

    actions = [
      "kms:CreateGrant",
      "kms:ListGrants",
      "kms:RevokeGrant",
    ]

    resources = ["*"]

    condition {
      test     = "Bool"
      variable = "kms:GrantIsForAWSResource"
      values   = ["true"]
    }
  }
}

# -----------------------------------------------------------------------------
# KMS Customer-Managed Key
# -----------------------------------------------------------------------------

resource "aws_kms_key" "platform" {
  description             = "Customer-managed key for ${var.project} platform encryption"
  deletion_window_in_days = var.deletion_window_in_days
  enable_key_rotation     = true
  rotation_period_in_days = 365
  policy                  = data.aws_iam_policy_document.key_policy.json
  multi_region            = false

  tags = merge(
    {
      Name        = "${var.project}-cmk"
      Project     = var.project
      Environment = var.environment
      Component   = "encryption"
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# -----------------------------------------------------------------------------
# KMS Alias
# -----------------------------------------------------------------------------

resource "aws_kms_alias" "platform" {
  name          = "alias/${var.project}"
  target_key_id = aws_kms_key.platform.key_id
}
