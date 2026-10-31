resource "aws_ssm_parameter" "google_sheet" {
  name  = "wedding-${var.environment}-google-sheet"
  type  = "SecureString"
  value = "set by hand"

  lifecycle {
    ignore_changes = [value]
  }
}
