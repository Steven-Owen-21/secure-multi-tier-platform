# Security Runbook: GuardDuty Findings Triage

## Purpose

This runbook provides step-by-step triage procedures for the top 5 most common GuardDuty findings in the platform environment. Follow these procedures when an SNS alert is received for a HIGH or CRITICAL severity finding.

## Prerequisites

- AWS Console access with SecurityAudit or equivalent permissions
- Access to CloudWatch Logs for application and VPC Flow Logs
- Access to the platform's SNS notification history

---

## Finding 1: UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration.OutsideAWS

### Description

IAM credentials associated with an EC2 instance or ECS task are being used from an external IP address.

### Severity

HIGH

### Triage Steps

1. **Identify the affected role**: Check the finding details for the IAM role ARN and the external IP address
2. **Check CloudTrail**: Search for API calls made with the compromised credentials from the external IP
3. **Verify legitimate use**: Confirm whether any authorised CI/CD or monitoring tool uses these credentials externally
4. **Assess blast radius**: List all API calls made from the external IP in the last 24 hours

### Remediation

1. **Revoke active sessions**: Add an inline deny policy with `aws:TokenIssueTime` condition to invalidate all current sessions
2. **Rotate credentials**: If ECS task role, force new task deployment to issue fresh credentials
3. **Block external IP**: Add to WAF IP deny list if confirmed malicious
4. **Investigate source**: Check VPC Flow Logs for data exfiltration patterns
5. **Post-incident**: Update permission boundary to add `aws:SourceVpc` condition

### Escalation

If credentials have been active externally for >1 hour, escalate to incident response — potential data breach.

---

## Finding 2: Recon:EC2/PortProbeUnprotectedPort

### Description

A port on a resource in the VPC is being probed from a known malicious IP address.

### Severity

MEDIUM → HIGH (depending on port and response)

### Triage Steps

1. **Identify the target**: Check which security group and ENI is being probed
2. **Check if port is open**: Verify security group rules — is the probed port actually accessible?
3. **Check VPC Flow Logs**: Look for ACCEPT vs REJECT records for the source IP
4. **Assess exposure**: Determine if the target resource is in a public or private subnet

### Remediation

1. **If port is exposed (ACCEPT)**: Tighten security group rules immediately to restrict source CIDR
2. **If port is blocked (REJECT)**: Lower priority — NACLs/security groups are working correctly
3. **Add to WAF IP set**: Block the source IP at the WAF layer if it's hitting the ALB
4. **Review NACLs**: Ensure private subnet NACLs explicitly deny traffic from outside VPC CIDR
5. **Monitor**: Set up a CloudWatch metric filter for repeated probes from the same source

### Escalation

If the probed port is open AND the resource responded, check for exploitation attempts in application logs.

---

## Finding 3: UnauthorizedAccess:EC2/TorClient or TorRelay

### Description

An EC2 instance or ECS task is communicating with a Tor network entry/exit node.

### Severity

HIGH

### Triage Steps

1. **Identify the resource**: Check which ECS task or ENI is making the connection
2. **Check VPC Flow Logs**: Identify the destination IP and port (typically 9001, 9030, or 443)
3. **Verify application behaviour**: Determine if the application legitimately connects to any external services that might route through Tor
4. **Check container image**: Verify the ECS task definition image hasn't been tampered with

### Remediation

1. **Isolate the task**: Update the security group to deny all outbound traffic except to known-good destinations
2. **Stop the task**: Force stop the ECS task to terminate the connection immediately
3. **Audit container image**: Check ECR image scan results for vulnerabilities or malware
4. **Review outbound rules**: Restrict ECS security group outbound to only required destinations (database, cache, VPC endpoints, NAT gateway)
5. **Deploy clean image**: Force new ECS deployment with verified image digest

### Escalation

Immediate escalation — Tor communication from a production workload indicates compromise or data exfiltration.

---

## Finding 4: CryptoCurrency:EC2/BitcoinTool.B!DNS

### Description

A resource is querying DNS names associated with cryptocurrency mining pools.

### Severity

HIGH

### Triage Steps

1. **Identify the resource**: Check which task or ENI is making the DNS query
2. **Check DNS logs**: If Route53 Resolver query logging is enabled, identify the queried domain
3. **Check CPU metrics**: Look for sustained high CPU utilisation on the identified task
4. **Review task definition**: Check if the ECS task definition has been modified recently

### Remediation

1. **Stop the task immediately**: Cryptocurrency mining consumes resources and may indicate container compromise
2. **Audit the container image**: Run ECR image scanning, check for unexpected binaries
3. **Check for privilege escalation**: Review CloudTrail for unusual IAM activity from the task role
4. **Rotate secrets**: If the task had access to Secrets Manager, rotate all credentials it could access
5. **Redeploy from known-good image**: Use a verified image digest, not a mutable tag
6. **Add DNS firewall**: Consider Route53 Resolver DNS Firewall to block known mining domains

### Escalation

Immediate — mining indicates container compromise. Investigate how the attacker gained access.

---

## Finding 5: Policy:S3/BucketBlockPublicAccessDisabled

### Description

Block Public Access settings have been removed from an S3 bucket.

### Severity

HIGH

### Triage Steps

1. **Identify the bucket**: Check which bucket had public access settings changed
2. **Check CloudTrail**: Identify who/what made the `PutBucketPublicAccessBlock` or `DeleteBucketPublicAccessBlock` API call
3. **Check current ACLs and policies**: Determine if the bucket is actually publicly accessible now
4. **Assess data sensitivity**: Identify what data the bucket contains (WAF logs, application data, backups)

### Remediation

1. **Re-enable Block Public Access**: Immediately restore all four BPA settings (BlockPublicAcls, IgnorePublicAcls, BlockPublicPolicy, RestrictPublicBuckets)
2. **Review bucket policy**: Remove any policy statements granting public access (Principal: "*")
3. **Check for data exposure**: Review S3 server access logs for anonymous GET requests during the exposure window
4. **Investigate the change source**: If Terraform didn't make the change, investigate manual console access or compromised credentials
5. **Add SCP guardrail**: Consider an SCP denying `s3:PutBucketPublicAccessBlock` except from the pipeline role

### Escalation

If bucket contained PII or credentials and was publicly accessible for any duration, treat as data breach.

---

## General Triage Workflow

```
SNS Alert Received
       │
       ▼
┌─────────────────┐
│ Identify Finding │
│ Type & Severity  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     HIGH/CRITICAL     ┌──────────────────┐
│ Check Severity  │ ───────────────────── │ Immediate Action  │
│                 │                        │ (isolate/block)   │
└────────┬────────┘                        └──────────────────┘
         │ MEDIUM/LOW
         ▼
┌─────────────────┐
│ Gather Context   │
│ (CloudTrail,     │
│  Flow Logs, CW)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Determine if     │
│ True Positive    │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
   Yes       No
    │         │
    ▼         ▼
Remediate  Suppress/Archive
    │
    ▼
Post-Incident Review
```

## Suppression Guidance

For known false positives (e.g., security scanners, penetration testing), create GuardDuty suppression rules:

- Filter by finding type + specific IP ranges (security scanner IPs)
- Filter by finding type + specific resource tags (penetration testing environments)
- Document all suppressions in this runbook with justification and review dates
