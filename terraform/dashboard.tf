# dashboard.tf - CloudWatch Dashboard for LLM Gateway Observability
# Provides real-time visibility into API Gateway, Lambda, and DynamoDB metrics

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}"

  dashboard_body = jsonencode({
    widgets = concat(
      # Row 1: API Gateway Metrics
      [
        {
          type   = "text"
          x      = 0
          y      = 0
          width  = 24
          height = 1
          properties = {
            markdown = "# API Gateway Metrics"
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 1
          width  = 8
          height = 6
          properties = {
            title  = "Request Count"
            region = data.aws_region.current.name
            stat   = "Sum"
            period = 60
            metrics = [
              ["AWS/ApiGateway", "Count", "ApiId", aws_apigatewayv2_api.main.id, { label = "Requests" }]
            ]
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 1
          width  = 8
          height = 6
          properties = {
            title  = "Request Latency (p50 / p99)"
            region = data.aws_region.current.name
            period = 60
            metrics = [
              ["AWS/ApiGateway", "Latency", "ApiId", aws_apigatewayv2_api.main.id, { stat = "p50", label = "p50" }],
              ["AWS/ApiGateway", "Latency", "ApiId", aws_apigatewayv2_api.main.id, { stat = "p99", label = "p99" }]
            ]
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 1
          width  = 8
          height = 6
          properties = {
            title  = "Error Rates (4xx / 5xx)"
            region = data.aws_region.current.name
            stat   = "Sum"
            period = 60
            metrics = [
              ["AWS/ApiGateway", "4xx", "ApiId", aws_apigatewayv2_api.main.id, { label = "4xx Errors", color = "#ff7f0e" }],
              ["AWS/ApiGateway", "5xx", "ApiId", aws_apigatewayv2_api.main.id, { label = "5xx Errors", color = "#d62728" }]
            ]
          }
        }
      ],

      # Row 2: Lambda Metrics
      [
        {
          type   = "text"
          x      = 0
          y      = 7
          width  = 24
          height = 1
          properties = {
            markdown = "# Lambda Metrics"
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 8
          width  = 8
          height = 6
          properties = {
            title  = "Concurrent Executions"
            region = data.aws_region.current.name
            stat   = "Maximum"
            period = 60
            metrics = [
              ["AWS/Lambda", "ConcurrentExecutions", "FunctionName", aws_lambda_function.gateway.function_name, { label = "Gateway" }],
              ["AWS/Lambda", "ConcurrentExecutions", "FunctionName", aws_lambda_function.auth.function_name, { label = "Auth" }],
              ["AWS/Lambda", "ConcurrentExecutions", "FunctionName", aws_lambda_function.usage.function_name, { label = "Usage" }]
            ]
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 8
          width  = 8
          height = 6
          properties = {
            title  = "Lambda Errors"
            region = data.aws_region.current.name
            stat   = "Sum"
            period = 60
            metrics = [
              ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.gateway.function_name, { label = "Gateway", color = "#d62728" }],
              ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.auth.function_name, { label = "Auth", color = "#ff7f0e" }],
              ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.usage.function_name, { label = "Usage", color = "#9467bd" }]
            ]
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 8
          width  = 8
          height = 6
          properties = {
            title  = "Lambda Duration (p50 / p99)"
            region = data.aws_region.current.name
            period = 60
            metrics = [
              ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.gateway.function_name, { stat = "p50", label = "Gateway p50" }],
              ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.gateway.function_name, { stat = "p99", label = "Gateway p99" }]
            ]
          }
        }
      ],

      # Row 3: DynamoDB Metrics
      [
        {
          type   = "text"
          x      = 0
          y      = 14
          width  = 24
          height = 1
          properties = {
            markdown = "# DynamoDB Metrics"
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 15
          width  = 8
          height = 6
          properties = {
            title  = "Consumed Read Capacity"
            region = data.aws_region.current.name
            stat   = "Sum"
            period = 60
            metrics = [
              ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", aws_dynamodb_table.api_keys.name, { label = "API Keys" }],
              ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", aws_dynamodb_table.usage.name, { label = "Usage" }],
              ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", aws_dynamodb_table.rate_limits.name, { label = "Rate Limits" }]
            ]
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 15
          width  = 8
          height = 6
          properties = {
            title  = "Consumed Write Capacity"
            region = data.aws_region.current.name
            stat   = "Sum"
            period = 60
            metrics = [
              ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", aws_dynamodb_table.api_keys.name, { label = "API Keys" }],
              ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", aws_dynamodb_table.usage.name, { label = "Usage" }],
              ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", aws_dynamodb_table.rate_limits.name, { label = "Rate Limits" }]
            ]
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 15
          width  = 8
          height = 6
          properties = {
            title  = "DynamoDB Throttled Requests"
            region = data.aws_region.current.name
            stat   = "Sum"
            period = 60
            metrics = [
              ["AWS/DynamoDB", "ThrottledRequests", "TableName", aws_dynamodb_table.api_keys.name, { label = "API Keys", color = "#d62728" }],
              ["AWS/DynamoDB", "ThrottledRequests", "TableName", aws_dynamodb_table.usage.name, { label = "Usage", color = "#ff7f0e" }],
              ["AWS/DynamoDB", "ThrottledRequests", "TableName", aws_dynamodb_table.rate_limits.name, { label = "Rate Limits", color = "#9467bd" }]
            ]
          }
        }
      ]
    )
  })

  depends_on = [
    aws_apigatewayv2_api.main,
    aws_lambda_function.gateway,
    aws_lambda_function.auth,
    aws_lambda_function.usage,
    aws_dynamodb_table.api_keys,
    aws_dynamodb_table.usage,
    aws_dynamodb_table.rate_limits
  ]
}
