output "deploy_role_arn" {
  value = aws_iam_role.deploy.arn
}

output "site_bucket" {
  value = aws_s3_bucket.site.id
}

output "distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

output "rsvp_function" {
  value = aws_lambda_function.rsvp.function_name
}
