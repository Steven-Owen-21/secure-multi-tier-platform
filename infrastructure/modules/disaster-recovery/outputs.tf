# -----------------------------------------------------------------------------
# Disaster Recovery Module — Outputs
# -----------------------------------------------------------------------------

# Global Cluster
output "global_cluster_id" {
  description = "ID of the RDS Global Cluster"
  value       = aws_rds_global_cluster.main.id
}

# Aurora DR Replica
output "dr_aurora_arn" {
  description = "ARN of the cross-region Aurora DR replica cluster"
  value       = aws_rds_cluster.dr_replica.arn
}

output "dr_aurora_endpoint" {
  description = "Reader endpoint of the DR Aurora replica (becomes writer after promotion)"
  value       = aws_rds_cluster.dr_replica.endpoint
}

output "dr_aurora_cluster_identifier" {
  description = "Cluster identifier of the DR Aurora replica"
  value       = aws_rds_cluster.dr_replica.cluster_identifier
}

output "dr_aurora_reader_endpoint" {
  description = "Reader endpoint of the DR Aurora replica cluster"
  value       = aws_rds_cluster.dr_replica.reader_endpoint
}

# S3 Cross-Region Replication
output "dr_s3_bucket_arns" {
  description = "ARNs of the DR replica S3 buckets in the secondary region"
  value       = aws_s3_bucket.dr_replica[*].arn
}

output "dr_s3_bucket_ids" {
  description = "IDs (names) of the DR replica S3 buckets"
  value       = aws_s3_bucket.dr_replica[*].id
}

output "s3_replication_role_arn" {
  description = "ARN of the IAM role used for S3 cross-region replication"
  value       = aws_iam_role.s3_replication.arn
}

# Route53 Health Checks
output "route53_health_check_ids" {
  description = "IDs of the Route53 health checks monitoring the primary ALB"
  value       = [aws_route53_health_check.primary_alb.id]
}

output "route53_health_check_arn" {
  description = "ARN of the Route53 health check on the primary ALB"
  value       = aws_route53_health_check.primary_alb.arn
}

# Route53 Failover Records
output "primary_failover_record_fqdn" {
  description = "FQDN of the primary failover routing record"
  value       = length(aws_route53_record.primary) > 0 ? aws_route53_record.primary[0].fqdn : ""
}

output "secondary_failover_record_fqdn" {
  description = "FQDN of the secondary failover routing record"
  value       = length(aws_route53_record.secondary) > 0 ? aws_route53_record.secondary[0].fqdn : ""
}
