resource "aws_dynamodb_table" "invitations" {
  name         = "wedding-${var.environment}-invitations"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "invite_code"

  attribute {
    name = "invite_code"
    type = "S"
  }

  # Can restore the table to any second in the last 35 days.
  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true
}
