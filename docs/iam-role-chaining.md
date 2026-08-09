# IAM Role Chaining Documentation

## Overview

The platform implements a three-tier IAM role chaining model to demonstrate enterprise identity governance patterns. Role chaining means one IAM role assumes another, creating a trust chain where each hop reduces the effective permissions available.

## Role Chain Architecture

```
┌──────────────────────┐
│  GitHub Actions OIDC  │  (External identity provider)
│  Provider             │
└──────────┬───────────┘
           │ Federate (OIDC token)
           ▼
┌──────────────────────┐
│  Pipeline Role        │  Maximum scope: Terraform operations
│  (arn:aws:iam::*:     │  Trust: GitHub OIDC provider
│   role/pipeline)      │  Condition: repo + branch
└──────────┬───────────┘
           │ sts:AssumeRole (with external ID)
           ▼
┌──────────────────────┐
│  Deployment Role      │  Maximum scope: Resource creation
│  (arn:aws:iam::*:     │  Trust: Pipeline Role ARN
│   role/deployer)      │  Condition: external ID match
└──────────┬───────────┘
           │ sts:AssumeRole (with session policy)
           ▼
┌──────────────────────┐
│  Service Role         │  Maximum scope: Application operations
│  (arn:aws:iam::*:     │  Trust: ECS + Deployment Role
│   role/app-service)   │  Boundary: Permission Boundary attached
│                       │  Session: Scoped to tagged resources
└──────────────────────┘
```

---

## Trust Policy Chain

### 1. Pipeline Role Trust Policy

The Pipeline Role is the entry point for CI/CD operations. It trusts only the GitHub OIDC provider with strict conditions.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:OWNER/secure-multi-tier-platform:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

**Key controls:**
- Only the specific GitHub repository can assume this role
- Only the `main` branch is trusted (prevents PR branch exploitation)
- Audience claim must match STS (prevents token reuse from other providers)

### 2. Deployment Role Trust Policy

The Deployment Role trusts only the Pipeline Role and requires an external ID for confused deputy prevention.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_ID:role/pipeline"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "secure-platform-deploy-RANDOM_SUFFIX"
        }
      }
    }
  ]
}
```

**Key controls:**
- Only the Pipeline Role ARN can assume this role (no other principals)
- External ID prevents confused deputy attacks
- Even if another account tries to use the Pipeline Role ARN, the external ID blocks assumption

### 3. Service Role Trust Policy

The Service Role is assumed by ECS tasks at runtime and by the Deployment Role during deployments.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-2"
        }
      }
    },
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_ID:role/deployer"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:ResourceTag/Project": "secure-multi-tier-platform"
        }
      }
    }
  ]
}
```

**Key controls:**
- ECS service can assume for task execution (runtime)
- Deployment Role can assume for configuration (deploy-time)
- Region restriction prevents cross-region assumption
- Tag condition ensures only platform-tagged resources can be accessed

---

## Permission Boundary Model

The Permission Boundary is an IAM policy attached to the Service Role that defines the **maximum possible permissions** regardless of the role's own policies.

### Concept

```
Effective Permissions = Identity Policy ∩ Permission Boundary ∩ Session Policy

Where:
- Identity Policy: What the role's attached policies ALLOW
- Permission Boundary: Maximum ceiling of what CAN be allowed
- Session Policy: Further restriction applied at assume-role time
```

### Permission Boundary Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowPlatformServices",
      "Effect": "Allow",
      "Action": [
        "rds-db:connect",
        "elasticache:*",
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
        "secretsmanager:GetSecretValue",
        "kms:Decrypt",
        "kms:GenerateDataKey",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "sns:Publish",
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyOutOfScope",
      "Effect": "Deny",
      "NotAction": [
        "rds-db:connect",
        "elasticache:*",
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
        "secretsmanager:GetSecretValue",
        "kms:Decrypt",
        "kms:GenerateDataKey",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "sns:Publish",
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords"
      ],
      "Resource": "*"
    }
  ]
}
```

**Effect**: Even if someone attaches `AdministratorAccess` to the Service Role, it can never call EC2, IAM, Lambda, or any service outside the allowed set.

### Why a Permission Boundary?

| Without Boundary | With Boundary |
|-----------------|---------------|
| Misconfigured role policy = full service access | Misconfigured role policy = still capped |
| Privilege escalation via policy attachment | Cannot escalate beyond boundary |
| Blast radius = entire AWS account | Blast radius = platform services only |

---

## Session Policy Scoping

When the Deployment Role assumes the Service Role, it passes a session policy that further restricts access to only platform-tagged resources:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:ResourceTag/Project": "secure-multi-tier-platform"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:ResourceTag/Project": "secure-multi-tier-platform"
        }
      }
    }
  ]
}
```

**Effect**: The session can only access S3 objects and secrets that are tagged with `Project=secure-multi-tier-platform`. Even if the Service Role's policy allows `s3:*` on `*`, the session policy restricts it to tagged resources only.

---

## Effective Permissions at Each Level

| Operation | Pipeline Role | Deployment Role | Service Role (runtime) |
|-----------|--------------|-----------------|----------------------|
| terraform apply | ✅ (via Deployer) | ✅ | ❌ |
| Create IAM roles | ✅ (via Deployer) | ✅ | ❌ (boundary denies) |
| Read secrets | ❌ | ❌ | ✅ (tagged only) |
| Write to S3 | ❌ | ✅ | ✅ (tagged only) |
| Connect to RDS | ❌ | ❌ | ✅ |
| Connect to Redis | ❌ | ❌ | ✅ |
| Publish to SNS | ❌ | ✅ | ✅ |
| Call EC2 APIs | ❌ | ✅ | ❌ (boundary denies) |
| Modify IAM | ❌ | ✅ (with boundary caveat) | ❌ (boundary denies) |

---

## Security Properties

1. **Least privilege**: Each role has only the permissions needed for its specific function
2. **Defence in depth**: Three independent controls (identity policy, boundary, session policy) must all agree
3. **Confused deputy prevention**: External ID required for cross-role assumption
4. **No long-lived credentials**: OIDC federation eliminates stored access keys
5. **Auditability**: Every role assumption logged in CloudTrail with session name and source identity
6. **Blast radius containment**: Compromised Service Role cannot escape the permission boundary
7. **Temporal restriction**: Session credentials expire (1 hour default), requiring re-assumption

---

## Monitoring and Auditing

### CloudTrail Events to Monitor

| Event | Significance |
|-------|-------------|
| `AssumeRole` with unexpected source | Potential role confusion attack |
| `AssumeRoleWithWebIdentity` from non-main branch | Branch protection bypass attempt |
| `AccessDenied` on Service Role | Boundary or session policy working correctly |
| `AssumeRole` without external ID | Confused deputy attempt (will fail) |

### IAM Access Analyzer

- Continuously analyses the Service Role for unused permissions
- Identifies external access (any principal outside the account that can assume roles)
- Generates findings when policy grants broader access than required
- Findings feed into Security Hub for unified visibility
