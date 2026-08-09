# -----------------------------------------------------------------------------
# WAF Module — Main Resources
# -----------------------------------------------------------------------------
# Creates a WAF Web ACL attached to the ALB with:
# - AWS Managed Rule Groups: CommonRuleSet, SQLiRuleSet,
#   KnownBadInputsRuleSet, AmazonIpReputationList
# - Rate-based rule: configurable requests per 5-minute window per source IP
# - Custom rule: blocks request bodies exceeding configurable size limit
# - WAF logging to S3 with prefix structure for analysis
# - Generic 403 custom response that doesn't reveal architecture details
# -----------------------------------------------------------------------------

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# WAF Web ACL
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl" "main" {
  name        = "${local.name_prefix}-web-acl"
  description = "WAF Web ACL protecting the ALB with managed rules, rate limiting, and body size restrictions."
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # ---------------------------------------------------------------------------
  # Custom Response Bodies — Generic 403 that doesn't reveal architecture
  # ---------------------------------------------------------------------------

  custom_response_body {
    key          = "blocked-response"
    content      = "{\"error\": \"Forbidden\", \"message\": \"Your request has been blocked.\", \"status\": 403}"
    content_type = "APPLICATION_JSON"
  }

  # ---------------------------------------------------------------------------
  # Rule 1: AWS Managed Rules — Common Rule Set
  # Protects against common web exploits (XSS, path traversal, etc.)
  # ---------------------------------------------------------------------------

  rule {
    name     = "aws-managed-common-rule-set"
    priority = 10

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-common-rules"
      sampled_requests_enabled   = true
    }
  }

  # ---------------------------------------------------------------------------
  # Rule 2: AWS Managed Rules — SQL Injection Rule Set
  # Protects against SQL injection attacks
  # ---------------------------------------------------------------------------

  rule {
    name     = "aws-managed-sqli-rule-set"
    priority = 20

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-sqli-rules"
      sampled_requests_enabled   = true
    }
  }

  # ---------------------------------------------------------------------------
  # Rule 3: AWS Managed Rules — Known Bad Inputs Rule Set
  # Blocks requests with known malicious patterns (e.g., Log4j, SSRF)
  # ---------------------------------------------------------------------------

  rule {
    name     = "aws-managed-known-bad-inputs"
    priority = 30

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-known-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  # ---------------------------------------------------------------------------
  # Rule 4: AWS Managed Rules — Amazon IP Reputation List
  # Blocks requests from known malicious IP addresses
  # ---------------------------------------------------------------------------

  rule {
    name     = "aws-managed-ip-reputation-list"
    priority = 40

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-ip-reputation"
      sampled_requests_enabled   = true
    }
  }

  # ---------------------------------------------------------------------------
  # Rule 5: Rate-Based Rule
  # Limits requests per source IP to prevent abuse and DDoS
  # ---------------------------------------------------------------------------

  rule {
    name     = "rate-limit-per-ip"
    priority = 50

    action {
      block {
        custom_response {
          response_code            = 403
          custom_response_body_key = "blocked-response"
        }
      }
    }

    statement {
      rate_based_statement {
        limit              = var.rate_limit
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  # ---------------------------------------------------------------------------
  # Rule 6: Body Size Limit
  # Blocks requests with bodies larger than the configured limit to prevent
  # payload-based attacks and resource exhaustion
  # ---------------------------------------------------------------------------

  rule {
    name     = "block-oversized-body"
    priority = 60

    action {
      block {
        custom_response {
          response_code            = 403
          custom_response_body_key = "blocked-response"
        }
      }
    }

    statement {
      size_constraint_statement {
        comparison_operator = "GT"
        size                = var.body_size_limit

        field_to_match {
          body {
            oversize_handling = "MATCH"
          }
        }

        text_transformation {
          priority = 0
          type     = "NONE"
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-body-size-limit"
      sampled_requests_enabled   = true
    }
  }

  # ---------------------------------------------------------------------------
  # Web ACL Visibility Config
  # ---------------------------------------------------------------------------

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name_prefix}-web-acl"
    sampled_requests_enabled   = true
  }

  tags = {
    Name      = "${local.name_prefix}-web-acl"
    Component = "waf"
  }
}

# -----------------------------------------------------------------------------
# WAF Web ACL Association with ALB
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl_association" "alb" {
  resource_arn = var.alb_arn
  web_acl_arn  = aws_wafv2_web_acl.main.arn
}

# -----------------------------------------------------------------------------
# WAF Logging — S3 Bucket
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "waf_logs" {
  count = var.enable_waf_logging ? 1 : 0

  # WAF logging requires bucket name to start with "aws-waf-logs-"
  bucket = "aws-waf-logs-${local.name_prefix}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name      = "aws-waf-logs-${local.name_prefix}"
    Component = "waf"
    Purpose   = "WAF request logging and analysis"
  }
}

resource "aws_s3_bucket_versioning" "waf_logs" {
  count = var.enable_waf_logging ? 1 : 0

  bucket = aws_s3_bucket.waf_logs[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "waf_logs" {
  count = var.enable_waf_logging ? 1 : 0

  bucket = aws_s3_bucket.waf_logs[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "waf_logs" {
  count = var.enable_waf_logging ? 1 : 0

  bucket = aws_s3_bucket.waf_logs[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "waf_logs" {
  count = var.enable_waf_logging ? 1 : 0

  bucket = aws_s3_bucket.waf_logs[0].id

  rule {
    id     = "waf-log-retention"
    status = "Enabled"

    filter {}

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = var.waf_log_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# -----------------------------------------------------------------------------
# WAF Logging Configuration
# Prefix structure: AWSLogs/{account_id}/WAFLogs/{region}/{web_acl_name}/
# This enables analysis of blocked requests by rule group and source IP
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl_logging_configuration" "main" {
  count = var.enable_waf_logging ? 1 : 0

  log_destination_configs = [aws_s3_bucket.waf_logs[0].arn]
  resource_arn            = aws_wafv2_web_acl.main.arn

  logging_filter {
    default_behavior = "KEEP"

    filter {
      behavior    = "KEEP"
      requirement = "MEETS_ANY"

      condition {
        action_condition {
          action = "BLOCK"
        }
      }

      condition {
        action_condition {
          action = "COUNT"
        }
      }
    }
  }
}
