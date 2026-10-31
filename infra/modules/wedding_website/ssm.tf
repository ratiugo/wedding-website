# The Google Sheet the notifier updates, and the service account key it signs in with:
# {"sheet_id": "...", "service_account_key": {...}}. Terraform only creates it; the
# real value is put in by hand, so the key never appears in Terraform state or git:
#
#   aws ssm put-parameter --name wedding-<env>-google-sheet --overwrite --value "..."
resource "aws_ssm_parameter" "google_sheet" {
  name  = "wedding-${var.environment}-google-sheet"
  type  = "SecureString"
  value = "set by hand"

  lifecycle {
    ignore_changes = [value]
  }
}
