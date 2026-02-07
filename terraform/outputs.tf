# outputs.tf - LLM Gateway Outputs

output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_stage.main.invoke_url
}

output "demo_api_key" {
  description = "Demo API key for testing"
  value       = "llm-${random_password.demo_api_key.result}"
  sensitive   = true
}

output "api_keys_table" {
  description = "DynamoDB table name for API keys"
  value       = aws_dynamodb_table.api_keys.name
}

output "usage_table" {
  description = "DynamoDB table name for usage tracking"
  value       = aws_dynamodb_table.usage.name
}

output "gateway_function" {
  description = "Gateway Lambda function name"
  value       = aws_lambda_function.gateway.function_name
}

output "region" {
  description = "AWS region"
  value       = data.aws_region.current.name
}

output "dashboard_url" {
  description = "CloudWatch Dashboard URL"
  value       = "https://${data.aws_region.current.name}.console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "request_logs_bucket" {
  description = "S3 bucket for request logs (if enabled)"
  value       = var.enable_request_logging ? aws_s3_bucket.request_logs[0].id : null
}

# Helpful commands output
output "quick_start" {
  description = "Quick start commands"
  value = <<-EOT
    
    ========================================
    🚀 LLM Gateway Deployed Successfully!
    ========================================
    
    API Endpoint: ${aws_apigatewayv2_stage.main.invoke_url}
    
    Get your API key:
      terraform output -raw demo_api_key
    
    Test health endpoint:
      curl ${aws_apigatewayv2_stage.main.invoke_url}/health
    
    Test with authentication:
      API_KEY=$(terraform output -raw demo_api_key)
      curl -H "x-api-key: $API_KEY" ${aws_apigatewayv2_stage.main.invoke_url}/v1/models
    
    Make a chat request:
      curl -X POST ${aws_apigatewayv2_stage.main.invoke_url}/v1/chat \
        -H "x-api-key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"model":"claude-3-haiku","messages":[{"role":"user","content":"Hello!"}]}'
    
    Check usage:
      curl -H "x-api-key: $API_KEY" ${aws_apigatewayv2_stage.main.invoke_url}/v1/usage
    
  EOT
}
