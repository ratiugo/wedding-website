# Things that exist once in the AWS account and are used by both environments.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.71"
    }
  }

  # The bucket in s3.tf. Its first apply kept state locally, because the bucket didn't
  # exist yet, then `terraform init -migrate-state` moved the state here.
  backend "s3" {
    bucket       = "tessandcolton-terraform-state"
    key          = "shared/terraform.tfstate"
    region       = "us-west-2"
    use_lockfile = true
  }
}

provider "aws" {
  region = "us-west-2"

  default_tags {
    tags = {
      Project = "wedding"
    }
  }
}
