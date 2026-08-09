###############################################################################
# AWS Backup Module - Outputs
###############################################################################

output "vault_arn" {
  description = "ARN of the primary backup vault"
  value       = aws_backup_vault.primary.arn
}

output "vault_name" {
  description = "Name of the primary backup vault"
  value       = aws_backup_vault.primary.name
}

output "secondary_vault_arn" {
  description = "ARN of the secondary (DR) backup vault"
  value       = aws_backup_vault.secondary.arn
}

output "secondary_vault_name" {
  description = "Name of the secondary (DR) backup vault"
  value       = aws_backup_vault.secondary.name
}

output "plan_arn" {
  description = "ARN of the backup plan"
  value       = aws_backup_plan.platform.arn
}

output "plan_id" {
  description = "ID of the backup plan"
  value       = aws_backup_plan.platform.id
}

output "selection_id" {
  description = "ID of the backup resource selection"
  value       = aws_backup_selection.tagged_resources.id
}

output "backup_role_arn" {
  description = "ARN of the IAM role used by AWS Backup"
  value       = aws_iam_role.backup.arn
}

output "backup_role_name" {
  description = "Name of the IAM role used by AWS Backup"
  value       = aws_iam_role.backup.name
}
