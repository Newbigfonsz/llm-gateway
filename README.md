# LLM Gateway

A centralized API gateway that routes AI requests to multiple providers (AWS Bedrock) with authentication, rate limiting, and cost tracking for FinOps visibility.

## 🎯 Problem Solved

Teams directly calling LLM APIs without visibility into:
- **Who** is using the AI services
- **How much** they're spending
- **What** requests are being made

This gateway provides centralized control, security, and FinOps capabilities.

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│  API Gateway │────▶│   Lambda    │
│  (Teams)    │     │   (HTTP)     │     │  (Gateway)  │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
            ┌──────────────┐           ┌──────────────┐            ┌──────────────┐
            │  DynamoDB    │           │  DynamoDB    │            │   Bedrock    │
            │  (API Keys)  │           │   (Usage)    │            │   (Claude)   │
            └──────────────┘           └──────────────┘            └──────────────┘
```

## 📦 AWS Resources Deployed

| Resource | Count | Purpose |
|----------|-------|---------|
| API Gateway (HTTP) | 1 | Request routing |
| Lambda Functions | 3 | Gateway, Auth, Usage handlers |
| DynamoDB Tables | 3 | API keys, usage tracking, rate limits |
| IAM Roles | 1 | Lambda execution permissions |
| CloudWatch Log Groups | 4 | Logging and monitoring |

**Total: ~15 resources** (deployed in under 60 seconds)

## 🚀 Quick Start

### Prerequisites

- AWS CLI configured with appropriate permissions
- Terraform >= 1.5.0
- AWS Bedrock model access enabled (Claude 3 Haiku recommended)

### Deploy

```powershell
# Clone/navigate to project
cd llm-gateway/terraform

# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Deploy (creates all resources)
terraform apply
# Type 'yes' when prompted

# Get your API endpoint and key
$API = terraform output -raw api_endpoint
$KEY = terraform output -raw demo_api_key

Write-Host "API: $API"
Write-Host "Key: $KEY"
```

### Test

```powershell
# Health check
Invoke-RestMethod -Uri "$API/health"

# List models (requires auth)
Invoke-RestMethod -Uri "$API/v1/models" -Headers @{"x-api-key"=$KEY}

# Chat completion
$body = '{"model":"claude-3-haiku","messages":[{"role":"user","content":"Hello!"}]}'
Invoke-RestMethod -Uri "$API/v1/chat" -Method POST -Headers @{"x-api-key"=$KEY;"Content-Type"="application/json"} -Body $body

# Check usage
Invoke-RestMethod -Uri "$API/v1/usage" -Headers @{"x-api-key"=$KEY}
```

## 📡 API Endpoints

### `GET /health`
Health check endpoint (no auth required).

```json
{
  "status": "healthy",
  "service": "llm-gateway",
  "timestamp": "2024-01-15T12:00:00Z",
  "version": "1.0.0"
}
```

### `GET /v1/models`
List available models.

**Headers:** `x-api-key: <your-key>`

```json
{
  "object": "list",
  "data": [
    {
      "id": "claude-3-haiku",
      "provider": "anthropic",
      "description": "Fast and efficient for simple tasks",
      "pricing": {"input_per_1k": 0.00025, "output_per_1k": 0.00125}
    }
  ]
}
```

### `POST /v1/chat`
Create a chat completion (OpenAI-compatible format).

**Headers:** 
- `x-api-key: <your-key>`
- `Content-Type: application/json`

**Request:**
```json
{
  "model": "claude-3-haiku",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain Kubernetes in one sentence."}
  ],
  "max_tokens": 1024,
  "temperature": 0.7
}
```

**Response:**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "model": "claude-3-haiku",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Kubernetes is an open-source container orchestration platform..."
    }
  }],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 42,
    "total_tokens": 67
  },
  "gateway_metadata": {
    "team_id": "demo-team",
    "latency_ms": 892,
    "cost_usd": 0.000059,
    "provider": "aws-bedrock"
  }
}
```

### `GET /v1/usage`
Get usage statistics for your team.

**Headers:** `x-api-key: <your-key>`

**Query Params:** `days` (default: 30)

```json
{
  "team_id": "demo-team",
  "team_name": "Demo Team",
  "period": {
    "days": 30,
    "start": "2024-01-01",
    "end": "2024-01-31"
  },
  "summary": {
    "total_requests": 150,
    "total_tokens": 45000,
    "total_cost_usd": 0.0562,
    "avg_daily_cost_usd": 0.00187
  },
  "by_model": [
    {"model": "claude-3-haiku", "requests": 140},
    {"model": "claude-3-sonnet", "requests": 10}
  ]
}
```

## 🔑 Key Features

| Feature | Business Value |
|---------|---------------|
| **API Key Auth** | Security & accountability - know who's using what |
| **Rate Limiting** | Prevent runaway costs - configurable per team |
| **Usage Tracking** | FinOps visibility - charge back to cost centers |
| **Multi-Provider** | No vendor lock-in - add OpenAI, Azure, etc. |
| **IaC (Terraform)** | Reproducible, auditable, version controlled |
| **Serverless** | Scales to zero, pay only for usage |

## 💰 Cost Estimation

| Component | Estimated Cost |
|-----------|---------------|
| API Gateway | $1.00 per million requests |
| Lambda | $0.20 per million invocations |
| DynamoDB | Pay per request (~$0.25/million) |
| CloudWatch | $0.50/GB logs |

**Typical usage (10K requests/month): < $5/month**

## 🛡️ Security Features

- API key authentication on all endpoints
- Rate limiting per team (default: 60 RPM)
- Request/response logging
- IAM least-privilege permissions
- No secrets in code (DynamoDB stores keys)

## 📈 Scaling Considerations

The architecture is already serverless and auto-scales:

- **Lambda**: Scales to 1000+ concurrent executions
- **DynamoDB**: On-demand scaling (pay per request)
- **API Gateway**: Handles 10K+ requests/second

For global deployment:
- Add CloudFront distribution
- Deploy to multiple regions
- Use DynamoDB Global Tables

## 🔧 Configuration

Edit `terraform/variables.tf`:

```hcl
variable "rate_limit_rpm" {
  default = 60  # Requests per minute per team
}

variable "default_model" {
  default = "anthropic.claude-3-haiku-20240307-v1:0"
}

variable "log_retention_days" {
  default = 7
}
```

## 🧹 Cleanup

```powershell
cd terraform
terraform destroy -auto-approve
```

## 📁 Project Structure

```
llm-gateway/
├── terraform/
│   ├── main.tf         # All AWS resources
│   ├── variables.tf    # Configuration variables
│   └── outputs.tf      # Output values
├── lambda/
│   ├── gateway/        # Main request handler
│   │   └── handler.py
│   ├── auth/           # API key management
│   │   └── handler.py
│   └── usage/          # Usage statistics
│       └── handler.py
└── scripts/
    └── demo.ps1        # Demo presentation script
```

## 🎤 Demo Script

See `scripts/demo.ps1` for a ready-to-run presentation script covering:
1. Infrastructure overview
2. Health check
3. Authentication demo
4. Live AI request
5. Cost tracking

## 🚧 Future Enhancements

- [ ] Prompt caching (reduce costs)
- [ ] Streaming responses
- [ ] Real-time dashboard
- [ ] OpenAI provider support
- [ ] Azure OpenAI provider support
- [ ] Request/response audit logging
- [ ] Cost alerts and budgets

## 📝 License

MIT License - feel free to use and modify.
