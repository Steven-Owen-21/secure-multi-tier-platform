# VPC Endpoint Cost/Security Trade-Off Documentation

## Overview

VPC endpoints enable private connectivity between the VPC and AWS services without traversing the public internet via NAT Gateway. This document explains the cost and security trade-offs between the two endpoint types and justifies the platform's endpoint selection.

## Endpoint Types

### Gateway Endpoints (Free)

Gateway endpoints are route-table-level constructs that redirect traffic destined for a specific AWS service to a private path within the AWS network.

| Characteristic | Detail |
|---------------|--------|
| Supported services | S3, DynamoDB only |
| Cost | Free (no hourly or data charges) |
| Implementation | Route table entry per subnet |
| DNS | Uses public DNS names (no private DNS) |
| Security | Endpoint policy restricts accessible resources |
| High availability | Managed by AWS, no AZ-specific deployment |
| Network path | Traffic stays within AWS network via route table |

### Interface Endpoints (PrivateLink, Paid)

Interface endpoints create ENIs (Elastic Network Interfaces) in specified subnets, providing a private IP address that routes to the AWS service.

| Characteristic | Detail |
|---------------|--------|
| Supported services | 100+ AWS services (CloudWatch, Secrets Manager, ECR, etc.) |
| Cost | £0.01/hour per AZ + £0.01/GB processed |
| Implementation | ENI in each specified subnet |
| DNS | Private DNS overrides public endpoints |
| Security | Security group controls + endpoint policy |
| High availability | Deploy in multiple AZs (ENI per AZ) |
| Network path | Traffic routes to ENI → PrivateLink → service |

---

## Platform Endpoint Selection

| Service | Endpoint Type | Justification |
|---------|--------------|---------------|
| S3 | Gateway | Free, high traffic (logs, static assets), no hourly cost |
| DynamoDB | Gateway | Free, Terraform state locking via DynamoDB |
| CloudWatch Logs | Interface | ECS tasks emit logs continuously; private path avoids NAT |
| Secrets Manager | Interface | Credential retrieval must be private (security-critical) |
| ECR API | Interface | Container image pulls must not traverse internet |
| ECR Docker | Interface | Docker layer downloads (large payloads) |

---

## Cost Analysis

### Without VPC Endpoints (NAT Gateway Only)

All AWS service API calls from private subnets traverse the NAT Gateway:

| Cost Component | Rate | Monthly Estimate |
|----------------|------|-----------------|
| NAT Gateway hourly | £0.045/hour × 2 AZs × 730 hours | £65.70 |
| NAT Gateway data processing | £0.045/GB | Varies by traffic |
| CloudWatch Logs via NAT | £0.045/GB × ~5GB/month | £0.23 |
| ECR pulls via NAT | £0.045/GB × ~2GB/month | £0.09 |
| Secrets Manager via NAT | £0.045/GB × negligible | ~£0 |

**Total NAT processing for AWS service traffic: ~£0.32/month** (demo usage)

### With VPC Endpoints (Current Configuration)

| Cost Component | Rate | Monthly Estimate |
|----------------|------|-----------------|
| NAT Gateway hourly (still needed for internet) | £0.045/hour × 2 AZs × 730 hours | £65.70 |
| S3 Gateway endpoint | Free | £0 |
| DynamoDB Gateway endpoint | Free | £0 |
| CloudWatch Logs Interface (2 AZs) | £0.01/hour × 2 × 730 hours | £14.60 |
| Secrets Manager Interface (2 AZs) | £0.01/hour × 2 × 730 hours | £14.60 |
| ECR API Interface (2 AZs) | £0.01/hour × 2 × 730 hours | £14.60 |
| ECR Docker Interface (2 AZs) | £0.01/hour × 2 × 730 hours | £14.60 |
| Data processing (all interfaces) | £0.01/GB × ~7GB | £0.07 |

**Total interface endpoint cost: ~£58.47/month** (if running 24/7)

### Demo-Only Cost (2-hour session)

| Component | Cost |
|-----------|------|
| Interface endpoints (4 × 2 AZs × 2 hours) | £0.16 |
| NAT Gateway (2 AZs × 2 hours) | £0.18 |
| Data processing | ~£0.01 |
| **Total networking cost per demo** | **£0.35** |

---

## Security Comparison

### NAT Gateway Path (Without Endpoints)

```
ECS Task → Private Subnet → NAT Gateway → Internet Gateway → AWS Service (public endpoint)
```

**Security characteristics:**
- Traffic leaves VPC (to NAT) but stays within AWS backbone
- Service accessed via public endpoint (TLS encrypted)
- No resource-level endpoint policy
- NAT Gateway provides some obfuscation (shared Elastic IP)
- Visible in VPC Flow Logs as outbound internet traffic

### VPC Endpoint Path (With Endpoints)

```
ECS Task → Private Subnet → ENI (Interface) or Route Table (Gateway) → AWS Service (private)
```

**Security characteristics:**
- Traffic never leaves the VPC (private path)
- Endpoint policy restricts which resources can be accessed
- Security group on interface endpoint controls which resources can connect
- Not visible as internet traffic in Flow Logs (appears as local traffic)
- Defence against DNS poisoning (private DNS resolution)
- Supports condition keys in IAM policies (aws:sourceVpce)

### Security Benefits Matrix

| Security Control | NAT Path | Gateway Endpoint | Interface Endpoint |
|-----------------|----------|------------------|-------------------|
| Traffic stays in VPC | No | Yes | Yes |
| Endpoint policy (resource restriction) | N/A | Yes | Yes |
| Security group control | No | No | Yes |
| Private DNS | No | No | Yes |
| IAM condition: aws:sourceVpce | No | Yes | Yes |
| No internet path required | No | Yes | Yes |

---

## Decision Framework: When to Use Each Type

### Use Gateway Endpoints When:

- Service is S3 or DynamoDB (only supported services)
- Free — no reason not to use them
- High-volume data transfer (S3 logs, large objects)
- Route table integration is sufficient (no per-request security group control needed)

### Use Interface Endpoints When:

- Security requirement mandates private connectivity (Secrets Manager, ECR)
- Need security group control on who can access the endpoint
- Need private DNS for transparent routing
- Service is not S3 or DynamoDB
- Compliance requires no internet-routable traffic for the service

### Use NAT Gateway (No Endpoint) When:

- Service has no VPC endpoint support
- Traffic volume is very low (cost of interface endpoint exceeds NAT processing)
- The service is non-sensitive (e.g., external API calls, package repositories)

---

## Platform Justification

| Service | Why Endpoint? |
|---------|---------------|
| **S3** | Free gateway; all log buckets and static assets accessed privately; endpoint policy restricts to platform buckets only |
| **DynamoDB** | Free gateway; Terraform state locking must be reliable and private |
| **CloudWatch Logs** | Security: application logs contain request details including tokens; continuous high-volume traffic |
| **Secrets Manager** | Security-critical: database credentials must never traverse a public path; IAM condition restricts to VPC only |
| **ECR** | Security: container images are intellectual property; large transfer volume during deployments |

Services **not** given endpoints (traverse NAT):
- **STS** (infrequent role assumption calls, low volume)
- **SNS** (outbound notifications only, low volume)
- **KMS** (consider adding if budget allows — encrypted operations are security-sensitive)

---

## Recommendations for Production

For a production deployment running 24/7:

1. **Add KMS interface endpoint** — encryption/decryption operations should be private
2. **Add STS interface endpoint** — role assumption for task roles should be private
3. **Evaluate single-AZ endpoints** — if budget constrained, deploy interface endpoints in one AZ only (reduced HA but halved cost)
4. **Monitor data processing charges** — if ECR pull volume is high, interface endpoint data cost may still be less than NAT processing cost
5. **Consider PrivateLink for third-party services** — if integrating with external SaaS via PrivateLink marketplace offerings
