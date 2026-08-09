output "distribution_domain" {
  description = "The domain name of the CloudFront distribution"
  value       = aws_cloudfront_distribution.main.domain_name
}

output "distribution_id" {
  description = "The identifier for the CloudFront distribution"
  value       = aws_cloudfront_distribution.main.id
}

output "distribution_arn" {
  description = "The ARN of the CloudFront distribution"
  value       = aws_cloudfront_distribution.main.arn
}

output "static_bucket_arn" {
  description = "The ARN of the S3 static assets bucket"
  value       = aws_s3_bucket.static_assets.arn
}

output "static_bucket_name" {
  description = "The name of the S3 static assets bucket"
  value       = aws_s3_bucket.static_assets.id
}

output "static_bucket_regional_domain" {
  description = "The regional domain name of the S3 static assets bucket"
  value       = aws_s3_bucket.static_assets.bucket_regional_domain_name
}

output "oac_id" {
  description = "The ID of the CloudFront Origin Access Control"
  value       = aws_cloudfront_origin_access_control.static_assets.id
}
