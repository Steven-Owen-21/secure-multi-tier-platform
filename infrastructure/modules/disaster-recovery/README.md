# Disaster Recovery Module

## Overview

This module implements cross-region disaster recovery for the secure-multi-tier-platform. It creates failover infrastructure in a secondary AWS region (default: `eu-west-1`) to enable recovery from a primary region (default: `eu-west-2`) failure.

**RPO:** 1 hour | **RTO:** 4 hours

## Architecture

```
Primary Region (eu-west-2)              Secondary Region (eu-west-1)
┌─────────────────────────┐             ┌─────────────────────────┐
│  ALB (health-checked)   │             │  Aurora Read Replica     │
│  Aurora Writer + Reader │──replicate──│  (promotable to writer) │
│  S3 Buckets             │──replicate──│  S3 Replica Buckets     │
└─────────────────────────┘             └─────────────────────────┘
            │                                       │
            └───────── Route53 Failover ────────────┘
                    (health check → failover)
```

## Components

### 1. Cross-Region Aurora Read Replica (Requirement 9.2)

- Creates an Aurora PostgreSQL cluster in the secondary region as a read replica of the primary cluster
- Encrypted at rest using a KMS key in the secondary region
- Can be promoted to a standalone cluster during regional failure
- Deployed in private subnets across multiple AZs in the secondary region

### 2. S3 Cross-Region Replication (Requirement 9.3)

- Configures cross-region replication on all critical S3 buckets
- Replication Time Control (RTC) enforces a **15-minute SLA** for object replication
- Creates destination buckets in the secondary region with versioning enabled
- Replication metrics enabled for monitoring compliance with SLA
- IAM role with least-privilege permissions for replication operations

### 3. Route53 Health Checks (Requirement 9.4)

- Monitors the primary ALB endpoint via HTTPS health checks
- Configuration:
  - **Failure threshold:** 3 consecutive failures
  - **Check interval:** 30 seconds
  - **Protocol:** HTTPS (configurable)
  - **Path:** `/health` (configurable)
- Triggers failover routing when primary is deemed unhealthy

### 4. Route53 Failover Routing (Requirement 9.5)

- Primary record: routes to primary region ALB (associated with health check)
- Secondary record: routes to secondary region ALB (activated on primary failure)
- Uses alias records for zero-TTL DNS resolution
- Automatic failover when health check transitions to unhealthy

## Usage

```hcl
module "disaster_recovery" {
  source = "./modules/disaster-recovery"

  providers = {
    aws           = aws
    aws.secondary = aws.secondary
  }

  project     = "secure-multi-tier-platform"
  environment = "demo"

  # Aurora DR
  rds_cluster_arn           = module.rds.cluster_arn
  rds_cluster_identifier    = module.rds.cluster_identifier
  dr_kms_key_arn            = aws_kms_key.dr.arn
  dr_subnet_ids             = module.vpc_secondary.private_subnet_ids
  dr_vpc_security_group_ids = [module.security_groups_secondary.db_sg_id]
  dr_instance_class         = "db.t3.medium"

  # S3 Replication
  s3_bucket_arns           = module.s3_lifecycle.bucket_arns
  s3_bucket_ids            = module.s3_lifecycle.bucket_names
  replication_time_minutes = 15

  # Route53
  alb_dns_name                   = module.alb.alb_dns_name
  health_check_port              = 443
  health_check_path              = "/health"
  health_check_protocol          = "HTTPS"
  health_check_failure_threshold = 3
  health_check_interval          = 30

  # Failover routing (optional — requires hosted zone)
  domain_name            = "api.example.com"
  hosted_zone_id         = aws_route53_zone.main.zone_id
  primary_alb_zone_id    = module.alb.alb_zone_id
  secondary_alb_dns_name = module.alb_secondary.alb_dns_name
  secondary_alb_zone_id  = module.alb_secondary.alb_zone_id
}
```

## Provider Configuration

This module requires two AWS provider configurations:

```hcl
provider "aws" {
  region = "eu-west-2"  # Primary region
}

provider "aws" {
  alias  = "secondary"
  region = "eu-west-1"  # Secondary (DR) region
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `project` | Project name for resource naming | `string` | `"secure-multi-tier-platform"` | no |
| `environment` | Deployment environment | `string` | `"demo"` | no |
| `primary_region` | Primary AWS region | `string` | `"eu-west-2"` | no |
| `secondary_region` | Secondary (DR) region | `string` | `"eu-west-1"` | no |
| `rds_cluster_arn` | ARN of primary Aurora cluster | `string` | — | yes |
| `dr_kms_key_arn` | KMS key ARN in secondary region | `string` | — | yes |
| `dr_subnet_ids` | Subnet IDs in secondary region (min 2) | `list(string)` | — | yes |
| `dr_vpc_security_group_ids` | Security groups for DR replica | `list(string)` | `[]` | no |
| `dr_instance_class` | Instance class for DR replica | `string` | `"db.t3.medium"` | no |
| `s3_bucket_arns` | Source bucket ARNs for replication | `list(string)` | — | yes |
| `s3_bucket_ids` | Source bucket names | `list(string)` | — | yes |
| `replication_time_minutes` | RTC SLA in minutes | `number` | `15` | no |
| `alb_dns_name` | Primary ALB DNS name | `string` | — | yes |
| `health_check_port` | Health check port | `number` | `443` | no |
| `health_check_path` | Health check path | `string` | `"/health"` | no |
| `health_check_protocol` | Health check protocol | `string` | `"HTTPS"` | no |
| `health_check_failure_threshold` | Failures before unhealthy | `number` | `3` | no |
| `health_check_interval` | Check interval (seconds) | `number` | `30` | no |
| `domain_name` | Domain for failover records | `string` | `""` | no |
| `hosted_zone_id` | Route53 hosted zone ID | `string` | `""` | no |
| `primary_alb_zone_id` | Primary ALB hosted zone ID | `string` | `""` | no |
| `secondary_alb_dns_name` | Secondary ALB DNS name | `string` | `""` | no |
| `secondary_alb_zone_id` | Secondary ALB hosted zone ID | `string` | `""` | no |

## Outputs

| Name | Description |
|------|-------------|
| `dr_aurora_arn` | ARN of the DR Aurora replica cluster |
| `dr_aurora_endpoint` | Endpoint of the DR Aurora replica |
| `dr_aurora_cluster_identifier` | Cluster identifier of the DR replica |
| `dr_s3_bucket_arns` | ARNs of the DR replica S3 buckets |
| `dr_s3_bucket_ids` | IDs (names) of the DR replica buckets |
| `s3_replication_role_arn` | IAM role ARN for S3 replication |
| `route53_health_check_ids` | Route53 health check IDs |
| `route53_health_check_arn` | Route53 health check ARN |
| `primary_failover_record_fqdn` | Primary failover record FQDN |
| `secondary_failover_record_fqdn` | Secondary failover record FQDN |

## Failover Procedure

1. **Detection:** Route53 health check detects 3 consecutive failures on primary ALB
2. **Automatic DNS failover:** Route53 routes traffic to secondary region ALB
3. **Aurora promotion:** Manually promote DR replica to standalone cluster:
   ```bash
   aws rds promote-read-replica-db-cluster \
     --db-cluster-identifier secure-multi-tier-platform-demo-aurora-dr-replica \
     --region eu-west-1
   ```
4. **Verification:** Confirm application connectivity to promoted Aurora cluster
5. **Failback:** After primary region recovery, re-establish replication and switch DNS back

## Cost Considerations

- Aurora DR replica: instance costs in secondary region (can use smaller instance class)
- S3 cross-region replication: data transfer + storage in secondary region
- Route53 health checks: $0.75/month per health check (HTTPS with string matching adds cost)
- For demo purposes, consider destroying DR resources when not actively demonstrating
