# ADR-005: Multi-AZ vs Multi-Region for High Availability

## Status

Accepted

## Date

2024-01-15

## Context

The platform must demonstrate enterprise high-availability patterns. Two strategies were evaluated:

1. **Multi-AZ only** — All components deployed across 2+ Availability Zones within a single region
2. **Multi-Region active-active** — Full stack deployed in multiple regions with synchronous replication
3. **Multi-Region active-passive (pilot light)** — Primary region active, secondary region with minimal resources for DR failover

## Decision

We chose **Multi-AZ as the primary HA strategy** with **multi-region active-passive (pilot light)** for disaster recovery.

## Rationale

| Criterion | Multi-AZ Only | Multi-Region Active-Active | Multi-Region Active-Passive |
|-----------|---------------|---------------------------|----------------------------|
| AZ failure tolerance | Yes | Yes | Yes |
| Region failure tolerance | No | Yes | Yes (with RTO) |
| Data consistency | Strong (synchronous) | Eventual (async replication) | Eventual (async) |
| Cost (demo) | Baseline | 2x baseline | Baseline + ~20% (replica costs) |
| Complexity | Low | Very high (conflict resolution, global tables) | Medium (failover automation) |
| RTO | <30s (within region) | Near-zero (already active) | 4 hours (stated target) |
| RPO | 0 (synchronous) | Seconds (async replication) | 1 hour (replication lag) |
| Portfolio demonstration value | Standard HA | Advanced distributed systems | Enterprise DR planning |

The active-passive approach was selected because:

- **Multi-AZ handles 99% of failure scenarios** — AZ failures are far more common than full region failures
- **RTO of 4 hours** (Requirement 9.1) does not require active-active — pilot light with Route53 failover is sufficient
- **RPO of 1 hour** (Requirement 9.1) is achievable with Aurora cross-region read replicas (continuous replication with <1 minute lag)
- **Cost efficiency** — secondary region only runs read replicas and S3 replication, not full compute stack
- **Demonstrates DR planning skills** — documenting RPO/RTO, failover procedures, and testing plans is highly valued in SA interviews
- **Realistic for the workload** — active-active adds significant complexity (write conflict resolution, global session management) without proportional value for a demo API

### Architecture Summary

| Component | Multi-AZ (Primary) | Multi-Region (DR) |
|-----------|--------------------|--------------------|
| ECS tasks | 2 tasks across 2 AZs | None (launch on failover) |
| Aurora | Writer + Reader across AZs | Cross-region read replica |
| Redis | Primary + Replica across AZs | None (cold start on failover) |
| ALB | Cross-AZ with health checks | Created on failover |
| S3 | Standard (3 AZ replication) | Cross-region replication |
| Route53 | Primary failover record | Secondary failover record |

## Consequences

- Region failure requires manual or automated failover process (documented in DR runbook)
- RTO of 4 hours means short outage during region failure (acceptable for this workload class)
- Aurora replica promotion in DR region takes 5–10 minutes
- Redis cache is cold in DR region (acceptable — cache warms naturally from database)
- Demo deployments use primary region only (DR infrastructure is defined but not provisioned during demos to save cost)

## Alternatives Considered

- **Multi-AZ only (no DR)**: Simpler and cheaper but fails to demonstrate DR planning — a key SA interview topic
- **Multi-Region active-active**: Technically impressive but adds complexity (DynamoDB Global Tables, conflict resolution, global Redis) that is disproportionate and would exceed the £5 demo budget significantly
