variable "environment" {
  description = "dev or prod. Used in resource names, and must match the GitHub environment the deploy job runs in."
  type        = string
}

variable "domains" {
  description = "The names the site is served on. The first is the certificate's main name."
  type        = list(string)
}

variable "home_page" {
  description = "The page in frontend/ that the site's root (/) shows, e.g. save-the-date.html."
  type        = string
}

variable "rsvp_open" {
  description = "Whether the RSVP API looks up and saves invitations. Off until invitations go out."
  type        = bool
}

variable "sender_name" {
  description = "The name RSVP emails show as coming from, e.g. \"Wedding RSVPs\"."
  type        = string
}

variable "sender_email" {
  description = "The address RSVP emails come from. Any address @tessandcolton.com works."
  type        = string
}

variable "recipient_emails" {
  description = "Who gets the RSVP emails. Each must be verified in SES (shared/ses.tf)."
  type        = list(string)
}

variable "alarm_email" {
  description = "Where to email when a Lambda fails. No alarms if null."
  type        = string
  default     = null
}
