# RDS Aurora PostgreSQL Module

## Overview

This module provisions an Amazon Aurora PostgreSQL 15 cluster configured for enterprise-grade reliability, security, and observability. The cluster deploys with a writer and one or more reader instances across different Availability Zones for automatic failover.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Private Subnets (DB Subnet Group)                  │
│                                                     │
│  ┌─────────────────┐    ┌─────────────────┐        │
│  │  Writer (AZ-a)  │    │  Reader (AZ-b)  │        │
│  │  ─────────────  │    │  ─────────────  │        │
│  │  Performance    │    │  Performance    │        │
│  │  Insights (7d)  │    │  Insights (7d)  │        │
│  │  Enhanced Mon.  │    │  Enhanced Mon.  │        │
│  └────────┬────────┘    └────────┬────────┘        │
│           │                      │                  │
│           └──────┬───────────────┘                  │
│                  │                                  │
│        ┌─────────┴──────────┐                      │
│        │  Aurora Cluster     │                      │
│        │  ────────────────  │                      │
│        │  KMS Encryption    │                      │
│        │  IAM Auth Enabled  │                      │
│        │  7-day Backups     │                      │
│        │  CloudWatch Logs   │                      │
│        └────────────────────┘                      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Features

| Feature | Configuration |
|---------|--------------|
| Engine | Aurora PostgreSQL 15.x |
| Multi-AZ | Writer + Reader in different AZs |
| Encryption | KMS customer-managed key (at rest) |
| Authentication | IAM database authentication enabled |
| Backups | 7-day retention, 02:00-03:00 UTC window |
| Performance Insights | 7-day retention, KMS encrypted |
| Enhanced Monitoring | 60-second granularity |
| Logging | PostgreSQL logs exported to CloudWatch |
| Parameters | Custom connection, logging, and performance settings |
| Network | Private subnets only, no public access |

## Usage

```hcl
module "rds" {
  source = "./modules/rds"

  project     = "secure-multi-tier-platform"
  environment = "demo"

  # Network
  private_subnet_ids = module.vpc.private_subnet_ids
  db_sg_id           = module.security_groups.db_sg_id

  # Encryption
  kms_key_arn = module.kms.key_arn

  # Credentials (source from Secrets Manager)
  master_username = var.db_master_username
  master_password = var.db_master_password

  tags = module.tagging.tags_map
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `project` | Project name for resource naming | `string` | `"secure-multi-tier-platform"` | no |
| `environment` | Deployment environment | `string` | `"demo"` | no |
| `private_subnet_ids` | Private subnet IDs for DB subnet group | `list(string)` | - | yes |
| `db_sg_id` | Database security group ID | `string` | - | yes |
| `kms_key_arn` | KMS key ARN for encryption at rest | `string` | - | yes |
| `engine_version` | Aurora PostgreSQL engine version | `string` | `"15.4"` | no |
| `instance_class` | DB instance class | `string` | `"db.t3.medium"` | no |
| `database_name` | Default database name | `string` | `"platform"` | no |
| `master_username` | Master database username | `string` | `"platform_admin"` | yes |
| `master_password` | Master database password | `string` | - | yes |
| `backup_retention_period` | Backup retention in days | `number` | `7` | no |
| `preferred_backup_window` | Daily backup window (UTC) | `string` | `"02:00-03:00"` | no |
| `preferred_maintenance_window` | Weekly maintenance window (UTC) | `string` | `"sun:04:00-sun:05:00"` | no |
| `max_connections` | Maximum database connections | `number` | `200` | no |
| `shared_buffers` | Shared buffers parameter | `string` | `"{DBInstanceClassMemory/32768}"` | no |
| `work_mem` | Work memory per operation (KB) | `string` | `"65536"` | no |
| `log_statement` | SQL statement logging level | `string` | `"mod"` | no |
| `log_min_duration_statement` | Min statement duration for logging (ms) | `number` | `1000` | no |
| `performance_insights_retention_period` | Performance Insights retention days | `number` | `7` | no |
| `reader_count` | Number of reader instances | `number` | `1` | no |
| `tags` | Additional resource tags | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| `cluster_endpoint` | Writer endpoint (read-write connections) |
| `reader_endpoint` | Reader endpoint (load-balanced read-only) |
| `cluster_arn` | ARN of the Aurora cluster |
| `cluster_id` | Identifier of the Aurora cluster |
| `cluster_identifier` | Cluster identifier string |
| `database_name` | Name of the default database |
| `port` | Port number (default 5432) |
| `writer_instance_id` | Writer instance identifier |
| `reader_instance_ids` | List of reader instance identifiers |
| `cluster_resource_id` | Cluster resource ID (for IAM auth) |
| `kms_grant_id` | KMS grant ID for Aurora encryption |
| `kms_grant_token` | KMS grant token |
| `enhanced_monitoring_role_arn` | IAM role ARN for Enhanced Monitoring |
| `db_subnet_group_name` | DB subnet group name |

## Custom Parameter Group Settings

### Cluster Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `log_statement` | `mod` | Log all data-modifying statements (INSERT, UPDATE, DELETE) |
| `log_min_duration_statement` | `1000` | Log queries taking longer than 1 second |

### Instance Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `max_connections` | `200` | Connection pool ceiling for application tier |
| `shared_buffers` | `{DBInstanceClassMemory/32768}` | Dynamic shared buffer allocation (~25% of instance memory) |
| `work_mem` | `65536` | 64MB work memory per sort/hash operation |

## Security

- **Encryption at rest**: All data encrypted with KMS customer-managed key via dedicated grant
- **No public access**: Instances deployed exclusively in private subnets
- **IAM authentication**: Token-based access from application tier (no static passwords in config)
- **Security group**: Only allows inbound PostgreSQL (5432) from application security group
- **KMS grant with encryption context**: Scoped to `Project=secure-multi-tier-platform`, `Component=database`

## Failover

Aurora automatically promotes a reader instance to writer if the current writer becomes unavailable. The failover typically completes within 30 seconds. Reader instances have promotion tiers assigned (1, 2, ...) to control failover priority.

## Requirements Referenced

- 3.1: Aurora PostgreSQL cluster with writer + reader across AZs
- 3.2: Encryption at rest with KMS customer-managed key
- 3.3: Automated backups (7-day retention, off-hours window)
- 3.4: Custom DB parameter group (connections, logging, performance)
- 3.5: Private subnet deployment, no public access
- 3.6: IAM database authentication enabled
- 3.7: Automatic failover (30-second target)
- 3.8: Performance Insights (7-day retention)
- 24.3: KMS grant for Aurora encryption with encryption context
