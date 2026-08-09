# Skills Matrix: Platform Components to Solutions Architect Job Requirements

## Overview

This matrix maps each project component to specific Solutions Architect job listing requirements, demonstrating coverage of the key competencies hiring managers evaluate.

## Core Competency Mapping

### Networking & Connectivity

| Job Requirement | Platform Component | Evidence |
|----------------|-------------------|----------|
| VPC design and subnet architecture | `infrastructure/modules/vpc/` | Multi-AZ VPC with public/private subnets, CIDR allocation |
| Network security (NACLs, security groups) | `infrastructure/modules/security-groups/` | Layered security with least-privilege rules per tier |
| NAT Gateway and internet routing | `infrastructure/modules/vpc/` | Per-AZ NAT Gateways with route table isolation |
| VPC endpoints and PrivateLink | `infrastructure/modules/vpc-endpoints/` | Gateway + Interface endpoints with endpoint policies |
| DNS and Route53 | `infrastructure/modules/disaster-recovery/` | Health checks, failover routing, DNS-based DR |
| Load balancing (ALB/NLB) | `infrastructure/modules/alb/` | Cross-AZ ALB with health checks and target groups |
| CDN and edge networking | `infrastructure/modules/cloudfront/` | CloudFront with cache behaviours, OAC, geo-restrictions |

### Database & Storage

| Job Requirement | Platform Component | Evidence |
|----------------|-------------------|----------|
| RDS/Aurora architecture | `infrastructure/modules/rds/` | Aurora PostgreSQL cluster, Multi-AZ, read replicas |
| Database high availability | `infrastructure/modules/rds/` | Automatic failover, cross-region replication |
| Caching strategies (ElastiCache) | `infrastructure/modules/elasticache/` | Redis replication group, cache-aside pattern |
| S3 storage management | `infrastructure/modules/s3-lifecycle/` | Lifecycle policies, intelligent tiering, versioning |
| Data encryption at rest | `infrastructure/modules/kms/` | CMK with grants, encryption context enforcement |
| Backup and recovery | `infrastructure/modules/backup/` | AWS Backup with cross-region vaults, vault lock |
| Database migration | `app/db/migrations/` | Alembic schema versioning |

### Security & Compliance

| Job Requirement | Platform Component | Evidence |
|----------------|-------------------|----------|
| IAM role design and least privilege | `infrastructure/modules/iam-advanced/` | Permission boundaries, session policies, role chaining |
| WAF and application security | `infrastructure/modules/waf/` | Managed + custom rules, rate limiting, logging |
| Secrets management | `infrastructure/modules/secrets-rotation/` | Secrets Manager with Lambda rotation |
| Encryption key management (KMS) | `infrastructure/modules/kms/` | Key policies, grants, encryption context |
| Security monitoring (GuardDuty) | `infrastructure/modules/monitoring/` | GuardDuty + Config + Security Hub integration |
| Compliance frameworks | `docs/well-architected-review.md` | Well-Architected Framework review (6 pillars) |
| Identity federation (OIDC) | `.github/workflows/` | GitHub OIDC federation, no stored credentials |

### Compute & Containers

| Job Requirement | Platform Component | Evidence |
|----------------|-------------------|----------|
| Container orchestration (ECS) | `infrastructure/modules/ecs/` | Fargate service with task definitions |
| Auto scaling | `infrastructure/modules/auto-scaling/` | Target tracking + step scaling + scheduled |
| Containerisation (Docker) | `Dockerfile`, `docker-compose.yml` | Multi-stage build, health checks |
| API design and management | `infrastructure/modules/api-gateway/` | REST API with usage plans, throttling, validation |
| Serverless (Lambda) | `infrastructure/modules/secrets-rotation/` | Rotation Lambda with lifecycle hooks |

### Operations & Observability

| Job Requirement | Platform Component | Evidence |
|----------------|-------------------|----------|
| Monitoring and alerting | `infrastructure/modules/observability/` | Composite alarms, anomaly detection, dashboards |
| Logging strategy | `app/middleware/logging.py` | Structured JSON logging, CloudWatch Logs Insights |
| Incident response | `docs/runbooks/` | Security triage and DR runbooks |
| Cost management | `docs/cost-analysis.md` | Cost analysis, tagging for allocation |
| Service quotas and limits | `infrastructure/modules/service-quotas/` | Proactive monitoring with 80% threshold alarms |

### Architecture & Design

| Job Requirement | Platform Component | Evidence |
|----------------|-------------------|----------|
| Multi-tier architecture design | Entire platform | Public/application/data tier separation |
| High availability patterns | Multi-AZ deployment across all components | Failover, health checks, auto-healing |
| Disaster recovery planning | `infrastructure/modules/disaster-recovery/` | RPO/RTO targets, cross-region replication |
| Infrastructure as Code | All `infrastructure/modules/` | 22 Terraform modules with clear interfaces |
| CI/CD pipeline design | `.github/workflows/` | Multi-stage pipeline with security scanning |
| Documentation and ADRs | `docs/adr/` | 7 Architecture Decision Records |
| Well-Architected reviews | `docs/well-architected-review.md` | All 6 pillars addressed |

### DevOps & Delivery

| Job Requirement | Platform Component | Evidence |
|----------------|-------------------|----------|
| CI/CD automation | `.github/workflows/ci.yml` | Lint → test → scan → build → deploy |
| Testing strategy | `tests/` | Unit + property-based + integration tests |
| Local development environments | `docker-compose.yml`, `Makefile` | Docker Compose + LocalStack parity |
| Code quality and linting | `pyproject.toml` | black, ruff, mypy configuration |
| Version control practices | `.github/` | Branch protection, PR workflows |

---

## Interview Discussion Points

### Per Component Deep-Dive Topics

| Component | Technical Discussion | Design Decision |
|-----------|---------------------|-----------------|
| VPC | CIDR planning, subnet sizing, NAT HA | Why /16 with /24 subnets? Growth planning |
| Security Groups | Stateful vs stateless, rule ordering | Why reference SGs instead of CIDRs? |
| Aurora | Storage architecture, failover mechanics | Why Aurora over RDS? Cost vs capability |
| Redis | Eviction policies, failover handling | Why Redis over Memcached? |
| Cognito | OIDC flow, token lifecycle, groups | Why Cognito over Auth0/Keycloak? |
| WAF | Rule evaluation order, WCU budget | Why managed rules + custom? |
| CloudFront | Cache invalidation, origin failover | Why CDN for an API? |
| Auto Scaling | Cooldown tuning, metric selection | Why CPU + request count together? |
| IAM | Effective permissions calculation | Why 3-tier role chain? |
| KMS | Grant lifecycle, encryption context | Why CMK over AWS-managed? |
| Backup | Vault lock modes, tag-based selection | Why governance mode over compliance? |
| Service Quotas | Proactive vs reactive monitoring | Why 80% threshold? |

### Scenario-Based Questions This Project Addresses

1. "Design a VPC for a multi-tier application" → Full VPC module with rationale
2. "How would you handle secrets rotation?" → Secrets Manager + Lambda rotation
3. "Explain your DR strategy" → Active-passive with documented RPO/RTO
4. "How do you control costs?" → Tagging, auto-scale-to-zero, lifecycle policies
5. "Walk me through your security layers" → WAF → NACLs → SGs → IAM → Encryption
6. "How do you monitor this in production?" → Composite alarms, dashboards, anomaly detection
7. "Explain IAM least privilege" → Permission boundaries + session policies + role chaining
8. "How do you handle database failover?" → Aurora automatic failover <30s + DR runbook

---

## Competency Coverage Summary

| SA Domain | Components Demonstrating | Coverage Level |
|-----------|------------------------|----------------|
| Networking | VPC, SGs, NACLs, Endpoints, ALB, CloudFront, Route53 | Comprehensive |
| Security | WAF, IAM, KMS, GuardDuty, Config, Security Hub, Cognito | Comprehensive |
| Database | Aurora, ElastiCache, Secrets rotation | Strong |
| Compute | ECS Fargate, Auto Scaling, Lambda | Strong |
| Storage | S3 lifecycle, Intelligent Tiering, Object Lock | Strong |
| Operations | CloudWatch, Backup, Service Quotas, Trusted Advisor | Strong |
| Architecture | Multi-tier, Multi-AZ, DR, Well-Architected | Comprehensive |
| DevOps | CI/CD, IaC, Docker, Testing | Strong |
| Cost Management | Tagging, Scale-to-zero, Lifecycle, Demo budget | Moderate |
| Governance | Permission boundaries, Config rules, Vault lock | Strong |
