# AWS Well-Architected Framework Review

## Overview

This document reviews the Secure Multi-Tier Platform against the six pillars of the AWS Well-Architected Framework, demonstrating how each architectural decision maps to enterprise best practices.

---

## 1. Operational Excellence

> The ability to support development and run workloads effectively, gain insight into their operations, and continuously improve supporting processes and procedures.

### Design Principles Applied

| Principle | Implementation |
|-----------|---------------|
| Perform operations as code | All infrastructure defined in Terraform modules with CI/CD automation |
| Make frequent, small, reversible changes | GitHub Actions pipeline with PR-based workflows and staged deployments |
| Refine operations procedures frequently | ADRs document decisions; runbooks are version-controlled |
| Anticipate failure | Multi-AZ deployment, health checks, auto-healing via ECS service scheduler |
| Learn from all operational failures | Structured JSON logging, Logs Insights saved queries, Contributor Insights |

### Key Components

| Component | Pillar Contribution |
|-----------|-------------------|
| **GitHub Actions CI/CD** | Automated lint, test, security scan, deploy pipeline |
| **CloudWatch Dashboards** | Real-time operational visibility (latency, errors, costs) |
| **Composite Alarms** | Reduced alert fatigue; alarm only on genuine platform degradation |
| **Anomaly Detection** | ML-based latency monitoring without static threshold maintenance |
| **Contributor Insights** | Top callers and error sources for operational triage |
| **Structured Logging** | Consistent JSON format enables Logs Insights analysis |
| **Makefile Targets** | Standardised operations: test, lint, format, migrate, seed, run |
| **Service Quotas Monitoring** | Proactive alerts at 80% of service limits |
| **Trusted Advisor** | Automated checks for cost, security, fault tolerance, performance |

### Observability Stack

- **Metrics**: CloudWatch metrics from ALB, ECS, RDS, ElastiCache, API Gateway
- **Logs**: Structured JSON → CloudWatch Logs → Logs Insights
- **Alarms**: Composite alarm (AND logic), anomaly detection, quota alarms
- **Dashboards**: 6-widget operational dashboard with API latency, errors, cache ratio, DB connections, task count, cost

---

## 2. Security

> The ability to protect data, systems, and assets to take advantage of cloud technologies to improve security.

### Design Principles Applied

| Principle | Implementation |
|-----------|---------------|
| Implement a strong identity foundation | IAM role chaining, permission boundaries, session policies |
| Enable traceability | VPC Flow Logs, CloudWatch Logs, GuardDuty, AWS Config |
| Apply security at all layers | WAF → NACLs → Security Groups → IAM → Encryption |
| Automate security best practices | AWS Config rules, Security Hub standards, automated rotation |
| Protect data in transit and at rest | KMS CMK encryption, TLS everywhere, Secrets Manager rotation |
| Keep people away from data | No SSH access, IAM auth for database, no long-lived credentials |
| Prepare for security events | GuardDuty findings → Security Hub → SNS alerts → Runbooks |

### Key Components

| Component | Pillar Contribution |
|-----------|-------------------|
| **WAF Web ACL** | Edge protection: SQL injection, XSS, rate limiting, IP reputation |
| **NACLs** | Stateless subnet-level packet filtering (defence-in-depth) |
| **Security Groups** | Stateful resource-level firewalls with least-privilege rules |
| **Permission Boundaries** | Maximum permission cap regardless of role policy |
| **Role Chaining** | Pipeline → Deployment → Service role with trust conditions |
| **Session Policies** | Runtime resource scoping to tagged resources only |
| **KMS CMK** | Centralised encryption with grants, encryption context, annual rotation |
| **Secrets Manager** | Automatic 30-day rotation with single-user strategy |
| **Cognito** | Managed OAuth2/OIDC, PKCE, JWT validation |
| **GuardDuty** | Intelligent threat detection across VPC, DNS, S3 |
| **AWS Config** | Continuous compliance monitoring (6 rules) |
| **Security Hub** | Unified findings from GuardDuty, Config, WAF |
| **IAM Access Analyzer** | Detection of unused permissions and external access |
| **CloudFront Geo-Restrictions** | GDPR compliance via geographic access control |
| **VPC Endpoints** | Private connectivity, traffic never traverses public internet |
| **S3 Object Lock** | Governance mode prevents audit log deletion |

### Encryption Coverage

| Data Store | At Rest | In Transit |
|-----------|---------|-----------|
| Aurora PostgreSQL | KMS CMK | TLS (SSL enforced) |
| ElastiCache Redis | KMS CMK | TLS |
| S3 Buckets | KMS CMK (SSE-KMS) | HTTPS only |
| Backup Vaults | KMS CMK | TLS |
| Secrets Manager | KMS CMK | TLS |

---

## 3. Reliability

> The ability of a workload to perform its intended function correctly and consistently.

### Design Principles Applied

| Principle | Implementation |
|-----------|---------------|
| Automatically recover from failure | ECS auto-healing, Aurora failover, Redis failover |
| Test recovery procedures | DR runbook with simulated failure procedures |
| Scale horizontally | ECS auto scaling with target tracking and step policies |
| Stop guessing capacity | Auto scaling based on CPU and request count metrics |
| Manage change in automation | Terraform-managed infrastructure, CI/CD pipeline |

### Key Components

| Component | Pillar Contribution |
|-----------|-------------------|
| **Multi-AZ Aurora** | Automatic failover in ~30 seconds |
| **Multi-AZ Redis** | Automatic failover to replica |
| **Multi-AZ ECS** | Tasks distributed across AZs, minimum 2 tasks |
| **ALB Health Checks** | Unhealthy targets removed within 90 seconds |
| **ECS Auto Scaling** | Target tracking (CPU 70%) + step scaling (request count) |
| **NAT Gateway per AZ** | AZ-isolated outbound connectivity |
| **Cross-Region Aurora Replica** | Promotable read replica for DR |
| **Cross-Region Backup** | Backup vault replication to secondary region |
| **Route 53 Failover** | DNS-based traffic routing on health check failure |
| **Cache Degradation** | App continues serving from Aurora if Redis unavailable |
| **Service Quotas** | Proactive monitoring prevents hitting service limits |

### Recovery Targets

| Metric | Target | Mechanism |
|--------|--------|-----------|
| RPO | 1 hour | Continuous Aurora replication + daily backups |
| RTO | 4 hours | Aurora promotion + Route 53 failover + backup restore |
| Single AZ failure | Automatic | Multi-AZ deployment across all tiers |
| Component failure | < 90 seconds | Health checks + ECS auto-healing |

### Auto Scaling Configuration

| Policy | Metric | Target | Cooldown |
|--------|--------|--------|----------|
| Target Tracking | CPU Utilisation | 70% | Out: 60s, In: 300s |
| Step Scaling | Request Count/Target | Steps: +1 at 1000, +2 at 2000 | - |
| Scheduled | Time-based | Scale to 0 outside demo hours | - |
| Boundaries | - | Min: 2, Max: 10 | - |

---

## 4. Performance Efficiency

> The ability to use computing resources efficiently to meet system requirements, and to maintain that efficiency as demand changes.

### Design Principles Applied

| Principle | Implementation |
|-----------|---------------|
| Democratise advanced technologies | Managed services (Aurora, ElastiCache, Cognito, API Gateway) |
| Go global in minutes | CloudFront edge caching, geo-distribution |
| Use serverless architectures | ECS Fargate (no server management) |
| Experiment more often | Local Docker Compose environment for rapid iteration |
| Consider mechanical sympathy | Cache-aside pattern, connection pooling, appropriate instance types |

### Key Components

| Component | Pillar Contribution |
|-----------|-------------------|
| **CloudFront CDN** | Edge caching: API (60s TTL), static assets (24h TTL) |
| **ElastiCache Redis** | Sub-millisecond query result caching, session storage |
| **Cache-Aside Pattern** | Reduces database load; cache hit serves immediately |
| **Aurora Read Replica** | Offloads read queries from writer instance |
| **Connection Pooling** | SQLAlchemy pool (size 10, overflow 20) reduces connection overhead |
| **ECS Fargate** | Right-sized tasks, no over-provisioned EC2 instances |
| **API Gateway Caching** | Response caching at the API management layer |
| **VPC Endpoints** | Lower latency for AWS service calls (no internet round-trip) |
| **Performance Insights** | 7-day query analysis for optimisation |
| **Anomaly Detection** | Detects latency regression without manual threshold tuning |

### Caching Strategy

| Layer | TTL | Purpose |
|-------|-----|---------|
| CloudFront (API) | 60 seconds | Edge response caching |
| CloudFront (Static) | 86,400 seconds | Static asset caching |
| Redis (Query Results) | 60 seconds (configurable) | Database query acceleration |
| Redis (Sessions) | 3,600 seconds | Session state storage |

---

## 5. Cost Optimisation

> The ability to run systems to deliver business value at the lowest price point.

### Design Principles Applied

| Principle | Implementation |
|-----------|---------------|
| Implement cloud financial management | Cost allocation tags, Service Quotas monitoring |
| Adopt a consumption model | Fargate (pay-per-task), on-demand demo deployment |
| Measure overall efficiency | CloudWatch dashboard cost widget, per-component tagging |
| Stop spending money on undifferentiated heavy lifting | Managed services (Aurora, Redis, Cognito, API Gateway) |
| Analyse and attribute expenditure | Mandatory tags: Project, Environment, CostCentre, Component |

### Key Components

| Component | Pillar Contribution |
|-----------|-------------------|
| **Scheduled Scaling** | Scale to 0 outside demo hours (weekdays 09:00-18:00 UTC) |
| **On-Demand Demo** | Provision → demonstrate → destroy; target < £5/2hr session |
| **Docker Compose Local** | £0 development cost with full service parity |
| **S3 Lifecycle Policies** | Automatic tiering: Standard → IA → Glacier → Expire |
| **S3 Intelligent Tiering** | Auto-moves infrequently accessed data to cheaper tiers |
| **Tagging Strategy** | Per-component cost allocation in Cost Explorer |
| **Cost Allocation Tags** | Project, Environment, Component activated for billing |
| **VPC Gateway Endpoints** | S3/DynamoDB access without NAT Gateway data charges |
| **Fargate** | Pay only for running tasks; no idle EC2 cost |
| **CloudFront Caching** | Reduces origin requests (lower compute cost) |
| **4-Hour Cost Alert** | SNS notification if demo runs beyond expected duration |
| **Trusted Advisor** | Automated cost optimisation recommendations |

### Cost Model

| Environment | Monthly Cost | Notes |
|-------------|-------------|-------|
| Development (local) | £0 | Docker Compose + LocalStack |
| Demo (2-hour session) | < £5 | On-demand provision + teardown |
| Idle (no demo running) | £0 | Scale-to-zero, no persistent resources |

---

## 6. Sustainability

> The ability to continually improve sustainability impacts by reducing energy consumption and increasing efficiency.

### Design Principles Applied

| Principle | Implementation |
|-----------|---------------|
| Understand your impact | Cost dashboard tracks resource consumption |
| Establish sustainability goals | Zero-cost local dev, minimal-cost demos |
| Maximise utilisation | Auto scaling ensures tasks match demand; scale-to-zero when idle |
| Anticipate and adopt new, more efficient offerings | Serverless Fargate, Aurora Serverless v2 ready |
| Use managed services | Shared infrastructure more efficient than dedicated |
| Reduce downstream impact | CDN caching reduces repeated origin processing |

### Key Components

| Component | Pillar Contribution |
|-----------|-------------------|
| **ECS Fargate** | Shared compute infrastructure, no idle server waste |
| **Scale-to-Zero** | No resources running outside demo hours |
| **Auto Scaling** | Right-sized capacity matching actual demand |
| **CloudFront Caching** | Reduced origin compute by serving from edge cache |
| **S3 Intelligent Tiering** | Moves data to energy-efficient cold storage automatically |
| **Glacier Archival** | Low-energy long-term storage for compliance data |
| **VPC Endpoints** | Shorter network paths reduce data transfer energy |
| **Spot-Ready Architecture** | ECS Fargate Spot capable for non-critical workloads |
| **Local Development** | Developer laptops instead of cloud resources for daily work |
| **On-Demand Provisioning** | Resources exist only during active demonstrations |

---

## Summary Matrix

| Pillar | Primary Components | Score |
|--------|-------------------|-------|
| Operational Excellence | CI/CD, CloudWatch, Composite Alarms, Logs Insights, Service Quotas | ✅ Strong |
| Security | WAF, IAM Advanced, KMS, Secrets Rotation, GuardDuty, Security Hub | ✅ Strong |
| Reliability | Multi-AZ, Auto Scaling, DR Replication, Route 53 Failover, Backup | ✅ Strong |
| Performance Efficiency | CloudFront, Redis Cache, Connection Pooling, Anomaly Detection | ✅ Strong |
| Cost Optimisation | Scale-to-Zero, Lifecycle Policies, Tagging, Local Dev, On-Demand | ✅ Strong |
| Sustainability | Serverless, Auto Scaling, Caching, On-Demand, Tiered Storage | ✅ Strong |

---

## References

- [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)
- Architecture diagrams: `docs/architecture/`
- ADRs: `docs/adr/`
- Runbooks: `docs/runbooks/`
