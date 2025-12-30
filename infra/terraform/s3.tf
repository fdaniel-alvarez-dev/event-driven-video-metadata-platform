resource "aws_s3_bucket" "uploads" {
  bucket        = "${local.name}-uploads"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket                  = aws_s3_bucket.uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_notification" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  eventbridge = true
}

output "uploads_bucket" {
  value = aws_s3_bucket.uploads.bucket
}

