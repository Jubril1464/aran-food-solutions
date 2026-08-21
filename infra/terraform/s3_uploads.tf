resource "aws_s3_bucket" "uploads" {
  bucket = "${var.project_name}-${var.environment}-uploads-${data.aws_caller_identity.current.account_id}"

  tags = { Name = "${var.project_name}-${var.environment}-uploads" }
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Product images are not sensitive and are served directly to shoppers, so
# this bucket allows public s3:GetObject. A fresh AWS account's *default*
# per-bucket public-access-block settings would silently reject the policy
# below unless overridden here — explicitly, and only for this one bucket
# (not an account-wide relaxation).
resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket                  = aws_s3_bucket.uploads.id
  block_public_acls       = true # ACLs stay blocked; only the bucket policy below grants access
  block_public_policy     = false
  ignore_public_acls      = true
  restrict_public_buckets = false
}

data "aws_iam_policy_document" "uploads_public_read" {
  statement {
    sid       = "PublicReadOnly"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
  }
}

resource "aws_s3_bucket_policy" "uploads" {
  bucket     = aws_s3_bucket.uploads.id
  policy     = data.aws_iam_policy_document.uploads_public_read.json
  depends_on = [aws_s3_bucket_public_access_block.uploads]
}

resource "aws_s3_bucket_cors_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  cors_rule {
    allowed_methods = ["GET"]
    allowed_origins = ["*"] # image bytes only, not credentialed — safe to allow any origin
    allowed_headers = ["*"]
    max_age_seconds = 3600
  }
}
