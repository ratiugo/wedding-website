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

variable "recipient_emails" {
  description = "Who gets the RSVP emails. Set in terraform.tfvars, which is gitignored."
  type        = list(string)
}

variable "reply_to" {
  description = "Where guest email replies go. Set in terraform.tfvars, which is gitignored."
  type        = string
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

  sender_name      = "Wedding RSVPs (dev)"
  sender_email     = "rsvp-dev@tessandcolton.com"
  recipient_emails = var.recipient_emails

  guest_sender_name  = "Colton & Tess"
  guest_sender_email = "hello@tessandcolton.com"
  reply_to           = var.reply_to
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
