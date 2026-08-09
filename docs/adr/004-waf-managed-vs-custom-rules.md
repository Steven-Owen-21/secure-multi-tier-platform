# ADR-004: WAF Managed Rules vs Custom Rules

## Status

Accepted

## Date

2024-01-15

## Context

The platform requires WAF protection on the ALB to defend against common web application attacks. AWS WAF offers three approaches:

1. **AWS Managed Rule Groups** — Pre-built, AWS-maintained rule sets covering OWASP Top 10 threats
2. **Custom Rules** — Individually authored rules for specific traffic patterns
3. **Third-party Managed Rules** — Marketplace rule sets from security vendors (Fortinet, Imperva, F5)

## Decision

We chose a **hybrid approach**: AWS Managed Rule Groups as the baseline, augmented with targeted custom rules for platform-specific requirements.

## Rationale

| Criterion | AWS Managed Rules | Custom Rules Only | Third-Party Rules |
|-----------|-------------------|-------------------|-------------------|
| Maintenance | AWS-updated automatically | Manual updates required | Vendor-updated |
| Coverage | OWASP Top 10, known bad inputs, IP reputation | Only what you write | Varies by vendor |
| False positives | Low (broad tuning by AWS) | Predictable (you control) | Variable |
| Cost | Included in WAF pricing | Included in WAF pricing | Additional marketplace subscription |
| Time to implement | Minutes | Hours per rule | Minutes + procurement |
| Customisability | Override actions per rule | Full control | Limited |

### Selected Configuration

**Managed Rule Groups (baseline protection):**

1. `AWSManagedRulesCommonRuleSet` — Core OWASP protections (XSS, path traversal, file inclusion)
2. `AWSManagedRulesSQLiRuleSet` — SQL injection patterns
3. `AWSManagedRulesKnownBadInputsRuleSet` — Known exploit payloads (Log4Shell, etc.)
4. `AWSManagedRulesAmazonIpReputationList` — Known malicious IP addresses

**Custom Rules (platform-specific):**

1. **Rate limiting** — 2000 requests per 5-minute window per IP (Requirement 7.2)
2. **Body size limit** — Block requests with bodies >8KB (Requirement 7.3)

This hybrid approach was selected because:

- **Managed rules provide immediate, comprehensive protection** without custom development effort
- **Automatic updates** from AWS cover emerging threats (new CVEs) without platform changes
- **Custom rules address specific requirements** (rate limiting thresholds, body size) not covered by managed groups
- **Per-rule override capability** allows count mode for tuning before enforcement
- **Zero additional cost** — managed rules are included in standard WAF pricing

## Consequences

- Dependency on AWS maintaining rule group quality and update cadence
- Limited visibility into individual managed rule logic (can monitor via WAF logs)
- False positives from managed rules require rule-level override (count mode or exclusion)
- Custom rate limit may need tuning per actual traffic patterns during demos

## Alternatives Considered

- **Custom rules only**: Maximum control but significant development and maintenance effort; misses emerging threats
- **Third-party rules (Fortinet/F5)**: Additional cost (£20–100/month) disproportionate to demo usage; adds vendor complexity
- **WAF + Shield Advanced**: DDoS protection at £3000/month — grossly over-engineered for portfolio project
