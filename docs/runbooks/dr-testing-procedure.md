# Disaster Recovery Testing Procedure

## Purpose

This document describes how to simulate a regional failure and verify recovery within the documented RTO (4 hours). DR testing should be conducted quarterly to validate runbook accuracy and team readiness.

## Test Types

| Type | Scope | Duration | Risk | Frequency |
|------|-------|----------|------|-----------|
| Tabletop exercise | Walkthrough only, no changes | 1 hour | None | Monthly |
| Component failover | Single service (Aurora, Redis) | 2 hours | Low | Quarterly |
| Full DR simulation | Complete regional failover | 4–6 hours | Medium | Bi-annually |

---

## Tabletop Exercise

### Objective

Verify team familiarity with the DR runbook without making infrastructure changes.

### Procedure

1. Gather all team members listed in the DR runbook contacts
2. Present a failure scenario (e.g., "eu-west-2 is experiencing complete outage")
3. Walk through each phase of the failover procedure verbally
4. Identify gaps: Are commands still valid? Are IAM permissions sufficient? Are contacts current?
5. Document action items and update the DR runbook

### Success Criteria

- All team members can describe their responsibilities
- Runbook commands are verified as syntactically correct
- No stale resource identifiers in the runbook
- Communication templates are reviewed and updated

---

## Component Failover Test

### Objective

Verify that individual component failover works correctly without full region failure.

### Test 1: Aurora Failover

```bash
# Trigger a planned failover of the Aurora cluster
aws rds failover-db-cluster \
  --db-cluster-identifier secure-platform-cluster \
  --region eu-west-2

# Measure failover time
# Start timer when failover initiated
# Stop timer when application health check returns 200

# Expected: <30 seconds
```

**Verification:**

- [ ] Application health check recovers within 30 seconds
- [ ] No 5xx errors in ALB access logs during failover window
- [ ] Application reconnects to new writer endpoint automatically
- [ ] CloudWatch alarm does not trigger (brief connection errors expected)

### Test 2: Redis Failover

```bash
# Trigger a planned failover of the Redis replication group
aws elasticache test-failover \
  --replication-group-id secure-platform-redis \
  --node-group-id 0001

# Expected: <15 seconds
```

**Verification:**

- [ ] Application continues serving requests (cache miss falls through to database)
- [ ] Warning log emitted for cache unavailability
- [ ] Cache connectivity restored within 15 seconds
- [ ] No data loss in active sessions (session re-created on next request if lost)

### Test 3: ECS Task Failure

```bash
# Kill one of the two running tasks
aws ecs stop-task \
  --cluster secure-platform-cluster \
  --task <task-arn> \
  --reason "DR testing - simulated task failure"

# Expected: ALB routes to healthy task immediately, replacement launches within 60 seconds
```

**Verification:**

- [ ] ALB stops routing to stopped task within 30 seconds (health check interval)
- [ ] Remaining task handles all traffic without errors
- [ ] ECS launches replacement task within 60 seconds
- [ ] New task passes health check and receives traffic

---

## Full DR Simulation

### Prerequisites

- Schedule maintenance window with stakeholders
- Ensure DR region Aurora replica is synchronised (lag < 1 minute)
- Confirm S3 cross-region replication is active and current
- Verify Terraform state for DR environment is accessible
- Have rollback plan ready (re-point DNS back to primary immediately if DR fails)

### Simulation Procedure

#### Step 1: Simulate Primary Region Failure (T+0)

```bash
# Option A: Block primary ALB (simulates health check failure)
# Add a security group rule blocking inbound HTTPS on ALB
aws ec2 revoke-security-group-ingress \
  --group-id <alb-sg-id> \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0

# Record time: T+0
echo "Primary region ALB blocked at $(date -u +%H:%M:%S)"
```

#### Step 2: Monitor Route53 Failover (T+0 to T+3min)

```bash
# Watch Route53 health check status
aws route53 get-health-check-status \
  --health-check-id <health-check-id>

# Expected: Health check fails after 3 consecutive checks (90 seconds)
# Route53 failover routing should activate within 60 seconds of health check failure
# Total expected detection time: ~2.5 minutes
```

#### Step 3: Execute DR Failover Runbook (T+3min to T+120min)

Follow the complete [Disaster Recovery Runbook](./disaster-recovery.md) failover procedure:

1. Promote Aurora cross-region replica
2. Deploy application in DR region
3. Verify DNS routing to DR region
4. Run smoke tests

#### Step 4: Measure Recovery Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Time to detect (Route53 health check failure) | <3 minutes | _____ |
| Time to promote Aurora replica | <10 minutes | _____ |
| Time to deploy ECS tasks | <15 minutes | _____ |
| Time to first successful API response from DR | <30 minutes | _____ |
| Total RTO (detection to full service) | <4 hours | _____ |
| Data loss (replication lag at failure time) | <1 hour | _____ |

#### Step 5: Restore Primary (Rollback)

```bash
# Re-allow traffic to primary ALB
aws ec2 authorize-security-group-ingress \
  --group-id <alb-sg-id> \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0

# Route53 health check will recover, failover routing returns to primary
# Allow 60 seconds for health check to pass + DNS TTL propagation
```

#### Step 6: Clean Up DR Resources

```bash
# Destroy DR compute resources (keep replica for future tests)
cd infrastructure/environments/dr
terraform destroy -target=module.ecs -target=module.alb
```

---

## Test Report Template

```markdown
# DR Test Report - {date}

## Test Type
[Tabletop / Component / Full Simulation]

## Participants
- {name} - {role}

## Scenario
{Description of the simulated failure}

## Results

### Metrics
| Metric | Target | Actual | Pass/Fail |
|--------|--------|--------|-----------|
| Detection time | <3 min | | |
| Aurora promotion | <10 min | | |
| Service restoration | <4 hours | | |
| Data loss (RPO) | <1 hour | | |

### Issues Found
1. {Issue description} - {Severity} - {Action item}

### Runbook Updates Required
1. {Section} - {Change needed}

### Action Items
| Item | Owner | Due Date | Status |
|------|-------|----------|--------|
| | | | |

## Conclusion
{Overall assessment: RTO/RPO targets met? Team readiness? Next test date?}
```

---

## Schedule

| Quarter | Test Type | Focus Area |
|---------|-----------|------------|
| Q1 | Tabletop + Component (Aurora) | Database failover timing |
| Q2 | Full simulation | End-to-end RTO measurement |
| Q3 | Tabletop + Component (Redis, ECS) | Application resilience |
| Q4 | Full simulation | Include failback procedure |
