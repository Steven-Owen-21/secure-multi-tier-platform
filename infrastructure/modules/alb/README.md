# ALB Module

Creates an internet-facing Application Load Balancer (layer 7) deployed across public subnets in multiple Availability Zones, with a target group configured for ECS Fargate IP-based targets and configurable health checks.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Public Tier                                                      │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Application Load Balancer (cross-zone enabled)              │ │
│  │                                                              │ │
│  │  ┌──────────────────┐       ┌──────────────────┐           │ │
│  │  │ Public Subnet    │       │ Public Subnet    │           │ │
│  │  │ AZ-a             │       │ AZ-b             │           │ │
│  │  └──────────────────┘       └──────────────────┘           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                         │                                         │
│                    HTTP Listener (:80)                            │
│                         │                                         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Target Group (IP-based, HTTP :8000)                         │ │
│  │                                                              │ │
│  │  Health Check: /health                                      │ │
│  │  Healthy: 2 checks │ Unhealthy: 3 checks                   │ │
│  │  Interval: 30s │ Timeout: 5s                                │ │
│  │                                                              │ │
│  │  ┌────────────┐  ┌────────────┐                            │ │
│  │  │ ECS Task   │  │ ECS Task   │ (Fargate, private subnets) │ │
│  │  │ AZ-a       │  │ AZ-b       │                            │ │
│  │  └────────────┘  └────────────┘                            │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **Application Load Balancer (Layer 7)**: HTTP/HTTPS traffic routing with content-based routing capability
- **Multi-AZ deployment**: Deployed across minimum 2 public subnets for high availability
- **Cross-zone load balancing**: Distributes traffic evenly across all registered targets in all AZs
- **IP-based target group**: Configured for ECS Fargate tasks (awsvpc networking mode)
- **Configurable health checks**: Path, thresholds, interval, and timeout all parameterised
- **Optional access logging**: S3-based access logs controlled by variable
- **Deletion protection**: Configurable (default: false for demo environments)
- **Deregistration delay**: Configurable drain time for graceful target removal

## Usage

```hcl
module "alb" {
  source = "./modules/alb"

  public_subnet_ids = module.vpc.public_subnet_ids
  alb_sg_id         = module.security_groups.alb_sg_id
  vpc_id            = module.vpc.vpc_id

  environment  = "demo"
  project_name = "secure-multi-tier-platform"

  # Health check configuration
  health_check_path                = "/health"
  health_check_healthy_threshold   = 2
  health_check_unhealthy_threshold = 3
  health_check_interval            = 30
  health_check_timeout             = 5

  # Optional: access logging
  enable_access_logging  = true
  access_log_bucket_name = module.s3_lifecycle.alb_log_bucket_name

  # Demo environment: deletion protection off
  enable_deletion_protection = false
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `public_subnet_ids` | List of public subnet IDs (minimum 2 AZs) | `list(string)` | n/a | yes |
| `alb_sg_id` | Security group ID for the ALB | `string` | n/a | yes |
| `vpc_id` | VPC ID for the target group | `string` | n/a | yes |
| `environment` | Deployment environment name | `string` | `"demo"` | no |
| `project_name` | Project name for resource naming | `string` | `"secure-multi-tier-platform"` | no |
| `app_port` | Application container port | `number` | `8000` | no |
| `health_check_path` | Health check endpoint path | `string` | `"/health"` | no |
| `health_check_healthy_threshold` | Consecutive successful checks to mark healthy | `number` | `2` | no |
| `health_check_unhealthy_threshold` | Consecutive failed checks to mark unhealthy | `number` | `3` | no |
| `health_check_interval` | Seconds between health checks | `number` | `30` | no |
| `health_check_timeout` | Seconds to wait for health check response | `number` | `5` | no |
| `enable_deletion_protection` | Enable ALB deletion protection | `bool` | `false` | no |
| `enable_access_logging` | Enable access logging to S3 | `bool` | `false` | no |
| `access_log_bucket_name` | S3 bucket for access logs (required if logging enabled) | `string` | `""` | no |
| `access_log_prefix` | S3 key prefix for access logs | `string` | `"alb-logs"` | no |
| `deregistration_delay` | Seconds to wait before deregistering a target | `number` | `30` | no |

## Outputs

| Name | Description |
|------|-------------|
| `alb_arn` | ARN of the Application Load Balancer |
| `alb_dns_name` | DNS name of the ALB |
| `alb_zone_id` | Hosted zone ID of the ALB (for Route53 alias records) |
| `target_group_arn` | ARN of the target group for ECS tasks |
| `target_group_name` | Name of the target group |
| `http_listener_arn` | ARN of the HTTP listener |
| `alb_id` | ID of the ALB |

## Health Check Configuration

The target group health check is configured to detect unhealthy ECS tasks quickly while avoiding false positives:

| Parameter | Default | Description |
|-----------|---------|-------------|
| Path | `/health` | Application health endpoint |
| Protocol | HTTP | Health check protocol |
| Port | traffic-port | Same port as application traffic |
| Healthy threshold | 2 | Must pass 2 consecutive checks |
| Unhealthy threshold | 3 | Must fail 3 consecutive checks |
| Interval | 30s | Time between checks |
| Timeout | 5s | Max wait for response |
| Success codes | 200 | Expected HTTP status |

**Failure detection time**: With unhealthy threshold of 3 and interval of 30s, an unhealthy target is detected within 90 seconds (3 × 30s). This meets Requirement 10.4 which states traffic stops routing within 90 seconds.

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | ~> 5.0 |

## Related Modules

- **vpc**: Provides `public_subnet_ids` for ALB placement and `vpc_id` for target group
- **security-groups**: Provides `alb_sg_id` restricting ALB inbound/outbound traffic
- **ecs**: Consumes `target_group_arn` to register Fargate tasks as targets
- **waf**: Consumes `alb_arn` to attach WAF Web ACL
- **api-gateway**: Consumes `alb_dns_name` for backend integration
- **observability**: Consumes `alb_arn` for CloudWatch metrics and alarms
