variable "email_recipients" {
  description = "Addresses the RSVP emails go to."
  type        = list(string)
}

data "aws_route53_zone" "main" {
  name = "tessandcolton.com"
}

resource "aws_sesv2_email_identity" "domain" {
  email_identity = "tessandcolton.com"
}

resource "aws_route53_record" "ses_dkim" {
  count = 3

  zone_id = data.aws_route53_zone.main.zone_id
  name    = "${aws_sesv2_email_identity.domain.dkim_signing_attributes[0].tokens[count.index]}._domainkey"
  type    = "CNAME"
  ttl     = 1800
  records = ["${aws_sesv2_email_identity.domain.dkim_signing_attributes[0].tokens[count.index]}.dkim.amazonses.com"]
}

resource "aws_route53_record" "dmarc" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "_dmarc"
  type    = "TXT"
  ttl     = 1800
  records = ["v=DMARC1; p=none"]
}

resource "aws_sesv2_email_identity" "recipient" {
  for_each = toset(var.email_recipients)

  email_identity = each.key
}
