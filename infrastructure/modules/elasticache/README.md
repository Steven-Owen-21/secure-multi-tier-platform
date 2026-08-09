# ElastiCache Redis Module

Provisions an Amazon ElastiCache Redis replication group with enterprise-grade security and high availability for the secure-multi-tier-platform.

## Features

- **Multi-AZ Deployment**: Primary + replica nodes distributed across different Availability Zones with automatic failover
- **Encryption at Rest**: Uses a KMS customer-managed key (CMK) via a scoped KMS grant with encryption context
- **Encryption in Transit**: TLS enabled for all client-to-node and node-to-node communication
- **Private Networking**: Deployed in private subnets via an ElastiCache subnet group; no public accessibility
- **Custom Parameter Group**: Tuned for platform workload (allkeys-lru eviction, idle timeout, keyspace notifications)
- **KMS Grant with Encryption Context**: Fine-grained access scoped to `Project=secure-multi-tier-platform, Component=cache`

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ VPC (Private Subnets)                               │
│                                                     │
│  ┌─────────────────┐    ┌─────────────────┐        │
│  │  Redis Primary   │    │  Redis Replica   │       │
│  │  (AZ-a)         │◄──►│  (AZ-b)         │       │
│  └─────────────────┘    └─────────────────┘        │
│         │                       │                   │
│         └───────┬───────────────┘                   │
│                 │                                    │
│         ┌──────┴──────┐                             │
│         │  Subnet Grp │                             │
│         └─────────────┘                             │
└─────────────────────────────────────────────────────┘
          │
    ┌─────┴─────┐
    │  KMS CMK  │ (encryption at rest via grant)
    └───────────┘
```

## Usage

```hcl
module "elasticache" {
  source = "./modules/elasticache"

  project     = "secure-multi-tier-platform"
  environment = "demo"

  private_subnet_ids = module.vpc.private_subnet_ids
  cache_sg_id        = module.security_groups.cache_sg_id
  kms_key_arn        = module.kms.key_arn

  # Optional overrides
  node_type              = "cache.t3.micro"
  engine_version         = "7.1"
  num_cache_clusters     = 2
  snapshot_retention_days = 7
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5 |
| aws | >= 5.0 |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project | Project name for naming and tagging | `string` | `"secure-multi-tier-platform"` | no |
| environment | Deployment environment (local, demo) | `string` | `"demo"` | no |
| private_subnet_ids | Private subnet IDs for the subnet group (min 2) | `list(string)` | - | yes |
| cache_sg_id | Security group ID for Redis traffic | `string` | - | yes |
| kms_key_arn | KMS key ARN for encryption at rest | `string` | - | yes |
| node_type | ElastiCache node instance type | `string` | `"cache.t3.micro"` | no |
| engine_version | Redis engine version | `string` | `"7.1"` | no |
| num_cache_clusters | Number of cache clusters (primary + replicas) | `number` | `2` | no |
| port | Redis port number | `number` | `6379` | no |
| maintenance_window | Weekly maintenance window (UTC) | `string` | `"sun:03:00-sun:04:00"` | no |
| snapshot_retention_days | Days to retain automatic snapshots | `number` | `7` | no |
| snapshot_window | Daily snapshot time range (UTC) | `string` | `"02:00-03:00"` | no |
| maxmemory_policy | Redis eviction policy | `string` | `"allkeys-lru"` | no |
| timeout | Idle connection timeout (seconds) | `number` | `300` | no |
| notify_keyspace_events | Keyspace event notification config | `string` | `"Ex"` | no |
| tags | Additional resource tags | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| primary_endpoint | Primary endpoint address for write operations |
| reader_endpoint | Reader endpoint address (load-balanced across replicas) |
| replication_group_id | ID of the Redis replication group |
| replication_group_arn | ARN of the Redis replication group |
| port | Port number the cluster listens on |
| parameter_group_name | Name of the custom parameter group |
| subnet_group_name | Name of the ElastiCache subnet group |
| kms_grant_id | ID of the KMS grant for encryption |

## Requirements Traceability

| Requirement | Implementation |
|-------------|---------------|
| 4.1 — Redis replication group with failover | `aws_elasticache_replication_group` with `automatic_failover_enabled = true`, `multi_az_enabled = true` |
| 4.2 — Encryption at rest and in transit | `at_rest_encryption_enabled = true`, `kms_key_id`, `transit_encryption_enabled = true` |
| 4.3 — Private subnet deployment | `aws_elasticache_subnet_group` with private subnet IDs |
| 4.4 — Custom parameter group | `aws_elasticache_parameter_group` with maxmemory-policy, timeout, notify-keyspace-events |
| 24.3 — KMS grant with encryption context | `aws_kms_grant` scoped to ElastiCache service with Project/Component context |

## Security Considerations

- All data encrypted at rest using the platform's KMS CMK
- TLS enforced for all connections (clients must use `rediss://` scheme)
- No public accessibility — accessible only from application tier via security group
- KMS grant uses encryption context constraints to prevent key misuse
- AUTH token should be stored in Secrets Manager and rotated (handled by secrets-rotation module)
