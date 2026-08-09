# -----------------------------------------------------------------------------
# VPC Endpoints Module — Main Resources
# -----------------------------------------------------------------------------
# Creates VPC endpoints for private connectivity to AWS services, keeping
# traffic off the public internet:
#
# Gateway Endpoints (free, route-table-based):
#   - S3 (with restrictive endpoint policy for platform buckets only)
#   - DynamoDB
#
# Interface Endpoints (ENI-based, private DNS enabled):
#   - CloudWatch Logs (logs)
#   - Secrets Manager (secretsmanager)
#   - ECR API (ecr.api)
#   - ECR Docker (ecr.dkr)
#
# The endpoint security group (passed in via endpoint_sg_id) restricts
# inbound HTTPS (443) to the Application Service security group only.
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Component   = "vpc-endpoints"
    },
    var.tags
  )
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# Gateway Endpoint — S3
# Free to use; traffic routes via route table entries rather than ENIs.
# Endpoint policy restricts access to platform buckets only.
# -----------------------------------------------------------------------------

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.route_table_ids
  policy            = local.s3_endpoint_policy

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpce-s3"
  })
}

locals {
  # If platform bucket ARNs are provided, restrict the endpoint policy to those
  # buckets only. Otherwise, allow access to all S3 buckets (open policy).
  s3_endpoint_policy = length(var.platform_bucket_arns) > 0 ? jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowPlatformBucketsOnly"
        Effect    = "Allow"
        Principal = "*"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:DeleteObject",
          "s3:ListMultipartUploadParts",
          "s3:AbortMultipartUpload"
        ]
        Resource = flatten([
          var.platform_bucket_arns,
          [for arn in var.platform_bucket_arns : "${arn}/*"]
        ])
      },
      {
        Sid       = "DenyNonPlatformBuckets"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = "*"
        Condition = {
          StringNotEquals = {
            "aws:ResourceArn" = flatten([
              var.platform_bucket_arns,
              [for arn in var.platform_bucket_arns : "${arn}/*"]
            ])
          }
        }
      }
    ]
  }) : null
}

# -----------------------------------------------------------------------------
# Gateway Endpoint — DynamoDB
# Free to use; traffic routes via route table entries.
# -----------------------------------------------------------------------------

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.route_table_ids

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpce-dynamodb"
  })
}

# -----------------------------------------------------------------------------
# Interface Endpoint — CloudWatch Logs
# Allows ECS tasks and application to ship logs without traversing NAT.
# -----------------------------------------------------------------------------

resource "aws_vpc_endpoint" "logs" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [var.endpoint_sg_id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpce-logs"
  })
}

# -----------------------------------------------------------------------------
# Interface Endpoint — Secrets Manager
# Allows application to retrieve rotated credentials privately.
# -----------------------------------------------------------------------------

resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [var.endpoint_sg_id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpce-secretsmanager"
  })
}

# -----------------------------------------------------------------------------
# Interface Endpoint — ECR API
# Required for ECS Fargate to pull container image metadata.
# -----------------------------------------------------------------------------

resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [var.endpoint_sg_id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpce-ecr-api"
  })
}

# -----------------------------------------------------------------------------
# Interface Endpoint — ECR Docker (dkr)
# Required for ECS Fargate to pull container image layers.
# -----------------------------------------------------------------------------

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [var.endpoint_sg_id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpce-ecr-dkr"
  })
}
