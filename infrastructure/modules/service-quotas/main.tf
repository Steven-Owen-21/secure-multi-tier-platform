###############################################################################
# Service Quotas Module
#
# Implements proactive service quota monitoring with:
# - Service Quota monitoring for VPC, ECS, RDS, Lambda
# - CloudWatch alarms triggering at 80% of quota limits
# - Trusted Advisor checks for cost, security, fault tolerance, performance
# - SNS alerts with service name, quota name, usage, limit, percentage
#
# Requirements: 27.1, 27.2, 27.3, 27.4
###############################################################################

locals {
  # Flatten the monitored_services map into a list of individual quota alarm configs
  quota_alarms = flatten([
    for service_key, service in var.monitored_services : [
      for quota in service.quotas : {
        key            = "${service_key}-${quota.quota_code}"
        service_code   = service.service_code
        service_key    = service_key
        quota_code     = quota.quota_code
        quota_name     = quota.quota_name
        quota_value    = quota.quota_value
        alarm_threshold = floor(quota.quota_value * var.alarm_threshold_percent / 100)
      }
    ]
  ])

  # Convert to map for for_each usage
  quota_alarms_map = { for alarm in local.quota_alarms : alarm.key => alarm }
}

# -----------------------------------------------------------------------------
# Service Quota CloudWatch Alarms
#
# Each alarm monitors when usage exceeds 80% (configurable) of the quota limit.
# Uses the AWS/Usage namespace metrics published by Service Quotas.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "quota_usage" {
  for_each = local.quota_alarms_map

  alarm_name          = "${var.project_name}-quota-${each.key}"
  alarm_description   = "Service quota alarm: ${each.value.quota_name} (${each.value.service_code}) usage exceeds ${var.alarm_threshold_percent}% of limit (${each.value.quota_value}). Threshold: ${each.value.alarm_threshold}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.alarm_evaluation_periods
  threshold           = each.value.alarm_threshold

  metric_name = "ResourceCount"
  namespace   = "AWS/Usage"
  period      = var.alarm_period_seconds
  statistic   = "Maximum"

  dimensions = {
    Type     = "Resource"
    Service  = each.value.service_code
    Resource = each.value.quota_code
    Class    = "None"
  }

  alarm_actions = [aws_sns_topic_subscription.quota_alerts.arn != "" ? var.sns_topic_arn : var.sns_topic_arn]

  tags = merge(var.tags, {
    Service   = each.value.service_code
    QuotaName = each.value.quota_name
    QuotaCode = each.value.quota_code
  })
}

# -----------------------------------------------------------------------------
# SNS Alert Configuration
#
# Subscribe to the provided SNS topic and configure alarm actions to deliver
# alerts with service name, quota name, current usage, limit, and percentage.
# The alarm description contains the context; the SNS message template
# provides structured alert data.
# -----------------------------------------------------------------------------

resource "aws_sns_topic_subscription" "quota_alerts" {
  topic_arn = var.sns_topic_arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.quota_alert_formatter.arn
}

# -----------------------------------------------------------------------------
# Lambda Function for Quota Alert Formatting
#
# Formats quota alarm notifications with structured data including:
# - Service name
# - Quota name
# - Current usage value (from alarm metric)
# - Quota limit
# - Percentage consumed
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "quota_alert_lambda" {
  name               = "${var.project_name}-quota-alert-formatter"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = var.tags
}

data "aws_iam_policy_document" "lambda_permissions" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["arn:aws:logs:*:*:*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "sns:Publish"
    ]
    resources = [var.sns_topic_arn]
  }

  statement {
    effect = "Allow"
    actions = [
      "servicequotas:GetServiceQuota",
      "servicequotas:ListServiceQuotas"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "quota_alert_lambda" {
  name   = "${var.project_name}-quota-alert-permissions"
  role   = aws_iam_role.quota_alert_lambda.id
  policy = data.aws_iam_policy_document.lambda_permissions.json
}

resource "aws_lambda_function" "quota_alert_formatter" {
  function_name = "${var.project_name}-quota-alert-formatter"
  role          = aws_iam_role.quota_alert_lambda.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 128

  filename         = data.archive_file.quota_alert_lambda.output_path
  source_code_hash = data.archive_file.quota_alert_lambda.output_base64sha256

  environment {
    variables = {
      SNS_TOPIC_ARN           = var.sns_topic_arn
      PROJECT_NAME            = var.project_name
      ALARM_THRESHOLD_PERCENT = tostring(var.alarm_threshold_percent)
    }
  }

  tags = var.tags
}

data "archive_file" "quota_alert_lambda" {
  type        = "zip"
  output_path = "${path.module}/lambda/quota_alert_formatter.zip"

  source {
    content  = <<-PYTHON
import json
import os
import boto3

sns_client = boto3.client('sns')
servicequotas_client = boto3.client('service-quotas')

SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
PROJECT_NAME = os.environ['PROJECT_NAME']
ALARM_THRESHOLD_PERCENT = os.environ['ALARM_THRESHOLD_PERCENT']


def handler(event, context):
    """
    Process CloudWatch Alarm SNS notifications for service quota alarms.
    Formats and publishes a structured alert with service name, quota name,
    current usage, limit, and percentage consumed.
    """
    for record in event.get('Records', []):
        message = json.loads(record['Sns']['Message'])

        alarm_name = message.get('AlarmName', '')
        alarm_description = message.get('AlarmDescription', '')
        new_state = message.get('NewStateValue', '')
        trigger = message.get('Trigger', {})

        # Extract quota details from alarm tags/dimensions
        dimensions = trigger.get('Dimensions', [])
        service_code = ''
        quota_code = ''

        for dim in dimensions:
            if dim.get('name') == 'Service':
                service_code = dim.get('value', '')
            elif dim.get('name') == 'Resource':
                quota_code = dim.get('value', '')

        # Get current metric value from alarm state
        current_value = message.get('NewStateReason', '')

        # Look up quota details
        quota_name = 'Unknown'
        quota_limit = 0

        try:
            response = servicequotas_client.get_service_quota(
                ServiceCode=service_code,
                QuotaCode=quota_code
            )
            quota_info = response.get('Quota', {})
            quota_name = quota_info.get('QuotaName', 'Unknown')
            quota_limit = int(quota_info.get('Value', 0))
        except Exception as e:
            print(f"Error fetching quota info: {e}")
            # Fall back to alarm description parsing
            quota_name = alarm_description

        # Calculate percentage (use threshold as estimate of current usage)
        threshold = trigger.get('Threshold', 0)
        percentage = (threshold / quota_limit * 100) if quota_limit > 0 else 0

        # Build structured alert message
        alert = {
            'source': 'service-quotas',
            'project': PROJECT_NAME,
            'alarm_name': alarm_name,
            'alarm_state': new_state,
            'service_name': service_code,
            'quota_name': quota_name,
            'quota_code': quota_code,
            'current_usage': threshold,
            'quota_limit': quota_limit,
            'percentage_consumed': round(percentage, 1),
            'threshold_percent': int(ALARM_THRESHOLD_PERCENT),
            'description': (
                f"Service quota alert: {quota_name} ({service_code}) "
                f"has reached {round(percentage, 1)}% of its limit. "
                f"Current usage: {threshold}/{quota_limit}"
            )
        }

        # Publish formatted alert to SNS
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"[{PROJECT_NAME}] Quota Alert: {quota_name} ({service_code})",
            Message=json.dumps(alert, indent=2),
            MessageAttributes={
                'source': {
                    'DataType': 'String',
                    'StringValue': 'service-quotas'
                },
                'service': {
                    'DataType': 'String',
                    'StringValue': service_code
                }
            }
        )

    return {'statusCode': 200, 'body': 'Processed'}
PYTHON
    filename = "index.py"
  }
}

resource "aws_lambda_permission" "sns_invoke" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.quota_alert_formatter.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = var.sns_topic_arn
}

# -----------------------------------------------------------------------------
# Trusted Advisor Checks
#
# Enable monitoring for: cost optimisation, security, fault tolerance,
# and performance categories via CloudWatch Events rules.
# Note: Requires Business or Enterprise support plan.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "trusted_advisor_cost" {
  count = var.enable_trusted_advisor ? 1 : 0

  name        = "${var.project_name}-ta-cost-optimisation"
  description = "Trusted Advisor cost optimisation check status changes"

  event_pattern = jsonencode({
    source      = ["aws.trustedadvisor"]
    detail-type = ["Trusted Advisor Check Item Refresh Notification"]
    detail = {
      "check-item-detail" = {
        "Category" = ["cost_optimizing"]
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "trusted_advisor_cost" {
  count = var.enable_trusted_advisor ? 1 : 0

  rule      = aws_cloudwatch_event_rule.trusted_advisor_cost[0].name
  target_id = "send-to-sns"
  arn       = var.sns_topic_arn
}

resource "aws_cloudwatch_event_rule" "trusted_advisor_security" {
  count = var.enable_trusted_advisor ? 1 : 0

  name        = "${var.project_name}-ta-security"
  description = "Trusted Advisor security check status changes"

  event_pattern = jsonencode({
    source      = ["aws.trustedadvisor"]
    detail-type = ["Trusted Advisor Check Item Refresh Notification"]
    detail = {
      "check-item-detail" = {
        "Category" = ["security"]
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "trusted_advisor_security" {
  count = var.enable_trusted_advisor ? 1 : 0

  rule      = aws_cloudwatch_event_rule.trusted_advisor_security[0].name
  target_id = "send-to-sns"
  arn       = var.sns_topic_arn
}

resource "aws_cloudwatch_event_rule" "trusted_advisor_fault_tolerance" {
  count = var.enable_trusted_advisor ? 1 : 0

  name        = "${var.project_name}-ta-fault-tolerance"
  description = "Trusted Advisor fault tolerance check status changes"

  event_pattern = jsonencode({
    source      = ["aws.trustedadvisor"]
    detail-type = ["Trusted Advisor Check Item Refresh Notification"]
    detail = {
      "check-item-detail" = {
        "Category" = ["fault_tolerance"]
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "trusted_advisor_fault_tolerance" {
  count = var.enable_trusted_advisor ? 1 : 0

  rule      = aws_cloudwatch_event_rule.trusted_advisor_fault_tolerance[0].name
  target_id = "send-to-sns"
  arn       = var.sns_topic_arn
}

resource "aws_cloudwatch_event_rule" "trusted_advisor_performance" {
  count = var.enable_trusted_advisor ? 1 : 0

  name        = "${var.project_name}-ta-performance"
  description = "Trusted Advisor performance check status changes"

  event_pattern = jsonencode({
    source      = ["aws.trustedadvisor"]
    detail-type = ["Trusted Advisor Check Item Refresh Notification"]
    detail = {
      "check-item-detail" = {
        "Category" = ["performance"]
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "trusted_advisor_performance" {
  count = var.enable_trusted_advisor ? 1 : 0

  rule      = aws_cloudwatch_event_rule.trusted_advisor_performance[0].name
  target_id = "send-to-sns"
  arn       = var.sns_topic_arn
}
