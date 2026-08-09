# KMS Encryption Governance Module

## Purpose

This module implements centralised KMS encryption governance for the secure-multi-tier-platform. It provisions a single customer-managed key (CMK) with a structured key policy that enforces fine-grained access control through three principal categories, encryption context conditions, and service-level restrictions.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     KMS Key Policy                           │
├─────────────────────────────────────────────────────────────┤
│ Key Administrators (Pipeline Role)                          │
│   → Full key management (Create, Describe, Enable, etc.)    │
├─────────────────────────────────────────────────────────────┤
│ Key Users (ECS Task Role, RDS Service)                      │
│   → Encrypt, Decrypt, ReEncrypt, GenerateDataKey            │
│   → Condition: EncryptionContext:Project = platform name    │
│   → Condition: ViaService = rds, elasticache, s3, backup    │
├─────────────────────────────────────────────────────────────┤
│ Grant Creators (Deployment Role)                            │
│   → CreateGrant, ListGrants, RevokeGrant                    │
│   → Condition: GrantIsForAWSResource = true                 │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **Single CMK** for all platform encryption (database, cache, S3, backups)
- **Automatic annual key rotation** (365-day rotation period)
- **Human-readable alias** (`alias/secure-multi-tier-platform`)
- **Encryption context enforcement** restricts usage to platform resources only
- **ViaService condition** limits key usage to approved AWS services
- **Grant-based access** for service-specific encryption (Aurora, ElastiCache)

## Usage

```hcl
module "kms" {
  source = "./modules/kms"

  project     = "secure-multi-tier-platform"
  environment = "demo"

  key_administrator_arns = [module.iam.pipeline_role_arn]
  key_user_arns          = [
    module.ecs.task_role_arn,
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/aws-service-role/rds.amazonaws.com/AWSServiceRoleForRDS"
  ]
  grant_creator_arns     = [module.iam.deployment_role_arn]

  allowed_via_services = [
    "rds.eu-west-2.amazonaws.com",
    "elasticache.eu-west-2.amazonaws.com",
    "s3.eu-west-2.amazonaws.com",
    "backup.eu-west-2.amazonaws.com",
  ]

  tags = module.tagging.tags_map
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `project` | Project name for alias and encryption context | `string` | `"secure-multi-tier-platform"` | no |
| `environment` | Deployment environment (local, demo) | `string` | `"demo"` | no |
| `key_administrator_arns` | IAM ARNs for key administration (Pipeline role) | `list(string)` | - | yes |
| `key_user_arns` | IAM ARNs for encrypt/decrypt operations (ECS, RDS) | `list(string)` | - | yes |
| `grant_creator_arns` | IAM ARNs for grant management (Deployment role) | `list(string)` | - | yes |
| `allowed_via_services` | AWS services permitted via kms:ViaService | `list(string)` | rds, elasticache, s3, backup (eu-west-2) | no |
| `deletion_window_in_days` | Days before scheduled deletion (7-30) | `number` | `30` | no |
| `tags` | Additional tags to apply | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| `key_arn` | ARN of the KMS customer-managed key |
| `key_id` | ID of the KMS customer-managed key |
| `alias_arn` | ARN of the KMS key alias |
| `alias_name` | Name of the KMS key alias |
| `key_policy_json` | JSON key policy document (for validation/testing) |

## Dependencies

This module has no upstream module dependencies and should be provisioned early in the dependency chain.

### Downstream Consumers

- `rds` — uses `key_arn` for Aurora cluster encryption at rest
- `elasticache` — uses `key_arn` for Redis encryption at rest
- `s3-lifecycle` — uses `key_arn` for bucket server-side encryption
- `backup` — uses `key_arn` for backup vault encryption
- `secrets-rotation` — uses `key_arn` for secrets encryption

## Key Policy Principal Mapping

| Category | Principals | Actions | Conditions |
|----------|-----------|---------|------------|
| Root Account | Account root | `kms:*` | None (required for policy functionality) |
| Key Administrators | Pipeline Role | `kms:Create*`, `kms:Describe*`, `kms:Enable*`, `kms:List*`, `kms:Put*`, `kms:Update*`, `kms:Revoke*`, `kms:Disable*`, `kms:Delete*`, `kms:TagResource`, `kms:ScheduleKeyDeletion`, `kms:CancelKeyDeletion` | None |
| Key Users | ECS Task Role, RDS Service | `kms:Encrypt`, `kms:Decrypt`, `kms:ReEncrypt*`, `kms:GenerateDataKey*`, `kms:DescribeKey` | `kms:EncryptionContext:Project` = project name, `kms:ViaService` = allowed services |
| Grant Creators | Deployment Role | `kms:CreateGrant`, `kms:ListGrants`, `kms:RevokeGrant` | `kms:GrantIsForAWSResource` = true |

## Security Considerations

- The root account access statement is required by AWS for key policy functionality but does not grant any principals direct access beyond what is explicitly defined
- Encryption context enforcement ensures the key cannot be used for resources outside the platform
- ViaService restrictions prevent direct API calls to KMS — usage must be through approved AWS services
- Grant-based access (rather than broad policy statements) provides per-service scoping for Aurora and ElastiCache encryption
- Annual key rotation ensures cryptographic best practices without requiring application changes
