data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_role" "deploy" {
  name = "wedding-${var.environment}-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRoleWithWebIdentity"
      Principal = { Federated = data.aws_iam_openid_connect_provider.github.arn }
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = "repo:ratiugo@11172937/wedding-website@1435342279:environment:${var.environment}"
        }
      }
    }]
  })
}

# Lets the deploy workflow upload the site to this environment's bucket and clear its
# CloudFront cache.
resource "aws_iam_role_policy" "deploy" {
  name = "deploy-site"
  role = aws_iam_role.deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.site.arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.site.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = "cloudfront:CreateInvalidation"
        Resource = aws_cloudfront_distribution.site.arn
      },
    ]
  })
}

# Lets the deploy workflow push Lambda images and point this environment's Lambdas at
# them.
resource "aws_iam_role_policy" "deploy_lambdas" {
  name = "deploy-lambdas"
  role = aws_iam_role.deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:DescribeImages",
        ]
        Resource = [data.aws_ecr_repository.rsvp.arn, data.aws_ecr_repository.notifier.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["lambda:UpdateFunctionCode", "lambda:GetFunction"]
        Resource = [aws_lambda_function.rsvp.arn, aws_lambda_function.notifier.arn]
      },
    ]
  })
}

# The RSVP Lambda's role.
resource "aws_iam_role" "rsvp" {
  name = "wedding-${var.environment}-rsvp"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rsvp_logs" {
  role       = aws_iam_role.rsvp.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Read invitations and save responses, and write RSVP events.
resource "aws_iam_role_policy" "rsvp" {
  name = "rsvp"
  role = aws_iam_role.rsvp.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
        Resource = aws_dynamodb_table.invitations.arn
      },
      {
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.rsvps.arn}/rsvps/*"
      },
    ]
  })
}

# The notifier Lambda's role.
resource "aws_iam_role" "notifier" {
  name = "wedding-${var.environment}-notifier"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "notifier_logs" {
  role       = aws_iam_role.notifier.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Read RSVP events and the Google Sheet parameter, and send email as sender_email.
resource "aws_iam_role_policy" "notifier" {
  name = "notifier"
  role = aws_iam_role.notifier.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.rsvps.arn}/rsvps/*"
      },
      {
        Effect   = "Allow"
        Action   = "ssm:GetParameter"
        Resource = aws_ssm_parameter.google_sheet.arn
      },
      {
        # SES checks this against the sender's and (in the sandbox) each recipient's
        # identity, so it's limited by the From address instead.
        Effect    = "Allow"
        Action    = "ses:SendEmail"
        Resource  = "*"
        Condition = { StringEquals = { "ses:FromAddress" = var.sender_email } }
      },
    ]
  })
}

moved {
  from = aws_iam_role_policy.deploy_rsvp
  to   = aws_iam_role_policy.deploy_lambdas
}
