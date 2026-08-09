###############################################################################
# Secrets Manager Rotation Module
#
# Defines secrets and automatic rotation for:
#   - Database credentials (Aurora PostgreSQL) with 30-day rotation
#   - Redis AUTH token with 30-day rotation
#
# Implements single-user rotation strategy via a Lambda function that
# executes four steps: createSecret, setSecret, testSecret, finishSecret.
#
# All secrets are encrypted with the platform's KMS customer-managed key.
# Rotation failures trigger SNS notifications with diagnostic details.
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
  common_tags = merge(
    {
      Project     = var.project
      Environment = var.environment
      Component   = "secrets"
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# =============================================================================
# DATABASE CREDENTIALS SECRET
# =============================================================================

resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${var.project}/database/credentials"
  description = "Aurora PostgreSQL database credentials with automatic ${var.rotation_days}-day rotation"
  kms_key_id  = var.kms_key_arn

  tags = merge(local.common_tags, {
    Name       = "${var.project}-db-credentials"
    SecretType = "database"
  })
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    engine   = "postgres"
    host     = var.db_cluster_endpoint
    port     = var.db_cluster_port
    dbname   = var.db_name
    username = var.db_master_username
    password = "INITIAL_PASSWORD_REPLACE_ON_FIRST_ROTATION"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret_rotation" "db_credentials" {
  secret_id           = aws_secretsmanager_secret.db_credentials.id
  rotation_lambda_arn = aws_lambda_function.secrets_rotation.arn

  rotation_rules {
    automatically_after_days = var.rotation_days
  }

  depends_on = [aws_lambda_permission.secretsmanager_invoke]
}

# =============================================================================
# REDIS AUTH TOKEN SECRET
# =============================================================================

resource "aws_secretsmanager_secret" "redis_auth_token" {
  name        = "${var.project}/redis/auth-token"
  description = "Redis AUTH token with automatic ${var.rotation_days}-day rotation"
  kms_key_id  = var.kms_key_arn

  tags = merge(local.common_tags, {
    Name       = "${var.project}-redis-auth-token"
    SecretType = "cache"
  })
}

resource "aws_secretsmanager_secret_version" "redis_auth_token" {
  secret_id = aws_secretsmanager_secret.redis_auth_token.id
  secret_string = jsonencode({
    auth_token = "INITIAL_TOKEN_REPLACE_ON_FIRST_ROTATION"
    host       = ""
    port       = 6379
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret_rotation" "redis_auth_token" {
  secret_id           = aws_secretsmanager_secret.redis_auth_token.id
  rotation_lambda_arn = aws_lambda_function.secrets_rotation.arn

  rotation_rules {
    automatically_after_days = var.rotation_days
  }

  depends_on = [aws_lambda_permission.secretsmanager_invoke]
}

# =============================================================================
# ROTATION LAMBDA FUNCTION
# =============================================================================

# IAM Role for the rotation Lambda
resource "aws_iam_role" "rotation_lambda" {
  name = "${var.project}-secrets-rotation-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${var.project}-secrets-rotation-lambda-role"
  })
}

# Policy: Secrets Manager access for rotation operations
resource "aws_iam_role_policy" "rotation_secretsmanager" {
  name = "${var.project}-rotation-secretsmanager"
  role = aws_iam_role.rotation_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsManagerRotationAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:DescribeSecret",
          "secretsmanager:GetSecretValue",
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecretVersionStage",
          "secretsmanager:GetRandomPassword",
        ]
        Resource = [
          aws_secretsmanager_secret.db_credentials.arn,
          aws_secretsmanager_secret.redis_auth_token.arn,
        ]
      },
      {
        Sid    = "KMSDecryptForSecrets"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey",
        ]
        Resource = [var.kms_key_arn]
      }
    ]
  })
}

# Policy: VPC access for Lambda (ENI management)
resource "aws_iam_role_policy_attachment" "rotation_lambda_vpc" {
  role       = aws_iam_role.rotation_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Policy: Basic Lambda execution (CloudWatch Logs)
resource "aws_iam_role_policy_attachment" "rotation_lambda_basic" {
  role       = aws_iam_role.rotation_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda function implementing single-user rotation strategy
resource "aws_lambda_function" "secrets_rotation" {
  function_name = "${var.project}-secrets-rotation"
  description   = "Implements single-user rotation strategy (createSecret, setSecret, testSecret, finishSecret)"
  role          = aws_iam_role.rotation_lambda.arn
  runtime       = "python3.11"
  handler       = "rotation_handler.lambda_handler"
  timeout       = 60
  memory_size   = 256

  filename         = data.archive_file.rotation_lambda.output_path
  source_code_hash = data.archive_file.rotation_lambda.output_base64sha256

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = var.lambda_security_group_ids
  }

  environment {
    variables = {
      SECRETS_MANAGER_ENDPOINT = "https://secretsmanager.${data.aws_region.current.name}.amazonaws.com"
      PROJECT                  = var.project
      ENVIRONMENT              = var.environment
    }
  }

  tags = merge(local.common_tags, {
    Name = "${var.project}-secrets-rotation"
  })

  depends_on = [
    aws_iam_role_policy.rotation_secretsmanager,
    aws_iam_role_policy_attachment.rotation_lambda_vpc,
    aws_iam_role_policy_attachment.rotation_lambda_basic,
  ]
}

# Permission for Secrets Manager to invoke the Lambda
resource "aws_lambda_permission" "secretsmanager_invoke" {
  statement_id  = "AllowSecretsManagerInvocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.secrets_rotation.function_name
  principal     = "secretsmanager.amazonaws.com"
}

# Package the rotation Lambda handler code
data "archive_file" "rotation_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/rotation_handler.py"
  output_path = "${path.module}/lambda/rotation_handler.zip"
}

# =============================================================================
# ROTATION FAILURE NOTIFICATIONS
# =============================================================================

# CloudWatch Event Rule to detect rotation failures
resource "aws_cloudwatch_event_rule" "rotation_failure" {
  name        = "${var.project}-secrets-rotation-failure"
  description = "Captures Secrets Manager rotation failure events"

  event_pattern = jsonencode({
    source      = ["aws.secretsmanager"]
    detail-type = ["AWS Service Event via CloudTrail"]
    detail = {
      eventName = ["RotationFailed"]
      requestParameters = {
        secretId = [
          aws_secretsmanager_secret.db_credentials.arn,
          aws_secretsmanager_secret.redis_auth_token.arn,
        ]
      }
    }
  })

  tags = merge(local.common_tags, {
    Name = "${var.project}-rotation-failure-rule"
  })
}

# CloudWatch Event Target — send to SNS on rotation failure
resource "aws_cloudwatch_event_target" "rotation_failure_sns" {
  count = var.sns_topic_arn != "" ? 1 : 0

  rule      = aws_cloudwatch_event_rule.rotation_failure.name
  target_id = "rotation-failure-sns"
  arn       = var.sns_topic_arn

  input_transformer {
    input_paths = {
      secretArn  = "$.detail.requestParameters.secretId"
      failedStep = "$.detail.additionalEventData.RotationStep"
      errorMsg   = "$.detail.errorMessage"
    }

    input_template = <<-EOF
      {
        "source": "secrets-rotation",
        "severity": "HIGH",
        "secret_arn": "<secretArn>",
        "failed_step": "<failedStep>",
        "error_details": "<errorMsg>",
        "project": "${var.project}",
        "environment": "${var.environment}",
        "message": "Secrets rotation failed for <secretArn> at step <failedStep>: <errorMsg>"
      }
    EOF
  }
}

# SNS Topic Policy — allow EventBridge to publish
resource "aws_sns_topic_policy" "rotation_failure" {
  count = var.sns_topic_arn != "" ? 1 : 0

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
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.rotation_failure.arn
          }
        }
      }
    ]
  })
}
