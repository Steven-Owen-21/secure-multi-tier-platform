# Disaster Recovery Runbook

## Purpose

This runbook documents the failover and failback procedures for the platform when the primary region (eu-west-2) becomes unavailable.

## Recovery Objectives

| Objective | Target | Measurement |
|-----------|--------|-------------|
| RPO (Recovery Point Objective) | 1 hour | Maximum data loss during failover |
| RTO (Recovery Time Objective) | 4 hours | Time from failure detection to service restoration |

## Architecture Overview

```
Primary Region (eu-west-2)              Secondary Region (eu-west-1)
┌─────────────────────────┐             ┌─────────────────────────┐
│ Route53 (Primary)        │             │ Route53 (Secondary)      │
│ CloudFront               │             │                          │
│ API Gateway + WAF        │             │                          │
│ ALB + ECS (2 tasks)      │             │                          │
│ Aurora Writer + Reader   │ ──async──── │ Aurora Cross-Region      │
│ Redis Primary + Replica  │             │   Read Replica           │
│ S3 Buckets              │ ──CRR─────── │ S3 Replica Buckets       │
│ Backup Vault            │ ──copy────── │ DR Backup Vault          │
└─────────────────────────┘             └─────────────────────────┘
```

---

## Failure Detection

### Automated Detection

Route53 health checks monitor the primary region ALB endpoint:

- **Protocol**: HTTPS
- **Path**: /health
- **Interval**: 30 seconds
- **Failure threshold**: 3 consecutive failures (90 seconds to detect)
- **Action**: Route53 failover routing activates secondary record

### Manual Detection Indicators

- CloudWatch composite alarm in ALARM state (5xx > 5%, CPU > 80%, DB connections maxed)
- AWS Health Dashboard showing regional degradation
- Multiple GuardDuty findings indicating widespread compromise
- Unable to reach AWS console for the affected region

---

## Failover Procedure

### Phase 1: Confirm Regional Failure (0–15 minutes)

1. **Verify the failure scope**: Check AWS Health Dashboard for regional service events
2. **Confirm Route53 health check status**: Verify health check has failed (3 consecutive)
3. **Check if failure is transient**: Wait for Route53 automatic failover (90 seconds)
4. **Decision point**: If Route53 has not failed over automatically, proceed to manual failover

### Phase 2: Promote Aurora Read Replica (15–30 minutes)

```bash
# Promote the cross-region Aurora read replica to standalone cluster
aws rds promote-read-replica-db-cluster \
  --db-cluster-identifier secure-platform-dr-cluster \
  --region eu-west-1

# Wait for promotion to complete (typically 5–10 minutes)
aws rds wait db-cluster-available \
  --db-cluster-identifier secure-platform-dr-cluster \
  --region eu-west-1

# Verify the promoted cluster is writable
aws rds describe-db-clusters \
  --db-cluster-identifier secure-platform-dr-cluster \
  --region eu-west-1 \
  --query 'DBClusters[0].Status'
```

### Phase 3: Deploy Application in DR Region (30–90 minutes)

```bash
# Apply Terraform configuration for DR region compute
cd infrastructure/environments/dr
terraform init
terraform apply -var="region=eu-west-1" -var="aurora_endpoint=<promoted-cluster-endpoint>"

# This provisions:
# - VPC (if not pre-provisioned)
# - ALB with health checks
# - ECS service with application tasks
# - Redis cluster (fresh, cache will warm from database)
# - WAF Web ACL attached to new ALB
```

### Phase 4: Update DNS (90–120 minutes)

```bash
# If Route53 failover hasn't activated automatically, manually update
aws route53 change-resource-record-sets \
  --hosted-zone-id <zone-id> \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.secure-platform.example.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "<dr-alb-zone-id>",
          "DNSName": "<dr-alb-dns-name>",
          "EvaluateTargetHealth": true
        }
      }
    }]
  }'
```

### Phase 5: Verify Recovery (120–180 minutes)

1. **Test API endpoint**: Run smoke tests against the DR region endpoint
2. **Verify data integrity**: Compare record counts and recent timestamps against known state
3. **Check authentication**: Verify Cognito tokens work (Cognito is regional — may need user pool in DR region)
4. **Monitor error rates**: Watch CloudWatch metrics for the first 30 minutes of live traffic

### Phase 6: Notify Stakeholders (180–240 minutes)

1. Update status page with DR activation notice
2. Document the failover timeline and any data loss
3. Record RPO achieved (actual replication lag at time of failure)
4. Record RTO achieved (time from detection to service restoration)

---

## Failback Procedure

### Prerequisites

- Primary region services fully restored (confirmed via AWS Health Dashboard)
- Aurora primary cluster rebuilt and data synchronised
- All primary region infrastructure verified via Terraform plan

### Phase 1: Rebuild Primary Region (Day 1)

```bash
# Reapply primary region infrastructure
cd infrastructure/environments/demo
terraform init
terraform apply

# Create Aurora cluster in primary region
# Set up replication FROM DR region TO primary
aws rds create-db-cluster \
  --db-cluster-identifier secure-platform-primary \
  --engine aurora-postgresql \
  --engine-version 15.4 \
  --replication-source-identifier <dr-cluster-arn> \
  --region eu-west-2
```

### Phase 2: Synchronise Data (Day 1–2)

1. Allow replication to catch up from DR region to primary
2. Monitor replication lag: target 0 seconds before cutover
3. Verify data consistency between regions

### Phase 3: Cutover to Primary (Day 2)

```bash
# Stop writes to DR region (maintenance mode)
# Promote primary cluster to standalone
aws rds promote-read-replica-db-cluster \
  --db-cluster-identifier secure-platform-primary \
  --region eu-west-2

# Wait for promotion
aws rds wait db-cluster-available \
  --db-cluster-identifier secure-platform-primary \
  --region eu-west-2

# Update ECS task definition with primary database endpoint
# Deploy new task revision

# Update Route53 to point back to primary
# Route53 failover will reactivate primary record when health check passes
```

### Phase 4: Decommission DR Resources

```bash
# Scale down DR compute resources
cd infrastructure/environments/dr
terraform destroy -target=module.ecs -target=module.alb

# Keep Aurora replica and S3 replication active for future DR readiness
```

### Phase 5: Post-Failback Verification

1. Confirm all traffic routing through primary region
2. Verify all integrations (Cognito, Secrets Manager, KMS) working correctly
3. Re-establish cross-region Aurora replication (primary → DR)
4. Run full integration test suite
5. Document lessons learned

---

## Communication Template

### Failover Notification

```
Subject: [PLATFORM] DR Failover Activated - {timestamp}

Status: Service recovered in DR region (eu-west-1)
Impact: API unavailable for approximately {duration}
Data loss: Estimated {RPO_actual} (replication lag at failure time)
Next steps: Monitoring DR region stability, planning failback

Timeline:
- {T+0m}: Primary region failure detected
- {T+Xm}: Failover procedure initiated
- {T+Ym}: Service restored in DR region
```

---

## Key Contacts

| Role | Responsibility |
|------|---------------|
| Platform Lead | Failover decision, stakeholder communication |
| Database Admin | Aurora promotion and data verification |
| DevOps Engineer | Terraform deployment, DNS changes |
| Security Lead | Assessment of whether failure is security-related |
