# Service Quotas Documentation

## Overview

This document lists all AWS service quotas relevant to the platform, their default limits, the platform's expected usage, and the rationale for monitoring each quota. CloudWatch alarms trigger at 80% utilisation to provide early warning before limits are reached.

## Monitored Quotas

### VPC Quotas

| Quota | Default Limit | Platform Usage | Alarm Threshold (80%) | Relevance |
|-------|--------------|----------------|----------------------|-----------|
| VPCs per region | 5 | 1 | 4 | Low risk but monitored for completeness |
| Subnets per VPC | 200 | 4 (2 public + 2 private) | 160 | Low risk |
| Security groups per VPC | 2500 | 6 (ALB, app, DB, cache, endpoint, default) | 2000 | Important if adding services |
| Rules per security group | 60 inbound, 60 outbound | <10 per group | 48 | Must not exceed with future rules |
| Network interfaces per region | 5000 | ~15 (ECS tasks, endpoints, ALB) | 4000 | Critical for scaling |
| Elastic IPs per region | 5 | 2 (NAT Gateways) | 4 | Tight default — monitor closely |
| NAT Gateways per AZ | 5 | 1 per AZ (2 total) | 4 | Low risk |
| Route tables per VPC | 200 | 6 (2 public + 2 private + 2 custom) | 160 | Low risk |
| VPC endpoints per VPC (Gateway) | 20 | 2 (S3, DynamoDB) | 16 | Low risk |
| VPC endpoints per VPC (Interface) | 50 | 4 (CW Logs, SM, ECR×2) | 40 | Monitor if adding services |

### ECS Quotas

| Quota | Default Limit | Platform Usage | Alarm Threshold (80%) | Relevance |
|-------|--------------|----------------|----------------------|-----------|
| Clusters per region | 10000 | 1 | 8000 | Low risk |
| Services per cluster | 5000 | 1 | 4000 | Low risk |
| Tasks per service (desired count) | 5000 | 2–10 (auto scaling range) | 4000 | Low risk |
| Fargate On-Demand vCPU per region | 6 | 2 (2 tasks × 1 vCPU) | 4.8 | **Critical** — default is low |
| Task definition revisions | Unlimited | ~50 (deployments) | N/A | No limit |
| Container instances per cluster | 2000 | 0 (Fargate, no EC2) | N/A | Not applicable |

**Note**: Fargate vCPU quota of 6 is very tight. If scaling to 10 tasks at 1 vCPU each, a quota increase to 12+ is required.

### RDS Quotas

| Quota | Default Limit | Platform Usage | Alarm Threshold (80%) | Relevance |
|-------|--------------|----------------|----------------------|-----------|
| DB clusters per region | 40 | 1 (+ 1 DR replica) | 32 | Low risk |
| DB instances per region | 40 | 3 (writer + reader + DR) | 32 | Low risk |
| Total storage per region (Aurora) | 100 TiB | <1 GiB | N/A | Not a concern |
| Manual DB cluster snapshots | 100 | <5 | 80 | Monitor during dev |
| Parameter groups | 50 | 2 (cluster + instance) | 40 | Low risk |
| Subnet groups | 50 | 1 | 40 | Low risk |

### ElastiCache Quotas

| Quota | Default Limit | Platform Usage | Alarm Threshold (80%) | Relevance |
|-------|--------------|----------------|----------------------|-----------|
| Nodes per region | 300 | 2 (primary + replica) | 240 | Low risk |
| Replication groups | 250 | 1 | 200 | Low risk |
| Nodes per replication group | 6 | 2 | 4 | Low risk |
| Parameter groups | 150 | 1 | 120 | Low risk |
| Subnet groups | 150 | 1 | 120 | Low risk |

### Lambda Quotas (Secrets Rotation)

| Quota | Default Limit | Platform Usage | Alarm Threshold (80%) | Relevance |
|-------|--------------|----------------|----------------------|-----------|
| Concurrent executions | 1000 | 1 (rotation only) | 800 | Low risk for platform |
| Function storage (deployment packages) | 75 GB | <50 MB | 60 GB | Low risk |
| Burst concurrency | 500–3000 (region-dependent) | 1 | N/A | Not a concern |

### S3 Quotas

| Quota | Default Limit | Platform Usage | Alarm Threshold (80%) | Relevance |
|-------|--------------|----------------|----------------------|-----------|
| Buckets per account | 100 | 5 (WAF logs, flow logs, app data, audit, static) | 80 | Monitor across all projects |
| Lifecycle rules per bucket | 1000 | 3–5 per bucket | 800 | Low risk |
| Replication rules per bucket | 1000 | 1 per bucket | N/A | Low risk |

### KMS Quotas

| Quota | Default Limit | Platform Usage | Alarm Threshold (80%) | Relevance |
|-------|--------------|----------------|----------------------|-----------|
| Customer managed keys per region | 100000 | 1 | N/A | Not a concern |
| Aliases per CMK | 50 | 1 | N/A | Not a concern |
| Grants per CMK | 50000 | 4 | N/A | Not a concern |
| Cryptographic operations (shared) | 5500–30000 req/sec | <10 req/sec | Region-dependent | Monitor in production |

### CloudWatch Quotas

| Quota | Default Limit | Platform Usage | Alarm Threshold (80%) | Relevance |
|-------|--------------|----------------|----------------------|-----------|
| Alarms per region | 5000 | ~15 (composite + children + quotas) | 4000 | Low risk |
| Dashboards per region | 5000 | 1 | 4000 | Low risk |
| Log groups per region | 1000000 | ~10 | N/A | Not a concern |
| Metric filters per log group | 100 | 5 | 80 | Low risk |

### WAF Quotas

| Quota | Default Limit | Platform Usage | Alarm Threshold (80%) | Relevance |
|-------|--------------|----------------|----------------------|-----------|
| Web ACLs per region | 100 | 1 | 80 | Low risk |
| Rules per Web ACL | 1500 WCU | ~700 WCU (managed groups) | 1200 WCU | **Monitor** — managed rules consume significant WCU |
| IP sets per region | 100 | 1–2 | 80 | Low risk |
| Rate-based rules per Web ACL | 10 | 1 | 8 | Low risk |

### AWS Backup Quotas

| Quota | Default Limit | Platform Usage | Alarm Threshold (80%) | Relevance |
|-------|--------------|----------------|----------------------|-----------|
| Backup vaults per region | 100 | 2 (primary + DR) | 80 | Low risk |
| Backup plans per region | 100 | 1 | 80 | Low risk |
| Recovery points per vault | 1000000 | <100 | N/A | Not a concern |
| Concurrent backup jobs | 500 | 3 (Aurora + EBS + S3) | 400 | Low risk |

---

## Quota Increase Rationale

The following quotas may require increase requests for production usage:

| Quota | Default | Required | Justification |
|-------|---------|----------|---------------|
| Fargate On-Demand vCPU | 6 | 12+ | Auto scaling to 10 tasks × 1 vCPU exceeds default |
| Elastic IPs per region | 5 | 10 | 2 NAT GWs + potential future NAT GWs in DR region |

**For the demo environment**: No quota increases are required. The platform operates well within all default limits during a 2-hour demo session.

---

## Alarm Configuration

All quota alarms use the following pattern:

```hcl
resource "aws_cloudwatch_metric_alarm" "quota_alarm" {
  alarm_name          = "quota-${service}-${quota_name}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = quota_limit * 0.8  # 80% of limit
  
  metric_name = "ResourceCount"
  namespace   = "AWS/Usage"
  statistic   = "Maximum"
  period      = 300  # 5-minute periods
  
  dimensions = {
    Type     = "Resource"
    Resource = quota_code
    Service  = service_code
    Class    = "None"
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
}
```

### SNS Alert Format

When a quota alarm triggers, the notification includes:

- **Service name**: The AWS service approaching its limit
- **Quota name**: The specific quota being consumed
- **Current usage**: The current resource count
- **Quota limit**: The maximum allowed
- **Percentage consumed**: Current/limit × 100
- **Recommended action**: Request increase or review resource cleanup

---

## Review Schedule

- **Monthly**: Check Trusted Advisor quota utilisation report
- **Quarterly**: Review whether platform growth requires quota increases
- **Before demos**: Verify no quotas are near limits that could cause demo failures
- **After scaling changes**: If max_capacity is increased, verify Fargate vCPU quota supports it
