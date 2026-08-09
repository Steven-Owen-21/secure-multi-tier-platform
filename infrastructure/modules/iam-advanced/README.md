# IAM Advanced Module

## Purpose

Implements enterprise IAM governance patterns demonstrating defence-in-depth identity management beyond basic role assignments. This module creates:

1. **Permission Boundary** — An IAM policy attached to application roles that caps the maximum effective permissions to only platform-required AWS services, regardless of what the role's own policies grant.

2. **Session Policy** — An inline policy document passed at assume-role time that further restricts effective permissions to only resources tagged `Project=secure-multi-tier-platform`.

3. **Role Chaining** — A three-role trust chain demonstrating enterprise role delegation:
   - **Pipeline Role** (GitHub OIDC) → assumes → **Deployment Role** → assumes → **Service Role** (ECS tasks)

4. **IAM Access Analyzer** — Account-level analyzer detecting unused permissions and external access to platform resources.

5. **Least-Privilege Application Policy** — Custom IAM policy granting the Application_Service only the specific actions it needs on specific resource ARNs (no wildcard resources).

## Architecture

```
Pipeline Role (GH OIDC)
    │
    │ sts:AssumeRole (external ID required)
    ▼
Deployment Role
    │
    │ sts:AssumeRole (external ID + tag match)
    ▼
Service Role (ECS tasks)
    │
    ├── Permission Boundary ──► Caps max permissions to platform services
    │
    └── Session Policy ──► Scopes to resources tagged Project=secure-multi-tier-platform
```

## Trust Policy Chain

| Role | Trusted By | Conditions |
|------|-----------|------------|
| Pipeline Role | GitHub OIDC provider | repo + branch (defined externally) |
| Deployment Role | Pipeline Role ARN | `sts:ExternalId` must match |
| Service Role | ECS service principal + Deployment Role | `aws:RequestTag/Project` must match |

## Permission Boundary Enforcement Model

The permission boundary defines the *maximum* permissions any application role can have:

- **Allowed**: Actions within the configured service set (S3, RDS, ElastiCache, ECS, ECR, CloudWatch, Secrets Manager, KMS, SNS, SQS, DynamoDB, Cognito, API Gateway, SSM Messages, X-Ray)
- **Explicitly Denied**: IAM privilege escalation (CreateRole, AttachRolePolicy, PutRolePolicy, etc.)
- **Explicitly Denied**: Organisation-level actions (organizations:*, account:*)
- **Implicitly Denied**: Any service not in the allowed set

Even if a role policy grants `ec2:*`, the boundary prevents it from taking effect because EC2 is not in the allowed service list (unless added to `allowed_services`).

## Session Policy Scoping

When assuming the Service role, the session policy restricts all actions to resources carrying the tag `Project=secure-multi-tier-platform`. This means:

- A role might have `s3:GetObject` on `*` via its policy
- The permission boundary allows `s3:*`
- But the session policy restricts to only S3 objects tagged with the project tag

Effective permission = Role Policy ∩ Permission Boundary ∩ Session Policy

## Usage

```hcl
module "iam_advanced" {
  source = "./modules/iam-advanced"

  project            = "secure-multi-tier-platform"
  environment        = "demo"
  ecs_task_role_arn  = module.ecs.task_role_arn
  pipeline_role_arn  = aws_iam_role.pipeline.arn
  resource_tag_value = "secure-multi-tier-platform"

  # Least-privilege resource ARNs for Application_Service
  application_s3_bucket_arns      = [module.s3_lifecycle.app_bucket_arn]
  application_dynamodb_table_arns = []
  application_secrets_arns        = module.secrets_rotation.secret_arns
  application_sns_topic_arns      = [aws_sns_topic.alerts.arn]
  application_kms_key_arns        = [module.kms.key_arn]

  tags = module.tagging.tags_map
}
```

## Key Inputs

| Variable | Description | Default |
|----------|-------------|---------|
| `ecs_task_role_arn` | ARN of the ECS task role | (required) |
| `pipeline_role_arn` | ARN of the Pipeline role (OIDC) | (required) |
| `resource_tag_value` | Project tag value for session policy scoping | `secure-multi-tier-platform` |
| `allowed_services` | Service prefixes allowed by permission boundary | Platform service set |
| `deployment_role_external_id` | External ID for Pipeline→Deployment assume | `secure-platform-deploy-ext-id` |
| `application_s3_bucket_arns` | S3 bucket ARNs for app policy | `[]` |
| `application_secrets_arns` | Secrets Manager ARNs for app policy | `[]` |
| `application_kms_key_arns` | KMS key ARNs for app policy | `[]` |

## Key Outputs

| Output | Description |
|--------|-------------|
| `permission_boundary_arn` | ARN of the permission boundary policy |
| `analyzer_arn` | ARN of the IAM Access Analyzer |
| `deployment_role_arn` | ARN of the Deployment role |
| `service_role_arn` | ARN of the Service role |
| `session_policy_json` | Session policy JSON for passing at assume-role time |
| `application_service_policy_arn` | ARN of the least-privilege app policy |

## Dependencies

- `ecs` module (provides `task_role_arn`)
- Pipeline role (created in CI/CD workflow or root module)
- `kms` module (provides key ARNs for app policy)
- `secrets-rotation` module (provides secret ARNs for app policy)

## Requirements

| Requirement | Implementation |
|-------------|---------------|
| 20.1 | Permission boundary limiting max permissions to platform services |
| 20.2 | Session policy restricting to tagged resources |
| 20.3 | Role chaining: Pipeline → Deployment → Service with trust policies |
| 20.4 | IAM Access Analyzer enabled in deployment region |
| 20.5 | Least-privilege custom policy with specific actions on specific ARNs |
