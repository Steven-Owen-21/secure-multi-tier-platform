# VPC Endpoints Module

Creates VPC endpoints for private connectivity to AWS services, keeping application traffic off the public internet and reducing NAT Gateway data processing costs.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ VPC                                                              │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Private Subnets                                          │    │
│  │                                                           │    │
│  │  ECS Tasks ──┬──► CloudWatch Logs Endpoint (Interface)   │    │
│  │              ├──► Secrets Manager Endpoint (Interface)    │    │
│  │              ├──► ECR API Endpoint (Interface)            │    │
│  │              └──► ECR Docker Endpoint (Interface)         │    │
│  │                                                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Route Tables ──┬──► S3 Gateway Endpoint (free)                  │
│                 └──► DynamoDB Gateway Endpoint (free)             │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **Gateway Endpoints (free)**:
  - S3 — with restrictive endpoint policy limiting access to platform buckets only
  - DynamoDB — route table entries in all private subnet route tables
- **Interface Endpoints (ENI-based)**:
  - CloudWatch Logs — private log shipping from ECS tasks
  - Secrets Manager — private credential retrieval
  - ECR API — container image metadata for Fargate pulls
  - ECR Docker — container image layer downloads for Fargate pulls
- **Private DNS enabled** on all Interface endpoints for seamless SDK usage
- **Endpoint security group** restricts inbound HTTPS (443) to Application SG only

## Gateway vs Interface Endpoints: Cost and Security Trade-offs

| Aspect | Gateway Endpoints | Interface Endpoints |
|--------|-------------------|---------------------|
| Cost | Free | ~£0.01/hour per AZ + data processing |
| Mechanism | Route table prefix list | ENI in subnet |
| DNS | Automatic (prefix list) | Private DNS zones |
| Services | S3, DynamoDB only | Most other AWS services |
| Security | Endpoint policy (IAM) | Security group + endpoint policy |
| Availability | Regional (no per-AZ cost) | Per-AZ ENI deployment |

**When to use Gateway endpoints:** Always for S3 and DynamoDB — they are free and provide the same private connectivity benefit.

**When to use Interface endpoints:** When the service requires private access and you want to avoid routing through NAT Gateway (which charges per GB processed). The hourly ENI cost is justified when data transfer volumes are significant or when strict network isolation is required.

## Usage

```hcl
module "vpc_endpoints" {
  source = "./modules/vpc-endpoints"

  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  route_table_ids    = module.vpc.private_route_table_ids
  endpoint_sg_id     = module.security_groups.endpoint_sg_id

  platform_bucket_arns = [
    module.s3_lifecycle.waf_logs_bucket_arn,
    module.s3_lifecycle.flow_logs_bucket_arn,
    module.s3_lifecycle.app_data_bucket_arn,
  ]

  environment  = "demo"
  project_name = "secure-multi-tier-platform"
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `vpc_id` | ID of the VPC | `string` | n/a | yes |
| `private_subnet_ids` | List of private subnet IDs for Interface endpoints | `list(string)` | n/a | yes |
| `route_table_ids` | List of private route table IDs for Gateway endpoints | `list(string)` | n/a | yes |
| `endpoint_sg_id` | Security group ID for Interface endpoints (inbound 443 from App SG) | `string` | n/a | yes |
| `platform_bucket_arns` | S3 bucket ARNs to restrict the S3 endpoint policy to | `list(string)` | `[]` | no |
| `environment` | Deployment environment name | `string` | `"demo"` | no |
| `project_name` | Project name for resource naming | `string` | `"secure-multi-tier-platform"` | no |
| `tags` | Additional tags to apply to all resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| `endpoint_ids` | Map of service names to VPC endpoint IDs |
| `s3_endpoint_id` | ID of the S3 Gateway endpoint |
| `dynamodb_endpoint_id` | ID of the DynamoDB Gateway endpoint |
| `logs_endpoint_id` | ID of the CloudWatch Logs Interface endpoint |
| `secretsmanager_endpoint_id` | ID of the Secrets Manager Interface endpoint |
| `ecr_api_endpoint_id` | ID of the ECR API Interface endpoint |
| `ecr_dkr_endpoint_id` | ID of the ECR Docker Interface endpoint |
| `s3_endpoint_prefix_list_id` | Prefix list ID for S3 Gateway endpoint |
| `dynamodb_endpoint_prefix_list_id` | Prefix list ID for DynamoDB Gateway endpoint |

## S3 Endpoint Policy

When `platform_bucket_arns` is provided, the S3 Gateway endpoint policy restricts access to only the specified platform buckets. This prevents any workload in the VPC from accessing arbitrary S3 buckets via the endpoint, providing defence-in-depth against data exfiltration.

**Allowed actions on platform buckets:**
- `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`
- `s3:ListBucket`, `s3:GetBucketLocation`
- `s3:ListMultipartUploadParts`, `s3:AbortMultipartUpload`

**Denied:** All S3 actions on any bucket not in the `platform_bucket_arns` list.

## Security

- Interface endpoints are protected by the endpoint security group which permits inbound HTTPS (443) from the Application Service security group only
- The S3 Gateway endpoint policy restricts bucket access to platform-owned buckets
- Private DNS ensures SDK calls resolve to endpoint ENIs automatically without code changes
- No internet traversal required for supported AWS service API calls

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | >= 5.0 |

## Related Modules

- **vpc**: Provides `vpc_id`, `private_subnet_ids`, `private_route_table_ids`
- **security-groups**: Provides `endpoint_sg_id` (inbound 443 from App SG)
- **s3-lifecycle**: Provides bucket ARNs for the S3 endpoint policy
- **ecs**: Consumes ECR and CloudWatch Logs endpoints for Fargate task operation
- **secrets-rotation**: Consumes Secrets Manager endpoint for credential retrieval
