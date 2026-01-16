# variables.tf - LLM Gateway Configuration Variables

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "llm-gateway"
}

variable "default_model" {
  description = "Default Bedrock model to use"
  type        = string
  default     = "anthropic.claude-3-haiku-20240307-v1:0"
}

variable "rate_limit_rpm" {
  description = "Default rate limit (requests per minute)"
  type        = number
  default     = 60
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

# Model pricing for cost tracking (per 1K tokens)
variable "model_pricing" {
  description = "Model pricing per 1K tokens (input/output)"
  type = map(object({
    input_per_1k  = number
    output_per_1k = number
  }))
  default = {
    "anthropic.claude-3-haiku-20240307-v1:0" = {
      input_per_1k  = 0.00025
      output_per_1k = 0.00125
    }
    "anthropic.claude-3-sonnet-20240229-v1:0" = {
      input_per_1k  = 0.003
      output_per_1k = 0.015
    }
    "anthropic.claude-3-5-sonnet-20240620-v1:0" = {
      input_per_1k  = 0.003
      output_per_1k = 0.015
    }
    "amazon.titan-text-express-v1" = {
      input_per_1k  = 0.0002
      output_per_1k = 0.0006
    }
  }
}
