variable "api_gateway_endpoint" {
  description = "The invoke URL of the API Gateway (e.g. https://abc123.execute-api.eu-west-2.amazonaws.com/prod)"
  type        = string

  validation {
    condition     = can(regex("^https://", var.api_gateway_endpoint))
    error_message = "API Gateway endpoint must use HTTPS protocol."
  }
}

variable "s3_static_bucket" {
  description = "Name of the S3 bucket for static assets (documentation, diagrams, error pages)"
  type        = string

  validation {
    condition     = length(var.s3_static_bucket) >= 3 && length(var.s3_static_bucket) <= 63
    error_message = "S3 bucket name must be between 3 and 63 characters."
  }
}

variable "geo_restrictions" {
  description = "List of ISO 3166-1 alpha-2 country codes allowed to access the distribution (default: GB + EU countries)"
  type        = list(string)
  default = [
    "GB", "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI",
    "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT",
    "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"
  ]

  validation {
    condition     = length(var.geo_restrictions) > 0
    error_message = "At least one country code must be specified in geo_restrictions."
  }
}

variable "environment" {
  description = "Deployment environment (local or demo)"
  type        = string
  default     = "demo"

  validation {
    condition     = contains(["local", "demo"], var.environment)
    error_message = "Environment must be 'local' or 'demo'."
  }
}

variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "secure-multi-tier-platform"
}

variable "tags" {
  description = "Additional tags to apply to resources"
  type        = map(string)
  default     = {}
}

variable "api_cache_ttl" {
  description = "Default TTL in seconds for /api/* cache behaviour"
  type        = number
  default     = 60

  validation {
    condition     = var.api_cache_ttl >= 0
    error_message = "API cache TTL must be non-negative."
  }
}

variable "static_cache_ttl" {
  description = "Default TTL in seconds for /static/* cache behaviour"
  type        = number
  default     = 86400

  validation {
    condition     = var.static_cache_ttl >= 0
    error_message = "Static cache TTL must be non-negative."
  }
}

variable "default_root_object" {
  description = "Default root object served when accessing the distribution root"
  type        = string
  default     = "index.html"
}

variable "price_class" {
  description = "CloudFront price class for the distribution"
  type        = string
  default     = "PriceClass_100"

  validation {
    condition     = contains(["PriceClass_100", "PriceClass_200", "PriceClass_All"], var.price_class)
    error_message = "Price class must be PriceClass_100, PriceClass_200, or PriceClass_All."
  }
}
