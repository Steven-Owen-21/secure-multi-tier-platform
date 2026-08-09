# WAF Module

Deploys an AWS WAF Web ACL attached to the Application Load Balancer, providing multi-layered web application protection using managed rule groups, rate limiting, and custom rules with structured logging for security analysis.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│ WAF Web ACL (attached to ALB)                                        │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Priority 10: CommonRuleSet                                      │ │
│  │   XSS, path traversal, file inclusion, protocol violations      │ │
│  ├─────────────────────────────────────────────────────────────────┤ │
│  │ Priority 20: SQLiRuleSet                                        │ │
│  │   SQL injection patterns in query, body, cookies                │ │
│  ├─────────────────────────────────────────────────────────────────┤ │
│  │ Priority 30: KnownBadInputsRuleSet                              │ │
│  │   Log4j/JNDI, SSRF, known exploit payloads                     │ │
│  ├─────────────────────────────────────────────────────────────────┤ │
│  │ Priority 40: AmazonIpReputationList                             │ │
│  │   Known malicious IPs, bot networks, compromised hosts          │ │
│  ├─────────────────────────────────────────────────────────────────┤ │
│  │ Priority 50: Rate-Based Rule (2000 req / 5 min / IP)           │ │
│  │   DDoS mitigation, brute-force prevention                      │ │
│  ├─────────────────────────────────────────────────────────────────┤ │
│  │ Priority 60: Body Size Limit (> 8KB blocked)                   │ │
│  │   Payload-based attack prevention, resource exhaustion          │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  Blocked requests → HTTP 403 (generic, no architecture details)      │
│                                                                       │
│  Logging → S3 (prefix: AWSLogs/{account}/WAFLogs/{region}/{acl})    │
└─────────────────────────────────────────────────────────────────────┘
```

## Features

- **AWS Managed Common Rule Set**: Protects against OWASP Top 10 threats including XSS, path traversal, and protocol violations
- **SQL Injection Protection**: Dedicated SQLi rule set detecting injection patterns in query strings, request bodies, and cookies
- **Known Bad Inputs**: Blocks known exploit payloads including Log4j/JNDI and SSRF attempts
- **IP Reputation Filtering**: Blocks requests from known malicious IP addresses using Amazon's threat intelligence
- **Rate Limiting**: Configurable per-IP rate limit (default: 2000 requests per 5-minute window) to prevent abuse
- **Body Size Restriction**: Blocks oversized request bodies (default: >8KB) to prevent payload-based attacks
- **Generic 403 Response**: Custom blocked response that doesn't reveal internal architecture details
- **Structured Logging**: WAF logs stored in S3 with prefix structure enabling analysis by rule group and source IP
- **S3 Lifecycle Management**: Automated transitions (Standard → IA → Glacier → Expire) for cost-effective log retention

## Threat Mitigation Summary

| Rule Group | Threats Mitigated | Expected False Positive Rate | Tuning Guidance |
|------------|-------------------|------------------------------|-----------------|
| CommonRuleSet | XSS, path traversal, file inclusion, protocol violations | Low-Medium | Exclude rules for known safe paths (e.g., rich text editor endpoints) |
| SQLiRuleSet | SQL injection in all request components | Low | May trigger on legitimate queries containing SQL keywords; use scope-down statements |
| KnownBadInputsRuleSet | Log4j, SSRF, known CVE payloads | Very Low | Rarely requires tuning; covers well-known exploit signatures |
| AmazonIpReputationList | Bot networks, compromised hosts, scanners | Very Low | No tuning needed; Amazon maintains the list |
| Rate-Based (2000/5min) | DDoS, brute force, credential stuffing | Low | Increase limit for high-traffic APIs; decrease for sensitive endpoints |
| Body Size (>8KB) | Large payload attacks, resource exhaustion | Medium | Increase limit if API accepts file uploads or large JSON bodies |

## Usage

```hcl
module "waf" {
  source = "./modules/waf"

  alb_arn         = module.alb.alb_arn
  rate_limit      = 2000
  body_size_limit = 8192

  environment  = "demo"
  project_name = "secure-multi-tier-platform"

  # Logging configuration
  enable_waf_logging     = true
  waf_log_retention_days = 365
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `alb_arn` | ARN of the ALB to protect | `string` | n/a | yes |
| `rate_limit` | Max requests per 5-min window per source IP | `number` | `2000` | no |
| `body_size_limit` | Max request body size in bytes | `number` | `8192` | no |
| `environment` | Deployment environment name | `string` | `"demo"` | no |
| `project_name` | Project name for resource naming | `string` | `"secure-multi-tier-platform"` | no |
| `enable_waf_logging` | Enable WAF logging to S3 | `bool` | `true` | no |
| `waf_log_retention_days` | Days to retain WAF logs before expiration | `number` | `365` | no |

## Outputs

| Name | Description |
|------|-------------|
| `web_acl_arn` | ARN of the WAF Web ACL |
| `web_acl_id` | ID of the WAF Web ACL |
| `web_acl_name` | Name of the WAF Web ACL |
| `waf_log_bucket` | S3 bucket name for WAF logs (null if logging disabled) |
| `waf_log_bucket_arn` | S3 bucket ARN for WAF logs (null if logging disabled) |
| `web_acl_capacity` | WCU consumed by this Web ACL |

## S3 Log Structure

WAF logs are stored with the following prefix structure, enabling analysis by rule group and source IP:

```
aws-waf-logs-{project}-{env}-{account_id}/
└── AWSLogs/
    └── {account_id}/
        └── WAFLogs/
            └── {region}/
                └── {web_acl_name}/
                    └── {year}/{month}/{day}/{hour}/
                        └── {log_file}.json.gz
```

Each log entry contains:
- `timestamp`: Request time
- `action`: ALLOW, BLOCK, or COUNT
- `terminatingRuleId`: Which rule triggered the block
- `httpRequest.clientIp`: Source IP address
- `httpRequest.uri`: Request path
- `ruleGroupList`: All rule groups evaluated and their results

## Custom Response

When a request is blocked, the ALB returns:

```json
{
  "error": "Forbidden",
  "message": "Your request has been blocked.",
  "status": 403
}
```

This response intentionally omits:
- WAF rule that triggered the block
- Internal service names or architecture details
- Stack traces or debug information
- Server software versions

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | ~> 5.0 |

## Related Modules

- **alb**: Provides `alb_arn` — the resource protected by this WAF Web ACL
- **s3-lifecycle**: May consume `waf_log_bucket` for centralised lifecycle management
- **observability**: May consume WAF CloudWatch metrics for dashboards and alarms
- **monitoring**: Security Hub receives WAF findings for unified security posture
