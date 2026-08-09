# -----------------------------------------------------------------------------
# Tagging Module — Main Configuration
# -----------------------------------------------------------------------------
# This module enforces the platform's mandatory tagging strategy. It generates
# a complete tag map from input variables and defines governance resources:
#   - Tag policy document with allowed values
#   - Cost allocation tag activation
#   - AWS Config rule checking required tags on all taggable resources
#
# Usage:
#   module "tagging" {
#     source      = "./modules/tagging"
#     environment = var.environment
#     component   = "vpc"
#     owner       = var.owner
#   }
#
# The tags_map output can then be merged into resource-level tags blocks.
# The provider-level default_tags (defined in the root module) applies
# Project, Environment, Owner, CostCentre, and ManagedBy to all resources
# automatically. This module adds the Component tag per-resource.
# -----------------------------------------------------------------------------

locals {
  # Complete mandatory tag set
  tags = {
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    CostCentre  = var.cost_centre
    ManagedBy   = "terraform"
    Component   = var.component
  }

  # Tag policy — allowed values for governance enforcement
  tag_policy = {
    Environment = ["local", "demo"]
    ManagedBy   = ["terraform"]
    Project     = ["secure-multi-tier-platform"]
  }

  # Tags activated for cost allocation in AWS Cost Explorer
  cost_allocation_tags = ["Project", "Environment", "Component"]
}

# -----------------------------------------------------------------------------
# Tag Policy Document
# -----------------------------------------------------------------------------
# Defines allowed values for mandatory tags. This document can be applied
# via AWS Organizations tag policies or used as reference documentation.
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "tag_policy" {
  statement {
    sid    = "EnforceEnvironmentTagValues"
    effect = "Deny"

    actions   = ["*"]
    resources = ["*"]

    condition {
      test     = "StringNotEquals"
      variable = "aws:RequestTag/Environment"
      values   = local.tag_policy["Environment"]
    }

    condition {
      test     = "ForAnyValue:StringEquals"
      variable = "aws:TagKeys"
      values   = ["Environment"]
    }
  }

  statement {
    sid    = "EnforceManagedByTagValues"
    effect = "Deny"

    actions   = ["*"]
    resources = ["*"]

    condition {
      test     = "StringNotEquals"
      variable = "aws:RequestTag/ManagedBy"
      values   = local.tag_policy["ManagedBy"]
    }

    condition {
      test     = "ForAnyValue:StringEquals"
      variable = "aws:TagKeys"
      values   = ["ManagedBy"]
    }
  }

  statement {
    sid    = "EnforceProjectTagValues"
    effect = "Deny"

    actions   = ["*"]
    resources = ["*"]

    condition {
      test     = "StringNotEquals"
      variable = "aws:RequestTag/Project"
      values   = local.tag_policy["Project"]
    }

    condition {
      test     = "ForAnyValue:StringEquals"
      variable = "aws:TagKeys"
      values   = ["Project"]
    }
  }
}

# -----------------------------------------------------------------------------
# Cost Allocation Tags
# -----------------------------------------------------------------------------
# Activates tags for cost allocation in AWS Cost Explorer.
# These resources enable per-component cost breakdown.
# -----------------------------------------------------------------------------

resource "aws_ce_cost_allocation_tag" "project" {
  tag_key = "Project"
  status  = "Active"
}

resource "aws_ce_cost_allocation_tag" "environment" {
  tag_key = "Environment"
  status  = "Active"
}

resource "aws_ce_cost_allocation_tag" "component" {
  tag_key = "Component"
  status  = "Active"
}

# -----------------------------------------------------------------------------
# AWS Config Rule — Required Tags
# -----------------------------------------------------------------------------
# Checks all taggable resources for the presence of mandatory tags and
# reports non-compliant resources.
# -----------------------------------------------------------------------------

resource "aws_config_config_rule" "required_tags" {
  name        = "${var.project}-required-tags"
  description = "Checks that all taggable resources have mandatory tags: Project, Environment, Owner, CostCentre, ManagedBy, Component"

  source {
    owner             = "AWS"
    source_identifier = "REQUIRED_TAGS"
  }

  input_parameters = jsonencode({
    tag1Key   = "Project"
    tag1Value = var.project
    tag2Key   = "Environment"
    tag3Key   = "Owner"
    tag4Key   = "CostCentre"
    tag5Key   = "ManagedBy"
    tag5Value = "terraform"
    tag6Key   = "Component"
  })

  tags = local.tags
}
