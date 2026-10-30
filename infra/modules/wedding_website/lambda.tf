data "aws_ecr_repository" "rsvp" {
  name = "wedding/rsvp"
}

resource "aws_lambda_function" "rsvp" {
  function_name = "wedding-${var.environment}-rsvp"
  role          = aws_iam_role.rsvp.arn
  package_type  = "Image"
  architectures = ["arm64"]
  memory_size   = 512
  timeout       = 10

  # Only used when the function is first created. After that, the deploy workflow sets
  # the image.
  image_uri = "${data.aws_ecr_repository.rsvp.repository_url}:bootstrap"

  environment {
    variables = {
      INVITATIONS_TABLE = aws_dynamodb_table.invitations.name
      RSVP_BUCKET       = aws_s3_bucket.rsvps.id
      RSVP_OPEN         = tostring(var.rsvp_open)
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
