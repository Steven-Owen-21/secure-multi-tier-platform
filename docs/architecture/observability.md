# Observability Architecture

## Overview

The observability layer provides operational insight through structured logging, composite alarms, anomaly detection, dashboards, and Contributor Insights. The goal is actionable alerts with reduced noise — composite alarms trigger only when multiple indicators confirm a problem.

```mermaid
graph TB
    subgraph Sources["Metric & Log Sources"]
        ALB_Metrics[ALB Metrics<br/>5xx rate, latency, requests]
        ECS_Metrics[ECS Metrics<br/>CPU, memory, task count]
        RDS_Metrics[RDS Metrics<br/>Connections, IOPS, latency]
        Redis_Metrics[Redis Metrics<br/>Hit rate, evictions, memory]
        APIGW_Metrics[API Gateway Metrics<br/>p50/p90/p99 latency]
        AppLogs[Application Logs<br/>Structured JSON]
        WAF_Logs[WAF Logs<br/>Blocked requests]
    end

    subgraph Processing["Processing & Analysis"]
        CWMetrics[CloudWatch Metrics]
        CWLogs[CloudWatch Logs]
        Insights[Logs Insights Queries]
        Contributor[Contributor Insights]
        Anomaly[Anomaly Detection]
    end

    subgraph Alerting["Alerting"]
        Child1[Child Alarm: ALB 5xx > 5%]
        Child2[Child Alarm: ECS CPU > 80%]
        Child3[Child Alarm: DB Conn > 80%]
        Composite[Composite Alarm<br/>ALL children in ALARM]
        AnomalyAlarm[Anomaly Alarm<br/>p99 latency breach]
    end

    subgraph Response["Response"]
        SNS[SNS Topic]
        Dashboard[CloudWatch Dashboard]
        Runbook[Ops Runbook]
    end

    ALB_Metrics & ECS_Metrics & RDS_Metrics & Redis_Metrics & APIGW_Metrics --> CWMetrics
    AppLogs & WAF_Logs --> CWLogs
    CWLogs --> Insights
    CWLogs --> Contributor
    CWMetrics --> Child1 & Child2 & Child3
    APIGW_Metrics --> Anomaly
    Anomaly --> AnomalyAlarm
    Child1 & Child2 & Child3 --> Composite
    Composite --> SNS
    AnomalyAlarm --> SNS
    CWMetrics --> Dashboard
    SNS --> Runbook
```

## Composite Alarm Structure

The composite alarm reduces alert fatigue by triggering only when multiple indicators confirm a genuine platform degradation.

```mermaid
graph TB
    subgraph CompositeAlarm["Composite Alarm: platform-degraded"]
        direction TB
        Logic["Trigger: ALL children in ALARM simultaneously"]
    end

    subgraph Children["Child Alarms"]
        C1["ALB 5xx Error Rate > 5%<br/>Period: 5 minutes<br/>Datapoints: 3/3"]
        C2["ECS CPU Utilisation > 80%<br/>Period: 3 minutes<br/>Datapoints: 3/3"]
        C3["RDS Connections > 80% of max<br/>Period: 5 minutes<br/>Datapoints: 3/3"]
    end

    C1 --> Logic
    C2 --> Logic
    C3 --> Logic
    Logic -->|"ALL in ALARM"| SNS[SNS Notification]
```

### Alarm State Evaluation

| Child 1 (5xx) | Child 2 (CPU) | Child 3 (DB) | Composite State |
|---------------|---------------|--------------|-----------------|
| OK | OK | OK | OK |
| ALARM | OK | OK | OK |
| ALARM | ALARM | OK | OK |
| ALARM | ALARM | ALARM | **ALARM** |
| INSUFFICIENT_DATA | ALARM | ALARM | OK |

**Rationale**: A single metric spike (e.g. brief CPU spike during deployment) should not page an operator. Only when errors, CPU pressure, and database saturation align does it indicate genuine platform distress.

## Anomaly Detection

### Configuration

| Parameter | Value |
|-----------|-------|
| Metric | API Gateway p99 latency |
| Training period | 14 days (auto-learns patterns) |
| Band width | 2 standard deviations |
| Alarm trigger | 3 consecutive datapoints outside upper band |
| Benefit | Detects latency degradation without static thresholds |

```mermaid
graph LR
    subgraph Model["Anomaly Detection Model"]
        Baseline[14-day baseline<br/>learns daily/weekly patterns]
        Band[Expected band<br/>±2 standard deviations]
    end

    subgraph Detection["Detection"]
        Metric[p99 latency measurement]
        Compare{Within band?}
        OK_State[OK]
        ALARM_State[ALARM<br/>3 consecutive breaches]
    end

    Baseline --> Band
    Metric --> Compare
    Compare -->|Yes| OK_State
    Compare -->|No, 3x| ALARM_State
    ALARM_State --> SNS[SNS Alert]
```

## CloudWatch Dashboard

### Widget Layout

```
┌─────────────────────────────────┬─────────────────────────────────┐
│ API Latency (p50 / p90 / p99)   │ Error Rates (4xx / 5xx)         │
│ Line graph, 5-min period        │ Stacked area, 5-min period      │
├─────────────────────────────────┼─────────────────────────────────┤
│ Cache Hit Ratio                 │ DB Active Connections           │
│ Single metric, percentage       │ Line graph with max_conn line   │
├─────────────────────────────────┼─────────────────────────────────┤
│ ECS Running Tasks               │ Cumulative Cost Estimate        │
│ Number widget with min/max ref  │ Number widget, current session  │
└─────────────────────────────────┴─────────────────────────────────┘
```

### Dashboard Widgets Detail

| Widget | Metric Source | Period | Statistic |
|--------|--------------|--------|-----------|
| API Latency | API Gateway | 5 min | p50, p90, p99 |
| Error Rates | ALB | 5 min | Sum (4xx, 5xx) |
| Cache Hit Ratio | Application custom metric | 1 min | Average |
| DB Connections | RDS | 5 min | Average |
| ECS Tasks | ECS | 1 min | Average (RunningTaskCount) |
| Cost Estimate | Billing | 6 hours | Maximum |

## CloudWatch Logs Insights

### Saved Queries

**Slow Requests (> 1 second)**:
```
fields @timestamp, method, path, duration_ms, user_id
| filter duration_ms > 1000
| sort duration_ms desc
| limit 50
```

**Authentication Failures by Source IP**:
```
fields @timestamp, source_ip, path, status_code
| filter status_code = 401
| stats count() as failures by source_ip
| sort failures desc
| limit 20
```

**Cache Misses by Endpoint**:
```
fields @timestamp, path, cache_hit
| filter cache_hit = false
| stats count() as misses by path
| sort misses desc
| limit 20
```

## Contributor Insights

### Rules

| Rule | Group By | Metric | Purpose |
|------|----------|--------|---------|
| Top Callers | API Key ID | Request Count | Identify heavy API consumers |
| Top Errors | Endpoint + Status Code | Error Count | Pinpoint problematic endpoints |

### Top Callers Rule

- **Log group**: API Gateway access logs
- **Contribution**: Grouped by `api_key_id`
- **Metric**: Count of requests per contributor
- **Display**: Top 10 contributors over selected time range

### Top Error Sources Rule

- **Log group**: API Gateway access logs
- **Contribution**: Grouped by `path` + `status_code`
- **Filter**: `status_code >= 400`
- **Display**: Top 10 error-producing endpoint/status combinations

## Structured Logging Format

All application logs are emitted as structured JSON:

```json
{
  "timestamp": "2024-01-15T14:30:00.123Z",
  "level": "INFO",
  "request_id": "req-abc123",
  "method": "GET",
  "path": "/api/products",
  "status_code": 200,
  "duration_ms": 45,
  "user_id": "usr-xyz789",
  "cache_hit": true,
  "correlation_id": "cor-def456"
}
```

## Service Quotas Monitoring

### Monitored Quotas

| Service | Quota | Default Limit | Alarm Threshold (80%) |
|---------|-------|--------------|----------------------|
| VPC | Subnets per VPC | 200 | 160 |
| VPC | Security groups per interface | 5 | 4 |
| ECS | Tasks per service | 5000 | 4000 |
| RDS | Instances per cluster | 15 | 12 |
| Lambda | Concurrent executions | 1000 | 800 |

### Quota Alarm Flow

```mermaid
sequenceDiagram
    participant SQ as Service Quotas
    participant CW as CloudWatch
    participant SNS as SNS Topic
    participant Ops as Operator

    SQ->>CW: Publish usage metric
    CW->>CW: Evaluate against 80% threshold
    alt Usage > 80%
        CW->>SNS: Trigger alarm
        SNS->>Ops: Alert with service, quota,<br/>usage, limit, percentage
    end
```
