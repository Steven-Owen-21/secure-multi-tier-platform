###############################################################################
# Security Groups Module
#
# Implements layered security groups following the principle of least privilege
# (defence-in-depth) for the secure-multi-tier-platform.
#
# Security Groups defined:
#   - ALB:              inbound HTTPS (443) from internet, all outbound
#   - Application:      inbound app_port from ALB SG only, outbound to DB/Cache/NAT
#   - Database:         inbound PostgreSQL (5432) from App SG only
#   - Cache:            inbound Redis (6379) from App SG only
#   - VPC Endpoints:    inbound HTTPS (443) from App SG only
#
# All groups use AWS default deny-all ingress baseline — only explicit allow
# rules are added. No inline ingress/egress rules are defined on the
# aws_security_group resources; instead, separate aws_vpc_security_group_*_rule
# resources provide the allow rules for clarity and auditability.
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

locals {
  common_tags = merge(
    {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Component   = "network-security"
    },
    var.tags
  )
}

# =============================================================================
# ALB Security Group
# Purpose: Controls traffic to the Application Load Balancer (public-facing)
# Permitted sources: Internet (0.0.0.0/0) on HTTPS only
# =============================================================================

resource "aws_security_group" "alb" {
  name        = "${var.project}-alb-sg"
  description = "ALB security group: permits inbound HTTPS (443) from internet, all outbound"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, {
    Name           = "${var.project}-alb-sg"
    SecurityTier   = "public"
    TrafficSources = "internet-https-443"
  })
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  description       = "Allow inbound HTTPS from internet"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"

  tags = merge(local.common_tags, {
    Name = "${var.project}-alb-ingress-https"
  })
}

resource "aws_vpc_security_group_egress_rule" "alb_all_outbound" {
  security_group_id = aws_security_group.alb.id
  description       = "Allow all outbound traffic from ALB"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"

  tags = merge(local.common_tags, {
    Name = "${var.project}-alb-egress-all"
  })
}

# =============================================================================
# Application Service Security Group
# Purpose: Controls traffic to ECS Fargate tasks running the API application
# Permitted inbound sources: ALB SG on app_port only
# Permitted outbound targets: Database SG, Cache SG, VPC endpoints, NAT (internet)
# =============================================================================

resource "aws_security_group" "app" {
  name        = "${var.project}-app-sg"
  description = "Application service security group: permits inbound on port ${var.app_port} from ALB SG only, outbound to DB, Cache, Endpoints, and NAT"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, {
    Name           = "${var.project}-app-sg"
    SecurityTier   = "private-application"
    TrafficSources = "alb-sg-port-${var.app_port}"
  })
}

resource "aws_vpc_security_group_ingress_rule" "app_from_alb" {
  security_group_id            = aws_security_group.app.id
  description                  = "Allow inbound traffic from ALB on application port"
  ip_protocol                  = "tcp"
  from_port                    = var.app_port
  to_port                      = var.app_port
  referenced_security_group_id = aws_security_group.alb.id

  tags = merge(local.common_tags, {
    Name = "${var.project}-app-ingress-from-alb"
  })
}

# Outbound: App → Database (PostgreSQL 5432)
resource "aws_vpc_security_group_egress_rule" "app_to_db" {
  security_group_id            = aws_security_group.app.id
  description                  = "Allow outbound to Database cluster on PostgreSQL port"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.db.id

  tags = merge(local.common_tags, {
    Name = "${var.project}-app-egress-to-db"
  })
}

# Outbound: App → Cache (Redis 6379)
resource "aws_vpc_security_group_egress_rule" "app_to_cache" {
  security_group_id            = aws_security_group.app.id
  description                  = "Allow outbound to Cache cluster on Redis port"
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
  referenced_security_group_id = aws_security_group.cache.id

  tags = merge(local.common_tags, {
    Name = "${var.project}-app-egress-to-cache"
  })
}

# Outbound: App → VPC Endpoints (HTTPS 443)
resource "aws_vpc_security_group_egress_rule" "app_to_endpoints" {
  security_group_id            = aws_security_group.app.id
  description                  = "Allow outbound to VPC endpoints on HTTPS port"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = aws_security_group.endpoints.id

  tags = merge(local.common_tags, {
    Name = "${var.project}-app-egress-to-endpoints"
  })
}

# Outbound: App → NAT Gateway (internet via VPC CIDR for NAT routing)
# NAT Gateways reside in public subnets; traffic routes via VPC CIDR to reach them
resource "aws_vpc_security_group_egress_rule" "app_to_nat" {
  security_group_id = aws_security_group.app.id
  description       = "Allow outbound HTTPS to internet via NAT Gateway"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"

  tags = merge(local.common_tags, {
    Name = "${var.project}-app-egress-to-nat"
  })
}

# =============================================================================
# Database Cluster Security Group
# Purpose: Controls traffic to Aurora PostgreSQL cluster
# Permitted inbound sources: Application SG on PostgreSQL port only
# =============================================================================

resource "aws_security_group" "db" {
  name        = "${var.project}-db-sg"
  description = "Database cluster security group: permits inbound PostgreSQL (5432) from Application SG only"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, {
    Name           = "${var.project}-db-sg"
    SecurityTier   = "private-data"
    TrafficSources = "app-sg-port-5432"
  })
}

resource "aws_vpc_security_group_ingress_rule" "db_from_app" {
  security_group_id            = aws_security_group.db.id
  description                  = "Allow inbound PostgreSQL from Application service"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.app.id

  tags = merge(local.common_tags, {
    Name = "${var.project}-db-ingress-from-app"
  })
}

# =============================================================================
# Cache Cluster Security Group
# Purpose: Controls traffic to ElastiCache Redis cluster
# Permitted inbound sources: Application SG on Redis port only
# =============================================================================

resource "aws_security_group" "cache" {
  name        = "${var.project}-cache-sg"
  description = "Cache cluster security group: permits inbound Redis (6379) from Application SG only"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, {
    Name           = "${var.project}-cache-sg"
    SecurityTier   = "private-data"
    TrafficSources = "app-sg-port-6379"
  })
}

resource "aws_vpc_security_group_ingress_rule" "cache_from_app" {
  security_group_id            = aws_security_group.cache.id
  description                  = "Allow inbound Redis from Application service"
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
  referenced_security_group_id = aws_security_group.app.id

  tags = merge(local.common_tags, {
    Name = "${var.project}-cache-ingress-from-app"
  })
}

# =============================================================================
# VPC Endpoints Security Group
# Purpose: Controls traffic to Interface VPC endpoints (CloudWatch, Secrets
#          Manager, ECR)
# Permitted inbound sources: Application SG on HTTPS (443) only
# =============================================================================

resource "aws_security_group" "endpoints" {
  name        = "${var.project}-endpoints-sg"
  description = "VPC endpoints security group: permits inbound HTTPS (443) from Application SG only"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, {
    Name           = "${var.project}-endpoints-sg"
    SecurityTier   = "private-services"
    TrafficSources = "app-sg-port-443"
  })
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_from_app" {
  security_group_id            = aws_security_group.endpoints.id
  description                  = "Allow inbound HTTPS from Application service to VPC endpoints"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = aws_security_group.app.id

  tags = merge(local.common_tags, {
    Name = "${var.project}-endpoints-ingress-from-app"
  })
}
