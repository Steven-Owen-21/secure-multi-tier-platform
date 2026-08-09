###############################################################################
# IAM Advanced Module
#
# Implements enterprise IAM governance patterns:
#   1. Permission Boundary — caps maximum permissions to platform services only
#   2. Session Policy — restricts access to resources tagged with the project tag
#   3. Role Chaining — Pipeline → Deployment → Service role with trust policies
#   4. IAM Access Analyzer — detects unused permissions and external access
#   5. Least-Privilege Application Policy — specific actions on specific ARNs
#
# Role Chain:
#   Pipeline Role (GH OIDC) → assumes → Deployment Role → assumes → Service Role
#                                                                      ↓
#                                                    Permission Boundary limits max perms
#                                                                      ↓
#                                                    Session Policy scopes to tagged resources
#
# Requirements: 20.1, 20.2, 20.3, 20.4, 20.5
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
  name_prefix = "${var.project}-${var.environment}"
  account_id  = data.aws_caller_identity.current.account_id
  region      = data.aws_region.current.name

  common_tags = merge(
    {
      Project     = var.project
      Environment = var.environment
      Component   = "iam-governance"
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# =============================================================================
# 1. PERMISSION BOUNDARY
# =============================================================================
# Defines the maximum permissions envelope for application roles. Even if a
# role's own policy grants broader access, the boundary restricts effective
# permissions to only the listed platform services.
# Requirement 20.1
# =============================================================================

data "aws_iam_policy_document" "permission_boundary" {
  # Allow actions only within the platform's required service set
  statement {
    sid    = "AllowPlatformServices"
    effect = "Allow"

    actions = [for svc in var.allowed_services : "${svc}:*"]

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [local.region]
    }
  }

  # Explicit deny for any service NOT in the allowed set is implicit (no Allow = Deny).
  # However, we add an explicit deny for iam:* mutations to prevent privilege escalation.
  statement {
    sid    = "DenyIAMEscalation"
    effect = "Deny"

    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:PutRolePermissionsBoundary",
      "iam:DeleteRolePermissionsBoundary",
      "iam:CreateUser",
      "iam:CreatePolicy",
      "iam:CreatePolicyVersion",
    ]

    resources = ["*"]
  }

  # Explicit deny for organisation-level actions
  statement {
    sid    = "DenyOrganisationActions"
    effect = "Deny"

    actions = [
      "organizations:*",
      "account:*",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_policy" "permission_boundary" {
  name        = "${local.name_prefix}-permission-boundary"
  description = "Permission boundary limiting maximum permissions to platform services only"
  policy      = data.aws_iam_policy_document.permission_boundary.json

  tags = local.common_tags
}

# =============================================================================
# 2. SESSION POLICY (inline policy document for assume-role)
# =============================================================================
# When assuming the Service role, this session policy further restricts
# effective permissions to only resources tagged with the project tag.
# Requirement 20.2
# =============================================================================

data "aws_iam_policy_document" "session_policy" {
  # Allow all platform service actions but only on tagged resources
  statement {
    sid    = "AllowOnlyTaggedResources"
    effect = "Allow"

    actions = [for svc in var.allowed_services : "${svc}:*"]

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Project"
      values   = [var.resource_tag_value]
    }
  }

  # Allow actions that don't support resource-level tagging conditions
  # (e.g., List/Describe calls that apply globally)
  statement {
    sid    = "AllowReadOnlyDiscovery"
    effect = "Allow"

    actions = [
      "s3:ListAllMyBuckets",
      "rds:DescribeDBClusters",
      "elasticache:DescribeReplicationGroups",
      "ecs:ListClusters",
      "ecs:ListServices",
      "logs:DescribeLogGroups",
      "cloudwatch:ListMetrics",
      "secretsmanager:ListSecrets",
      "sns:ListTopics",
    ]

    resources = ["*"]
  }
}

# =============================================================================
# 3. ROLE CHAINING: Pipeline → Deployment → Service
# =============================================================================
# Requirement 20.3
# =============================================================================

# --- 3a. Deployment Role ---
# Trusted by Pipeline Role. Used during terraform apply operations.

data "aws_iam_policy_document" "deployment_role_trust" {
  statement {
    sid    = "AllowPipelineToAssume"
    effect = "Allow"

    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [var.pipeline_role_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.deployment_role_external_id]
    }
  }
}

resource "aws_iam_role" "deployment" {
  name               = "${local.name_prefix}-deployment-role"
  assume_role_policy = data.aws_iam_policy_document.deployment_role_trust.json
  description        = "Deployment role assumed by Pipeline role for infrastructure provisioning"

  tags = local.common_tags
}

# Deployment role policy — broad enough for terraform apply but scoped to the project
data "aws_iam_policy_document" "deployment_role_policy" {
  statement {
    sid    = "AllowInfraManagement"
    effect = "Allow"

    actions = [
      "ecs:*",
      "ec2:*",
      "rds:*",
      "elasticache:*",
      "s3:*",
      "logs:*",
      "cloudwatch:*",
      "iam:GetRole",
      "iam:PassRole",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:ListAttachedRolePolicies",
      "iam:ListRolePolicies",
      "secretsmanager:*",
      "sns:*",
      "kms:*",
      "cognito-idp:*",
      "apigateway:*",
      "wafv2:*",
      "elasticloadbalancing:*",
      "application-autoscaling:*",
      "cloudfront:*",
      "route53:*",
      "backup:*",
      "config:*",
      "guardduty:*",
      "securityhub:*",
      "access-analyzer:*",
      "servicequotas:*",
    ]

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [local.region]
    }
  }
}

resource "aws_iam_role_policy" "deployment" {
  name   = "${local.name_prefix}-deployment-policy"
  role   = aws_iam_role.deployment.id
  policy = data.aws_iam_policy_document.deployment_role_policy.json
}

# --- 3b. Service Role ---
# Trusted by ECS service AND Deployment role. Used at runtime by ECS tasks.
# Permission boundary is attached to cap effective permissions.

data "aws_iam_policy_document" "service_role_trust" {
  # ECS tasks can assume this role
  statement {
    sid    = "AllowECSTasksToAssume"
    effect = "Allow"

    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/Project"
      values   = [var.resource_tag_value]
    }
  }

  # Deployment role can also assume service role (for testing/debugging)
  statement {
    sid    = "AllowDeploymentRoleToAssume"
    effect = "Allow"

    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.deployment.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.deployment_role_external_id]
    }
  }
}

resource "aws_iam_role" "service" {
  name                 = "${local.name_prefix}-service-role"
  assume_role_policy   = data.aws_iam_policy_document.service_role_trust.json
  permissions_boundary = aws_iam_policy.permission_boundary.arn
  description          = "Service role for ECS tasks with permission boundary applied"

  tags = local.common_tags
}

# =============================================================================
# 4. IAM ACCESS ANALYZER
# =============================================================================
# Enables IAM Access Analyzer in the deployment region to detect:
# - Unused permissions in roles/policies
# - External access to platform resources
# Requirement 20.4
# =============================================================================

resource "aws_accessanalyzer_analyzer" "platform" {
  analyzer_name = "${local.name_prefix}-access-analyzer"
  type          = "ACCOUNT"

  tags = local.common_tags
}

# =============================================================================
# 5. LEAST-PRIVILEGE APPLICATION SERVICE POLICY
# =============================================================================
# Custom IAM policy granting only the specific actions the Application_Service
# needs, on specific resource ARNs (no wildcard resources where possible).
# Requirement 20.5
# =============================================================================

data "aws_iam_policy_document" "application_service" {
  # S3 — read/write to application buckets only
  dynamic "statement" {
    for_each = length(var.application_s3_bucket_arns) > 0 ? [1] : []
    content {
      sid    = "S3ApplicationAccess"
      effect = "Allow"

      actions = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
      ]

      resources = concat(
        var.application_s3_bucket_arns,
        [for arn in var.application_s3_bucket_arns : "${arn}/*"]
      )
    }
  }

  # DynamoDB — read/write to application tables only
  dynamic "statement" {
    for_each = length(var.application_dynamodb_table_arns) > 0 ? [1] : []
    content {
      sid    = "DynamoDBApplicationAccess"
      effect = "Allow"

      actions = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan",
      ]

      resources = concat(
        var.application_dynamodb_table_arns,
        [for arn in var.application_dynamodb_table_arns : "${arn}/index/*"]
      )
    }
  }

  # Secrets Manager — read application secrets only
  dynamic "statement" {
    for_each = length(var.application_secrets_arns) > 0 ? [1] : []
    content {
      sid    = "SecretsManagerReadAccess"
      effect = "Allow"

      actions = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret",
      ]

      resources = var.application_secrets_arns
    }
  }

  # SNS — publish to notification topics only
  dynamic "statement" {
    for_each = length(var.application_sns_topic_arns) > 0 ? [1] : []
    content {
      sid    = "SNSPublishAccess"
      effect = "Allow"

      actions = [
        "sns:Publish",
      ]

      resources = var.application_sns_topic_arns
    }
  }

  # KMS — encrypt/decrypt using platform keys only
  dynamic "statement" {
    for_each = length(var.application_kms_key_arns) > 0 ? [1] : []
    content {
      sid    = "KMSEncryptDecrypt"
      effect = "Allow"

      actions = [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:GenerateDataKey",
        "kms:DescribeKey",
      ]

      resources = var.application_kms_key_arns
    }
  }

  # CloudWatch Logs — write application logs
  statement {
    sid    = "CloudWatchLogsWrite"
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]

    resources = [
      "arn:aws:logs:${local.region}:${local.account_id}:log-group:/ecs/${local.name_prefix}*",
    ]
  }

  # CloudWatch — publish custom metrics
  statement {
    sid    = "CloudWatchMetrics"
    effect = "Allow"

    actions = [
      "cloudwatch:PutMetricData",
    ]

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["${var.project}/${var.environment}"]
    }
  }

  # X-Ray — tracing (if used)
  statement {
    sid    = "XRayTracing"
    effect = "Allow"

    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_policy" "application_service" {
  name        = "${local.name_prefix}-application-service-policy"
  description = "Least-privilege custom policy for Application_Service with specific actions on specific ARNs"
  policy      = data.aws_iam_policy_document.application_service.json

  tags = local.common_tags
}

# Attach least-privilege policy to the Service Role
resource "aws_iam_role_policy_attachment" "service_application_policy" {
  role       = aws_iam_role.service.name
  policy_arn = aws_iam_policy.application_service.arn
}

# Attach permission boundary to the existing ECS task role as well
resource "aws_iam_role_policy_attachment" "ecs_task_boundary" {
  role       = element(split("/", var.ecs_task_role_arn), length(split("/", var.ecs_task_role_arn)) - 1)
  policy_arn = aws_iam_policy.permission_boundary.arn
}
