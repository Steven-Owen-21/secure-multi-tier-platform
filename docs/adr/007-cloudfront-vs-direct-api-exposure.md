# ADR-007: CloudFront CDN vs Direct API Exposure

## Status

Accepted

## Date

2024-01-15

## Context

The platform API endpoint can be exposed to clients in two ways:

1. **Direct API Gateway exposure** — Clients connect directly to the regional API Gateway endpoint
2. **CloudFront distribution** — Clients connect to CloudFront edge locations which proxy to API Gateway

Additionally, static assets (OpenAPI docs, architecture diagrams) need a delivery mechanism.

## Decision

We chose **CloudFront** as the entry point for both API traffic and static assets.

## Rationale

| Criterion | CloudFront + API GW | Direct API Gateway |
|-----------|--------------------|--------------------|
| Edge caching | Yes (configurable per path) | No (regional only) |
| DDoS protection | AWS Shield Standard (included) | AWS Shield Standard (included) |
| SSL termination | Edge (global PoPs) | Regional endpoint only |
| Custom error pages | Supported (S3 static pages) | Limited (Gateway responses) |
| Geographic restrictions | Native feature | Not available |
| Static asset hosting | OAC to S3 (secure) | Separate S3 website endpoint |
| Cost (demo 2hr) | ~£0 (free tier: 1TB/month, 10M requests) | ~£0 |
| Latency (UK clients) | ~5ms (London edge) | ~10ms (eu-west-2 direct) |
| Additional origin options | Multiple origins, failover groups | Single ALB integration |

CloudFront was selected because:

- **Cache behaviours** enable differentiated caching: 60s for API responses, 86400s for static assets (Requirement 18.3)
- **Origin Access Control (OAC)** provides secure S3 access without making the bucket public (Requirement 18.2)
- **Geographic restrictions** demonstrate GDPR compliance patterns (Requirement 18.5) — a valuable SA discussion point
- **Custom error pages** from S3 provide branded error responses (Requirement 18.4)
- **Zero additional cost** within free tier for demo-scale traffic
- **Portfolio demonstration** — shows understanding of edge architecture and content delivery patterns
- **Static documentation hosting** — architecture diagrams and OpenAPI spec served from S3 via CloudFront

### Cache Behaviour Configuration

| Path Pattern | Origin | TTL | Cache Policy |
|-------------|--------|-----|-------------|
| `/api/*` | API Gateway | 60 seconds | CachingOptimized with query strings |
| `/static/*` | S3 bucket | 86400 seconds (24hr) | CachingOptimized |
| Default (`*`) | S3 bucket | 86400 seconds | CachingOptimized |

## Consequences

- Adds a layer of complexity to request tracing (CloudFront request IDs differ from API Gateway request IDs)
- Cache invalidation required when static content changes (automated in CI/CD pipeline)
- API caching (60s TTL) means slightly stale responses for rapidly changing data (acceptable for read-heavy demo workload; writes bypass cache via POST/PUT/DELETE)
- CloudFront distribution provisioning adds ~10 minutes to demo deployment time

## Alternatives Considered

- **Direct API Gateway**: Simpler architecture but misses the opportunity to demonstrate CDN patterns, geographic restrictions, and multi-origin configuration
- **CloudFront + ALB (bypassing API GW)**: Eliminates API Gateway but loses usage plans, throttling, and request validation — these are key demonstration features
- **S3 static website hosting (separate from API)**: Requires public bucket or presigned URLs; less elegant than unified CloudFront distribution with OAC
