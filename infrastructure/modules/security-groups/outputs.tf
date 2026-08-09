###############################################################################
# Security Groups Module - Outputs
###############################################################################

output "alb_sg_id" {
  description = "ID of the ALB security group (inbound HTTPS from internet)"
  value       = aws_security_group.alb.id
}

output "app_sg_id" {
  description = "ID of the Application Service security group (inbound from ALB on app port)"
  value       = aws_security_group.app.id
}

output "db_sg_id" {
  description = "ID of the Database Cluster security group (inbound PostgreSQL from App SG)"
  value       = aws_security_group.db.id
}

output "cache_sg_id" {
  description = "ID of the Cache Cluster security group (inbound Redis from App SG)"
  value       = aws_security_group.cache.id
}

output "endpoint_sg_id" {
  description = "ID of the VPC Endpoints security group (inbound HTTPS from App SG)"
  value       = aws_security_group.endpoints.id
}
