data "aws_ecr_repository" "rsvp" {
  name = "wedding/rsvp"
}

resource "aws_lambda_function" "rsvp" {
  function_name = "wedding-${var.environment}-rsvp"
  role          = aws_iam_role.rsvp.arn
  package_type  = "Image"
  architectures = ["arm64"]
  memory_size   = 512
  timeout = 30

  # Only used when the function is first created. After that, the deploy workflow sets
  # the image.
  image_uri = "${data.aws_ecr_repository.rsvp.repository_url}:bootstrap"

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.rsvp.id]
  }

  environment {
    variables = {
      DATABASE_URL      = "postgresql://rsvp_app@${aws_rds_cluster.main.endpoint}:5432/wedding?sslmode=require"
      DATABASE_IAM_AUTH = "true"
      RSVP_BUCKET       = aws_s3_bucket.rsvps.id
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.rsvp.name
  }

  lifecycle {
    ignore_changes = [image_uri]
  }
}

resource "aws_cloudwatch_log_group" "rsvp" {
  name              = "/aws/lambda/wedding-${var.environment}-rsvp"
  retention_in_days = 30
}
