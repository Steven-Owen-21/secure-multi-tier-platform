# Auto Scaling Module

Configures ECS Application Auto Scaling for the platform's Fargate service with multiple scaling strategies to balance performance and cost.

## Purpose

This module implements dynamic capacity management for the ECS service using three complementary scaling strategies:

1. **Target Tracking (CPU)** — Maintains CPU utilisation at the configured target (default 70%) by automatically adjusting task count.
2. **Step Scaling (Request Count)** — Responds to ALB request count per target with graduated scaling steps for moderate and high load.
3. **Scheduled Scaling** — Scales the service to zero outside configurable demo hours as a cost safety mechanism.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│           Application Auto Scaling                   │
├──────────────┬──────────────────┬───────────────────┤
│ Target Track │   Step Scaling   │ Scheduled Scaling  │
│ CPU @ 70%    │ RequestCount/Tgt │ Weekdays 09-18 UTC│
│              │ 1000→+1, 2000→+2│                    │
├──────────────┴──────────────────┴───────────────────┤
│ Scalable Target: ECS Service (min: 2, max: 10)      │
└─────────────────────────────────────────────────────┘
```

## Usage

```hcl
module "auto_scaling" {
  source = "./modules/auto-scaling"

  ecs_service_name       = module.ecs.service_name
  ecs_cluster_name       = module.ecs.cluster_name
  alb_arn_suffix         = module.alb.alb_arn_suffix
  target_group_arn_suffix = module.alb.target_group_arn_suffix

  min_capacity = 2
  max_capacity = 10
  cpu_target   = 70

  enable_scheduled_scaling = true
  demo_schedule_start      = "cron(0 9 ? * MON-FRI *)"
  demo_schedule_end        = "cron(0 18 ? * MON-FRI *)"

  tags = module.tagging.tags_map
}
```

## Dependencies

- **ECS module** — Provides the service name and cluster name
- **ALB module** — Provides the ALB and target group ARN suffixes for request count metrics

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `ecs_service_name` | Name of the ECS service | `string` | — | yes |
| `ecs_cluster_name` | Name of the ECS cluster | `string` | — | yes |
| `min_capacity` | Minimum number of ECS tasks | `number` | `2` | no |
| `max_capacity` | Maximum number of ECS tasks | `number` | `10` | no |
| `cpu_target` | Target CPU utilisation percentage | `number` | `70` | no |
| `scale_out_cooldown` | Cooldown in seconds after scale-out | `number` | `60` | no |
| `scale_in_cooldown` | Cooldown in seconds after scale-in | `number` | `300` | no |
| `alb_arn_suffix` | ARN suffix of the ALB | `string` | — | yes |
| `target_group_arn_suffix` | ARN suffix of the target group | `string` | — | yes |
| `request_count_threshold_moderate` | Request count threshold for +1 task | `number` | `1000` | no |
| `request_count_threshold_high` | Request count threshold for +2 tasks | `number` | `2000` | no |
| `demo_schedule_start` | Cron expression for scale-up time | `string` | `cron(0 9 ? * MON-FRI *)` | no |
| `demo_schedule_end` | Cron expression for scale-down time | `string` | `cron(0 18 ? * MON-FRI *)` | no |
| `enable_scheduled_scaling` | Whether to enable scheduled scaling | `bool` | `true` | no |
| `tags` | Tags to apply to resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| `scaling_policy_arns` | Map of scaling policy ARNs (cpu_target_tracking, request_count_step) |
| `scalable_target_id` | ID of the Application Auto Scaling scalable target |
| `request_count_alarm_arn` | ARN of the CloudWatch alarm triggering step scaling |
| `scheduled_action_arns` | Map of scheduled action ARNs (scale_up, scale_down); empty if disabled |

## Scaling Behaviour

### Target Tracking (CPU)

- Scales out when average CPU exceeds 70% (configurable)
- Scales in when CPU drops below target
- Cooldowns prevent thrashing: 60s scale-out, 300s scale-in

### Step Scaling (Request Count)

| Request Count Per Target | Action |
|--------------------------|--------|
| 1000–2000 | Add 1 task |
| 2000+ | Add 2 tasks |

### Scheduled Scaling

- **Scale up**: Restores min/max capacity at demo start (default: weekdays 09:00 UTC)
- **Scale down**: Sets min and max to 0 at demo end (default: weekdays 18:00 UTC)
- Disable with `enable_scheduled_scaling = false` for always-on environments

## Cost Safety

The scheduled scaling rule ensures the service is not running outside demo hours, preventing unexpected charges. The default schedule targets weekday business hours (09:00–18:00 UTC).
