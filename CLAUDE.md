# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM Gateway is a serverless API gateway that centralizes AI/LLM requests to AWS Bedrock, providing authentication, rate limiting, usage tracking, and cost visibility (FinOps).

**Tech Stack**: Terraform (AWS), Python 3.11 Lambda, DynamoDB, API Gateway v2 (HTTP), AWS Bedrock

## Common Commands

```bash
# Deploy infrastructure
cd terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# Get API endpoint and demo key
terraform output -raw api_endpoint
terraform output -raw demo_api_key

# Destroy infrastructure
terraform destroy
```

**Testing**:
```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run tests with coverage
pytest --cov=lambda

# Run a single test file
pytest tests/test_gateway.py

# Run a specific test
pytest tests/test_gateway.py::TestAuthentication::test_missing_api_key_returns_401

# Lint Python code
ruff check lambda/ tests/
```

**Pre-commit Hook**: Automatically runs `ruff check` and `pytest` before each commit. Located at `.git/hooks/pre-commit`.

**CI Pipeline**: GitHub Actions runs on every PR (`.github/workflows/ci.yml`):
- Terraform validate
- Ruff lint
- Pytest with coverage

**Manual API Testing** (PowerShell):
```powershell
$API = terraform output -raw api_endpoint
$KEY = terraform output -raw demo_api_key

Invoke-RestMethod -Uri "$API/health"
$body = '{"model":"nova-micro","messages":[{"role":"user","content":"Hello!"}]}'
Invoke-RestMethod -Uri "$API/v1/chat" -Method POST -Headers @{"x-api-key"=$KEY;"Content-Type"="application/json"} -Body $body
```

## Architecture

```
Client → API Gateway → Lambda (gateway/handler.py) → AWS Bedrock
                              ↓
                         DynamoDB (3 tables: api-keys, usage, rate-limits)
```

**Request Flow**:
1. API Gateway routes to gateway Lambda
2. Lambda validates API key against DynamoDB api-keys table
3. Checks rate limit (rate-limits table with 2-min TTL)
4. Maps user-friendly model name to Bedrock model ID
5. Invokes Bedrock with provider-specific formatting (Anthropic/Nova/Titan)
6. Tracks usage to DynamoDB (usage table with 90-day TTL)
7. Returns OpenAI-compatible response with gateway metadata

**Lambda Functions**:
- `lambda/gateway/handler.py` (524 lines): Main router - handles /health, /v1/models, /v1/chat, /v1/usage
- `lambda/auth/handler.py`: API key management (admin, not exposed via API Gateway)
- `lambda/usage/handler.py`: Usage statistics aggregation

## Supported Models

Model mappings are defined in `lambda/gateway/handler.py`:
- `nova-micro` (default), `nova-lite` - Amazon Nova models
- `claude-3-haiku`, `claude-3-sonnet`, `claude-3.5-sonnet` - Anthropic models
- `titan-text-express` - Amazon Titan

Each model type requires different request formatting in the `invoke_bedrock_model` function.

## Key Configuration

- `terraform/terraform.tfvars`: Region (us-east-1), environment, rate limits
- `terraform/variables.tf`: Variable definitions with defaults
- Model pricing is hardcoded in `lambda/gateway/handler.py` (MODEL_PRICING dict)

## API Endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| GET /health | None | Health check |
| GET /v1/models | x-api-key | List models with pricing |
| POST /v1/chat | x-api-key | OpenAI-compatible chat completion (supports streaming) |
| GET /v1/usage | x-api-key | Usage stats for team (query: ?days=30) |

## Streaming

Add `"stream": true` to POST /v1/chat requests to receive Server-Sent Events:

```json
{"model": "claude-3-haiku", "messages": [{"role": "user", "content": "Hello"}], "stream": true}
```

Response is `Content-Type: text/event-stream` with SSE format:
```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello"}}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

**Streaming support by model:**
- Anthropic (claude-3-*): Supported via `invoke_model_with_response_stream`
- Nova (nova-micro, nova-lite): Supported via `invoke_model_with_response_stream`
- Titan: Not supported (returns 400 error)

**Implementation:** `stream_anthropic_model()` and `stream_nova_model()` in `lambda/gateway/handler.py`

## Observability

CloudWatch dashboard (`terraform/dashboard.tf`) provides real-time monitoring:

| Section | Widgets |
|---------|---------|
| API Gateway | Request Count, Latency (p50/p99), Error Rates (4xx/5xx) |
| Lambda | Concurrent Executions, Errors, Duration (p50/p99) |
| DynamoDB | Consumed Read/Write Capacity, Throttled Requests |

Access the dashboard after deployment:
```bash
terraform output dashboard_url
```

## Rules

- Never run `terraform apply` without a plan file; always use `terraform plan -out=tfplan` then `terraform apply tfplan`
- All Terraform resources must include tags: `Environment`, `Project`, `Owner`
- No wildcard (`*`) actions or resources in IAM policies; always use specific ARNs and actions
- Use underscores for Terraform resource names (e.g., `aws_lambda_function.gateway_handler`), hyphens for AWS resource names (e.g., `llm-gateway-dev`)
- State is stored in S3; never modify `.tfstate` files directly
- Python code must pass `ruff check` before committing
