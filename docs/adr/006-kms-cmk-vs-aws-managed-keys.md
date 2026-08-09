# ADR-006: KMS Customer-Managed Key (CMK) vs AWS-Managed Keys

## Status

Accepted

## Date

2024-01-15

## Context

The platform requires encryption at rest for all data stores (Aurora, ElastiCache, S3, Backups). AWS provides two key management options:

1. **AWS-managed keys** (aws/rds, aws/s3, etc.) — Default keys managed entirely by AWS
2. **Customer-managed keys (CMK)** — Keys created and managed by the customer with full control over key policy, rotation, and grants

## Decision

We chose a **single customer-managed KMS key** (CMK) with grants for service-specific access.

## Rationale

| Criterion | Customer-Managed Key | AWS-Managed Keys |
|-----------|---------------------|------------------|
| Key policy control | Full (custom principals, conditions) | None (AWS-controlled) |
| Encryption context | Supported (enforce per-service) | Service-dependent |
| Grants | Supported (fine-grained, revocable) | Not available |
| Rotation | Annual automatic + manual | Annual automatic (non-configurable) |
| Cross-region | Manual replication (multi-region key) | Per-region only |
| Audit trail | Full CloudTrail logging with context | Limited metadata |
| Cost | £0.83/month + £0.03/10k requests | Free |
| Deletion control | 7–30 day waiting period (configurable) | Cannot delete |
| Portfolio demonstration value | Enterprise encryption governance | Basic compliance |

A customer-managed key was selected because:

- **Key policy control** enables the principal-category model (Requirement 24.1): administrators, users, and grant creators with distinct permissions
- **Encryption context** enforcement (Requirement 24.6) ensures that only platform resources can use the key — a CMK-only feature
- **Grants model** (Requirement 24.3) allows fine-grained, revocable access per service without broadening key policy
- **Cross-region backup** requires CMK re-encryption in the DR region (Requirement 26.3) — only possible with customer-managed keys
- **Audit completeness** — CloudTrail logs all CMK operations with encryption context, enabling security analysis
- **Negligible cost impact** — £0.83/month is within noise for the demo budget, and demo sessions lasting 2 hours incur <£0.01 in API request charges
- **SA portfolio positioning** — demonstrates enterprise key management governance that AWS-managed keys cannot show

### Grant Architecture

| Grant | Grantee | Operations | Encryption Context |
|-------|---------|------------|-------------------|
| Aurora | RDS service | Encrypt, Decrypt | Project=secure-multi-tier-platform, Component=database |
| ElastiCache | ElastiCache service | Encrypt, Decrypt | Project=secure-multi-tier-platform, Component=cache |
| S3 | S3 service | Encrypt, Decrypt | Via bucket policy delegation |
| Backup | AWS Backup service | CopyGrant | Cross-region backup encryption |

## Consequences

- Single key creates a blast radius — if the key is disabled, all encrypted data is inaccessible (mitigated by IAM controls on key deletion with 30-day waiting period)
- Key rotation creates new backing key material but doesn't re-encrypt existing data (acceptable — old material remains available for decryption)
- Cross-region DR requires either a multi-region key or re-encryption with a DR region key
- Terraform must manage grant lifecycle — grants must be revoked before resources are destroyed

## Alternatives Considered

- **AWS-managed keys**: Zero cost and zero management, but no key policy control, no encryption context enforcement, and no grants — fails to demonstrate encryption governance (Requirement 24)
- **Multiple CMKs per service**: Better blast radius isolation but unnecessary complexity and cost for a demo project; single key with grants achieves equivalent access control
- **AWS CloudHSM**: Full HSM control at £1.60/hour — grossly over-engineered and budget-breaking for the demo use case
