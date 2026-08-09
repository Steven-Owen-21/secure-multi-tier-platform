# Tagging Module

Enforces the platform's mandatory tagging strategy, generates a complete tag map for all resources, and provisions governance resources for tag compliance monitoring.

## Purpose

This module implements the resource tagging strategy for the Secure Multi-Tier Platform, satisfying Requirement 25 (Resource Tagging Strategy and Cost Allocation). It provides:

1. **Tag generation** — Produces a complete mandatory tag map from input variables
2. **Tag policy** — Defines allowed values for governance enforcement
3. **Cost allocation** — Activates tags for per-component cost breakdown in AWS Cost Explorer
4. **Compliance checking** — AWS Config rule verifying all taggable resources carry mandatory tags

## Mandatory Tags

| Tag Key | Source | Allowed Values |
|---------|--------|----------------|
| Project | variable (default) | `secure-multi-tier-platform` |
| Environment | variable | `local`, `demo` |
| Owner | variable | any non-empty string |
| CostCentre | variable (default) | any non-empty string |
| ManagedBy | fixed | `terraform` |
| Component | variable | any non-empty string (max 64 chars) |

## Usage

```hcl
module "tagging" {
  source      = "./modules/tagging"
  environment = var.environment
  component   = "vpc"
  owner       = var.owner
}

# Use the generated tags on a specific resource
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  tags       = module.tagging.tags_map
}
```

## Provider Default Tags

The root module's AWS provider `default_tags` block automatically applies Project, Environment, Owner, CostCentre, and ManagedBy to all resources. This module adds the **Component** tag which varies per-resource and generates the full map for explicit use.

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| environment | Deployment environment | `string` | — | yes |
| component | Component name for the resource | `string` | — | yes |
| owner | Resource owner | `string` | — | yes |
| project | Project name | `string` | `"secure-multi-tier-platform"` | no |
| cost_centre | Cost centre for billing | `string` | `"engineering"` | no |

## Outputs

| Name | Description |
|------|-------------|
| tags_map | Complete map of all 6 mandatory tags |

## Dependencies

- **AWS Config** must be enabled (via the `monitoring` module) for the required-tags rule to function
- **AWS Cost Explorer** must be activated in the account for cost allocation tags

## Resources Created

| Resource | Purpose |
|----------|---------|
| `aws_ce_cost_allocation_tag.project` | Activates Project tag for cost allocation |
| `aws_ce_cost_allocation_tag.environment` | Activates Environment tag for cost allocation |
| `aws_ce_cost_allocation_tag.component` | Activates Component tag for cost allocation |
| `aws_config_config_rule.required_tags` | Config rule checking mandatory tags |

## Tag Policy

The module defines an IAM policy document (`data.aws_iam_policy_document.tag_policy`) that enforces allowed values:

- **Environment**: must be `local` or `demo`
- **ManagedBy**: must be `terraform`
- **Project**: must be `secure-multi-tier-platform`

This policy document can be attached to IAM roles or used with AWS Organizations tag policies to prevent non-compliant tag values at creation time.
