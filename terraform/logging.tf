# logging.tf - S3 Request Logging Infrastructure
# Logs request metadata (model, tokens, latency, team_id) to S3 for analytics

# -----------------------------------------------------------------------------
# S3 BUCKET FOR REQUEST LOGS
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "request_logs" {
  count  = var.enable_request_logging ? 1 : 0
  bucket = "${var.project_name}-request-logs-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-request-logs"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "request_logs" {
  count  = var.enable_request_logging ? 1 : 0
  bucket = aws_s3_bucket.request_logs[0].id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    filter {
      prefix = "logs/"
    }

    expiration {
      days = var.request_log_retention_days
    }

    # Transition to cheaper storage after 30 days
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    # Transition to Glacier after 90 days (if retention > 90)
    dynamic "transition" {
      for_each = var.request_log_retention_days > 90 ? [1] : []
      content {
        days          = 90
        storage_class = "GLACIER"
      }
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "request_logs" {
  count  = var.enable_request_logging ? 1 : 0
  bucket = aws_s3_bucket.request_logs[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "request_logs" {
  count  = var.enable_request_logging ? 1 : 0
  bucket = aws_s3_bucket.request_logs[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "request_logs" {
  count  = var.enable_request_logging ? 1 : 0
  bucket = aws_s3_bucket.request_logs[0].id

  versioning_configuration {
    status = "Suspended"
  }
}

# -----------------------------------------------------------------------------
# IAM POLICY FOR S3 ACCESS
# -----------------------------------------------------------------------------

resource "aws_iam_role_policy" "lambda_s3_logging" {
  count = var.enable_request_logging ? 1 : 0
  name  = "${var.project_name}-lambda-s3-logging"
  role  = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.request_logs[0].arn}/*"
      }
    ]
  })
}
