# -----------------------------------------------------------------------------
# Tagging Module — Input Variables
# -----------------------------------------------------------------------------

variable "environment" {
  description = "Deployment environment (local or demo)"
  type        = string

  validation {
    condition     = contains(["local", "demo"], var.environment)
    error_message = "environment must be either 'local' or 'demo'."
  }
}

variable "component" {
  description = "Component name for the resource being tagged (e.g. vpc, rds, ecs)"
  type        = string

  validation {
    condition     = length(var.component) > 0 && length(var.component) <= 64
    error_message = "component must be a non-empty string of at most 64 characters."
  }
}

variable "owner" {
  description = "Owner of the resource for cost allocation and accountability"
  type        = string

  validation {
    condition     = length(var.owner) > 0 && length(var.owner) <= 128
    error_message = "owner must be a non-empty string of at most 128 characters."
  }
}

variable "project" {
  description = "Project name — fixed to secure-multi-tier-platform"
  type        = string
  default     = "secure-multi-tier-platform"

  validation {
    condition     = var.project == "secure-multi-tier-platform"
    error_message = "project must be 'secure-multi-tier-platform'."
  }
}

variable "cost_centre" {
  description = "Cost centre for billing allocation"
  type        = string
  default     = "engineering"

  validation {
    condition     = length(var.cost_centre) > 0 && length(var.cost_centre) <= 128
    error_message = "cost_centre must be a non-empty string of at most 128 characters."
  }
}
