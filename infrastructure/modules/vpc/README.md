# VPC Module

Creates a production-grade AWS VPC with public and private subnets across multiple Availability Zones, implementing enterprise network isolation and high-availability networking patterns.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ VPC (10.0.0.0/16)                                               │
│                                                                   │
│  ┌─────────────────────────┐  ┌─────────────────────────┐       │
│  │ Public Subnet AZ-a      │  │ Public Subnet AZ-b      │       │
│  │ 10.0.1.0/24             │  │ 10.0.2.0/24             │       │
│  │ • NAT Gateway           │  │ • NAT Gateway           │       │
│  │ • Route → IGW           │  │ • Route → IGW           │       │
│  └─────────────────────────┘  └─────────────────────────┘       │
│                                                                   │
│  ┌─────────────────────────┐  ┌─────────────────────────┐       │
│  │ Private Subnet AZ-a     │  │ Private Subnet AZ-b     │       │
│  │ 10.0.10.0/24            │  │ 10.0.11.0/24            │       │
│  │ • Route → NAT GW (AZ-a)│  │ • Route → NAT GW (AZ-b)│       │
│  └─────────────────────────┘  └─────────────────────────┘       │
│                                                                   │
│  Internet Gateway                                                 │
│  VPC Flow Logs → CloudWatch (30-day retention)                   │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **Multi-AZ deployment**: Public and private subnets in 2–4 Availability Zones
- **NAT Gateway per AZ**: Ensures private subnet outbound traffic stays AZ-local for resilience
- **Separate route tables**: Per-subnet routing control for fine-grained network policy
- **Network ACLs**:
  - Public subnets: Allow HTTPS (443) and ephemeral ports (1024–65535) inbound
  - Private subnets: Allow inbound only from VPC CIDR
- **VPC Flow Logs**: All traffic (ACCEPT + REJECT) captured to CloudWatch Logs
- **DNS support**: Both `enableDnsHostnames` and `enableDnsSupport` enabled

## Usage

```hcl
module "vpc" {
  source = "./modules/vpc"

  vpc_cidr     = "10.0.0.0/16"
  az_count     = 2
  subnet_bits  = 8
  environment  = "demo"
  project_name = "secure-multi-tier-platform"
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `vpc_cidr` | CIDR block for the VPC (must be /16) | `string` | n/a | yes |
| `az_count` | Number of Availability Zones (2–4) | `number` | `2` | no |
| `subnet_bits` | Additional bits for subnet CIDR (8 = /24 from /16) | `number` | `8` | no |
| `environment` | Deployment environment name | `string` | `"demo"` | no |
| `project_name` | Project name for resource naming | `string` | `"secure-multi-tier-platform"` | no |
| `flow_log_retention_days` | CloudWatch retention for flow logs | `number` | `30` | no |

## Outputs

| Name | Description |
|------|-------------|
| `vpc_id` | ID of the VPC |
| `vpc_cidr_block` | CIDR block of the VPC |
| `public_subnet_ids` | List of public subnet IDs |
| `private_subnet_ids` | List of private subnet IDs |
| `public_subnet_cidr_blocks` | List of public subnet CIDR blocks |
| `private_subnet_cidr_blocks` | List of private subnet CIDR blocks |
| `nat_gateway_ids` | List of NAT Gateway IDs |
| `nat_gateway_public_ips` | List of NAT Gateway Elastic IPs |
| `internet_gateway_id` | ID of the Internet Gateway |
| `public_route_table_ids` | List of public route table IDs |
| `private_route_table_ids` | List of private route table IDs |
| `flow_log_group_arn` | ARN of the VPC Flow Logs CloudWatch group |
| `availability_zones` | List of Availability Zones used |

## Network ACL Rules

### Public Subnets

| Rule # | Direction | Protocol | Port Range | Source/Dest | Action |
|--------|-----------|----------|------------|-------------|--------|
| 100 | Inbound | TCP | 443 | 0.0.0.0/0 | Allow |
| 110 | Inbound | TCP | 1024–65535 | 0.0.0.0/0 | Allow |
| * | Inbound | All | All | 0.0.0.0/0 | Deny |
| 100 | Outbound | All | All | 0.0.0.0/0 | Allow |

### Private Subnets

| Rule # | Direction | Protocol | Port Range | Source/Dest | Action |
|--------|-----------|----------|------------|-------------|--------|
| 100 | Inbound | All | All | VPC CIDR | Allow |
| * | Inbound | All | All | 0.0.0.0/0 | Deny |
| 100 | Outbound | All | All | 0.0.0.0/0 | Allow |

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | ~> 5.0 |

## Related Modules

- **security-groups**: Consumes `vpc_id` to create resource-level firewalls
- **vpc-endpoints**: Consumes `vpc_id`, `private_subnet_ids`, `private_route_table_ids`
- **alb**: Consumes `public_subnet_ids` for internet-facing load balancer placement
- **ecs**: Consumes `private_subnet_ids` for application task placement
