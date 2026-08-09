# -----------------------------------------------------------------------------
# Cognito Module — Main Resources
# -----------------------------------------------------------------------------
# Creates a Cognito User Pool with:
# - Email-based sign-up with verification
# - Strong password policy (min 12 chars, uppercase, lowercase, number, symbol)
# - User pool client with Authorization Code + PKCE flow
# - Role-based access control groups (admin, manager, viewer)
# - IAM role mappings for each group
# -----------------------------------------------------------------------------

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# Cognito User Pool
# -----------------------------------------------------------------------------

resource "aws_cognito_user_pool" "main" {
  name = "${local.name_prefix}-user-pool"

  # Email-based sign-up
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # Email verification configuration
  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "${var.project_name} — Verify your email"
    email_message        = "Your verification code is: {####}"
  }

  # Password policy: min 12 chars, uppercase, lowercase, number, symbol
  password_policy {
    minimum_length                   = var.password_minimum_length
    require_uppercase                = true
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  # Schema attributes
  schema {
    name                     = "email"
    attribute_data_type      = "String"
    required                 = true
    mutable                  = true
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 5
      max_length = 255
    }
  }

  schema {
    name                     = "name"
    attribute_data_type      = "String"
    required                 = true
    mutable                  = true
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 1
      max_length = 255
    }
  }

  # Account recovery via verified email
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # User pool add-ons
  user_pool_add_ons {
    advanced_security_mode = "ENFORCED"
  }

  tags = {
    Name      = "${local.name_prefix}-user-pool"
    Component = "authentication"
  }
}

# -----------------------------------------------------------------------------
# Cognito User Pool Domain
# -----------------------------------------------------------------------------

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${local.name_prefix}-auth"
  user_pool_id = aws_cognito_user_pool.main.id
}

# -----------------------------------------------------------------------------
# Cognito User Pool Client
# Configured for Authorization Code flow with PKCE support.
# Access token expires after 1 hour, refresh token after 30 days.
# -----------------------------------------------------------------------------

resource "aws_cognito_user_pool_client" "main" {
  name         = "${local.name_prefix}-client"
  user_pool_id = aws_cognito_user_pool.main.id

  # Authorization Code flow with PKCE (no client secret for public clients)
  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]

  # Callback and logout URLs
  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  # Token validity
  access_token_validity  = var.access_token_validity
  refresh_token_validity = var.refresh_token_validity
  id_token_validity      = var.access_token_validity

  token_validity_units {
    access_token  = "hours"
    refresh_token = "days"
    id_token      = "hours"
  }

  # Prevent user existence errors from leaking information
  prevent_user_existence_errors = "ENABLED"

  # Explicit auth flows
  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH",
  ]
}

# -----------------------------------------------------------------------------
# Cognito User Pool Groups — Role-Based Access Control
# Groups: admin, manager, viewer with associated IAM role mappings.
# -----------------------------------------------------------------------------

resource "aws_cognito_user_group" "admin" {
  name         = "admin"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Administrators with full platform access"
  precedence   = 1
  role_arn     = var.admin_role_arn != "" ? var.admin_role_arn : null
}

resource "aws_cognito_user_group" "manager" {
  name         = "manager"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Managers with read/write access to products and orders"
  precedence   = 10
  role_arn     = var.manager_role_arn != "" ? var.manager_role_arn : null
}

resource "aws_cognito_user_group" "viewer" {
  name         = "viewer"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Viewers with read-only access to products and orders"
  precedence   = 100
  role_arn     = var.viewer_role_arn != "" ? var.viewer_role_arn : null
}
