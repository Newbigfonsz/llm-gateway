# main.tf - LLM Gateway Infrastructure
# A centralized API that routes AI requests to multiple providers

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "llm-gateway"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# -----------------------------------------------------------------------------
# DATA SOURCES
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# LOCALS
# -----------------------------------------------------------------------------

locals {
  # Construct Bedrock model ARNs from model IDs
  bedrock_model_arns = [
    for model_id in var.bedrock_model_ids :
    "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/${model_id}"
  ]
}

# -----------------------------------------------------------------------------
# DYNAMODB TABLES
# -----------------------------------------------------------------------------

# API Keys table - stores team API keys and metadata
resource "aws_dynamodb_table" "api_keys" {
  name           = "${var.project_name}-api-keys-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "api_key"
  
  attribute {
    name = "api_key"
    type = "S"
  }
  
  attribute {
    name = "team_id"
    type = "S"
  }
  
  global_secondary_index {
    name            = "team-index"
    hash_key        = "team_id"
    projection_type = "ALL"
  }
  
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
  
  tags = {
    Name = "${var.project_name}-api-keys"
  }
}

# Usage tracking table - stores request counts and token usage
resource "aws_dynamodb_table" "usage" {
  name           = "${var.project_name}-usage-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "team_id"
  range_key      = "date"
  
  attribute {
    name = "team_id"
    type = "S"
  }
  
  attribute {
    name = "date"
    type = "S"
  }
  
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
  
  tags = {
    Name = "${var.project_name}-usage"
  }
}

# Rate limiting table - tracks request counts for rate limiting
resource "aws_dynamodb_table" "rate_limits" {
  name           = "${var.project_name}-rate-limits-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "key"
  
  attribute {
    name = "key"
    type = "S"
  }
  
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
  
  tags = {
    Name = "${var.project_name}-rate-limits"
  }
}

# -----------------------------------------------------------------------------
# IAM ROLES AND POLICIES
# -----------------------------------------------------------------------------

# Lambda execution role
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Lambda policy - DynamoDB, Bedrock, CloudWatch
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.api_keys.arn,
          "${aws_dynamodb_table.api_keys.arn}/index/*",
          aws_dynamodb_table.usage.arn,
          aws_dynamodb_table.rate_limits.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = local.bedrock_model_arns
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# LAMBDA FUNCTIONS
# -----------------------------------------------------------------------------

# Package Lambda code
data "archive_file" "gateway_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/gateway"
  output_path = "${path.module}/builds/gateway.zip"
}

data "archive_file" "auth_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/auth"
  output_path = "${path.module}/builds/auth.zip"
}

data "archive_file" "usage_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/usage"
  output_path = "${path.module}/builds/usage.zip"
}

# Gateway Lambda - handles /v1/chat and /v1/models
resource "aws_lambda_function" "gateway" {
  filename         = data.archive_file.gateway_lambda.output_path
  function_name    = "${var.project_name}-gateway-${var.environment}"
  role             = aws_iam_role.lambda_role.arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.gateway_lambda.output_base64sha256
  runtime          = "python3.11"
  timeout          = 60
  memory_size      = 256
  
  environment {
    variables = {
      ENVIRONMENT       = var.environment
      API_KEYS_TABLE    = aws_dynamodb_table.api_keys.name
      USAGE_TABLE       = aws_dynamodb_table.usage.name
      RATE_LIMITS_TABLE = aws_dynamodb_table.rate_limits.name
      DEFAULT_MODEL     = var.default_model
      RATE_LIMIT_RPM    = var.rate_limit_rpm
    }
  }
  
  tags = {
    Name = "${var.project_name}-gateway"
  }
}

# Auth Lambda - handles API key validation
resource "aws_lambda_function" "auth" {
  filename         = data.archive_file.auth_lambda.output_path
  function_name    = "${var.project_name}-auth-${var.environment}"
  role             = aws_iam_role.lambda_role.arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.auth_lambda.output_base64sha256
  runtime          = "python3.11"
  timeout          = 10
  memory_size      = 128
  
  environment {
    variables = {
      API_KEYS_TABLE = aws_dynamodb_table.api_keys.name
    }
  }
  
  tags = {
    Name = "${var.project_name}-auth"
  }
}

# Usage Lambda - handles /v1/usage endpoint
resource "aws_lambda_function" "usage" {
  filename         = data.archive_file.usage_lambda.output_path
  function_name    = "${var.project_name}-usage-${var.environment}"
  role             = aws_iam_role.lambda_role.arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.usage_lambda.output_base64sha256
  runtime          = "python3.11"
  timeout          = 10
  memory_size      = 128
  
  environment {
    variables = {
      USAGE_TABLE    = aws_dynamodb_table.usage.name
      API_KEYS_TABLE = aws_dynamodb_table.api_keys.name
    }
  }
  
  tags = {
    Name = "${var.project_name}-usage"
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "gateway_logs" {
  name              = "/aws/lambda/${aws_lambda_function.gateway.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "auth_logs" {
  name              = "/aws/lambda/${aws_lambda_function.auth.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "usage_logs" {
  name              = "/aws/lambda/${aws_lambda_function.usage.function_name}"
  retention_in_days = var.log_retention_days
}

# -----------------------------------------------------------------------------
# API GATEWAY
# -----------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "main" {
  name          = "${var.project_name}-api-${var.environment}"
  protocol_type = "HTTP"
  
  cors_configuration {
    allow_headers = ["Content-Type", "x-api-key", "Authorization"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_origins = var.cors_allowed_origins
    max_age       = 300
  }
  
  tags = {
    Name = "${var.project_name}-api"
  }
}

resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = var.environment
  auto_deploy = true
  
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      responseLength = "$context.responseLength"
      integrationLatency = "$context.integrationLatency"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days
}

# Lambda integrations
resource "aws_apigatewayv2_integration" "gateway" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.gateway.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "usage" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.usage.invoke_arn
  payload_format_version = "2.0"
}

# Routes
resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.gateway.id}"
}

resource "aws_apigatewayv2_route" "models" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /v1/models"
  target    = "integrations/${aws_apigatewayv2_integration.gateway.id}"
}

resource "aws_apigatewayv2_route" "chat" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /v1/chat"
  target    = "integrations/${aws_apigatewayv2_integration.gateway.id}"
}

resource "aws_apigatewayv2_route" "usage" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /v1/usage"
  target    = "integrations/${aws_apigatewayv2_integration.usage.id}"
}

# Lambda permissions for API Gateway
resource "aws_lambda_permission" "gateway" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.gateway.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "usage" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.usage.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# -----------------------------------------------------------------------------
# INITIAL API KEY (Demo)
# -----------------------------------------------------------------------------

resource "random_password" "demo_api_key" {
  length  = 32
  special = false
}

resource "aws_dynamodb_table_item" "demo_api_key" {
  table_name = aws_dynamodb_table.api_keys.name
  hash_key   = aws_dynamodb_table.api_keys.hash_key
  
  item = jsonencode({
    api_key = {
      S = "llm-${random_password.demo_api_key.result}"
    }
    team_id = {
      S = "demo-team"
    }
    team_name = {
      S = "Demo Team"
    }
    rate_limit_rpm = {
      N = tostring(var.rate_limit_rpm)
    }
    created_at = {
      S = timestamp()
    }
    is_active = {
      BOOL = true
    }
  })

  lifecycle {
    ignore_changes = [item]
  }
}
