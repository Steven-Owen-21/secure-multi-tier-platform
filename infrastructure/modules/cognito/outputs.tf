# -----------------------------------------------------------------------------
# Cognito Module — Outputs
# -----------------------------------------------------------------------------

output "user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = aws_cognito_user_pool.main.id
}

output "user_pool_arn" {
  description = "ARN of the Cognito User Pool"
  value       = aws_cognito_user_pool.main.arn
}

output "client_id" {
  description = "ID of the Cognito User Pool Client"
  value       = aws_cognito_user_pool_client.main.id
}

output "jwks_url" {
  description = "JWKS (JSON Web Key Set) URL for JWT token verification"
  value       = "https://cognito-idp.${data.aws_region.current.name}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/jwks.json"
}

output "user_pool_endpoint" {
  description = "Endpoint URL of the Cognito User Pool"
  value       = aws_cognito_user_pool.main.endpoint
}

output "user_pool_domain" {
  description = "Domain of the Cognito User Pool (hosted UI)"
  value       = aws_cognito_user_pool_domain.main.domain
}

output "oauth2_endpoint" {
  description = "OAuth2 authorization endpoint URL"
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${data.aws_region.current.name}.amazoncognito.com"
}

output "admin_group_name" {
  description = "Name of the admin user pool group"
  value       = aws_cognito_user_group.admin.name
}

output "manager_group_name" {
  description = "Name of the manager user pool group"
  value       = aws_cognito_user_group.manager.name
}

output "viewer_group_name" {
  description = "Name of the viewer user pool group"
  value       = aws_cognito_user_group.viewer.name
}
