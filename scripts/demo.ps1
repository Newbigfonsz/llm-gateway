# LLM Gateway Demo Script
# ========================
# A centralized API that routes AI requests to multiple providers

# Prerequisites: Run these once
# cd C:\Users\Public\llm-gateway\terraform
# terraform init
# terraform apply

# Set variables (update these after terraform apply)
$API = "YOUR_API_ENDPOINT_HERE"  # e.g., https://abc123.execute-api.us-east-1.amazonaws.com/dev
$KEY = "YOUR_API_KEY_HERE"        # Run: terraform output -raw demo_api_key

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   LLM GATEWAY DEMO" -ForegroundColor Cyan  
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ============================================
# OPENING (30 sec)
# ============================================
Write-Host @"
"I built an LLM Gateway - a centralized API that routes AI requests 
to multiple providers like AWS Bedrock. It solves the problem of teams 
directly calling LLM APIs without visibility into costs or usage. 
Let me show you."
"@ -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to continue..."

# ============================================
# 1. SHOW INFRASTRUCTURE (Terraform)
# ============================================
Write-Host "`n--- 1. INFRASTRUCTURE AS CODE ---" -ForegroundColor Green
Write-Host "Everything is Infrastructure as Code - Terraform deploys 24 AWS resources in under a minute." -ForegroundColor White
Write-Host ""

# Show main.tf structure
Write-Host "Key resources in main.tf:" -ForegroundColor Cyan
Write-Host "  - API Gateway (HTTP API)"
Write-Host "  - 3 Lambda Functions (gateway, auth, usage)"
Write-Host "  - 3 DynamoDB Tables (api-keys, usage, rate-limits)"
Write-Host "  - IAM Roles and Policies"
Write-Host "  - CloudWatch Log Groups"
Write-Host ""

# Optional: Show terraform output
# terraform output

Read-Host "Press Enter to continue..."

# ============================================
# 2. HEALTH CHECK
# ============================================
Write-Host "`n--- 2. HEALTH CHECK ---" -ForegroundColor Green
Write-Host "Health endpoint for monitoring and load balancer checks." -ForegroundColor White
Write-Host ""
Write-Host "Command: Invoke-RestMethod -Uri `"$API/health`"" -ForegroundColor DarkGray

$health = Invoke-RestMethod -Uri "$API/health"
$health | ConvertTo-Json
Write-Host ""

Read-Host "Press Enter to continue..."

# ============================================
# 3. AUTHENTICATION DEMO
# ============================================
Write-Host "`n--- 3. AUTHENTICATION DEMO ---" -ForegroundColor Green
Write-Host "Every team gets their own API key. We track who's using what." -ForegroundColor White
Write-Host ""

# Without API key - should fail
Write-Host "Without API key (should fail):" -ForegroundColor Yellow
try {
    Invoke-RestMethod -Uri "$API/v1/models" -ErrorAction Stop
} catch {
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# With API key - should work
Write-Host "With API key (should work):" -ForegroundColor Yellow
$models = Invoke-RestMethod -Uri "$API/v1/models" -Headers @{"x-api-key"=$KEY}
$models | ConvertTo-Json -Depth 3
Write-Host ""

Read-Host "Press Enter to continue..."

# ============================================
# 4. LIVE AI REQUEST
# ============================================
Write-Host "`n--- 4. LIVE AI REQUEST ---" -ForegroundColor Green
Write-Host "Request goes through our gateway to Bedrock, response comes back with token counts." -ForegroundColor White
Write-Host ""

$body = @{
    model = "claude-3-haiku"
    messages = @(
        @{
            role = "user"
            content = "Explain Kubernetes in one sentence."
        }
    )
} | ConvertTo-Json

Write-Host "Request body:" -ForegroundColor Yellow
Write-Host $body
Write-Host ""

Write-Host "Calling API..." -ForegroundColor Cyan
$response = Invoke-RestMethod -Uri "$API/v1/chat" -Method POST -Headers @{
    "x-api-key" = $KEY
    "Content-Type" = "application/json"
} -Body $body

Write-Host "Response:" -ForegroundColor Yellow
Write-Host "  Content: $($response.choices[0].message.content)" -ForegroundColor White
Write-Host ""
Write-Host "  Tokens - Input: $($response.usage.prompt_tokens), Output: $($response.usage.completion_tokens)" -ForegroundColor Cyan
Write-Host "  Cost: `$$($response.gateway_metadata.cost_usd)" -ForegroundColor Green
Write-Host "  Latency: $($response.gateway_metadata.latency_ms)ms" -ForegroundColor Gray
Write-Host ""

Read-Host "Press Enter to continue..."

# ============================================
# 5. COST TRACKING (FinOps)
# ============================================
Write-Host "`n--- 5. COST TRACKING (FinOps) ---" -ForegroundColor Green
Write-Host "We track tokens and costs per team automatically." -ForegroundColor White
Write-Host ""

$usage = Invoke-RestMethod -Uri "$API/v1/usage?days=30" -Headers @{"x-api-key"=$KEY}
Write-Host "Usage Summary for $($usage.team_name):" -ForegroundColor Yellow
Write-Host "  Total Requests: $($usage.summary.total_requests)"
Write-Host "  Total Tokens: $($usage.summary.total_tokens)"
Write-Host "  Total Cost: `$$($usage.summary.total_cost_usd)"
Write-Host "  Avg Daily Cost: `$$([math]::Round($usage.summary.avg_daily_cost_usd, 4))"
Write-Host ""

if ($usage.by_model.Count -gt 0) {
    Write-Host "Usage by Model:" -ForegroundColor Yellow
    foreach ($model in $usage.by_model) {
        Write-Host "  $($model.model): $($model.requests) requests"
    }
}
Write-Host ""

Read-Host "Press Enter to continue..."

# ============================================
# KEY TALKING POINTS
# ============================================
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "   KEY FEATURES & BUSINESS VALUE" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$features = @(
    @{Feature="API Key Auth"; Value="Security & accountability - know who's using what"},
    @{Feature="Rate Limiting"; Value="Prevent runaway costs - 60 RPM default per team"},
    @{Feature="Usage Tracking"; Value="FinOps visibility - charge back to teams"},
    @{Feature="Multi-Provider"; Value="No vendor lock-in - switch providers easily"},
    @{Feature="IaC (Terraform)"; Value="Reproducible, auditable, version controlled"},
    @{Feature="Serverless"; Value="Scales to zero, pay only for what you use"}
)

foreach ($f in $features) {
    Write-Host "  $($f.Feature): " -ForegroundColor Yellow -NoNewline
    Write-Host $f.Value -ForegroundColor White
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   DEMO COMPLETE!" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# ============================================
# IF ASKED...
# ============================================
Write-Host "`n--- IF ASKED... ---" -ForegroundColor Magenta

Write-Host @"

Q: "Why not just use Bedrock directly?"
A: "Direct access means no visibility. With this gateway, finance can see 
   costs per team, security can audit requests, and we can add rate limits 
   or switch providers without changing client code."

Q: "How would you scale this?"
A: "It's already serverless - Lambda and DynamoDB scale automatically. 
   For global, I'd add CloudFront and deploy to multiple regions."

Q: "What would you add next?"
A: "Prompt caching to reduce costs, streaming responses, and a dashboard 
   for real-time usage metrics."
"@ -ForegroundColor Gray

# ============================================
# CLEANUP (after demo)
# ============================================
Write-Host "`n--- CLEANUP (run after demo) ---" -ForegroundColor Red
Write-Host "cd C:\Users\Public\llm-gateway\terraform" -ForegroundColor DarkGray
Write-Host "terraform destroy -auto-approve" -ForegroundColor DarkGray
