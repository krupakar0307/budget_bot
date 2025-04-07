provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "bucket" {
  bucket   = "${var.bucket_name}-${var.environment}"
  tags_all = var.tags_all
}

resource "aws_s3_bucket_public_access_block" "bucket" {
  bucket = aws_s3_bucket.bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
