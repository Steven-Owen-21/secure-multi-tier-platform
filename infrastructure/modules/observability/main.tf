###############################################################################
# Observability Module
#
# Implements advanced CloudWatch observability including:
# - Composite alarm (ALL children must be in ALARM)
# - Anomaly detection on API Gateway p99 latency
# - Operational dashboard with key platform metrics
# - Saved CloudWatch Logs Insights queries
# - Contributor Insights rules
# - SNS notification on composite alarm state change
###############################################################################

# -----------------------------------------------------------------------------
# Child Alarm 1: ALB 5xx Error Rate > 5% (5-minute period)
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "alb_5xx_rate" {
  alarm_name          = "${var.project_name}-alb-5xx-rate"
  alarm_description   = "ALB 5xx error rate exceeds ${var.alb_5xx_threshold}% over 5-minute period"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = var.alb_5xx_threshold

  metric_query {
    id          = "error_rate"
    expression  = "(errors / requests) * 100"
    label       = "5xx Error Rate (%)"
    return_data = true
  }

  metric_query {
    id = "errors"

    metric {
      metric_name = "HTTPCode_ELB_5XX_Count"
      namespace   = "AWS/ApplicationELB"
      period      = 300
      stat        = "Sum"

      dimensions = {
        LoadBalancer = var.alb_full_name
      }
    }
  }

  metric_query {
    id = "requests"

    metric {
      metric_name = "RequestCount"
      namespace   = "AWS/ApplicationELB"
      period      = 300
      stat        = "Sum"

      dimensions = {
        LoadBalancer = var.alb_full_name
      }
    }
  }

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Child Alarm 2: ECS CPU Utilisation > 80% (3-minute period)
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
  alarm_name          = "${var.project_name}-ecs-cpu-high"
  alarm_description   = "ECS service CPU utilisation exceeds ${var.ecs_cpu_threshold}% over 3-minute period"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 180
  statistic           = "Average"
  threshold           = var.ecs_cpu_threshold

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.ecs_service_name
  }

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Child Alarm 3: RDS Connections > 80% of max_connections (5-minute period)
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "db_connections_high" {
  alarm_name          = "${var.project_name}-db-connections-high"
  alarm_description   = "RDS connections exceed ${var.db_connections_threshold_percent}% of max_connections (${local.db_connections_threshold}) over 5-minute period"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = local.db_connections_threshold

  dimensions = {
    DBClusterIdentifier = var.rds_cluster_identifier
  }

  tags = var.tags
}

locals {
  db_connections_threshold = floor(var.rds_max_connections * var.db_connections_threshold_percent / 100)
  region                   = data.aws_region.current.name
}

# -----------------------------------------------------------------------------
# Composite Alarm: ALL children must be in ALARM simultaneously
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_composite_alarm" "platform_degraded" {
  alarm_name        = "${var.project_name}-platform-degraded"
  alarm_description = "Platform degraded: ALL child alarms are in ALARM state simultaneously (ALB 5xx > ${var.alb_5xx_threshold}%, ECS CPU > ${var.ecs_cpu_threshold}%, DB connections > ${var.db_connections_threshold_percent}% of max)"

  alarm_rule = "ALARM(${aws_cloudwatch_metric_alarm.alb_5xx_rate.alarm_name}) AND ALARM(${aws_cloudwatch_metric_alarm.ecs_cpu_high.alarm_name}) AND ALARM(${aws_cloudwatch_metric_alarm.db_connections_high.alarm_name})"

  alarm_actions = [var.sns_topic_arn]

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Anomaly Detection: API Gateway p99 Latency (2 std dev band)
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "api_latency_anomaly" {
  alarm_name          = "${var.project_name}-api-p99-latency-anomaly"
  alarm_description   = "API Gateway p99 latency has breached the anomaly detection band (${var.anomaly_detection_band} standard deviations) for 3 consecutive datapoints"
  comparison_operator = "GreaterThanUpperThreshold"
  evaluation_periods  = 3
  threshold_metric_id = "anomaly_band"

  metric_query {
    id          = "p99_latency"
    return_data = true

    metric {
      metric_name = "Latency"
      namespace   = "AWS/ApiGateway"
      period      = 300
      stat        = "p99"

      dimensions = {
        ApiName = var.api_gateway_name
        Stage   = var.api_gateway_stage
      }
    }
  }

  metric_query {
    id          = "anomaly_band"
    expression  = "ANOMALY_DETECTION_BAND(p99_latency, ${var.anomaly_detection_band})"
    label       = "p99 Latency Anomaly Band"
    return_data = true
  }

  tags = var.tags
}

# -----------------------------------------------------------------------------
# CloudWatch Dashboard
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_dashboard" "platform" {
  dashboard_name = "${var.project_name}-${var.environment}"
  dashboard_body = jsonencode({
    widgets = [
      # Row 1: API Latency (p50/p90/p99) | Error Rates (4xx/5xx)
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "API Latency (p50/p90/p99)"
          region = local.region
          metrics = [
            ["AWS/ApiGateway", "Latency", "ApiName", var.api_gateway_name, "Stage", var.api_gateway_stage, { stat = "p50", label = "p50" }],
            ["AWS/ApiGateway", "Latency", "ApiName", var.api_gateway_name, "Stage", var.api_gateway_stage, { stat = "p90", label = "p90" }],
            ["AWS/ApiGateway", "Latency", "ApiName", var.api_gateway_name, "Stage", var.api_gateway_stage, { stat = "p99", label = "p99" }]
          ]
          period = 300
          view   = "timeSeries"
          yAxis = {
            left = {
              label     = "Milliseconds"
              showUnits = false
            }
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Error Rates (4xx/5xx)"
          region = local.region
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_Target_4XX_Count", "LoadBalancer", var.alb_full_name, { stat = "Sum", label = "4xx Errors" }],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", var.alb_full_name, { stat = "Sum", label = "5xx Errors" }]
          ]
          period = 300
          view   = "timeSeries"
          yAxis = {
            left = {
              label     = "Count"
              showUnits = false
            }
          }
        }
      },
      # Row 2: Cache Hit Ratio | DB Active Connections
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Cache Hit Ratio"
          region = local.region
          metrics = [
            ["AWS/ElastiCache", "CacheHitRate", "ReplicationGroupId", var.elasticache_cluster_id, { stat = "Average", label = "Hit Rate %" }]
          ]
          period = 300
          view   = "timeSeries"
          yAxis = {
            left = {
              label     = "Percentage"
              showUnits = false
              min       = 0
              max       = 100
            }
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "DB Active Connections"
          region = local.region
          metrics = [
            ["AWS/RDS", "DatabaseConnections", "DBClusterIdentifier", var.rds_cluster_identifier, { stat = "Average", label = "Active Connections" }]
          ]
          period = 300
          view   = "timeSeries"
          annotations = {
            horizontal = [
              {
                label = "80% Threshold"
                value = local.db_connections_threshold
                color = "#ff7f0e"
              }
            ]
          }
          yAxis = {
            left = {
              label     = "Connections"
              showUnits = false
              min       = 0
            }
          }
        }
      },
      # Row 3: ECS Running Tasks | Cumulative Cost Estimate
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "ECS Running Tasks"
          region = local.region
          metrics = [
            ["ECS/ContainerInsights", "RunningTaskCount", "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name, { stat = "Average", label = "Running Tasks" }]
          ]
          period = 300
          view   = "timeSeries"
          yAxis = {
            left = {
              label     = "Tasks"
              showUnits = false
              min       = 0
            }
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "Cumulative Cost Estimate"
          region = local.region
          metrics = [
            ["AWS/Billing", "EstimatedCharges", "Currency", "USD", { stat = "Maximum", label = "Estimated Charges (USD)" }]
          ]
          period = 21600
          view   = "timeSeries"
          yAxis = {
            left = {
              label     = "USD"
              showUnits = false
              min       = 0
            }
          }
        }
      }
    ]
  })
}

data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# CloudWatch Logs Insights Saved Queries
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_query_definition" "slow_requests" {
  name            = "${var.project_name}/slow-requests"
  log_group_names = [var.log_group_name]

  query_string = <<-EOT
    fields @timestamp, method, path, duration_ms, status_code, request_id, user_id
    | filter duration_ms > 1000
    | sort duration_ms desc
    | limit 50
  EOT
}

resource "aws_cloudwatch_query_definition" "auth_failures_by_ip" {
  name            = "${var.project_name}/auth-failures-by-ip"
  log_group_names = [var.log_group_name]

  query_string = <<-EOT
    fields @timestamp, source_ip, path, status_code, error_code
    | filter status_code = 401 or status_code = 403
    | stats count(*) as failure_count by source_ip
    | sort failure_count desc
    | limit 20
  EOT
}

resource "aws_cloudwatch_query_definition" "cache_misses_by_endpoint" {
  name            = "${var.project_name}/cache-misses-by-endpoint"
  log_group_names = [var.log_group_name]

  query_string = <<-EOT
    fields @timestamp, path, cache_hit, duration_ms
    | filter cache_hit = 0 or cache_hit = "false"
    | stats count(*) as miss_count, avg(duration_ms) as avg_latency by path
    | sort miss_count desc
    | limit 20
  EOT
}

# -----------------------------------------------------------------------------
# Contributor Insights Rules (via CloudFormation — no native Terraform resource)
# -----------------------------------------------------------------------------

resource "aws_cloudformation_stack" "contributor_insights_top_callers" {
  name = "${var.project_name}-ci-top-callers"

  template_body = jsonencode({
    AWSTemplateFormatVersion = "2010-09-09"
    Description              = "Contributor Insights rule: Top 10 callers by request count"
    Resources = {
      TopCallersRule = {
        Type = "AWS::CloudWatch::InsightRule"
        Properties = {
          RuleName  = "${var.project_name}-top-callers-by-request-count"
          RuleState = "ENABLED"
          RuleBody = jsonencode({
            Schema = {
              Name    = "CloudWatchLogRule"
              Version = 1
            }
            AggregateOn = "Count"
            Contribution = {
              Filters = []
              Keys    = ["$.api_key_id"]
            }
            LogFormat      = "JSON"
            LogGroupNames  = [var.api_gateway_log_group_name]
          })
        }
      }
    }
    Outputs = {
      RuleName = {
        Value = { Ref = "TopCallersRule" }
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudformation_stack" "contributor_insights_top_errors" {
  name = "${var.project_name}-ci-top-errors"

  template_body = jsonencode({
    AWSTemplateFormatVersion = "2010-09-09"
    Description              = "Contributor Insights rule: Top 10 error sources by path"
    Resources = {
      TopErrorsRule = {
        Type = "AWS::CloudWatch::InsightRule"
        Properties = {
          RuleName  = "${var.project_name}-top-error-sources-by-path"
          RuleState = "ENABLED"
          RuleBody = jsonencode({
            Schema = {
              Name    = "CloudWatchLogRule"
              Version = 1
            }
            AggregateOn = "Count"
            Contribution = {
              Filters = [
                {
                  Match       = "$.status_code"
                  GreaterThan = 399
                }
              ]
              Keys = ["$.path", "$.status_code"]
            }
            LogFormat      = "JSON"
            LogGroupNames  = [var.api_gateway_log_group_name]
          })
        }
      }
    }
    Outputs = {
      RuleName = {
        Value = { Ref = "TopErrorsRule" }
      }
    }
  })

  tags = var.tags
}

# -----------------------------------------------------------------------------
# SNS Notification — Composite Alarm Action
#
# The composite alarm above already has alarm_actions = [var.sns_topic_arn]
# which sends a notification when transitioning to ALARM state.
# The notification includes all child alarm states and metric values
# as part of the standard CloudWatch composite alarm notification payload.
# -----------------------------------------------------------------------------
