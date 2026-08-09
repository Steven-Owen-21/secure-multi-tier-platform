# ECS Fargate Module

Deploys an ECS Fargate service for the Application_Service with high-availability and zero-downtime deployment capabilities.

## Architecture

- **ECS Cluster** with Container Insights enabled for observability
- **Fargate Tasks** running the Application_Service container in private subnets
- **Multi-AZ placement** with minimum 2 tasks distributed across different Availability Zones
- **Zero-downtime deployments** via rolling update (min healthy 100%, max 200%)
- **ALB integration** for health-checked traffic routing with automatic deregistration of unhealthy tasks
- **Deployment circuit breaker** with automatic rollback on failed deployments

## Requirements Addressed

| Requirement | Description |
|-------------|-------------|
| 10.3 | ECS Fargate service with minimum 2 tasks across different AZs |
| 10.4 | ALB stops routing to failed tasks within 90s; ECS launches replacements |
| 10.5 | Deployment config: min healthy 100%, max 200% for zero-downtime |

## Usage

```hcl
module "ecs" {
  source = "./modules/ecs"

  private_subnet_ids = module.vpc.private_subnet_ids
  app_sg_id          = module.security_groups.app_sg_id
  target_group_arn   = module.alb.target_group_arn
  ecr_image_uri      = "123456789012.dkr.ecr.eu-west-2.amazonaws.com/secure-multi-tier-platform:latest"

  environment_variables = {
    DATABASE_URL = "postgresql+asyncpg://user:pass@db-host:5432/app"
    REDIS_URL    = "rediss://cache-host:6379/0"
    COGNITO_POOL_ID = "eu-west-2_abc123"
  }

  secrets = {
    DB_PASSWORD     = "arn:aws:secretsmanager:eu-west-2:123456789012:secret:db-password-abc123"
    REDIS_AUTH_TOKEN = "arn:aws:secretsmanager:eu-west-2:123456789012:secret:redis-token-def456"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| private_subnet_ids | Private subnet IDs for task placement (min 2 AZs) | list(string) | - | yes |
| app_sg_id | Security group ID for ECS tasks | string | - | yes |
| target_group_arn | ALB target group ARN | string | - | yes |
| ecr_image_uri | Full ECR image URI with tag | string | - | yes |
| environment | Deployment environment name | string | "demo" | no |
| project_name | Project name for resource naming | string | "secure-multi-tier-platform" | no |
| app_port | Container listening port | number | 8000 | no |
| desired_count | Number of tasks (min 2 for HA) | number | 2 | no |
| cpu | Fargate CPU units | number | 256 | no |
| memory | Fargate memory (MiB) | number | 512 | no |
| environment_variables | Non-sensitive env vars for the container | map(string) | {} | no |
| secrets | Secret name → Secrets Manager ARN mapping | map(string) | {} | no |
| log_retention_days | CloudWatch log retention | number | 30 | no |
| assign_public_ip | Assign public IP to tasks | bool | false | no |
| health_check_grace_period | Seconds before health checks apply | number | 60 | no |
| enable_execute_command | Enable ECS Exec for debugging | bool | false | no |
| aws_region | AWS region | string | "eu-west-2" | no |

## Outputs

| Name | Description |
|------|-------------|
| service_arn | ARN of the ECS service |
| task_definition_arn | ARN of the task definition |
| cluster_arn | ARN of the ECS cluster |
| cluster_name | Name of the ECS cluster |
| service_name | Name of the ECS service |
| task_execution_role_arn | ARN of the task execution role |
| task_role_arn | ARN of the task role |
| log_group_name | CloudWatch log group name |

## Deployment Strategy

The module implements a zero-downtime rolling deployment:

1. New tasks are launched (up to 200% of desired count)
2. ALB health checks verify new tasks are healthy
3. Old tasks are drained and terminated
4. If deployment fails, circuit breaker triggers automatic rollback

## Health Checking

Tasks are health-checked at two levels:

1. **Container health check**: `curl -f http://localhost:8000/health` every 30s
2. **ALB health check**: Configured in the ALB module (path `/health`, interval 30s, unhealthy threshold 3)

When a task fails the ALB health check, it is deregistered from the target group and replaced by the ECS service scheduler.

## Security

- Tasks run in private subnets with no public IP by default
- Task execution role follows least privilege (ECR pull, log write, secrets read)
- Task role is minimal by default; extend via additional policies for application needs
- Secrets are injected at runtime from Secrets Manager (never stored in task definition)
