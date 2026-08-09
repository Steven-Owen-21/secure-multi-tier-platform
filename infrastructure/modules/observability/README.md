# Observability Module

Implements advanced CloudWatch observability for the platform, providing composite alarms, anomaly detection, operational dashboards, saved log queries, and Contributor Insights rules.

## Purpose

This module addresses enterprise monitoring patterns that reduce alert fatigue while providing actionable operational insight. It combines multiple signals into a single composite alarm, uses ML-based anomaly detection for latency monitoring, and provides pre-built queries and dashboards for rapid incident investigation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Composite Alarm: platform-degraded               │
│                    (triggers only when ALL children in ALARM)         │
├───────────────────┬───────────────────────┬─────────────────────────┤
│ ALB 5xx > 5%      │ ECS CPU > 80%         │ DB Connections > 80%    │
│ (5-min period)    │ (3-min period)        │ (5-min period)          │
└───────────────────┴───────────────────────┴─────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   SNS Topic     │
                    │ (Notification)  │
                    └─────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│              Anomaly Detection: API Gateway p99 Latency               │
│              (2 std dev band, 3 consecutive datapoints)               │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     CloudWatch Dashboard                              │
├───────────────────────────┬─────────────────────────────────────────┤
│ API Latency (p50/p90/p99) │ Error Rates (4xx/5xx)                   │
├───────────────────────────┼─────────────────────────────────────────┤
│ Cache Hit Ratio           │ DB Active Connections                    │
├───────────────────────────┼─────────────────────────────────────────┤
│ ECS Running Tasks         │ Cumulative Cost Estimate                 │
└───────────────────────────┴─────────────────────────────────────────┘
```

## Usage

```hcl
module "observability" {
  source = "./modules/observability"

  environment            = var.environment
  alb_arn_suffix         = module.alb.alb_arn_suffix
  alb_full_name          = module.alb.alb_full_name
  ecs_service_name       = module.ecs.service_name
  ecs_cluster_name       = module.ecs.cluster_name
  rds_cluster_identifier = module.rds.cluster_identifier
  rds_max_connections    = 100
  api_gateway_name       = module.api_gateway.api_name
  api_gateway_stage      = "production"
  elasticache_cluster_id = module.elasticache.replication_group_id
  sns_topic_arn          = module.monitoring.sns_topic_arn

  tags = module.tagging.tags_map
}
```

## Dependencies

- **ALB module** — Provides ALB ARN suffix and full name for metric dimensions
- **ECS module** — Provides service and cluster names for CPU metrics
- **RDS module** — Provides cluster identifier for connection metrics
- **API Gateway module** — Provides API name for latency metrics
- **ElastiCache module** — Provides replication group ID for cache metrics
- **Monitoring module** — Provides SNS topic ARN for notifications

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `project_name` | Project name for resource naming | `string` | `"secure-multi-tier-platform"` | no |
| `environment` | Deployment environment | `string` | — | yes |
| `alb_arn_suffix` | ALB ARN suffix | `string` | — | yes |
| `alb_full_name` | ALB full name for metrics | `string` | — | yes |
| `ecs_service_name` | ECS service name | `string` | — | yes |
| `ecs_cluster_name` | ECS cluster name | `string` | — | yes |
| `rds_cluster_identifier` | RDS cluster identifier | `string` | — | yes |
| `rds_max_connections` | Maximum DB connections | `number` | `100` | no |
| `api_gateway_name` | API Gateway REST API name | `string` | — | yes |
| `api_gateway_stage` | API Gateway stage name | `string` | `"production"` | no |
| `elasticache_cluster_id` | ElastiCache replication group ID | `string` | — | yes |
| `sns_topic_arn` | SNS topic ARN for notifications | `string` | — | yes |
| `log_group_name` | Application log group name | `string` | `"/ecs/secure-multi-tier-platform"` | no |
| `api_gateway_log_group_name` | API Gateway access log group name | `string` | `"/aws/apigateway/secure-multi-tier-platform"` | no |
| `alb_5xx_threshold` | ALB 5xx error rate threshold (%) | `number` | `5` | no |
| `ecs_cpu_threshold` | ECS CPU utilisation threshold (%) | `number` | `80` | no |
| `db_connections_threshold_percent` | DB connections threshold (% of max) | `number` | `80` | no |
| `anomaly_detection_band` | Standard deviations for anomaly band | `number` | `2` | no |
| `tags` | Tags to apply to resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| `composite_alarm_arn` | ARN of the composite alarm |
| `composite_alarm_name` | Name of the composite alarm |
| `dashboard_arn` | ARN of the CloudWatch dashboard |
| `dashboard_name` | Name of the CloudWatch dashboard |
| `child_alarm_arns` | Map of child alarm ARNs |
| `anomaly_detection_alarm_arn` | ARN of the anomaly detection alarm |
| `logs_insights_query_ids` | Map of saved Logs Insights query IDs |
| `contributor_insights_rule_names` | Map of Contributor Insights rule names |

## Composite Alarm Behaviour

The composite alarm uses AND logic — it only triggers when **all three** child alarms are simultaneously in ALARM state. This significantly reduces alert noise by only notifying when the platform is experiencing correlated degradation across multiple tiers.

| ALB 5xx | ECS CPU | DB Connections | Composite State |
|---------|---------|----------------|-----------------|
| OK | OK | OK | OK |
| ALARM | OK | OK | OK |
| OK | ALARM | OK | OK |
| OK | OK | ALARM | OK |
| ALARM | ALARM | OK | OK |
| ALARM | OK | ALARM | OK |
| OK | ALARM | ALARM | OK |
| ALARM | ALARM | ALARM | **ALARM** |

## Anomaly Detection

The API Gateway p99 latency anomaly alarm uses CloudWatch's machine learning model to establish a baseline band (default: 2 standard deviations). The alarm triggers when the metric breaches the upper band for 3 consecutive 5-minute datapoints, indicating sustained latency degradation beyond normal patterns.

## Saved Logs Insights Queries

| Query | Purpose | Key Fields |
|-------|---------|------------|
| Slow Requests | Find requests exceeding 1 second | timestamp, method, path, duration_ms |
| Auth Failures by IP | Identify brute force attempts | source_ip, failure_count |
| Cache Misses by Endpoint | Find cache optimisation opportunities | path, miss_count, avg_latency |

## Contributor Insights Rules

| Rule | Grouping | Purpose |
|------|----------|---------|
| Top Callers | API Key ID | Identify high-volume consumers for capacity planning |
| Top Error Sources | Endpoint + Status Code | Identify problematic endpoints for prioritised fixes |

## Cost Considerations

- CloudWatch alarms: ~$0.10/alarm/month (5 alarms = ~$0.50/month)
- Dashboard: $3.00/dashboard/month
- Logs Insights queries: $0.005 per GB scanned (on-demand when run)
- Contributor Insights: $0.02 per rule per 1M matching log events
- Anomaly detection: Included in alarm cost

For demo deployments, the total monthly cost is typically under $5.
