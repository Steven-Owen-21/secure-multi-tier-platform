###############################################################################
# ElastiCache Redis Module - Outputs
###############################################################################

output "primary_endpoint" {
  description = "Primary endpoint address for write operations"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "reader_endpoint" {
  description = "Reader endpoint address for read operations (distributes across replicas)"
  value       = aws_elasticache_replication_group.redis.reader_endpoint_address
}

output "replication_group_id" {
  description = "ID of the Redis replication group"
  value       = aws_elasticache_replication_group.redis.id
}

output "replication_group_arn" {
  description = "ARN of the Redis replication group"
  value       = aws_elasticache_replication_group.redis.arn
}

output "port" {
  description = "Port number the Redis cluster is listening on"
  value       = var.port
}

output "parameter_group_name" {
  description = "Name of the custom Redis parameter group"
  value       = aws_elasticache_parameter_group.redis.name
}

output "subnet_group_name" {
  description = "Name of the ElastiCache subnet group"
  value       = aws_elasticache_subnet_group.redis.name
}

output "kms_grant_id" {
  description = "ID of the KMS grant for ElastiCache encryption"
  value       = aws_kms_grant.elasticache.grant_id
}
