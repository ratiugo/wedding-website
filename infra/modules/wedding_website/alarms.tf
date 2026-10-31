# Emails alarm_email when something fails out of sight. Only created when alarm_email
# is set (prod), since errors in dev are expected while experimenting.

resource "aws_sns_topic" "alarms" {
  count = var.alarm_email == null ? 0 : 1

  name = "wedding-${var.environment}-alarms"
}

# Sends a confirmation email first; alarms arrive once it's confirmed.
resource "aws_sns_topic_subscription" "alarms" {
  count = var.alarm_email == null ? 0 : 1

  topic_arn = aws_sns_topic.alarms[0].arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# A Lambda crashed: a guest saw "Something went wrong" (rsvp), or an RSVP didn't
# reach the sheet or our inboxes (notifier).
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = var.alarm_email == null ? {} : {
    rsvp     = aws_lambda_function.rsvp.function_name
    notifier = aws_lambda_function.notifier.function_name
  }

  alarm_name          = "${each.value}-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = each.value }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms[0].arn]
  ok_actions          = [aws_sns_topic.alarms[0].arn]
}

# An RSVP was saved, but its event didn't reach S3, so the notifier never ran. The
# RSVP Lambda logs this rather than failing, so it isn't counted as an error.
resource "aws_cloudwatch_log_metric_filter" "rsvp_publish_failed" {
  count = var.alarm_email == null ? 0 : 1

  name           = "rsvp-publish-failed"
  log_group_name = aws_cloudwatch_log_group.rsvp.name
  pattern        = "\"Failed to publish RSVP event\""

  metric_transformation {
    namespace = "Wedding"
    name      = "${var.environment}-rsvp-publish-failed"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "rsvp_publish_failed" {
  count = var.alarm_email == null ? 0 : 1

  alarm_name          = "wedding-${var.environment}-rsvp-publish-failed"
  namespace           = "Wedding"
  metric_name         = "${var.environment}-rsvp-publish-failed"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms[0].arn]
}
