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

data "aws_ecr_repository" "notifier" {
  name = "wedding/notifier"
}


resource "aws_lambda_function" "notifier" {
  function_name = "wedding-${var.environment}-notifier"
  role          = aws_iam_role.notifier.arn
  package_type  = "Image"
  architectures = ["arm64"]
  memory_size   = 512
  timeout       = 30

  image_uri = "${data.aws_ecr_repository.notifier.repository_url}:bootstrap"

  environment {
    variables = {
      RSVP_BUCKET            = aws_s3_bucket.rsvps.id
      GOOGLE_SHEET_PARAMETER = aws_ssm_parameter.google_sheet.name
      SENDER_NAME            = var.sender_name
      SENDER_EMAIL           = var.sender_email
      RECIPIENT_EMAILS       = join(",", var.recipient_emails)
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.notifier.name
  }

  lifecycle {
    ignore_changes = [image_uri]
  }
}

resource "aws_cloudwatch_log_group" "notifier" {
  name              = "/aws/lambda/wedding-${var.environment}-notifier"
  retention_in_days = 30
}

resource "aws_lambda_permission" "rsvps_bucket" {
  statement_id  = "AllowRsvpsBucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.notifier.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.rsvps.arn
}
