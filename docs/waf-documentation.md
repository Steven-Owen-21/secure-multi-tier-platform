# WAF Documentation

## Overview

The platform uses AWS WAF (Web Application Firewall) attached to the Application Load Balancer to inspect and filter HTTP requests before they reach the application tier. The WAF configuration uses a combination of AWS-managed rule groups and custom rules.

## Web ACL Structure

```
Web ACL: secure-platform-waf
├── Rule 1: AWS-AWSManagedRulesAmazonIpReputationList (priority 1)
├── Rule 2: AWS-AWSManagedRulesCommonRuleSet (priority 2)
├── Rule 3: AWS-AWSManagedRulesSQLiRuleSet (priority 3)
├── Rule 4: AWS-AWSManagedRulesKnownBadInputsRuleSet (priority 4)
├── Rule 5: Custom-RateLimit (priority 5)
├── Rule 6: Custom-BodySizeLimit (priority 6)
└── Default Action: ALLOW
```

Rules are evaluated in priority order. If a rule matches, its action is taken immediately (BLOCK or COUNT). If no rules match, the default action (ALLOW) is applied.

---

## Rule Groups

### 1. AWSManagedRulesAmazonIpReputationList

**Priority**: 1 (evaluated first)

**Purpose**: Block requests from IP addresses known to be associated with bots, threats, or abuse.

**Threats Mitigated**:
- Requests from known botnet command-and-control servers
- Traffic from IP addresses associated with active campaigns
- Requests from hosting providers commonly used for attacks

**Sub-Rules**:
| Rule Name | Action | Description |
|-----------|--------|-------------|
| AWSManagedIPReputationList | BLOCK | IPs identified as bots or threats |
| AWSManagedReconnaissanceList | BLOCK | IPs performing reconnaissance scans |

**Expected False Positive Rate**: Very low (<0.01%)

**Tuning Guidance**: 
- If a legitimate service IP is blocked, add it to a custom IP allow list (evaluated before managed rules)
- Monitor WAF logs for BLOCK actions from this rule group and verify against known partner/vendor IP ranges

---

### 2. AWSManagedRulesCommonRuleSet (CRS)

**Priority**: 2

**Purpose**: Protect against the OWASP Top 10 most critical web application security risks.

**Threats Mitigated**:
| Rule Name | Threat | OWASP Category |
|-----------|--------|----------------|
| NoUserAgent_HEADER | Bot traffic without User-Agent | Reconnaissance |
| UserAgent_BadBots_HEADER | Known malicious bot signatures | A07:2021 |
| SizeRestrictions_QUERYSTRING | Oversized query strings | Buffer overflow |
| SizeRestrictions_Cookie_HEADER | Oversized cookies | Buffer overflow |
| SizeRestrictions_BODY | Oversized request bodies | Buffer overflow |
| CrossSiteScripting_COOKIE | XSS in cookies | A03:2021 (Injection) |
| CrossSiteScripting_QUERYARGUMENTS | XSS in query parameters | A03:2021 |
| CrossSiteScripting_BODY | XSS in request body | A03:2021 |
| CrossSiteScripting_URIPATH | XSS in URI path | A03:2021 |
| EC2MetaDataSSRF_BODY | SSRF targeting EC2 metadata | A10:2021 (SSRF) |
| EC2MetaDataSSRF_COOKIE | SSRF in cookies | A10:2021 |
| EC2MetaDataSSRF_URIPATH | SSRF in URI path | A10:2021 |
| EC2MetaDataSSRF_QUERYARGUMENTS | SSRF in query params | A10:2021 |
| GenericLFI_QUERYARGUMENTS | Local file inclusion | A01:2021 (Broken Access) |
| GenericLFI_URIPATH | Path traversal in URI | A01:2021 |
| GenericLFI_BODY | LFI in request body | A01:2021 |
| RestrictedExtensions_URIPATH | Requests for sensitive file types | A01:2021 |
| RestrictedExtensions_QUERYARGUMENTS | Sensitive extensions in params | A01:2021 |
| GenericRFI_QUERYARGUMENTS | Remote file inclusion | A03:2021 |
| GenericRFI_BODY | RFI in request body | A03:2021 |
| GenericRFI_URIPATH | RFI in URI path | A03:2021 |

**Expected False Positive Rate**: Low–moderate (0.1–1%)

**Tuning Guidance**:
- **XSS rules**: May trigger on legitimate HTML content in request bodies. If your API accepts rich text, set CrossSiteScripting_BODY to COUNT mode and validate at the application layer instead
- **SizeRestrictions**: May trigger on legitimate file uploads. Adjust body size in custom rule (Rule 6) rather than disabling this check
- **LFI/RFI rules**: May trigger on URLs containing `../` in legitimate path parameters. If needed, create a scope-down statement excluding specific URI paths
- **SSRF rules**: Critical — do not disable. If triggering on legitimate internal URLs, add to a custom allow rule with specific path matching

---

### 3. AWSManagedRulesSQLiRuleSet

**Priority**: 3

**Purpose**: Detect and block SQL injection attempts in all request components.

**Threats Mitigated**:
| Rule Name | Inspection Target | Attack Pattern |
|-----------|-------------------|----------------|
| SQLi_QUERYARGUMENTS | Query string parameters | `' OR 1=1 --`, UNION SELECT |
| SQLi_BODY | Request body | SQL in JSON/form payloads |
| SQLi_COOKIE | Cookie values | Session fixation via SQLi |
| SQLi_URIPATH | URI path segments | Path-based injection |

**Expected False Positive Rate**: Low (0.05%)

**Tuning Guidance**:
- **JSON APIs** (this platform): False positives rare because JSON structure naturally escapes SQL metacharacters
- If a legitimate field value triggers SQLi detection (e.g., a product description containing SQL keywords), use a scope-down statement on the specific URI path + field combination
- Never disable SQLi rules globally — scope exclusions to specific endpoints only
- Consider setting to COUNT mode during initial deployment, then switching to BLOCK after 7 days with no false positives

---

### 4. AWSManagedRulesKnownBadInputsRuleSet

**Priority**: 4

**Purpose**: Block request patterns associated with known vulnerabilities and exploit frameworks.

**Threats Mitigated**:
| Rule Name | Threat | CVE/Reference |
|-----------|--------|---------------|
| JavaDeserializationRCE_HEADER | Java deserialization attacks | Multiple CVEs |
| JavaDeserializationRCE_BODY | Java deserialization in body | Multiple CVEs |
| JavaDeserializationRCE_URIPATH | Java deserialization in URI | Multiple CVEs |
| JavaDeserializationRCE_QUERYSTRING | Java deser in params | Multiple CVEs |
| Host_localhost_HEADER | Host header injection | SSRF |
| PROPFIND_METHOD | WebDAV reconnaissance | Information disclosure |
| ExploitablePaths_URIPATH | Known vulnerable paths | Various frameworks |
| Log4JRCE_HEADER | Log4Shell exploitation | CVE-2021-44228 |
| Log4JRCE_QUERYSTRING | Log4Shell in params | CVE-2021-44228 |
| Log4JRCE_BODY | Log4Shell in body | CVE-2021-44228 |
| Log4JRCE_URIPATH | Log4Shell in URI | CVE-2021-44228 |

**Expected False Positive Rate**: Very low (<0.01%)

**Tuning Guidance**:
- These rules target specific exploit payloads — false positives are extremely rare
- Do not disable or set to COUNT mode — these are critical protections
- If Log4Shell rules trigger on legitimate `${...}` syntax (e.g., in CloudFormation template submissions), scope-down to exclude that specific endpoint

---

### 5. Custom Rule: Rate Limiting

**Priority**: 5

**Purpose**: Prevent abuse and brute-force attacks by limiting request volume per IP address.

**Configuration**:
```hcl
rule {
  name     = "RateLimit"
  priority = 5
  action { block {} }
  
  statement {
    rate_based_statement {
      limit              = 2000
      aggregate_key_type = "IP"
    }
  }
}
```

**Threats Mitigated**:
- Brute-force authentication attempts
- API abuse and scraping
- Credential stuffing attacks
- Application-layer DDoS

**Threshold**: 2000 requests per 5-minute window per source IP

**Expected False Positive Rate**: Low — 2000 requests/5 minutes = ~7 requests/second sustained

**Tuning Guidance**:
- Monitor WAF metrics for rate-limit blocks during normal load testing
- If legitimate clients (monitoring tools, CI/CD) are blocked, either increase the limit or add their IPs to a custom allow list
- For authentication endpoints specifically, consider a lower threshold (separate rate-based rule on /auth/* path)
- After demo events with high traffic, temporarily increase the limit via Terraform variable

---

### 6. Custom Rule: Body Size Limit

**Priority**: 6

**Purpose**: Block requests with bodies exceeding 8KB to prevent payload-based attacks and resource exhaustion.

**Configuration**:
```hcl
rule {
  name     = "BodySizeLimit"
  priority = 6
  action { block {} }
  
  statement {
    size_constraint_statement {
      field_to_match { body {} }
      comparison_operator = "GT"
      size                = 8192  # 8KB
      text_transformation {
        priority = 0
        type     = "NONE"
      }
    }
  }
}
```

**Threats Mitigated**:
- Large payload DoS (memory exhaustion)
- Hidden exploit payloads in oversized requests
- ZIP bomb or decompression attacks (at transport layer)

**Expected False Positive Rate**: Very low — platform API accepts JSON payloads typically <2KB

**Tuning Guidance**:
- If a legitimate endpoint needs larger bodies (e.g., bulk import), create a scope-down statement that excludes that specific path from this rule
- Monitor for 403 responses correlated with legitimate operations (check WAF logs for sampled requests)
- The 8KB limit matches API Gateway's default payload limit — requests would fail at API GW anyway

---

## WAF Logging

### Log Destination

WAF logs are sent to an S3 bucket with the following structure:

```
s3://secure-platform-waf-logs/
  └── AWSLogs/
      └── {account-id}/
          └── WAFLogs/
              └── {region}/
                  └── {web-acl-name}/
                      └── {year}/{month}/{day}/{hour}/
                          └── {5-minute-interval}-{hash}.log.gz
```

### Key Log Fields

| Field | Description | Use Case |
|-------|-------------|----------|
| `action` | ALLOW, BLOCK, COUNT | Filter for blocked requests |
| `terminatingRuleId` | Rule that matched | Identify which rule triggered |
| `ruleGroupList` | All evaluated rule groups | Understand evaluation path |
| `httpRequest.clientIp` | Source IP | Identify attackers |
| `httpRequest.uri` | Request path | Identify targeted endpoints |
| `httpRequest.headers` | Request headers | Investigate request details |

### Analysis Queries

**Top blocked IPs (last 24 hours):**
```sql
-- Athena query on WAF logs
SELECT httpRequest.clientIp, COUNT(*) as block_count
FROM waf_logs
WHERE action = 'BLOCK'
  AND from_unixtime(timestamp/1000) > current_timestamp - interval '24' hour
GROUP BY httpRequest.clientIp
ORDER BY block_count DESC
LIMIT 20;
```

**Blocks by rule group:**
```sql
SELECT terminatingRuleId, COUNT(*) as count
FROM waf_logs
WHERE action = 'BLOCK'
GROUP BY terminatingRuleId
ORDER BY count DESC;
```

---

## Monitoring and Alerts

### CloudWatch Metrics

| Metric | Namespace | Description | Alarm Threshold |
|--------|-----------|-------------|-----------------|
| BlockedRequests | AWS/WAFV2 | Total blocked requests | >100/minute (anomaly) |
| AllowedRequests | AWS/WAFV2 | Total allowed requests | Baseline monitoring |
| CountedRequests | AWS/WAFV2 | Requests in COUNT mode | Tuning analysis |

### Operational Dashboard

The CloudWatch dashboard includes a WAF widget showing:
- Blocked vs allowed request ratio (5-minute periods)
- Top terminating rules (bar chart)
- Rate-limit trigger frequency

---

## Annual Review Checklist

- [ ] Review AWS managed rule group release notes for new rules
- [ ] Analyse WAF logs for false positive patterns over the past quarter
- [ ] Update rate limit threshold based on traffic growth
- [ ] Verify body size limit still appropriate for API endpoints
- [ ] Check if new endpoints require rule exclusions
- [ ] Review IP reputation list effectiveness (blocks vs false positives)
- [ ] Test WAF rules against current OWASP Top 10 attack patterns
