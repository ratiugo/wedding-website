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
    key          = "prod/terraform.tfstate"
    region       = "us-west-2"
    use_lockfile = true
  }
}

variable "recipient_emails" {
  description = "Who gets the RSVP emails. Set in terraform.tfvars, which is gitignored."
  type        = list(string)
}

variable "alarm_email" {
  description = "Where to email when a Lambda fails. Set in terraform.tfvars, which is gitignored."
  type        = string
}

provider "aws" {
  region = "us-west-2"

  default_tags {
    tags = {
      Project     = "wedding"
      Environment = "prod"
    }
  }
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = "wedding"
      Environment = "prod"
    }
  }
}

module "wedding_website" {
  source = "../modules/wedding_website"

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  environment = "prod"
  domains     = ["tessandcolton.com", "www.tessandcolton.com"]

  # The save-the-date until invitations go out; then index.html and rsvp_open = true.
  home_page = "save-the-date.html"
  rsvp_open = false

  sender_name      = "Wedding RSVPs"
  sender_email     = "rsvp@tessandcolton.com"
  recipient_emails = var.recipient_emails
  alarm_email      = var.alarm_email
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

output "notifier_function" {
  value = module.wedding_website.notifier_function
}
