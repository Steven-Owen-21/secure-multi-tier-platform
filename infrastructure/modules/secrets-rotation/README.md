# Secrets Rotation Module

## Purpose

Manages secrets stored in AWS Secrets Manager with automatic rotation for database credentials and Redis AUTH tokens. Implements the single-user rotation strategy via a Lambda function.

## Architecture

```
Secrets Manager                    Rotation Lambda
┌─────────────────┐               ┌─────────────────────┐
│ DB Credentials  │──rotation────>│ 1. createSecret     │
│ (30-day cycle)  │               │ 2. setSecret        │
├─────────────────┤               │ 3. testSecret       │
│ Redis Auth Token│──rotation────>│ 4. finishSecret     │
│ (30-day cycle)  │               └─────────────────────┘
└─────────────────┘                        │
        │                                  │
        │ KMS Encryption                   │ VPC Access
        ▼                                  ▼
┌─────────────────┐               ┌─────────────────────┐
│ KMS CMK         │               │ Aurora PostgreSQL    │
│ (platform key)  │               │ ElastiCache Redis    │
└─────────────────┘               └─────────────────────┘
```

## Rotation Strategy

This module implements the **single-user rotation strategy**:

1. **createSecret** — Generates a new password/token and stores it as `AWSPENDING`
2. **setSecret** — Applies the new credentials to the target service (ALTER USER for PostgreSQL)
3. **testSecret** — Validates the new credentials by attempting a connection
4. **finishSecret** — Promotes `AWSPENDING` to `AWSCURRENT` and demotes old version to `AWSPREVIOUS`

Applications continue using cached `AWSCURRENT` credentials until their local TTL expires, then fetch the new `AWSCURRENT` value from Secrets Manager.

## Failure Notifications

When rotation fails, an EventBridge rule captures the failure event and publishes to SNS with:
- Secret ARN identifying which credential failed
- Rotation step that failed (createSecret, setSecret, testSecret, finishSecret)
- Error details describing the failure

## Usage

```hcl
module "secrets_rotation" {
  source = "./modules/secrets-rotation"

  project             = "secure-multi-tier-platform"
  environment         = "demo"
  db_cluster_endpoint = module.rds.cluster_endpoint
  db_cluster_port     = 5432
  db_name             = "platform"
  db_master_username  = "platform_admin"
  kms_key_arn         = module.kms.key_arn
  rotation_days       = 30
  vpc_id              = module.vpc.vpc_id
  private_subnet_ids  = module.vpc.private_subnet_ids
  lambda_security_group_ids = [module.security_groups.app_sg_id]
  sns_topic_arn       = aws_sns_topic.alerts.arn
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project | Project name for resource naming | string | `"secure-multi-tier-platform"` | no |
| environment | Deployment environment | string | `"demo"` | no |
| db_cluster_endpoint | Aurora cluster writer endpoint | string | - | yes |
| db_cluster_port | Aurora cluster port | number | `5432` | no |
| db_name | Database name | string | `"platform"` | no |
| db_master_username | Database master username | string | `"platform_admin"` | no |
| kms_key_arn | KMS key ARN for secret encryption | string | - | yes |
| rotation_days | Days between rotations | number | `30` | no |
| vpc_id | VPC ID for Lambda deployment | string | - | yes |
| private_subnet_ids | Private subnet IDs for Lambda | list(string) | - | yes |
| lambda_security_group_ids | Security group IDs for Lambda | list(string) | - | yes |
| sns_topic_arn | SNS topic ARN for failure alerts | string | `""` | no |
| tags | Additional resource tags | map(string) | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| secret_arns | Map of secret ARNs (database, redis) |
| rotation_lambda_arn | ARN of the rotation Lambda function |
| rotation_lambda_function_name | Name of the rotation Lambda |
| db_secret_arn | ARN of the database credentials secret |
| redis_secret_arn | ARN of the Redis AUTH token secret |
| rotation_role_arn | ARN of the Lambda execution role |

## Dependencies

- **kms** module — provides `kms_key_arn` for secret encryption
- **vpc** module — provides `vpc_id` and `private_subnet_ids`
- **security-groups** module — provides security group IDs for Lambda VPC access
- **rds** module — provides `cluster_endpoint` for rotation target

## Security Considerations

- All secrets encrypted with the platform's KMS customer-managed key
- Rotation Lambda runs inside the VPC with access only to required subnets
- Lambda IAM role follows least-privilege (only manages specific secret ARNs)
- Passwords generated using `secrets` module (cryptographically secure)
- Database connections use SSL enforcement (`sslmode=require`)
