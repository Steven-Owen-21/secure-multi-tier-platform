# -----------------------------------------------------------------------------
# Tagging Module — Outputs
# -----------------------------------------------------------------------------

output "tags_map" {
  description = "Complete map of mandatory tags for use by all platform resources"
  value = {
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    CostCentre  = var.cost_centre
    ManagedBy   = "terraform"
    Component   = var.component
  }
}
