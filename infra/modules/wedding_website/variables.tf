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
