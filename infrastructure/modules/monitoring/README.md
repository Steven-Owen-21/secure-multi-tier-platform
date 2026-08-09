# Monitoring Module

Enables integrated security monitoring using GuardDuty, AWS Config, and Security Hub to provide a unified security posture management approach with automated alerting for HIGH and CRITICAL findings.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Security Monitoring Stack                                                │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │   GuardDuty     │  │   AWS Config    │  │       WAF               │ │
│  │                 │  │                 │  │   (external input)       │ │
│  │  S3 Protection  │  │  5 Config Rules │  │                         │ │
│  │  Threat Intel   │  │  Compliance     │  │                         │ │
│  └────────┬────────┘  └────────┬────────┘  └────────────┬────────────┘ │
│           │                    │                         │              │
│           ▼                    ▼                         ▼              │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                     Security Hub                                     ││
│  │  AWS Foundational Security Best Practices + CIS Benchmarks          ││
│  │  Unified findings dashboard                                          ││
│  └────────────────────────────────┬────────────────────────────────────┘│
│                                   │                                      │
│                                   ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                      EventBridge Rules                               ││
│  │  GuardDuty severity >= 7 (HIGH/CRITICAL)                            ││
│  │  Config NON_COMPLIANT                                                ││
│  │  Security Hub HIGH/CRITICAL                                          ││
│  └────────────────────────────────┬────────────────────────────────────┘│
│                                   │                                      │
│                                   ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                    SNS Topic (Alerts)                                 ││
│  │  Structured alert messages with finding details                      ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

## Features

- **GuardDuty Threat Detection**: Enabled with S3 protection for monitoring CloudTrail, VPC Flow Logs, and DNS logs
- **AWS Config Compliance Rules**: Five rules monitoring encryption, flow logs, and IAM hygiene
- **Security Hub Aggregation**: Combines findings from GuardDuty, Config, and WAF with industry benchmarks
- **Automated Alerting**: EventBridge routes HIGH/CRITICAL findings to SNS with structured alert messages
- **CIS Benchmarks**: AWS Foundations Benchmark enabled for industry-standard compliance checks
- **Config Non-Compliance Alerts**: Real-time notifications when resources drift from compliance

## AWS Config Rules

| Rule Name | What It Checks | Source Identifier |
|-----------|---------------|-------------------|
| `encrypted-volumes` | EBS volumes in attached state are encrypted | `ENCRYPTED_VOLUMES` |
| `rds-encryption-enabled` | RDS instances have storage encryption enabled | `RDS_STORAGE_ENCRYPTED` |
| `s3-bucket-server-side-encryption-enabled` | S3 buckets have SSE configured | `S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED` |
| `vpc-flow-logs-enabled` | VPCs have flow logs enabled | `VPC_FLOW_LOGS_ENABLED` |
| `iam-user-no-policies-check` | IAM users don't have directly attached policies | `IAM_USER_NO_POLICIES_CHECK` |

## Alert Flow

1. **GuardDuty** detects a threat (e.g., suspicious API call, compromised credentials)
2. Finding is published to EventBridge with severity metadata
3. EventBridge rule filters for severity >= 7 (HIGH/CRITICAL)
4. Alert formatted with finding type, affected resource, and remediation guidance
5. Published to SNS topic for team notification (email, Slack, PagerDuty, etc.)

The same pattern applies for Config non-compliance and Security Hub imported findings.

## Usage

```hcl
module "monitoring" {
  source = "./modules/monitoring"

  sns_topic_arn = aws_sns_topic.alerts.arn

  environment  = "demo"
  project_name = "secure-multi-tier-platform"

  # Feature toggles (disable for local development)
  enable_guardduty    = true
  enable_config       = true
  enable_security_hub = true
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `sns_topic_arn` | ARN of the SNS topic for alert notifications | `string` | n/a | yes |
| `environment` | Deployment environment name | `string` | `"demo"` | no |
| `project_name` | Project name for resource naming | `string` | `"secure-multi-tier-platform"` | no |
| `enable_guardduty` | Enable GuardDuty threat detection | `bool` | `true` | no |
| `enable_config` | Enable AWS Config compliance monitoring | `bool` | `true` | no |
| `enable_security_hub` | Enable Security Hub aggregation | `bool` | `true` | no |

## Outputs

| Name | Description |
|------|-------------|
| `guardduty_detector_id` | ID of the GuardDuty detector |
| `guardduty_detector_arn` | ARN of the GuardDuty detector |
| `config_recorder_id` | ID of the AWS Config recorder |
| `config_recorder_name` | Name of the AWS Config recorder |
| `security_hub_arn` | ARN of the Security Hub subscription |
| `config_rules` | Map of Config rule names to ARNs |
| `config_logs_bucket` | S3 bucket name for Config delivery |
| `config_logs_bucket_arn` | S3 bucket ARN for Config delivery |
| `guardduty_event_rule_arn` | EventBridge rule ARN for GuardDuty alerts |
| `config_event_rule_arn` | EventBridge rule ARN for Config alerts |
| `securityhub_event_rule_arn` | EventBridge rule ARN for Security Hub alerts |

## Security Hub Standards

| Standard | Description |
|----------|-------------|
| AWS Foundational Security Best Practices v1.0.0 | AWS-curated best practices covering identity, logging, monitoring, and data protection |
| CIS AWS Foundations Benchmark v1.2.0 | Industry-standard controls from the Center for Internet Security |

## SNS Alert Message Format

All alerts follow a consistent structure:

```json
{
  "source": "guardduty | config | securityhub",
  "severity": "HIGH | CRITICAL",
  "finding_type": "Description of the finding type",
  "affected_resource": "ARN or identifier of the affected resource",
  "description": "Human-readable description of the finding",
  "recommended_action": "Remediation guidance",
  "timestamp": "ISO 8601 timestamp",
  "account_id": "AWS account ID",
  "region": "AWS region"
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | ~> 5.0 |

## Related Modules

- **observability**: CloudWatch dashboards and composite alarms for operational monitoring
- **waf**: WAF findings are aggregated by Security Hub
- **disaster-recovery**: Consumes monitoring outputs for cross-region alerting
- **kms**: Encryption rules validated by Config encrypted-volumes rule
- **vpc**: Flow logs validated by Config vpc-flow-logs-enabled rule
