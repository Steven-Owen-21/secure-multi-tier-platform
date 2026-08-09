# -----------------------------------------------------------------------------
# Monitoring Module — Main Resources
# -----------------------------------------------------------------------------
# Enables security monitoring services across the platform:
# - GuardDuty with S3 protection for threat detection
# - AWS Config rules for compliance monitoring
# - Security Hub for aggregated security findings
# - SNS notifications for HIGH/CRITICAL findings
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
# GuardDuty — Threat Detection
# -----------------------------------------------------------------------------
# Enables GuardDuty with S3 protection for intelligent threat detection.
# Monitors CloudTrail, VPC Flow Logs, and DNS logs for suspicious activity.
# -----------------------------------------------------------------------------

resource "aws_guardduty_detector" "main" {
  enable = true

  tags = {
    Name      = "${local.name_prefix}-guardduty"
    Component = "monitoring"
  }
}

# Enable S3 protection as a separate feature resource
resource "aws_guardduty_detector_feature" "s3_protection" {
  detector_id = aws_guardduty_detector.main.id
  name        = "S3_DATA_EVENTS"
  status      = "ENABLED"
}

# -----------------------------------------------------------------------------
# GuardDuty → SNS Notification for HIGH/CRITICAL Findings
# Uses EventBridge to route GuardDuty findings to SNS
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "guardduty_high_critical" {
  name        = "${local.name_prefix}-guardduty-high-critical-findings"
  description = "Routes GuardDuty HIGH and CRITICAL severity findings to SNS for alerting."

  event_pattern = jsonencode({
    source      = ["aws.guardduty"]
    detail-type = ["GuardDuty Finding"]
    detail = {
      severity = [{ numeric = [">=", 7] }]
    }
  })

  tags = {
    Name      = "${local.name_prefix}-guardduty-findings-rule"
    Component = "monitoring"
  }
}

resource "aws_cloudwatch_event_target" "guardduty_to_sns" {
  rule      = aws_cloudwatch_event_rule.guardduty_high_critical.name
  target_id = "guardduty-to-sns"
  arn       = var.sns_topic_arn

  input_transformer {
    input_paths = {
      severity    = "$.detail.severity"
      type        = "$.detail.type"
      description = "$.detail.description"
      resource    = "$.detail.resource.resourceType"
      account     = "$.detail.accountId"
      region      = "$.detail.region"
      time        = "$.detail.updatedAt"
    }

    input_template = <<EOF
{
  "source": "guardduty",
  "severity": "<severity>",
  "finding_type": "<type>",
  "affected_resource": "<resource>",
  "description": "<description>",
  "recommended_action": "Review the GuardDuty finding in the AWS console and follow the remediation guidance.",
  "timestamp": "<time>",
  "account_id": "<account>",
  "region": "<region>"
}
EOF
  }
}

# -----------------------------------------------------------------------------
# AWS Config — Compliance Monitoring
# -----------------------------------------------------------------------------
# Enables AWS Config with a recorder and delivery channel, plus compliance
# rules for encryption, flow logs, and IAM best practices.
# -----------------------------------------------------------------------------

resource "aws_config_configuration_recorder" "main" {
  name     = "${local.name_prefix}-config-recorder"
  role_arn = aws_iam_role.config_role.arn

  recording_group {
    all_supported                 = true
    include_global_resource_types = true
  }
}

resource "aws_config_delivery_channel" "main" {
  name           = "${local.name_prefix}-config-delivery"
  s3_bucket_name = aws_s3_bucket.config_logs.id

  depends_on = [aws_config_configuration_recorder.main]
}

resource "aws_config_configuration_recorder_status" "main" {
  name       = aws_config_configuration_recorder.main.name
  is_enabled = true

  depends_on = [aws_config_delivery_channel.main]
}

# -----------------------------------------------------------------------------
# Config IAM Role
# -----------------------------------------------------------------------------

resource "aws_iam_role" "config_role" {
  name = "${local.name_prefix}-config-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name      = "${local.name_prefix}-config-role"
    Component = "monitoring"
  }
}

resource "aws_iam_role_policy_attachment" "config_policy" {
  role       = aws_iam_role.config_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
}

resource "aws_iam_role_policy" "config_s3_delivery" {
  name = "${local.name_prefix}-config-s3-delivery"
  role = aws_iam_role.config_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetBucketAcl"
        ]
        Resource = [
          aws_s3_bucket.config_logs.arn,
          "${aws_s3_bucket.config_logs.arn}/*"
        ]
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Config S3 Bucket for Delivery Channel
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "config_logs" {
  bucket = "${local.name_prefix}-config-logs-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name      = "${local.name_prefix}-config-logs"
    Component = "monitoring"
    Purpose   = "AWS Config delivery channel storage"
  }
}

resource "aws_s3_bucket_versioning" "config_logs" {
  bucket = aws_s3_bucket.config_logs.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "config_logs" {
  bucket = aws_s3_bucket.config_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "config_logs" {
  bucket = aws_s3_bucket.config_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# AWS Config Rules
# -----------------------------------------------------------------------------

# Rule 1: encrypted-volumes — Checks that EBS volumes are encrypted
resource "aws_config_config_rule" "encrypted_volumes" {
  name        = "encrypted-volumes"
  description = "Checks whether EBS volumes that are in an attached state are encrypted."

  source {
    owner             = "AWS"
    source_identifier = "ENCRYPTED_VOLUMES"
  }

  depends_on = [aws_config_configuration_recorder_status.main]

  tags = {
    Name      = "${local.name_prefix}-rule-encrypted-volumes"
    Component = "monitoring"
  }
}

# Rule 2: rds-encryption-enabled — Checks RDS instances are encrypted at rest
resource "aws_config_config_rule" "rds_encryption_enabled" {
  name        = "rds-encryption-enabled"
  description = "Checks whether storage encryption is enabled for your RDS DB instances."

  source {
    owner             = "AWS"
    source_identifier = "RDS_STORAGE_ENCRYPTED"
  }

  depends_on = [aws_config_configuration_recorder_status.main]

  tags = {
    Name      = "${local.name_prefix}-rule-rds-encryption"
    Component = "monitoring"
  }
}

# Rule 3: s3-bucket-server-side-encryption-enabled — Checks S3 buckets have SSE
resource "aws_config_config_rule" "s3_bucket_sse_enabled" {
  name        = "s3-bucket-server-side-encryption-enabled"
  description = "Checks that S3 buckets have server-side encryption enabled."

  source {
    owner             = "AWS"
    source_identifier = "S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED"
  }

  depends_on = [aws_config_configuration_recorder_status.main]

  tags = {
    Name      = "${local.name_prefix}-rule-s3-sse"
    Component = "monitoring"
  }
}

# Rule 4: vpc-flow-logs-enabled — Checks VPCs have flow logs enabled
resource "aws_config_config_rule" "vpc_flow_logs_enabled" {
  name        = "vpc-flow-logs-enabled"
  description = "Checks whether Amazon Virtual Private Cloud flow logs are found and enabled for VPCs."

  source {
    owner             = "AWS"
    source_identifier = "VPC_FLOW_LOGS_ENABLED"
  }

  depends_on = [aws_config_configuration_recorder_status.main]

  tags = {
    Name      = "${local.name_prefix}-rule-vpc-flow-logs"
    Component = "monitoring"
  }
}

# Rule 5: iam-user-no-policies-check — Checks IAM users have no direct policies
resource "aws_config_config_rule" "iam_user_no_policies" {
  name        = "iam-user-no-policies-check"
  description = "Checks that none of your IAM users have policies attached. IAM users should inherit permissions from groups or roles."

  source {
    owner             = "AWS"
    source_identifier = "IAM_USER_NO_POLICIES_CHECK"
  }

  depends_on = [aws_config_configuration_recorder_status.main]

  tags = {
    Name      = "${local.name_prefix}-rule-iam-user-no-policies"
    Component = "monitoring"
  }
}

# -----------------------------------------------------------------------------
# Config Non-Compliance → SNS Notification
# Uses EventBridge to route Config compliance change events to SNS
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "config_non_compliance" {
  name        = "${local.name_prefix}-config-non-compliance"
  description = "Routes AWS Config non-compliance events to SNS for alerting."

  event_pattern = jsonencode({
    source      = ["aws.config"]
    detail-type = ["Config Rules Compliance Change"]
    detail = {
      messageType        = ["ComplianceChangeNotification"]
      newEvaluationResult = {
        complianceType = ["NON_COMPLIANT"]
      }
    }
  })

  tags = {
    Name      = "${local.name_prefix}-config-compliance-rule"
    Component = "monitoring"
  }
}

resource "aws_cloudwatch_event_target" "config_to_sns" {
  rule      = aws_cloudwatch_event_rule.config_non_compliance.name
  target_id = "config-to-sns"
  arn       = var.sns_topic_arn

  input_transformer {
    input_paths = {
      rule_name    = "$.detail.configRuleName"
      resource_arn = "$.detail.resourceId"
      compliance   = "$.detail.newEvaluationResult.complianceType"
      account      = "$.detail.awsAccountId"
      region       = "$.detail.awsRegion"
      time         = "$.detail.newEvaluationResult.resultRecordedTime"
    }

    input_template = <<EOF
{
  "source": "config",
  "severity": "HIGH",
  "finding_type": "Config Rule Non-Compliance",
  "affected_resource": "<resource_arn>",
  "description": "Config rule '<rule_name>' detected non-compliance on resource <resource_arn>. Compliance status: <compliance>.",
  "recommended_action": "Review the non-compliant resource and remediate according to the Config rule requirements.",
  "timestamp": "<time>",
  "account_id": "<account>",
  "region": "<region>"
}
EOF
  }
}

# -----------------------------------------------------------------------------
# Security Hub — Aggregated Security Findings
# -----------------------------------------------------------------------------
# Enables Security Hub with AWS Foundational Security Best Practices and
# CIS AWS Foundations Benchmark standards. Aggregates findings from
# GuardDuty, Config, and WAF.
# -----------------------------------------------------------------------------

resource "aws_securityhub_account" "main" {}

resource "aws_securityhub_standards_subscription" "aws_foundational" {
  standards_arn = "arn:aws:securityhub:${data.aws_region.current.name}::standards/aws-foundational-security-best-practices/v/1.0.0"

  depends_on = [aws_securityhub_account.main]
}

resource "aws_securityhub_standards_subscription" "cis_benchmark" {
  standards_arn = "arn:aws:securityhub:::ruleset/cis-aws-foundations-benchmark/v/1.2.0"

  depends_on = [aws_securityhub_account.main]
}

# -----------------------------------------------------------------------------
# Security Hub → SNS Notification for HIGH/CRITICAL Findings
# Routes imported findings to SNS via EventBridge
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "securityhub_high_critical" {
  name        = "${local.name_prefix}-securityhub-high-critical"
  description = "Routes Security Hub HIGH and CRITICAL findings to SNS for alerting."

  event_pattern = jsonencode({
    source      = ["aws.securityhub"]
    detail-type = ["Security Hub Findings - Imported"]
    detail = {
      findings = {
        Severity = {
          Label = ["HIGH", "CRITICAL"]
        }
      }
    }
  })

  tags = {
    Name      = "${local.name_prefix}-securityhub-findings-rule"
    Component = "monitoring"
  }
}

resource "aws_cloudwatch_event_target" "securityhub_to_sns" {
  rule      = aws_cloudwatch_event_rule.securityhub_high_critical.name
  target_id = "securityhub-to-sns"
  arn       = var.sns_topic_arn
}

# -----------------------------------------------------------------------------
# SNS Topic Policy — Allow EventBridge to publish
# -----------------------------------------------------------------------------

resource "aws_sns_topic_policy" "monitoring_events" {
  arn = var.sns_topic_arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgePublish"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "sns:Publish"
        Resource = var.sns_topic_arn
        Condition = {
          ArnLike = {
            "aws:SourceArn" = "arn:aws:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:rule/${local.name_prefix}-*"
          }
        }
      }
    ]
  })
}
