# Security Groups Module

## Purpose

This module implements layered security groups following the principle of least privilege (defence-in-depth) for the secure-multi-tier-platform. Each security group enforces strict traffic controls ensuring resources can only communicate with explicitly permitted peers on specific ports.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Security Group Topology                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Internet ──[443]──► ALB SG ──[8000]──► App SG ──[5432]──► DB SG      │
│                                            │                            │
│                                            ├──[6379]──► Cache SG        │
│                                            │                            │
│                                            ├──[443]───► Endpoints SG    │
│                                            │                            │
│                                            └──[443]───► NAT (internet)  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Design Decisions

- **Explicit deny-all ingress baseline**: AWS security groups deny all inbound traffic by default. No inline ingress rules are defined on the `aws_security_group` resources; only explicit `aws_vpc_security_group_ingress_rule` resources add allow rules.
- **Security group references over CIDR**: Where possible, rules reference other security groups rather than CIDR blocks, ensuring traffic is only accepted from resources actually attached to the permitted group.
- **Separate rule resources**: Using `aws_vpc_security_group_ingress_rule` and `aws_vpc_security_group_egress_rule` (rather than inline rules) provides individual resource tracking, easier auditing, and avoids rule conflicts.
- **Descriptive tags**: Every security group and rule carries tags describing its purpose, security tier, and permitted traffic sources for operational visibility.

## Security Groups

| Security Group | Inbound Rules | Outbound Rules |
|---------------|---------------|----------------|
| ALB | TCP 443 from 0.0.0.0/0 | All traffic to 0.0.0.0/0 |
| Application | TCP 8000 from ALB SG | TCP 5432 to DB SG, TCP 6379 to Cache SG, TCP 443 to Endpoints SG, TCP 443 to 0.0.0.0/0 (NAT) |
| Database | TCP 5432 from App SG | (default deny — no explicit egress rules) |
| Cache | TCP 6379 from App SG | (default deny — no explicit egress rules) |
| VPC Endpoints | TCP 443 from App SG | (default deny — no explicit egress rules) |

## Usage

```hcl
module "security_groups" {
  source = "./modules/security-groups"

  project     = "secure-multi-tier-platform"
  environment = "demo"
  vpc_id      = module.vpc.vpc_id
  vpc_cidr    = module.vpc.vpc_cidr
  app_port    = 8000

  tags = module.tagging.tags_map
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `project` | Project name for resource naming and tagging | `string` | `"secure-multi-tier-platform"` | no |
| `environment` | Deployment environment (local, demo) | `string` | `"demo"` | no |
| `vpc_id` | ID of the VPC for security group creation | `string` | - | yes |
| `vpc_cidr` | CIDR block of the VPC | `string` | - | yes |
| `app_port` | Port the Application Service listens on | `number` | `8000` | no |
| `tags` | Additional tags to apply to all resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| `alb_sg_id` | ID of the ALB security group |
| `app_sg_id` | ID of the Application Service security group |
| `db_sg_id` | ID of the Database Cluster security group |
| `cache_sg_id` | ID of the Cache Cluster security group |
| `endpoint_sg_id` | ID of the VPC Endpoints security group |

## Dependencies

### Upstream

- **VPC module**: Provides `vpc_id` and `vpc_cidr` inputs

### Downstream Consumers

- `alb` — uses `alb_sg_id` for load balancer network configuration
- `ecs` — uses `app_sg_id` for Fargate task networking
- `rds` — uses `db_sg_id` for Aurora cluster security
- `elasticache` — uses `cache_sg_id` for Redis cluster security
- `vpc-endpoints` — uses `endpoint_sg_id` for interface endpoint security

## Security Considerations

- All security groups start from an implicit deny-all ingress baseline (AWS default behaviour)
- No security group permits inbound traffic from `0.0.0.0/0` except the ALB on port 443
- Database and cache security groups have no egress rules, relying on stateful return traffic only
- The application security group's outbound rules are scoped to specific ports and destination groups
- Security group references (rather than CIDRs) ensure dynamic, membership-based access control
- All resources tagged with `SecurityTier` and `TrafficSources` for compliance auditing

## Requirement Traceability

| Requirement | Implementation |
|-------------|---------------|
| 2.1 ALB SG inbound HTTPS from internet | `aws_vpc_security_group_ingress_rule.alb_https` |
| 2.2 App SG inbound from ALB only, outbound to DB/Cache/NAT | `aws_vpc_security_group_ingress_rule.app_from_alb` + egress rules |
| 2.3 DB SG inbound PostgreSQL from App SG | `aws_vpc_security_group_ingress_rule.db_from_app` |
| 2.4 Cache SG inbound Redis from App SG | `aws_vpc_security_group_ingress_rule.cache_from_app` |
| 2.5 Explicit deny-all ingress baseline | AWS default + no inline ingress rules |
| 2.6 Descriptive tags on all groups | `tags` blocks with Name, SecurityTier, TrafficSources |
