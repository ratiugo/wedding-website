variable "environment" {
  description = "dev or prod. Used in resource names, and must match the GitHub environment the deploy job runs in."
  type        = string
}

variable "domains" {
  description = "The names the site is served on. The first is the certificate's main name."
  type        = list(string)
}
