###############################################################################
# KMS Encryption Governance Module - Outputs
###############################################################################

output "key_arn" {
  description = "ARN of the KMS customer-managed key"
  value       = aws_kms_key.platform.arn
}

output "key_id" {
  description = "ID of the KMS customer-managed key"
  value       = aws_kms_key.platform.key_id
}

output "alias_arn" {
  description = "ARN of the KMS key alias (alias/secure-multi-tier-platform)"
  value       = aws_kms_alias.platform.arn
}

output "alias_name" {
  description = "Name of the KMS key alias"
  value       = aws_kms_alias.platform.name
}

output "key_policy_json" {
  description = "JSON representation of the key policy (useful for validation and testing)"
  value       = data.aws_iam_policy_document.key_policy.json
}
