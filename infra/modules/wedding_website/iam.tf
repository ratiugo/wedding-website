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

# Lets the deploy workflow push RSVP images and point this environment's Lambda at one.
resource "aws_iam_role_policy" "deploy_rsvp" {
  name = "deploy-rsvp"
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
        Resource = data.aws_ecr_repository.rsvp.arn
      },
      {
        Effect   = "Allow"
        Action   = ["lambda:UpdateFunctionCode", "lambda:GetFunction"]
        Resource = aws_lambda_function.rsvp.arn
      },
    ]
  })
}

# The RSVP Lambda's own role.
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
