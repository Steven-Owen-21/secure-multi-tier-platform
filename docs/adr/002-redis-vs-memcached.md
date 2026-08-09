# ADR-002: ElastiCache Redis vs Memcached

## Status

Accepted

## Date

2024-01-15

## Context

The platform requires a caching layer for two purposes:

1. **Session storage** — User session data with TTL management
2. **Query result caching** — Database query results with cache-aside pattern and invalidation

Both ElastiCache Redis and ElastiCache Memcached were evaluated.

## Decision

We chose **ElastiCache Redis 7** with a replication group (primary + 1 replica).

## Rationale

| Criterion | Redis | Memcached |
|-----------|-------|-----------|
| Data structures | Rich (strings, hashes, sets, sorted sets, lists) | Key-value only |
| Persistence | Optional AOF/RDB snapshots | None |
| Replication | Native primary/replica with automatic failover | None (client-side sharding) |
| TLS in transit | Supported | Supported (since 1.6.12) |
| Encryption at rest | Supported | Supported |
| Pub/Sub | Supported (useful for cache invalidation) | Not available |
| Session management | Native TTL per key, atomic operations | TTL per key only |
| Multi-AZ failover | Automatic with replica promotion | Manual (re-provision) |
| Keyspace notifications | Supported (invalidation events) | Not available |

Redis was selected because:

- **Automatic failover** with replica promotion satisfies the HA requirement (Requirement 4.1) without application-level handling
- **Rich data structures** (hashes for sessions, sorted sets for pagination) simplify application code
- **Keyspace notifications** enable cache invalidation patterns required by the cache-aside implementation (Requirement 4.6)
- **TLS + AUTH token** provides defence-in-depth for the caching layer (Requirement 4.2)
- **Single-node replica** is sufficient for the demo workload while demonstrating Multi-AZ patterns

## Consequences

- Single-threaded model means vertical scaling for CPU-bound operations (acceptable for demo workload)
- Slightly higher memory overhead per key compared to Memcached
- Redis AUTH token must be rotated via Secrets Manager (adds rotation Lambda complexity)
- Application must handle the failover window (~15 seconds) gracefully — implemented via cache-miss fallback to database

## Alternatives Considered

- **Memcached**: Simpler, multi-threaded, but no replication/failover — unsuitable for session storage reliability requirement
- **Redis Cluster mode**: Horizontal sharding — over-engineered for demo scale, adds operational complexity without portfolio benefit
- **DynamoDB DAX**: Tightly coupled to DynamoDB — not applicable to PostgreSQL query caching pattern
