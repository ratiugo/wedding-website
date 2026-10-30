terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.71"
    }
  }

  backend "s3" {
    bucket       = "tessandcolton-terraform-state"
    key          = "dev/terraform.tfstate"
    region       = "us-west-2"
    use_lockfile = true
  }
}

provider "aws" {
  region = "us-west-2"

  default_tags {
    tags = {
      Project     = "wedding"
      Environment = "dev"
    }
  }
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = "wedding"
      Environment = "dev"
    }
  }
}

module "wedding_website" {
  source = "../modules/wedding_website"

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  environment = "dev"
  domains     = ["dev.tessandcolton.com"]

  # The full site, with the save-the-date at /save-the-date.
  home_page = "index.html"
  rsvp_open = true
}

output "deploy_role_arn" {
  value = module.wedding_website.deploy_role_arn
}

output "site_bucket" {
  value = module.wedding_website.site_bucket
}

output "distribution_id" {
  value = module.wedding_website.distribution_id
}

output "rsvp_function" {
  value = module.wedding_website.rsvp_function
}
