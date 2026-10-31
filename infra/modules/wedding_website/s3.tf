resource "aws_s3_bucket" "site" {
  bucket = "tessandcolton-${var.environment}-site"
}

# Only this environment's CloudFront distribution can read the site's files.
resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "s3:GetObject"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Resource  = "${aws_s3_bucket.site.arn}/*"
      Condition = {
        StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.site.arn }
      }
    }]
  })
}

# The RSVP Lambda writes an event here for every response (rsvps/<invite code>/...).
resource "aws_s3_bucket" "rsvps" {
  bucket = "tessandcolton-${var.environment}-rsvps"
}

# Each new RSVP event runs the notifier. S3 retries twice if it fails.
resource "aws_s3_bucket_notification" "rsvps" {
  bucket = aws_s3_bucket.rsvps.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.notifier.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "rsvps/"
    filter_suffix       = ".json"
  }

  depends_on = [aws_lambda_permission.rsvps_bucket]
}
