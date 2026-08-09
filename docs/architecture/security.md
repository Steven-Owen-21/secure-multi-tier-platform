# Security Architecture

## Defence-in-Depth Strategy

The platform implements multiple overlapping security controls across network, identity, application, and data layers. No single control failure can compromise the system.

```mermaid
graph TB
    subgraph Edge["Layer 1: Edge Protection"]
        CF_Shield[CloudFront + Shield Standard]
        GeoRestrict[Geographic Restrictions]
    end

    subgraph Network["Layer 2: Network Security"]
        WAF_Layer[WAF Web ACL]
        NACLs[Network ACLs]
        SGs[Security Groups]
        VPCEndpoints[Private Endpoints]
    end

    subgraph Identity["Layer 3: Identity & Access"]
        Cognito_Auth[Cognito OAuth2/OIDC]
        PermBoundary[Permission Boundaries]
        RoleChain[Role Chaining]
        SessionPolicy[Session Policies]
    end

    subgraph Application["Layer 4: Application Security"]
        JWTValid[JWT Validation]
        InputValid[Input Validation]
        RateLimit[Rate Limiting]
    end

    subgraph DataLayer["Layer 5: Data Protection"]
        KMS_Enc[KMS CMK Encryption]
        TLS[TLS In-Transit]
        SecretsMgr[Secrets Rotation]
    end

    subgraph Detection["Layer 6: Detection & Response"]
        GuardDuty_Det[GuardDuty Threat Detection]
        ConfigComp[AWS Config Compliance]
        SecHub_Agg[Security Hub Aggregation]
        IAMAnalyzer[IAM Access Analyzer]
    end

    Edge --> Network --> Identity --> Application --> DataLayer
    Detection -.->|Monitors all layers| Edge & Network & Identity & Application & DataLayer
```

## IAM Architecture

### Role Chain Model

```mermaid
graph LR
    subgraph GitHub["GitHub Actions"]
        OIDC[OIDC Token]
    end

    subgraph Roles["IAM Role Chain"]
        Pipeline[Pipeline Role]
        Deploy[Deployment Role]
        Service[Service Role<br/>ECS Tasks]
    end

    subgraph Controls["Governance Controls"]
        PB[Permission Boundary]
        SP[Session Policy]
        Tags[Resource Tags]
    end

    OIDC -->|"assume (OIDC trust)"| Pipeline
    Pipeline -->|"assume (external ID)"| Deploy
    Deploy -->|"assume (tag condition)"| Service
    PB -->|"caps maximum"| Service
    SP -->|"scopes to tagged resources"| Service
    Tags -->|"Project=secure-multi-tier-platform"| SP
```

### Trust Policy Chain

| Role | Trusted By | Condition |
|------|-----------|-----------|
| Pipeline Role | GitHub OIDC provider | `sub` matches repo + branch |
| Deployment Role | Pipeline Role ARN | External ID required |
| Service Role | ECS service principal + Deployment Role | Tag match: `Project=secure-multi-tier-platform` |

### Permission Boundary

The permission boundary attached to application roles defines the maximum possible permissions regardless of the role's own policy:

**Allowed services** (platform services only):
- `s3:*` (scoped to platform buckets)
- `rds-db:connect` (IAM auth)
- `elasticache:*` (scoped to platform clusters)
- `secretsmanager:GetSecretValue` (platform secrets only)
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
- `kms:Decrypt`, `kms:GenerateDataKey` (platform key only)
- `xray:PutTraceSegments`

**Explicitly denied** (regardless of role policy):
- All IAM actions (`iam:*`)
- All organisations actions (`organizations:*`)
- KMS key management actions
- Any service not in the allowed set

### Session Policies

Applied at assume-role time to restrict effective permissions to tagged resources:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "*",
    "Resource": "*",
    "Condition": {
      "StringEquals": {
        "aws:ResourceTag/Project": "secure-multi-tier-platform"
      }
    }
  }]
}
```

## KMS Encryption Governance

### Key Policy Structure

```mermaid
graph TB
    subgraph KeyPolicy["KMS Key Policy"]
        Admin["Key Administrators<br/>(Pipeline Role)"]
        Users["Key Users<br/>(ECS Task Role, RDS Service)"]
        GrantCreators["Grant Creators<br/>(Deployment Role)"]
    end

    subgraph Operations["Permitted Operations"]
        AdminOps["Create, Describe, Enable,<br/>Disable, Delete, Tag,<br/>Schedule/Cancel Deletion"]
        UserOps["Encrypt, Decrypt,<br/>ReEncrypt, GenerateDataKey,<br/>DescribeKey"]
        GrantOps["CreateGrant, ListGrants,<br/>RevokeGrant<br/>(GrantIsForAWSResource)"]
    end

    Admin --> AdminOps
    Users --> UserOps
    GrantCreators --> GrantOps
```

### KMS Grants

| Grant | Principal | Operations | Encryption Context |
|-------|-----------|-----------|-------------------|
| Aurora | RDS service | Encrypt, Decrypt | `Project=secure-multi-tier-platform, Component=database` |
| ElastiCache | ElastiCache service | Encrypt, Decrypt | `Project=secure-multi-tier-platform, Component=cache` |
| S3 | S3 service (via bucket policy) | Encrypt, Decrypt | `Project=secure-multi-tier-platform, Component=storage` |
| Backup | AWS Backup service | CopyGrant | Cross-region backup encryption |

### Condition Keys

- `kms:EncryptionContext:Project` = `secure-multi-tier-platform` (all operations)
- `kms:ViaService` restricts usage to specific AWS services (rds, elasticache, s3, backup)
- Annual automatic key rotation enabled

## WAF Configuration

### Rule Groups

| Rule Group | Purpose | Action |
|-----------|---------|--------|
| AWSManagedRulesCommonRuleSet | OWASP Top 10 protection | Block |
| AWSManagedRulesSQLiRuleSet | SQL injection prevention | Block |
| AWSManagedRulesKnownBadInputsRuleSet | Known exploit patterns | Block |
| AWSManagedRulesAmazonIpReputationList | Known malicious IPs | Block |
| Rate-based rule | DDoS mitigation | Block (2000 req/5min/IP) |
| Body size rule | Payload attacks | Block (> 8KB) |

### WAF Processing Flow

```mermaid
flowchart LR
    Request[Incoming Request] --> IPRep{IP Reputation}
    IPRep -->|Blocked| Deny1[403]
    IPRep -->|Pass| Rate{Rate Limit}
    Rate -->|Exceeded| Deny2[403]
    Rate -->|Pass| Size{Body Size}
    Size -->|> 8KB| Deny3[403]
    Size -->|Pass| SQL{SQLi Check}
    SQL -->|Detected| Deny4[403]
    SQL -->|Pass| Common{Common Rules}
    Common -->|Violation| Deny5[403]
    Common -->|Pass| Allow[Forward to ALB]
```

## Secrets Rotation

### Rotation Flow (Single-User Strategy)

```mermaid
sequenceDiagram
    participant SM as Secrets Manager
    participant Lambda as Rotation Lambda
    participant Aurora as Aurora PostgreSQL
    participant App as Application

    SM->>Lambda: Step 1: createSecret
    Lambda->>SM: Generate new password → AWSPENDING

    SM->>Lambda: Step 2: setSecret
    Lambda->>Aurora: ALTER USER ... PASSWORD (new)
    Aurora-->>Lambda: OK

    SM->>Lambda: Step 3: testSecret
    Lambda->>Aurora: Connect with AWSPENDING credentials
    Aurora-->>Lambda: Connection successful

    SM->>Lambda: Step 4: finishSecret
    Lambda->>SM: AWSPENDING → AWSCURRENT<br/>AWSCURRENT → AWSPREVIOUS

    Note over App: App continues using cached<br/>AWSCURRENT until local TTL expires
    App->>SM: Fetch new AWSCURRENT (after TTL)
```

### Rotation Configuration

| Parameter | Value |
|-----------|-------|
| Rotation interval | 30 days |
| Strategy | Single-user |
| Credential caching TTL | 30 days (matches rotation) |
| Failure notification | SNS alert with secret ARN and failed step |
| Encryption | KMS CMK |

## Security Monitoring

### Detection Services

```mermaid
graph TB
    subgraph Sources["Detection Sources"]
        GD[GuardDuty<br/>Threat Detection]
        Config[AWS Config<br/>Compliance Rules]
        WAF_Log[WAF Logs<br/>Blocked Requests]
        IAM_AA[IAM Access Analyzer<br/>External Access]
    end

    subgraph Aggregation["Aggregation"]
        SH[Security Hub<br/>Unified Findings]
    end

    subgraph Response["Response"]
        SNS[SNS Topic]
        Email[Email Alerts]
        Runbook[Incident Runbook]
    end

    GD --> SH
    Config --> SH
    WAF_Log --> SH
    IAM_AA --> SH
    SH --> SNS
    SNS --> Email
    SNS --> Runbook
```

### AWS Config Compliance Rules

| Rule | Purpose |
|------|---------|
| encrypted-volumes | All EBS volumes use encryption |
| rds-encryption-enabled | Database encryption at rest |
| s3-bucket-server-side-encryption-enabled | S3 bucket encryption |
| vpc-flow-logs-enabled | Network traffic logging |
| iam-user-no-policies-check | No inline user policies |
| required-tags | Mandatory tag compliance |

### GuardDuty Finding Severity Actions

| Severity | Action |
|----------|--------|
| LOW | Log finding, weekly review |
| MEDIUM | SNS alert, 24-hour response target |
| HIGH | Immediate SNS alert, 4-hour response target |
| CRITICAL | Immediate SNS alert, 1-hour response target, consider resource isolation |
