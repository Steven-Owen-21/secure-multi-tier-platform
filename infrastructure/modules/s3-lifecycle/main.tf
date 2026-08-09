###############################################################################
# S3 Lifecycle Management Module
#
# Creates and manages S3 buckets with lifecycle rules:
# - WAF Logs bucket: Standard → IA (30d) → Glacier (90d) → Expire (365d)
# - VPC Flow Logs bucket: Expire after configured retention
# - Application Data bucket: Intelligent Tiering with archive access tier
# - Audit Logs bucket: Standard → IA → Glacier → Expire, Object Lock governance
###############################################################################

locals {
  bucket_prefix = "${var.project}-${var.environment}"
}

# -----------------------------------------------------------------------------
# WAF Logs Bucket
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "waf_logs" {
  bucket = "${local.bucket_prefix}-waf-logs"

  tags = merge(var.tags, {
    Component = "waf-logs"
  })
}

resource "aws_s3_bucket_versioning" "waf_logs" {
  bucket = aws_s3_bucket.waf_logs.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "waf_logs" {
  bucket = aws_s3_bucket.waf_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "waf_logs" {
  bucket = aws_s3_bucket.waf_logs.id

  rule {
    id     = "waf-logs-lifecycle"
    status = "Enabled"

    filter {}

    transition {
      days          = var.waf_log_ia_transition_days
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = var.waf_log_glacier_transition_days
      storage_class = "GLACIER"
    }

    expiration {
      days = var.waf_log_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }
  }
}

resource "aws_s3_bucket_public_access_block" "waf_logs" {
  bucket = aws_s3_bucket.waf_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# VPC Flow Logs Bucket
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "flow_logs" {
  bucket = "${local.bucket_prefix}-flow-logs"

  tags = merge(var.tags, {
    Component = "flow-logs"
  })
}

resource "aws_s3_bucket_server_side_encryption_configuration" "flow_logs" {
  bucket = aws_s3_bucket.flow_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "flow_logs" {
  bucket = aws_s3_bucket.flow_logs.id

  rule {
    id     = "flow-logs-lifecycle"
    status = "Enabled"

    filter {}

    expiration {
      days = var.flow_log_retention_days
    }
  }
}

resource "aws_s3_bucket_public_access_block" "flow_logs" {
  bucket = aws_s3_bucket.flow_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# Application Data Bucket
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "application_data" {
  bucket = "${local.bucket_prefix}-application-data"

  tags = merge(var.tags, {
    Component = "application-data"
  })
}

resource "aws_s3_bucket_versioning" "application_data" {
  bucket = aws_s3_bucket.application_data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "application_data" {
  bucket = aws_s3_bucket.application_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_intelligent_tiering_configuration" "application_data" {
  bucket = aws_s3_bucket.application_data.id
  name   = "archive-tier"

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = var.intelligent_tiering_archive_days
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "application_data" {
  bucket = aws_s3_bucket.application_data.id

  rule {
    id     = "noncurrent-version-expiration"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }
  }
}

resource "aws_s3_bucket_public_access_block" "application_data" {
  bucket = aws_s3_bucket.application_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# Audit Logs Bucket (with Object Lock governance mode)
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "audit_logs" {
  bucket              = "${local.bucket_prefix}-audit-logs"
  object_lock_enabled = true

  tags = merge(var.tags, {
    Component = "audit-logs"
  })
}

resource "aws_s3_bucket_versioning" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_object_lock_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  rule {
    default_retention {
      mode = "GOVERNANCE"
      days = var.object_lock_retention_days
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  rule {
    id     = "audit-logs-lifecycle"
    status = "Enabled"

    filter {}

    transition {
      days          = var.audit_log_ia_transition_days
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = var.audit_log_glacier_transition_days
      storage_class = "GLACIER"
    }

    expiration {
      days = var.audit_log_retention_days
    }
  }
}

resource "aws_s3_bucket_public_access_block" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
