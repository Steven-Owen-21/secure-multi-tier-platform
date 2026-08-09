# AWS Backup Module

## Purpose

This module implements centralised backup management with cross-region replication for the secure-multi-tier-platform. It provisions AWS Backup vaults, a backup plan with resource-specific rules, vault lock in governance mode, and tag-based resource selection for automatic backup coverage.

## Architecture

```
Primary Region (eu-west-2)              Secondary Region (eu-west-1)
┌──────────────────────────┐            ┌──────────────────────────┐
│  Primary Backup Vault    │ ──copy───> │ Secondary Backup Vault   │
│  (KMS encrypted)         │            │  (default encryption)    │
│  Vault Lock: Gov mode    │            │  Vault Lock: Gov mode    │
└──────────────────────────┘            └──────────────────────────┘
         ▲
         │
┌──────────────────────────┐
│      Backup Plan         │
├──────────────────────────┤
│ Aurora: Daily 03:00, 7d  │
│ EBS:    Daily 04:00, 14d │
│ S3:     Weekly Sun 05:00,│
│         30d              │
└──────────────────────────┘
         ▲
         │
┌──────────────────────────┐
│  Resource Selection      │
│  Tag: BackupEnabled=true │
└──────────────────────────┘
```

## Features

- **Primary vault** encrypted with platform KMS customer-managed key
- **Secondary vault** in DR region for geographic redundancy
- **Vault lock (governance mode)** prevents backup deletion during retention period
- **Three backup rules** with distinct schedules and retention:
  - Aurora: Daily at 03:00 UTC, 7-day retention
  - EBS: Daily at 04:00 UTC, 14-day retention
  - S3: Weekly (Sunday) at 05:00 UTC, 30-day retention
- **Cross-region copy** on all rules for disaster recovery
- **Tag-based selection** (`BackupEnabled=true`) for automatic resource inclusion
- **Least-privilege IAM role** scoped to tagged resources only

## Usage

```hcl
module "backup" {
  source = "./modules/backup"

  project     = "secure-multi-tier-platform"
  environment = "demo"

  kms_key_arn      = module.kms.key_arn
  secondary_region = "eu-west-1"
  backup_tag_key   = "BackupEnabled"

  aurora_retention_days = 7
  ebs_retention_days   = 14
  s3_retention_days    = 30

  tags = module.tagging.tags_map
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `project` | Project name for resource naming and tagging | `string` | `"secure-multi-tier-platform"` | no |
| `environment` | Deployment environment (local, demo) | `string` | `"demo"` | no |
| `kms_key_arn` | ARN of the KMS key for vault encryption | `string` | - | yes |
| `secondary_region` | DR region for cross-region vault | `string` | `"eu-west-1"` | no |
| `backup_tag_key` | Tag key for resource selection | `string` | `"BackupEnabled"` | no |
| `backup_tag_value` | Tag value for resource selection | `string` | `"true"` | no |
| `aurora_retention_days` | Aurora backup retention (1-365) | `number` | `7` | no |
| `ebs_retention_days` | EBS backup retention (1-365) | `number` | `14` | no |
| `s3_retention_days` | S3 backup retention (1-365) | `number` | `30` | no |
| `aurora_schedule` | Cron expression for Aurora backups | `string` | `"cron(0 3 * * ? *)"` | no |
| `ebs_schedule` | Cron expression for EBS backups | `string` | `"cron(0 4 * * ? *)"` | no |
| `s3_schedule` | Cron expression for S3 backups | `string` | `"cron(0 5 ? * SUN *)"` | no |
| `vault_lock_changeable_days` | Governance mode cooling-off period | `number` | `3` | no |
| `vault_lock_min_retention_days` | Minimum retention enforced by vault lock | `number` | `7` | no |
| `vault_lock_max_retention_days` | Maximum retention enforced by vault lock | `number` | `365` | no |
| `tags` | Additional tags to apply | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| `vault_arn` | ARN of the primary backup vault |
| `vault_name` | Name of the primary backup vault |
| `secondary_vault_arn` | ARN of the secondary (DR) backup vault |
| `secondary_vault_name` | Name of the secondary (DR) backup vault |
| `plan_arn` | ARN of the backup plan |
| `plan_id` | ID of the backup plan |
| `selection_id` | ID of the backup resource selection |
| `backup_role_arn` | ARN of the IAM role used by AWS Backup |
| `backup_role_name` | Name of the IAM role used by AWS Backup |

## Dependencies

### Upstream

- `kms` — provides `kms_key_arn` for primary vault encryption

### Downstream

- Root module — consumes `vault_arn` and `plan_arn` for reference
- Resources tagged `BackupEnabled=true` are automatically included in backup selection

## Backup Schedule Reference

| Resource | Rule Name | Schedule | Retention | Cross-Region |
|----------|-----------|----------|-----------|--------------|
| Aurora | `aurora-daily` | Daily 03:00 UTC | 7 days | Yes |
| EBS | `ebs-daily` | Daily 04:00 UTC | 14 days | Yes |
| S3 | `s3-weekly` | Sunday 05:00 UTC | 30 days | Yes |

## Vault Lock Behaviour

Both primary and secondary vaults use governance mode vault lock:

- **Governance mode** allows authorised principals with `backup:DeleteBackupVault` permission to remove the lock if needed (unlike compliance mode which is irreversible)
- A cooling-off period (default 3 days) allows policy changes before the lock becomes active
- Minimum and maximum retention periods are enforced — backups cannot be deleted before the minimum retention expires

## IAM Role Permissions

The backup IAM role follows least-privilege principles:

| Permission Category | Actions | Scope |
|---|---|---|
| Backup operations | StartBackupJob, StartCopyJob, StartRestoreJob | Tagged resources only |
| RDS operations | CreateDBClusterSnapshot, RestoreDBClusterFromSnapshot | Tagged resources only |
| EBS operations | CreateSnapshot, CopySnapshot, CreateVolume | Tagged resources only |
| S3 operations | GetObject, PutObject, ListBucket | Tagged resources only |
| KMS operations | Decrypt, Encrypt, GenerateDataKey, CreateGrant | Platform KMS key only |
| Vault operations | MountCapsule, TagResource, DescribeBackupVault | Platform vaults only |

## Security Considerations

- Primary vault uses the platform's KMS CMK — all backups are encrypted at rest
- Cross-region copies maintain encryption in transit and at rest
- Vault lock prevents accidental or malicious deletion of recovery points
- IAM role is scoped exclusively to resources tagged `BackupEnabled=true`
- KMS permissions are restricted to the single platform CMK ARN
- Vault access is restricted to the two platform vaults only
