# CloudFront only accepts certificates from us-east-1
terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws.us_east_1]
    }
  }
}

# The account and region the default provider points at.
data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
