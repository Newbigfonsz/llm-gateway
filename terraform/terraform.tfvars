# terraform.tfvars - LLM Gateway Configuration
# Uncomment and modify values as needed

aws_region         = "us-east-1"
environment        = "dev"
project_name       = "llm-gateway"
default_model      = "anthropic.claude-3-haiku-20240307-v1:0"
rate_limit_rpm     = 60
log_retention_days = 7
