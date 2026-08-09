###############################################################################
# CloudFront Distribution Module
#
# Creates a CloudFront distribution with:
# - API Gateway as primary origin (HTTPS-only)
# - S3 bucket for static assets with Origin Access Control
# - Cache behaviours for /api/* (60s TTL) and /static/* (86400s TTL)
# - Custom error pages (403, 404, 503) from S3 static bucket
# - Geographic restrictions (default: GB + EU)
# - Default root object for static documentation
###############################################################################

locals {
  api_gateway_domain = replace(replace(var.api_gateway_endpoint, "https://", ""), "/", "")
  s3_origin_id       = "S3-${var.s3_static_bucket}"
  api_origin_id      = "APIGateway-${var.project_name}"
}

###############################################################################
# S3 Static Assets Bucket
###############################################################################

resource "aws_s3_bucket" "static_assets" {
  bucket = var.s3_static_bucket

  tags = merge(var.tags, {
    Name      = var.s3_static_bucket
    Component = "cloudfront-static"
  })
}

resource "aws_s3_bucket_versioning" "static_assets" {
  bucket = aws_s3_bucket.static_assets.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "static_assets" {
  bucket = aws_s3_bucket.static_assets.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "static_assets" {
  bucket = aws_s3_bucket.static_assets.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

###############################################################################
# Origin Access Control (OAC) for S3
###############################################################################

resource "aws_cloudfront_origin_access_control" "static_assets" {
  name                              = "${var.project_name}-static-oac"
  description                       = "OAC for S3 static assets bucket - read-only access for CloudFront"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

###############################################################################
# S3 Bucket Policy - Allow CloudFront OAC read-only access
###############################################################################

resource "aws_s3_bucket_policy" "static_assets" {
  bucket = aws_s3_bucket.static_assets.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontServicePrincipalReadOnly"
        Effect    = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.static_assets.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.main.arn
          }
        }
      }
    ]
  })
}

###############################################################################
# Cache Policies
###############################################################################

resource "aws_cloudfront_cache_policy" "api" {
  name        = "${var.project_name}-api-cache-policy"
  comment     = "Cache policy for API responses with short TTL"
  default_ttl = var.api_cache_ttl
  min_ttl     = 0
  max_ttl     = var.api_cache_ttl * 2

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }

    headers_config {
      header_behavior = "whitelist"
      headers {
        items = ["Authorization", "Accept"]
      }
    }

    query_strings_config {
      query_string_behavior = "all"
    }
  }
}

resource "aws_cloudfront_cache_policy" "static" {
  name        = "${var.project_name}-static-cache-policy"
  comment     = "Cache policy for static assets with long TTL"
  default_ttl = var.static_cache_ttl
  min_ttl     = 0
  max_ttl     = var.static_cache_ttl * 2

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }

    headers_config {
      header_behavior = "none"
    }

    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

###############################################################################
# CloudFront Distribution
###############################################################################

resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.project_name} CDN distribution (${var.environment})"
  default_root_object = var.default_root_object
  price_class         = var.price_class

  # Primary origin: API Gateway (HTTPS-only)
  origin {
    domain_name = local.api_gateway_domain
    origin_id   = local.api_origin_id

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # S3 origin for static assets with OAC
  origin {
    domain_name              = aws_s3_bucket.static_assets.bucket_regional_domain_name
    origin_id                = local.s3_origin_id
    origin_access_control_id = aws_cloudfront_origin_access_control.static_assets.id
  }

  # Default cache behaviour - routes to S3 static bucket (documentation)
  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = local.s3_origin_id
    cache_policy_id        = aws_cloudfront_cache_policy.static.id
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
  }

  # /api/* cache behaviour - routes to API Gateway
  ordered_cache_behavior {
    path_pattern           = "/api/*"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = local.api_origin_id
    cache_policy_id        = aws_cloudfront_cache_policy.api.id
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
  }

  # /static/* cache behaviour - routes to S3 static assets
  ordered_cache_behavior {
    path_pattern           = "/static/*"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = local.s3_origin_id
    cache_policy_id        = aws_cloudfront_cache_policy.static.id
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
  }

  # Custom error pages served from S3 static bucket
  custom_error_response {
    error_code            = 403
    response_code         = 403
    response_page_path    = "/errors/403.html"
    error_caching_min_ttl = 60
  }

  custom_error_response {
    error_code            = 404
    response_code         = 404
    response_page_path    = "/errors/404.html"
    error_caching_min_ttl = 60
  }

  custom_error_response {
    error_code            = 503
    response_code         = 503
    response_page_path    = "/errors/503.html"
    error_caching_min_ttl = 10
  }

  # Geographic restrictions
  restrictions {
    geo_restriction {
      restriction_type = "whitelist"
      locations        = var.geo_restrictions
    }
  }

  # Default CloudFront certificate (no custom domain for demo)
  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = merge(var.tags, {
    Name      = "${var.project_name}-distribution"
    Component = "cloudfront"
  })
}
