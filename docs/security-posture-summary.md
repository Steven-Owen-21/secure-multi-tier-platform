# Security Posture Summary

## Overview

This document summarises all security controls implemented in the platform, their layering across network, application, and data tiers, and the defence-in-depth strategy that ensures no single control failure exposes the system to compromise.

## Defence-in-Depth Model

```
┌─────────────────────────────────────────────────────────────────┐
│                        Layer 1: Edge                             │
│  CloudFront │ WAF │ Geographic Restrictions │ Shield Standard    │
├─────────────────────────────────────────────────────────────────┤
│                     Layer 2: Network Perimeter                   │
│  NACLs │ Security Groups │ VPC Isolation │ Private Subnets       │
├─────────────────────────────────────────────────────────────────┤
│                     Layer 3: API Management                      │
│  API Gateway │ Rate Limiting │ Request Validation │ Usage Plans  │
├─────────────────────────────────────────────────────────────────┤
│                     Layer 4: Authentication                      │
│  Cognito OIDC │ JWT Validation │ RBAC │ Token Expiry            │
├─────────────────────────────────────────────────────────────────┤
│                     Layer 5: Application                         │
│  Input Validation │ Structured Logging │ Error Handling          │
├─────────────────────────────────────────────────────────────────┤
│                     Layer 6: Identity & Access                   │
│  Permission Boundaries │ Session Policies │ Role Chaining │ IAM │
├─────────────────────────────────────────────────────────────────┤
│                     Layer 7: Data Protection                     │
│  KMS CMK │ Encryption at Rest │ TLS in Transit │ Secrets Rotation│
├─────────────────────────────────────────────────────────────────┤
│                     Layer 8: Detection & Response                │
│  GuardDuty │ Config │ Security Hub │ IAM Access Analyzer        │
├─────────────────────────────────────────────────────────────────┤
│                     Layer 9: Recovery                            │
│  AWS Backup │ Cross-Region Replication │ Vault Lock              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Edge Security

| Control | Implementation | Threat Mitigated |
|---------|---------------|-----------------|
| CloudFront | CDN with edge POP distribution | DDoS amplification, latency-based attacks |
| WAF Web ACL | 4 managed rule groups + 2 custom rules | OWASP Top 10, SQLi, XSS, rate abuse |
| Geographic restrictions | Allow-list GB + EU countries | Reduces attack surface from high-risk regions |
| AWS Shield Standard | Automatic (included with CloudFront) | Volumetric DDoS (Layer 3/4) |
| Custom error pages | Generic 403/404/503 from S3 | Information leakage prevention |

**Key principle**: Block known-bad traffic before it reaches the application.

---

## Layer 2: Network Security

| Control | Implementation | Threat Mitigated |
|---------|---------------|-----------------|
| VPC isolation | /16 VPC with no peering | Lateral movement from other accounts |
| Public/private subnet separation | Application and data tiers in private subnets | Direct internet exposure of backend |
| NACLs (public subnets) | Allow HTTPS + ephemeral only | Port scanning, non-HTTPS access |
| NACLs (private subnets) | Allow VPC CIDR only | External access to private resources |
| Security groups (ALB) | Inbound 443 from 0.0.0.0/0 only | Non-HTTPS traffic |
| Security groups (App) | Inbound 8000 from ALB SG only | Direct access bypassing ALB |
| Security groups (DB) | Inbound 5432 from App SG only | Direct database access |
| Security groups (Cache) | Inbound 6379 from App SG only | Direct cache access |
| Security groups (Endpoints) | Inbound 443 from App SG only | Unauthorised endpoint access |
| NAT Gateway (per AZ) | Outbound-only internet access | Inbound connections to private subnets |
| VPC Flow Logs | All traffic logged (ACCEPT + REJECT) | Forensic analysis, anomaly detection |
| VPC endpoints | Private connectivity to AWS services | Data exfiltration via public internet |

**Key principle**: No resource in a private subnet is reachable from outside the VPC unless traffic passes through the ALB.

---

## Layer 3: API Security

| Control | Implementation | Threat Mitigated |
|---------|---------------|-----------------|
| API Gateway request validation | JSON Schema per endpoint | Malformed payload attacks |
| Usage plans and throttling | Free/Standard/Premium tiers | API abuse, scraping, DoS |
| API keys | Client identification | Unauthorised access, attribution |
| Rate limiting (WAF) | 2000 req/5min per IP | Brute force, credential stuffing |
| Body size limit (WAF) | 8KB maximum | Large payload DoS |
| Stage-specific configuration | Dev/staging/production stages | Environment isolation |

**Key principle**: Validate and rate-limit all requests before they reach application code.

---

## Layer 4: Authentication & Authorization

| Control | Implementation | Threat Mitigated |
|---------|---------------|-----------------|
| Cognito OAuth2/OIDC | Authorization Code + PKCE | Token theft (implicit flow), CSRF |
| Password policy | 12 chars, mixed case + number + symbol | Weak password attacks |
| Email verification | Required at sign-up | Account enumeration |
| JWT validation | Signature, expiry, audience checks | Token forgery, replay attacks |
| Role-based access control | admin/manager/viewer groups | Privilege escalation |
| Token expiry | Access: 1 hour, Refresh: 30 days | Stolen token window |
| 401/403 responses | Structured errors without details | Information leakage |

**Key principle**: Verify identity and authorization on every request with short-lived, cryptographically validated tokens.

---

## Layer 5: Application Security

| Control | Implementation | Threat Mitigated |
|---------|---------------|-----------------|
| Pydantic input validation | Schema-level field constraints | Injection, type confusion |
| Parameterised queries | SQLAlchemy ORM (no raw SQL) | SQL injection |
| Structured JSON logging | request_id, user_id, no PII | Log injection, forensic gaps |
| Global error handler | Generic messages, no stack traces | Information disclosure |
| SSL database connections | `sslmode=require` enforced | Connection eavesdropping |
| TLS Redis connections | `ssl=True` in redis-py client | Cache data interception |
| Connection pooling limits | Pool size 10, max overflow 20 | Connection exhaustion DoS |

**Key principle**: Validate all input, parameterise all queries, and reveal nothing useful to attackers in error responses.

---

## Layer 6: Identity Governance

| Control | Implementation | Threat Mitigated |
|---------|---------------|-----------------|
| Permission boundary | Caps Service Role to platform services only | Privilege escalation |
| Session policy | Restricts to tagged resources | Cross-tenant data access |
| Role chaining (3-tier) | Pipeline → Deployer → Service | Single role compromise |
| External ID | Required for cross-role assumption | Confused deputy attacks |
| OIDC federation | No stored credentials in CI/CD | Credential leakage from repos |
| IAM Access Analyzer | Continuous unused permission detection | Permission drift |
| Least-privilege policies | Specific actions on specific ARNs | Over-permissioned roles |

**Key principle**: Even if an attacker compromises one role, boundaries and session policies prevent escalation beyond the platform's scope.

---

## Layer 7: Data Protection

| Control | Implementation | Threat Mitigated |
|---------|---------------|-----------------|
| KMS CMK encryption | All data stores encrypted at rest | Data theft from storage |
| Encryption context | Enforced per service/component | Incorrect key usage |
| KMS grants (not broad policy) | Fine-grained, revocable access | Excessive key access |
| Annual key rotation | Automatic new backing material | Long-term key compromise |
| TLS 1.2+ in transit | All connections (ALB, DB, Cache, APIs) | Network eavesdropping |
| Secrets Manager | Credentials never in code or env vars | Hard-coded credential exposure |
| 30-day secret rotation | Lambda-based automatic rotation | Stale credential access |
| S3 Object Lock | Governance mode on audit logs | Evidence tampering |
| Block public access | All S3 buckets | Accidental public exposure |

**Key principle**: All data is encrypted at rest and in transit, credentials are rotated automatically, and audit logs are immutable.

---

## Layer 8: Detection & Response

| Control | Implementation | Threat Mitigated |
|---------|---------------|-----------------|
| GuardDuty | Threat detection (network + API behaviour) | Active intrusion, credential abuse |
| AWS Config rules | Resource compliance monitoring | Configuration drift |
| Security Hub | Aggregated findings + benchmarks | Visibility gaps |
| IAM Access Analyzer | External access detection | Unintended public exposure |
| Composite alarms | Multi-signal alerting (AND logic) | Alert fatigue from single-metric noise |
| Anomaly detection | P99 latency ML-based baseline | Novel attack patterns |
| VPC Flow Logs | Network traffic analysis | Lateral movement, exfiltration |
| WAF logging | Blocked request analysis | Attack pattern evolution |
| CloudTrail | API call audit (all regions) | Unauthorised API usage |
| SNS notifications | Real-time alerts to operators | Delayed incident response |

**Key principle**: Detect threats through multiple independent signals, correlate findings centrally, and alert with low noise.

---

## Layer 9: Recovery & Resilience

| Control | Implementation | Threat Mitigated |
|---------|---------------|-----------------|
| AWS Backup (daily) | Aurora, EBS, S3 snapshots | Data loss from any cause |
| Cross-region backup copy | DR vault in secondary region | Regional disaster |
| Vault lock (governance mode) | Prevent backup deletion | Ransomware, insider threat |
| Aurora cross-region replica | Continuous replication (<1 min lag) | Regional database failure |
| S3 cross-region replication | 15-minute SLA | Regional storage failure |
| Route53 failover routing | Automatic DNS-based failover | Regional service failure |
| Multi-AZ deployment | All stateful components across 2 AZs | AZ failure |
| ECS auto-healing | Task replacement on health check failure | Individual task failure |

**Key principle**: No single point of failure exists, and recovery from any scope of failure (task, AZ, region) is documented with tested procedures.

---

## Compliance Alignment

| Framework/Standard | Coverage |
|-------------------|----------|
| AWS Well-Architected (Security Pillar) | All best practices addressed |
| CIS AWS Foundations Benchmark | Security Hub checks enabled |
| OWASP Top 10 (2021) | WAF managed rules + application validation |
| GDPR considerations | Geographic restrictions, encryption, audit logging |
| SOC 2 Type II controls | Logging, access control, encryption, monitoring |

---

## Security Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Mean time to detect (MTTD) | <5 minutes | GuardDuty + Route53 health check interval |
| Mean time to respond (MTTR) | <30 minutes | SNS → runbook → action |
| WAF block rate | 0.1–2% of total traffic | CloudWatch WAF metrics |
| Security Hub score | >90% | AWS Foundational Security Best Practices |
| Config compliance | 100% of rules passing | AWS Config dashboard |
| Unused IAM permissions | 0 findings | IAM Access Analyzer |
| Secrets rotation success | 100% | CloudWatch rotation metrics |

---

## Risk Acceptance

| Risk | Likelihood | Impact | Mitigation | Residual Risk |
|------|-----------|--------|------------|---------------|
| Cognito service outage | Low | High (no auth) | Cached token validation (local JWKS) | Accepted |
| KMS key deletion | Very Low | Critical (all data lost) | 30-day deletion window, IAM controls | Accepted |
| DDoS exceeding Shield Standard | Low | Medium (degraded) | CloudFront absorbs, WAF rate limits | Accepted (Shield Advanced not justified) |
| Zero-day in managed rules | Low | Medium | Application-layer validation as backup | Accepted |
| Insider threat (IAM admin) | Very Low | High | CloudTrail audit, permission boundaries | Accepted |
