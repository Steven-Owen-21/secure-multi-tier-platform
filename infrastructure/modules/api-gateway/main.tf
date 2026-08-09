# -----------------------------------------------------------------------------
# API Gateway Module — Main Resources
# -----------------------------------------------------------------------------
# Creates an API Gateway REST API with:
# - Regional endpoint fronting the ALB
# - Multiple deployment stages (development, staging, production)
# - Tiered usage plans: free, standard, premium
# - API keys per usage plan
# - Request payload validation with JSON Schema models
# - Custom domain with ACM certificate
# - Access logging to CloudWatch (request ID, source IP, method, path, status,
#   latency, API key ID)
# -----------------------------------------------------------------------------

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# REST API — Regional Endpoint
# -----------------------------------------------------------------------------

resource "aws_api_gateway_rest_api" "main" {
  name        = "${local.name_prefix}-api"
  description = "Secure Multi-Tier Platform REST API fronting the ALB backend"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Name      = "${local.name_prefix}-api"
    Component = "api-gateway"
  }
}

# -----------------------------------------------------------------------------
# Cognito Authorizer
# -----------------------------------------------------------------------------

resource "aws_api_gateway_authorizer" "cognito" {
  name            = "${local.name_prefix}-cognito-authorizer"
  rest_api_id     = aws_api_gateway_rest_api.main.id
  type            = "COGNITO_USER_POOLS"
  provider_arns   = [var.cognito_user_pool_arn]
  identity_source = "method.request.header.Authorization"
}

# -----------------------------------------------------------------------------
# Request Validation — JSON Schema Models
# -----------------------------------------------------------------------------

resource "aws_api_gateway_request_validator" "body" {
  name                        = "validate-request-body"
  rest_api_id                 = aws_api_gateway_rest_api.main.id
  validate_request_body       = true
  validate_request_parameters = false
}

resource "aws_api_gateway_request_validator" "full" {
  name                        = "validate-body-and-params"
  rest_api_id                 = aws_api_gateway_rest_api.main.id
  validate_request_body       = true
  validate_request_parameters = true
}

# Product creation JSON Schema model
resource "aws_api_gateway_model" "product_create" {
  rest_api_id  = aws_api_gateway_rest_api.main.id
  name         = "ProductCreate"
  description  = "JSON Schema for product creation payload"
  content_type = "application/json"

  schema = jsonencode({
    "$schema" = "http://json-schema.org/draft-04/schema#"
    title     = "ProductCreate"
    type      = "object"
    required  = ["name", "price_pence", "stock_quantity", "category"]
    properties = {
      name = {
        type      = "string"
        minLength = 1
        maxLength = 255
      }
      description = {
        type      = "string"
        maxLength = 2000
      }
      price_pence = {
        type    = "integer"
        minimum = 1
        maximum = 100000
      }
      stock_quantity = {
        type    = "integer"
        minimum = 0
      }
      category = {
        type      = "string"
        minLength = 1
        maxLength = 100
      }
    }
    additionalProperties = false
  })
}

# Order creation JSON Schema model
resource "aws_api_gateway_model" "order_create" {
  rest_api_id  = aws_api_gateway_rest_api.main.id
  name         = "OrderCreate"
  description  = "JSON Schema for order creation payload"
  content_type = "application/json"

  schema = jsonencode({
    "$schema" = "http://json-schema.org/draft-04/schema#"
    title     = "OrderCreate"
    type      = "object"
    required  = ["items"]
    properties = {
      items = {
        type     = "array"
        minItems = 1
        maxItems = 50
        items = {
          type     = "object"
          required = ["product_id", "quantity"]
          properties = {
            product_id = {
              type    = "string"
              pattern = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            }
            quantity = {
              type    = "integer"
              minimum = 1
              maximum = 100
            }
          }
          additionalProperties = false
        }
      }
    }
    additionalProperties = false
  })
}

# -----------------------------------------------------------------------------
# Resources — Proxy Integration to ALB
# -----------------------------------------------------------------------------

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy" {
  rest_api_id          = aws_api_gateway_rest_api.main.id
  resource_id          = aws_api_gateway_resource.proxy.id
  http_method          = "ANY"
  authorization        = "COGNITO_USER_POOLS"
  authorizer_id        = aws_api_gateway_authorizer.cognito.id
  api_key_required     = true
  request_validator_id = aws_api_gateway_request_validator.body.id
}

resource "aws_api_gateway_integration" "proxy" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy.http_method
  type                    = "HTTP_PROXY"
  integration_http_method = "ANY"
  uri                     = "http://${var.alb_dns_name}/{proxy}"
  connection_type         = "INTERNET"

  request_parameters = {
    "integration.request.path.proxy" = "method.request.path.proxy"
  }
}

# Root resource health endpoint (no auth required)
resource "aws_api_gateway_method" "root" {
  rest_api_id      = aws_api_gateway_rest_api.main.id
  resource_id      = aws_api_gateway_rest_api.main.root_resource_id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = false
}

resource "aws_api_gateway_integration" "root" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_rest_api.main.root_resource_id
  http_method             = aws_api_gateway_method.root.http_method
  type                    = "HTTP_PROXY"
  integration_http_method = "GET"
  uri                     = "http://${var.alb_dns_name}/"
  connection_type         = "INTERNET"
}

# -----------------------------------------------------------------------------
# Gateway Responses — Structured Error Responses
# -----------------------------------------------------------------------------

resource "aws_api_gateway_gateway_response" "unauthorized" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  response_type = "UNAUTHORIZED"
  status_code   = "401"

  response_templates = {
    "application/json" = jsonencode({
      error      = "UNAUTHORIZED"
      message    = "Authentication required. Provide a valid Bearer token."
      request_id = "$context.requestId"
    })
  }
}

resource "aws_api_gateway_gateway_response" "access_denied" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  response_type = "ACCESS_DENIED"
  status_code   = "403"

  response_templates = {
    "application/json" = jsonencode({
      error      = "ACCESS_DENIED"
      message    = "You do not have permission to access this resource."
      request_id = "$context.requestId"
    })
  }
}

resource "aws_api_gateway_gateway_response" "bad_request" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  response_type = "BAD_REQUEST_BODY"
  status_code   = "400"

  response_templates = {
    "application/json" = jsonencode({
      error      = "BAD_REQUEST"
      message    = "Request body failed validation. Check the request payload against the API schema."
      request_id = "$context.requestId"
    })
  }
}

resource "aws_api_gateway_gateway_response" "throttled" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  response_type = "THROTTLED"
  status_code   = "429"

  response_templates = {
    "application/json" = jsonencode({
      error      = "THROTTLED"
      message    = "Rate limit exceeded. Please retry after a short delay."
      request_id = "$context.requestId"
    })
  }
}

resource "aws_api_gateway_gateway_response" "internal_error" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  response_type = "DEFAULT_5XX"
  status_code   = "500"

  response_templates = {
    "application/json" = jsonencode({
      error      = "INTERNAL_SERVER_ERROR"
      message    = "An unexpected error occurred. Please try again later."
      request_id = "$context.requestId"
    })
  }
}

# -----------------------------------------------------------------------------
# Deployment
# -----------------------------------------------------------------------------

resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.proxy.id,
      aws_api_gateway_method.proxy.id,
      aws_api_gateway_integration.proxy.id,
      aws_api_gateway_method.root.id,
      aws_api_gateway_integration.root.id,
      aws_api_gateway_model.product_create.id,
      aws_api_gateway_model.order_create.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Log Group for Access Logging
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "api_access_logs" {
  for_each = toset(var.stages)

  name              = "/aws/apigateway/${local.name_prefix}-api/${each.value}"
  retention_in_days = var.access_log_retention_days

  tags = {
    Name      = "${local.name_prefix}-api-logs-${each.value}"
    Component = "api-gateway"
    Stage     = each.value
  }
}

# -----------------------------------------------------------------------------
# Stages — development, staging, production
# -----------------------------------------------------------------------------

resource "aws_api_gateway_stage" "stages" {
  for_each = toset(var.stages)

  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = each.value

  variables = {
    environment  = each.value
    alb_endpoint = var.alb_dns_name
    log_level    = each.value == "production" ? "ERROR" : "INFO"
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access_logs[each.value].arn
    format = jsonencode({
      requestId  = "$context.requestId"
      sourceIp   = "$context.identity.sourceIp"
      httpMethod = "$context.httpMethod"
      path       = "$context.path"
      status     = "$context.status"
      latency    = "$context.responseLatency"
      apiKeyId   = "$context.identity.apiKeyId"
    })
  }

  tags = {
    Name        = "${local.name_prefix}-api-${each.value}"
    Component   = "api-gateway"
    Environment = each.value
  }

  depends_on = [aws_api_gateway_account.main]
}

# -----------------------------------------------------------------------------
# Method Settings — Enable Detailed Metrics per Stage
# -----------------------------------------------------------------------------

resource "aws_api_gateway_method_settings" "all" {
  for_each = toset(var.stages)

  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.stages[each.value].stage_name
  method_path = "*/*"

  settings {
    metrics_enabled    = var.enable_detailed_metrics
    logging_level      = each.value == "production" ? "ERROR" : "INFO"
    data_trace_enabled = each.value != "production"
  }
}

# -----------------------------------------------------------------------------
# API Gateway Account — CloudWatch Role (required for logging)
# -----------------------------------------------------------------------------

resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn
}

resource "aws_iam_role" "api_gateway_cloudwatch" {
  name = "${local.name_prefix}-apigw-cloudwatch-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name      = "${local.name_prefix}-apigw-cloudwatch-role"
    Component = "api-gateway"
  }
}

resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  role       = aws_iam_role.api_gateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

# -----------------------------------------------------------------------------
# Usage Plans — Free, Standard, Premium
# -----------------------------------------------------------------------------

resource "aws_api_gateway_usage_plan" "free" {
  name        = "${local.name_prefix}-free-plan"
  description = "Free tier: ${var.free_tier_daily_limit} requests/day, ${var.free_tier_burst_limit}/s burst"

  dynamic "api_stages" {
    for_each = toset(var.stages)
    content {
      api_id = aws_api_gateway_rest_api.main.id
      stage  = aws_api_gateway_stage.stages[api_stages.value].stage_name
    }
  }

  quota_settings {
    limit  = var.free_tier_daily_limit
    period = "DAY"
  }

  throttle_settings {
    burst_limit = var.free_tier_burst_limit
    rate_limit  = var.free_tier_rate_limit
  }

  tags = {
    Name      = "${local.name_prefix}-free-plan"
    Component = "api-gateway"
    Tier      = "free"
  }
}

resource "aws_api_gateway_usage_plan" "standard" {
  name        = "${local.name_prefix}-standard-plan"
  description = "Standard tier: ${var.standard_tier_daily_limit} requests/day, ${var.standard_tier_burst_limit}/s burst"

  dynamic "api_stages" {
    for_each = toset(var.stages)
    content {
      api_id = aws_api_gateway_rest_api.main.id
      stage  = aws_api_gateway_stage.stages[api_stages.value].stage_name
    }
  }

  quota_settings {
    limit  = var.standard_tier_daily_limit
    period = "DAY"
  }

  throttle_settings {
    burst_limit = var.standard_tier_burst_limit
    rate_limit  = var.standard_tier_rate_limit
  }

  tags = {
    Name      = "${local.name_prefix}-standard-plan"
    Component = "api-gateway"
    Tier      = "standard"
  }
}

resource "aws_api_gateway_usage_plan" "premium" {
  name        = "${local.name_prefix}-premium-plan"
  description = "Premium tier: ${var.premium_tier_daily_limit} requests/day, ${var.premium_tier_burst_limit}/s burst"

  dynamic "api_stages" {
    for_each = toset(var.stages)
    content {
      api_id = aws_api_gateway_rest_api.main.id
      stage  = aws_api_gateway_stage.stages[api_stages.value].stage_name
    }
  }

  quota_settings {
    limit  = var.premium_tier_daily_limit
    period = "DAY"
  }

  throttle_settings {
    burst_limit = var.premium_tier_burst_limit
    rate_limit  = var.premium_tier_rate_limit
  }

  tags = {
    Name      = "${local.name_prefix}-premium-plan"
    Component = "api-gateway"
    Tier      = "premium"
  }
}

# -----------------------------------------------------------------------------
# API Keys — One per Usage Plan
# -----------------------------------------------------------------------------

resource "aws_api_gateway_api_key" "free" {
  name        = "${local.name_prefix}-free-key"
  description = "API key for the free usage plan"
  enabled     = true

  tags = {
    Name      = "${local.name_prefix}-free-key"
    Component = "api-gateway"
    Tier      = "free"
  }
}

resource "aws_api_gateway_api_key" "standard" {
  name        = "${local.name_prefix}-standard-key"
  description = "API key for the standard usage plan"
  enabled     = true

  tags = {
    Name      = "${local.name_prefix}-standard-key"
    Component = "api-gateway"
    Tier      = "standard"
  }
}

resource "aws_api_gateway_api_key" "premium" {
  name        = "${local.name_prefix}-premium-key"
  description = "API key for the premium usage plan"
  enabled     = true

  tags = {
    Name      = "${local.name_prefix}-premium-key"
    Component = "api-gateway"
    Tier      = "premium"
  }
}

# Associate keys with usage plans
resource "aws_api_gateway_usage_plan_key" "free" {
  key_id        = aws_api_gateway_api_key.free.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.free.id
}

resource "aws_api_gateway_usage_plan_key" "standard" {
  key_id        = aws_api_gateway_api_key.standard.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.standard.id
}

resource "aws_api_gateway_usage_plan_key" "premium" {
  key_id        = aws_api_gateway_api_key.premium.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.premium.id
}

# -----------------------------------------------------------------------------
# Custom Domain Name (optional)
# -----------------------------------------------------------------------------

resource "aws_api_gateway_domain_name" "custom" {
  count = var.custom_domain_name != "" ? 1 : 0

  domain_name              = var.custom_domain_name
  regional_certificate_arn = var.acm_certificate_arn

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Name      = "${local.name_prefix}-custom-domain"
    Component = "api-gateway"
  }
}

# Map production stage to custom domain
resource "aws_api_gateway_base_path_mapping" "custom" {
  count = var.custom_domain_name != "" ? 1 : 0

  api_id      = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.stages["production"].stage_name
  domain_name = aws_api_gateway_domain_name.custom[0].domain_name
}
