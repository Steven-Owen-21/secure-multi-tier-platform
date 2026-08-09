# API Gateway Module

Creates an Amazon API Gateway REST API with regional endpoint configuration fronting the Application Load Balancer, tiered usage plans with API keys, request payload validation, custom domain support, and CloudWatch access logging.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│ API Gateway (Regional Endpoint)                                          │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ REST API                                                            │ │
│  │                                                                     │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐  │ │
│  │  │ Request         │  │ Cognito         │  │ Usage Plan       │  │ │
│  │  │ Validation      │  │ Authorizer      │  │ Enforcement      │  │ │
│  │  │ (JSON Schema)   │  │ (JWT)           │  │ (API Key)        │  │ │
│  │  └─────────────────┘  └─────────────────┘  └──────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                              │                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Stages                                                              │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐                  │ │
│  │  │development │  │ staging    │  │ production │                   │ │
│  │  └────────────┘  └────────────┘  └────────────┘                  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                              │                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Usage Plans                                                         │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                        │ │
│  │  │ Free     │  │ Standard │  │ Premium  │                         │ │
│  │  │ 100/day  │  │ 10k/day  │  │ 100k/day │                        │ │
│  │  │ 10/s     │  │ 50/s     │  │ 200/s    │                        │ │
│  │  └──────────┘  └──────────┘  └──────────┘                        │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                              │                                           │
│                    HTTP_PROXY Integration                                │
│                              │                                           │
│                    ┌─────────▼──────────┐                               │
│                    │ Application Load   │                                │
│                    │ Balancer (ALB)     │                                │
│                    └────────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────┘

           Access Logs → CloudWatch Logs
           (requestId, sourceIp, method, path, status, latency, apiKeyId)
```

## Features

- **Regional REST API**: Deployed in the same region as the ALB backend for low latency
- **Cognito Authorizer**: JWT-based authentication via Cognito User Pools
- **Request Validation**: JSON Schema models for ProductCreate and OrderCreate payloads
- **Tiered Usage Plans**: Free (100 req/day), Standard (10k/day), Premium (100k/day)
- **API Keys**: One key per usage plan for client identification and rate enforcement
- **Multiple Stages**: development, staging, production with stage-specific variables
- **Structured Error Responses**: Consistent JSON error format for all 4xx/5xx responses
- **Access Logging**: CloudWatch Logs with request ID, source IP, method, path, status, latency, API key ID
- **Custom Domain**: Optional custom domain with ACM TLS certificate (regional endpoint)
- **Detailed Metrics**: Per-method CloudWatch metrics enabled by default

## Usage

```hcl
module "api_gateway" {
  source = "./modules/api-gateway"

  alb_dns_name          = module.alb.alb_dns_name
  cognito_user_pool_arn = module.cognito.user_pool_arn

  environment  = "demo"
  project_name = "secure-multi-tier-platform"

  # Optional: custom domain
  custom_domain_name  = "api.example.com"
  acm_certificate_arn = aws_acm_certificate.api.arn

  # Usage plan configuration (defaults shown)
  free_tier_daily_limit     = 100
  free_tier_burst_limit     = 10
  standard_tier_daily_limit = 10000
  standard_tier_burst_limit = 50
  premium_tier_daily_limit  = 100000
  premium_tier_burst_limit  = 200

  # Logging
  access_log_retention_days = 30
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `alb_dns_name` | DNS name of the ALB backend | `string` | n/a | yes |
| `cognito_user_pool_arn` | ARN of the Cognito user pool for authorization | `string` | n/a | yes |
| `environment` | Deployment environment name | `string` | `"demo"` | no |
| `project_name` | Project name for resource naming | `string` | `"secure-multi-tier-platform"` | no |
| `custom_domain_name` | Custom domain (leave empty to skip) | `string` | `""` | no |
| `acm_certificate_arn` | ACM certificate ARN for custom domain | `string` | `""` | no |
| `stages` | List of stage names to create | `list(string)` | `["development","staging","production"]` | no |
| `free_tier_daily_limit` | Free plan daily request quota | `number` | `100` | no |
| `free_tier_burst_limit` | Free plan burst limit (req/s) | `number` | `10` | no |
| `free_tier_rate_limit` | Free plan steady-state rate (req/s) | `number` | `5` | no |
| `standard_tier_daily_limit` | Standard plan daily request quota | `number` | `10000` | no |
| `standard_tier_burst_limit` | Standard plan burst limit (req/s) | `number` | `50` | no |
| `standard_tier_rate_limit` | Standard plan steady-state rate (req/s) | `number` | `25` | no |
| `premium_tier_daily_limit` | Premium plan daily request quota | `number` | `100000` | no |
| `premium_tier_burst_limit` | Premium plan burst limit (req/s) | `number` | `200` | no |
| `premium_tier_rate_limit` | Premium plan steady-state rate (req/s) | `number` | `100` | no |
| `access_log_retention_days` | CloudWatch log retention in days | `number` | `30` | no |
| `enable_detailed_metrics` | Enable detailed CloudWatch metrics | `bool` | `true` | no |

## Outputs

| Name | Description |
|------|-------------|
| `api_endpoint` | Invoke URL of the production stage |
| `api_id` | ID of the REST API |
| `api_arn` | ARN of the REST API |
| `api_execution_arn` | Execution ARN (for IAM permissions) |
| `api_key_ids` | Map of tier to API key IDs |
| `api_key_values` | Map of tier to API key values (sensitive) |
| `usage_plan_ids` | Map of tier to usage plan IDs |
| `stage_invoke_urls` | Map of stage name to invoke URL |
| `stage_arns` | Map of stage name to stage ARN |
| `cloudwatch_log_group_arns` | Map of stage to log group ARN |
| `custom_domain_name` | Custom domain name (empty if not configured) |
| `custom_domain_regional_domain_name` | Regional domain for CNAME/alias records |
| `custom_domain_regional_zone_id` | Zone ID for Route53 alias records |
| `authorizer_id` | ID of the Cognito authorizer |

## Usage Plans

| Plan | Daily Quota | Burst (req/s) | Steady Rate (req/s) | Use Case |
|------|-------------|---------------|---------------------|----------|
| Free | 100 | 10 | 5 | Evaluation / public demos |
| Standard | 10,000 | 50 | 25 | Internal applications |
| Premium | 100,000 | 200 | 100 | High-volume production clients |

## Access Log Format

The access log captures the following fields per request:

| Field | Description |
|-------|-------------|
| `requestId` | Unique API Gateway request identifier |
| `sourceIp` | Client source IP address |
| `httpMethod` | HTTP method (GET, POST, etc.) |
| `path` | Request path |
| `status` | HTTP response status code |
| `latency` | Response latency in milliseconds |
| `apiKeyId` | ID of the API key used (for usage tracking) |

## Request Validation

JSON Schema models are defined for payload validation:

- **ProductCreate**: Validates product creation requests (name, price_pence, stock_quantity, category)
- **OrderCreate**: Validates order creation requests (items array with product_id UUID and quantity)

Invalid requests are rejected at the API Gateway layer with a 400 response before reaching the ALB.

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | ~> 5.0 |

## Related Modules

- **alb**: Provides `alb_dns_name` as the backend integration endpoint
- **cognito**: Provides `cognito_user_pool_arn` for JWT authorizer
- **cloudfront**: Consumes `api_endpoint` as the API origin
- **observability**: Consumes `stage_arns` for CloudWatch monitoring
