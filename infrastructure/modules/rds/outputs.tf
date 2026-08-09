###############################################################################
# RDS Aurora PostgreSQL Module - Outputs
###############################################################################

output "cluster_endpoint" {
  description = "Writer endpoint for the Aurora PostgreSQL cluster (read-write connections)"
  value       = aws_rds_cluster.aurora.endpoint
}

output "reader_endpoint" {
  description = "Reader endpoint for the Aurora PostgreSQL cluster (read-only connections, load-balanced across readers)"
  value       = aws_rds_cluster.aurora.reader_endpoint
}

output "cluster_arn" {
  description = "ARN of the Aurora PostgreSQL cluster"
  value       = aws_rds_cluster.aurora.arn
}

output "cluster_id" {
  description = "Identifier of the Aurora PostgreSQL cluster"
  value       = aws_rds_cluster.aurora.id
}

output "cluster_identifier" {
  description = "Cluster identifier string"
  value       = aws_rds_cluster.aurora.cluster_identifier
}

output "database_name" {
  description = "Name of the default database"
  value       = aws_rds_cluster.aurora.database_name
}

output "port" {
  description = "Port number the cluster is listening on"
  value       = aws_rds_cluster.aurora.port
}

output "writer_instance_id" {
  description = "Identifier of the writer instance"
  value       = aws_rds_cluster_instance.writer.id
}

output "reader_instance_ids" {
  description = "List of reader instance identifiers"
  value       = aws_rds_cluster_instance.reader[*].id
}

output "cluster_resource_id" {
  description = "The cluster resource ID (used for IAM database authentication)"
  value       = aws_rds_cluster.aurora.cluster_resource_id
}

output "kms_grant_id" {
  description = "ID of the KMS grant for Aurora encryption"
  value       = aws_kms_grant.aurora_encryption.grant_id
}

output "kms_grant_token" {
  description = "Grant token for the Aurora KMS encryption grant"
  value       = aws_kms_grant.aurora_encryption.grant_token
}

output "enhanced_monitoring_role_arn" {
  description = "ARN of the IAM role used for RDS Enhanced Monitoring"
  value       = aws_iam_role.rds_enhanced_monitoring.arn
}

output "db_subnet_group_name" {
  description = "Name of the DB subnet group"
  value       = aws_db_subnet_group.aurora.name
}
