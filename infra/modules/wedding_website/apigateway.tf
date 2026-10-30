resource "aws_apigatewayv2_api" "rsvp" {
  name          = "wedding-${var.environment}-rsvp"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "rsvp" {
  api_id                 = aws_apigatewayv2_api.rsvp.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.rsvp.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "rsvp" {
  for_each = toset(["GET /rsvp/{invite_code}", "PUT /rsvp/{invite_code}"])

  api_id    = aws_apigatewayv2_api.rsvp.id
  route_key = each.value
  target    = "integrations/${aws_apigatewayv2_integration.rsvp.id}"
}

# Named "api" so its URLs start with /api, matching the site's /api/* path in
# CloudFront. API Gateway removes the stage name before matching routes.
resource "aws_apigatewayv2_stage" "api" {
  api_id      = aws_apigatewayv2_api.rsvp.id
  name        = "api"
  auto_deploy = true
  default_route_settings {
    throttling_rate_limit  = 10
    throttling_burst_limit = 20
  }
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rsvp.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.rsvp.execution_arn}/*/*"
}
