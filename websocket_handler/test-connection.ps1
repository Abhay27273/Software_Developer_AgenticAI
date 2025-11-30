# Test WebSocket Connection Script

param(
    [string]$StackName = "agenticai-websocket-stack",
    [string]$AwsRegion = "us-east-1"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "WebSocket Connection Test" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Get WebSocket endpoint
Write-Host "`nGetting WebSocket endpoint..." -ForegroundColor Yellow
$endpoint = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query "Stacks[0].Outputs[?OutputKey=='WebSocketEndpoint'].OutputValue" `
    --output text `
    --region $AwsRegion

if ([string]::IsNullOrEmpty($endpoint)) {
    Write-Host "Error: Could not get WebSocket endpoint" -ForegroundColor Red
    exit 1
}

Write-Host "Endpoint: $endpoint" -ForegroundColor Green

# Get ALB DNS for health check
$albDns = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDNS'].OutputValue" `
    --output text `
    --region $AwsRegion

# Test 1: Health Check
Write-Host "`n[Test 1] Testing health endpoint..." -ForegroundColor Yellow
try {
    $healthResponse = Invoke-WebRequest -Uri "http://$albDns/health" -TimeoutSec 10
    if ($healthResponse.StatusCode -eq 200) {
        Write-Host "  ✓ Health check passed" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Health check failed: Status $($healthResponse.StatusCode)" -ForegroundColor Red
    }
} catch {
    Write-Host "  ✗ Health check failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 2: Check ECS Service
Write-Host "`n[Test 2] Checking ECS service status..." -ForegroundColor Yellow
$clusterName = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query "Stacks[0].Outputs[?OutputKey=='ECSClusterName'].OutputValue" `
    --output text `
    --region $AwsRegion

$serviceName = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query "Stacks[0].Outputs[?OutputKey=='WebSocketServiceName'].OutputValue" `
    --output text `
    --region $AwsRegion

$serviceStatus = aws ecs describe-services `
    --cluster $clusterName `
    --services $serviceName `
    --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}' `
    --output json `
    --region $AwsRegion | ConvertFrom-Json

Write-Host "  Status: $($serviceStatus.Status)" -ForegroundColor $(if ($serviceStatus.Status -eq "ACTIVE") { "Green" } else { "Red" })
Write-Host "  Running: $($serviceStatus.Running) / $($serviceStatus.Desired)" -ForegroundColor $(if ($serviceStatus.Running -eq $serviceStatus.Desired) { "Green" } else { "Yellow" })

# Test 3: Check Target Health
Write-Host "`n[Test 3] Checking ALB target health..." -ForegroundColor Yellow
$tgArn = aws elbv2 describe-target-groups `
    --names "agenticai-tg-$($StackName.Split('-')[-1])" `
    --query 'TargetGroups[0].TargetGroupArn' `
    --output text `
    --region $AwsRegion 2>$null

if (-not [string]::IsNullOrEmpty($tgArn)) {
    $targetHealth = aws elbv2 describe-target-health `
        --target-group-arn $tgArn `
        --query 'TargetHealthDescriptions[0].TargetHealth.State' `
        --output text `
        --region $AwsRegion

    Write-Host "  Target Health: $targetHealth" -ForegroundColor $(if ($targetHealth -eq "healthy") { "Green" } else { "Red" })
} else {
    Write-Host "  Could not find target group" -ForegroundColor Yellow
}

# Test 4: Check Recent Logs
Write-Host "`n[Test 4] Checking recent logs..." -ForegroundColor Yellow
$logGroup = "/ecs/agenticai-websocket-$($StackName.Split('-')[-1])"
$recentLogs = aws logs tail $logGroup --since 5m --format short --region $AwsRegion 2>$null | Select-Object -First 5

if ($recentLogs) {
    Write-Host "  Recent log entries:" -ForegroundColor White
    $recentLogs | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
} else {
    Write-Host "  No recent logs found" -ForegroundColor Yellow
}

# Summary
Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "Test Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "WebSocket Endpoint: $endpoint" -ForegroundColor White
Write-Host "ALB DNS: $albDns" -ForegroundColor White
Write-Host "`nTo test WebSocket connection:" -ForegroundColor Yellow
Write-Host "  1. Install wscat: npm install -g wscat" -ForegroundColor White
Write-Host "  2. Connect: wscat -c $endpoint" -ForegroundColor White
Write-Host "`nOr use Python:" -ForegroundColor Yellow
Write-Host @"
  import asyncio, websockets, json
  
  async def test():
      async with websockets.connect("$endpoint") as ws:
          print(await ws.recv())  # Welcome message
          await ws.send(json.dumps({"action": "ping"}))
          print(await ws.recv())  # Pong response
  
  asyncio.run(test())
"@ -ForegroundColor White
Write-Host "==========================================" -ForegroundColor Cyan
