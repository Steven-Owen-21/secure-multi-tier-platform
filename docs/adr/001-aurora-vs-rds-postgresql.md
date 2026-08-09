# ADR-001: Aurora PostgreSQL vs Standard RDS PostgreSQL

## Status

Accepted

## Date

2024-01-15

## Context

The platform requires a managed relational database for the data tier. Two options within the AWS RDS ecosystem were evaluated:

1. **Standard RDS PostgreSQL** — Single-instance or Multi-AZ deployment with manual read replica configuration
2. **Aurora PostgreSQL** — AWS-proprietary storage engine with native cluster topology and automatic failover

Key evaluation criteria: failover speed, operational overhead, cost for short demo sessions, Multi-AZ native support, and alignment with SA portfolio demonstration goals.

## Decision

We chose **Aurora PostgreSQL 15** as the database engine.

## Rationale

| Criterion | Aurora PostgreSQL | Standard RDS PostgreSQL |
|-----------|------------------|------------------------|
| Failover time | <30 seconds (native) | 60–120 seconds (DNS propagation) |
| Read replicas | Up to 15, shared storage | Up to 5, async replication lag |
| Storage | Auto-scaling, distributed | Pre-provisioned EBS |
| Multi-AZ | Native cluster topology | Standby instance (synchronous) |
| IAM auth | Supported | Supported |
| Cost (demo 2hr) | ~£0.15 (db.t4g.medium) | ~£0.10 (db.t4g.medium) |
| Portfolio impact | Demonstrates enterprise-grade choice | Perceived as entry-level |

Aurora was selected because:

- **Native Multi-AZ clustering** aligns with the HA requirement (Requirement 10) without additional configuration
- **Sub-30-second failover** satisfies the RTO requirement for the database tier (Requirement 9)
- **Shared storage architecture** means read replicas share the same data with no replication lag, simplifying DR (Requirement 9.2)
- **Cross-region read replicas** enable the DR architecture with minimal additional configuration
- **Marginal cost difference** (~£0.05 extra per 2-hour demo) is negligible against the architectural benefits
- **SA portfolio positioning** — Aurora demonstrates awareness of enterprise database patterns expected in senior SA roles

## Consequences

- Slightly higher cost per hour compared to standard RDS (offset by demo-only usage pattern)
- Lock-in to Aurora-specific features (cluster endpoints, storage auto-scaling) — acceptable for portfolio project
- Cross-region replica promotion during DR requires Aurora-specific Terraform configuration
- Performance Insights and Enhanced Monitoring available at no additional cost for demo-duration usage

## Alternatives Considered

- **Standard RDS PostgreSQL Multi-AZ**: Lower cost but slower failover and less impressive portfolio demonstration
- **Aurora Serverless v2**: Auto-scaling compute but unpredictable costs for budget-constrained demo; min 0.5 ACU still charges when idle
