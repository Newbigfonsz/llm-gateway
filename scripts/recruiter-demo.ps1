# ============================================================================
# LLM GATEWAY - RECRUITER DEMO SCRIPT
# ============================================================================
# Author: Alphonzo Jones Jr
# GitHub: https://github.com/Newbigfonsz/llm-gateway
# ============================================================================

Clear-Host
Write-Host ""
Write-Host "  ╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║              🚀 LLM GATEWAY - LIVE DEMO                       ║" -ForegroundColor Cyan
Write-Host "  ║   Centralized AI API with Auth, Rate Limiting & FinOps       ║" -ForegroundColor Cyan
Write-Host "  ╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

# Get credentials
Set-Location "$PSScriptRoot\..\terraform"
$API = terraform output -raw api_endpoint
$KEY = terraform output -raw demo_api_key
Set-Location "$PSScriptRoot"

Write-Host "`n  API: $API" -ForegroundColor DarkGray
Write-Host ""
Read-Host "  Press Enter to start"

# 1. Health Check
Write-Host "`n  1️⃣  HEALTH CHECK" -ForegroundColor Yellow
$health = Invoke-RestMethod -Uri "$API/health"
Write-Host "  Status: $($health.status) | Version: $($health.version)" -ForegroundColor Green
Read-Host "`n  Press Enter"

# 2. Authentication
Write-Host "`n  2️⃣  AUTHENTICATION" -ForegroundColor Yellow
Write-Host "  Without key: " -NoNewline
try { Invoke-RestMethod -Uri "$API/v1/models" -ErrorAction Stop | Out-Null } 
catch { Write-Host "❌ 401 Unauthorized" -ForegroundColor Red }
Write-Host "  With key:    ✅ Authenticated" -ForegroundColor Green
Read-Host "`n  Press Enter"

# 3. Live AI Request
Write-Host "`n  3️⃣  LIVE AI REQUEST" -ForegroundColor Yellow
$body = @{model="nova-micro"; messages=@(@{role="user"; content="Explain Kubernetes in one sentence."})} | ConvertTo-Json -Depth 3
$r = Invoke-RestMethod -Uri "$API/v1/chat" -Method POST -Headers @{"x-api-key"=$KEY; "Content-Type"="application/json"} -Body $body
Write-Host "  Response: $($r.choices[0].message.content)" -ForegroundColor White
Write-Host "  Tokens: $($r.usage.total_tokens) | Cost: `$$($r.gateway_metadata.cost_usd) | Latency: $($r.gateway_metadata.latency_ms)ms" -ForegroundColor Cyan
Read-Host "`n  Press Enter"

# 4. Usage Tracking
Write-Host "`n  4️⃣  USAGE TRACKING (FinOps)" -ForegroundColor Yellow
$u = Invoke-RestMethod -Uri "$API/v1/usage" -Headers @{"x-api-key"=$KEY}
Write-Host "  Team: $($u.team_name) | Requests: $($u.summary.total_requests) | Cost: `$$($u.summary.total_cost_usd)" -ForegroundColor Cyan
Read-Host "`n  Press Enter"

# 5. Key Features
Write-Host "`n  📋 KEY FEATURES" -ForegroundColor Yellow
Write-Host "  • API Key Auth      → Security & accountability" -ForegroundColor White
Write-Host "  • Rate Limiting     → Prevent runaway costs" -ForegroundColor White
Write-Host "  • Usage Tracking    → FinOps / chargeback" -ForegroundColor White
Write-Host "  • Multi-Provider    → No vendor lock-in" -ForegroundColor White
Write-Host "  • Serverless        → Scales to zero" -ForegroundColor White
Write-Host "  • IaC (Terraform)   → Reproducible" -ForegroundColor White

Write-Host "`n  ✅ DEMO COMPLETE!" -ForegroundColor Green
Write-Host "  GitHub: https://github.com/Newbigfonsz/llm-gateway`n" -ForegroundColor DarkGray
