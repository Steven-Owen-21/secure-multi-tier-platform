# -----------------------------------------------------------------------------
# Cognito Module — Input Variables
# -----------------------------------------------------------------------------

variable "callback_urls" {
  description = "List of allowed callback URLs for the user pool client (OAuth2 redirect URIs)."
  type        = list(string)

  validation {
    condition     = length(var.callback_urls) > 0
    error_message = "At least one callback URL must be provided."
  }
}

variable "logout_urls" {
  description = "List of allowed logout/sign-out URLs for the user pool client."
  type        = list(string)

  validation {
    condition     = length(var.logout_urls) > 0
    error_message = "At least one logout URL must be provided."
  }
}

variable "environment" {
  description = "Deployment environment name (used for resource naming)."
  type        = string
  default     = "demo"
}

variable "project_name" {
  description = "Project name used in resource naming."
  type        = string
  default     = "secure-multi-tier-platform"
}

variable "admin_role_arn" {
  description = "IAM role ARN to associate with the admin user pool group."
  type        = string
  default     = ""
}

variable "manager_role_arn" {
  description = "IAM role ARN to associate with the manager user pool group."
  type        = string
  default     = ""
}

variable "viewer_role_arn" {
  description = "IAM role ARN to associate with the viewer user pool group."
  type        = string
  default     = ""
}

variable "access_token_validity" {
  description = "Access token validity in hours."
  type        = number
  default     = 1

  validation {
    condition     = var.access_token_validity >= 1 && var.access_token_validity <= 24
    error_message = "access_token_validity must be between 1 and 24 hours."
  }
}

variable "refresh_token_validity" {
  description = "Refresh token validity in days."
  type        = number
  default     = 30

  validation {
    condition     = var.refresh_token_validity >= 1 && var.refresh_token_validity <= 3650
    error_message = "refresh_token_validity must be between 1 and 3650 days."
  }
}

variable "password_minimum_length" {
  description = "Minimum password length."
  type        = number
  default     = 12

  validation {
    condition     = var.password_minimum_length >= 8 && var.password_minimum_length <= 99
    error_message = "password_minimum_length must be between 8 and 99."
  }
}
