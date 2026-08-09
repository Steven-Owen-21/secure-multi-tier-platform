###############################################################################
# Secrets Manager Rotation Module - Outputs
###############################################################################

output "secret_arns" {
  description = "Map of secret ARNs keyed by type (database, redis)"
  value = {
    database = aws_secretsmanager_secret.db_credentials.arn
    redis    = aws_secretsmanager_secret.redis_auth_token.arn
  }
}

output "rotation_lambda_arn" {
  description = "ARN of the secrets rotation Lambda function"
  value       = aws_lambda_function.secrets_rotation.arn
}

output "rotation_lambda_function_name" {
  description = "Name of the secrets rotation Lambda function"
  value       = aws_lambda_function.secrets_rotation.function_name
}

output "db_secret_arn" {
  description = "ARN of the database credentials secret"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "redis_secret_arn" {
  description = "ARN of the Redis AUTH token secret"
  value       = aws_secretsmanager_secret.redis_auth_token.arn
}

output "rotation_role_arn" {
  description = "ARN of the IAM role used by the rotation Lambda"
  value       = aws_iam_role.rotation_lambda.arn
}
