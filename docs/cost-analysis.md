# Cost Analysis

## Overview

This document compares the platform architecture costs at three scale points: development (£0), demo (£5/2hr), and hypothetical production (monthly estimate for 1000 concurrent users).

---

## Development Environment: £0/month

The local development environment uses Docker Compose and incurs no AWS costs.

| Component | Local Implementation | Cost |
|-----------|---------------------|------|
| Database | PostgreSQL 15 (Docker container) | £0 |
| Cache | Redis 7 (Docker container) | £0 |
| AWS Services | LocalStack (Docker container) | £0 |
| Compute | FastAPI (local Python process) | £0 |
| Auth | LocalStack Cognito emulation | £0 |
| Storage | Local filesystem (S3 via LocalStack) | £0 |
| KMS | LocalStack KMS emulation | £0 |
| Monitoring | Local logging (stdout) | £0 |
| **Total** | | **£0** |

### What's Covered Locally

- Full API functionality (CRUD operations, auth flows)
- Database migrations and schema testing
- Cache-aside pattern validation
- Property-based tests (no AWS required)
- Integration tests against LocalStack

### What Requires AWS (Demo Only)

- Multi-AZ failover behaviour
- Real CloudFront distribution
- GuardDuty/Security Hub findings
- Cross-region replication
- WAF with real traffic inspection
- Auto scaling under load

---

## Demo Environment: £5 Target for 2-Hour Session

### Cost Breakdown by Service

| Service | Resource | Hourly Rate | 2-Hour Cost |
|---------|----------|-------------|-------------|
| **Aurora PostgreSQL** | db.t4g.medium (writer) | £0.073 | £0.15 |
| | db.t4g.medium (reader) | £0.073 | £0.15 |
| **ElastiCache Redis** | cache.t4g.micro (primary) | £0.016 | £0.03 |
| | cache.t4g.micro (replica) | £0.016 | £0.03 |
| **ECS Fargate** | 2 tasks × 1 vCPU × 2 GB | £0.04/task | £0.16 |
| **NAT Gateway** | 2 × per-AZ | £0.045 each | £0.18 |
| **ALB** | Application Load Balancer | £0.023 | £0.05 |
| | LCU charges (minimal) | ~£0.01 | £0.02 |
| **API Gateway** | REST API (per-request) | £0.003/1k | ~£0.01 |
| **VPC Endpoints** | 4 interface endpoints × 2 AZs | £0.01/hr each | £0.16 |
| **WAF** | Web ACL + rules | £0.005 | £0.01 |
| **CloudFront** | Distribution (free tier) | £0 | £0.00 |
| **KMS** | 1 CMK + API calls | £0.0008/hr + £0.03/10k | £0.01 |
| **Secrets Manager** | 2 secrets + API calls | £0.0005/hr each | ~£0.01 |
| **CloudWatch** | Alarms + dashboards + logs | Variable | £0.05 |
| **S3** | Log buckets (minimal data) | Negligible | £0.01 |
| **Route53** | Health checks (2) | £0.50/month prorated | £0.01 |
| **GuardDuty** | Enabled (minimal activity) | £0.004/hr | £0.01 |
| **AWS Config** | 5 rules | £0.003/evaluation | £0.02 |
| **Security Hub** | Enabled | £0.0010/finding | £0.01 |
| **AWS Backup** | Vault (no recovery points in 2hr) | £0 | £0.00 |
| **Service Quotas** | Monitoring (CW alarms) | Included in CW | £0.00 |
| **IAM Access Analyzer** | Enabled | £0 | £0.00 |

### Total Demo Cost

| Category | Subtotal |
|----------|----------|
| Compute (ECS + ALB) | £0.23 |
| Database (Aurora) | £0.30 |
| Cache (Redis) | £0.06 |
| Networking (NAT + Endpoints) | £0.34 |
| Security (WAF + GuardDuty + Config + SecHub) | £0.05 |
| API & CDN (API GW + CloudFront) | £0.01 |
| Operations (CW + KMS + Secrets + Route53) | £0.09 |
| Storage (S3 + Backup) | £0.01 |
| **Grand Total (2 hours)** | **£1.09** |

### Safety Margin

The £5 target includes significant headroom for:

- Extended demo duration (up to ~8 hours before hitting £5)
- Variable data transfer charges during live demonstrations
- Unexpected CloudWatch log ingestion volume
- Multiple demo deployments in a single day

### Cost Safety Controls

1. **4-hour cost alert**: SNS notification if infrastructure runs beyond 4 hours without teardown
2. **Scheduled scale-to-zero**: ECS tasks scale to 0 outside demo hours
3. **terraform destroy**: Complete teardown returns monthly cost to £0
4. **Budget alarm**: AWS Budgets alert at £5 and £10 thresholds

---

## Hypothetical Production: Monthly Estimate (1000 Concurrent Users)

### Assumptions

- 1000 concurrent users during business hours (12 hours/day, 22 days/month)
- Average 10 API requests/user/minute during active hours
- 500 MB database storage, growing 10 GB/month
- 80% cache hit ratio
- 50 GB/month data transfer out

### Cost Breakdown

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| **Aurora PostgreSQL** | db.r6g.large (writer) + db.r6g.large (reader) | £475 |
| | Storage (100 GB) + I/O | £50 |
| | Cross-region replica | £240 |
| **ElastiCache Redis** | cache.r6g.large (primary + replica) | £350 |
| **ECS Fargate** | 4–10 tasks × 2 vCPU × 4 GB (auto scaling) | £580 |
| **NAT Gateway** | 2 × per-AZ + data processing (50 GB) | £70 |
| **ALB** | Load balancer + LCU (high request count) | £45 |
| **API Gateway** | ~150M requests/month | £450 |
| **VPC Endpoints** | 4 interface endpoints × 2 AZs (730 hours) | £58 |
| **WAF** | Web ACL + rules + requests | £15 |
| **CloudFront** | 50 GB transfer + 150M requests | £85 |
| **KMS** | CMK + ~500k crypto operations/month | £20 |
| **Secrets Manager** | 4 secrets + rotation | £5 |
| **CloudWatch** | 15 alarms + dashboard + 100 GB logs | £80 |
| **S3** | 500 GB storage + lifecycle transitions | £15 |
| **Route53** | Hosted zone + health checks + queries | £5 |
| **GuardDuty** | VPC flow log + CloudTrail analysis | £30 |
| **AWS Config** | 5 rules + evaluations | £10 |
| **Security Hub** | Findings aggregation | £5 |
| **AWS Backup** | Daily backups + cross-region copy (50 GB) | £15 |
| **Service Quotas** | Monitoring (included in CW) | £0 |
| **IAM Access Analyzer** | Enabled | £0 |
| **Data Transfer** | 50 GB out (after CloudFront) | £4 |

### Total Production Estimate

| Category | Monthly Cost |
|----------|-------------|
| Compute | £625 |
| Database | £765 |
| Cache | £350 |
| Networking | £173 |
| API & CDN | £535 |
| Security | £60 |
| Operations | £105 |
| Storage & Backup | £30 |
| **Grand Total** | **~£2,643/month** |

### Cost Optimisation Opportunities (Production)

| Optimisation | Potential Saving | Trade-off |
|-------------|------------------|-----------|
| Reserved Instances (Aurora + Redis, 1-year) | ~30% on DB/Cache (£330/month) | Commitment |
| Fargate Savings Plans (1-year) | ~20% on compute (£115/month) | Commitment |
| API Gateway HTTP API (instead of REST) | ~70% on API GW (£315/month) | Fewer features |
| Single NAT Gateway | £35/month | Reduced AZ resilience |
| CloudFront reserved capacity | Varies | Volume commitment |
| **Total potential savings** | **~£795/month** | Mix of commitments |

**Optimised production cost**: ~£1,848/month

---

## Cost Comparison Summary

| Environment | Monthly Cost | Per-User Cost | Notes |
|-------------|-------------|---------------|-------|
| Development | £0 | N/A | Docker Compose + LocalStack |
| Demo (2-hour session) | £1.09 one-off | N/A | Well within £5 target |
| Production (1000 users) | £2,643 | £2.64/user/month | On-demand pricing |
| Production (optimised) | £1,848 | £1.85/user/month | With reserved capacity |

---

## Key Takeaways for SA Interviews

1. **Zero-cost development** demonstrates cost-awareness and local-first development practices
2. **£1.09 demo cost** shows the platform can be demonstrated live without financial risk
3. **Production estimates** show understanding of cost drivers at scale
4. **Optimisation paths** demonstrate knowledge of AWS pricing models (RIs, Savings Plans)
5. **Cost safety controls** (scale-to-zero, alerts, teardown) demonstrate operational maturity
