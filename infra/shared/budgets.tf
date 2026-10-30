variable "alert_email" {
  description = "Where budget alerts are sent. Set in terraform.tfvars, which is gitignored."
  type        = string
}

# Emails when this month's spending is forecast to pass the limit, and again when it
# actually passes 80% of it. Expected spending is a couple of dollars a month.
resource "aws_budgets_budget" "monthly" {
  name         = "wedding-monthly"
  budget_type  = "COST"
  limit_amount = "5"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
}
