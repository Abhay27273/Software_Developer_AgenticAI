# Test API Authentication
# This script tests the API authentication implementation

param(
    [string]$ApiEndpoint,
    [string]$ApiKey
)

Write-Host "Testing API Authentication..." -ForegroundColor Cyan

# If parameters not provided, try to get from stack outputs
if (-not $ApiEndpoint -or -not $ApiKey) {
    Write-Host "Retrieving API endpoint and key from AWS..." -ForegroundColor Yellow
    
    $stackName = "agenticai-stack"
    $outputs = aws cloudformation describe-stacks --stack-name $stackName --query "Stacks[0].Outputs" --output json | ConvertFrom-Json
    
    $ApiEndpoint = ($outputs | Where-Object { $_.OutputKey -eq "ApiEndpoint" }).OutputValue
    $apiKeyId = ($outputs | Where-Object { $_.OutputKey -eq "ApiKeyId" }).OutputValue
    
    if (-not $ApiKey) {
        $ApiKey = aws apigateway get-api-key --api-key $apiKeyId --include-value --query "value" --output text
    }
}

Write-Host "`nAPI Endpoint: $ApiEndpoint" -ForegroundColor White
Write-Host "API Key: $($ApiKey.Substring(0, 10))..." -ForegroundColor White

# Test 1: Request without API key (should fail with 401 or 403)
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Test 1: Request without API key" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

$response = curl -s -w "`n%{http_code}" "$($ApiEndpoint)health"
$statusCode = $response[-1]
Write-Host "Status Code: $statusCode" -ForegroundColor $(if ($statusCode -eq "401" -or $statusCode -eq "403") { "Green" } else { "Red" })

if ($statusCode -eq "401" -or $statusCode -eq "403") {
    Write-Host "✓ PASS: Request without API key was rejected" -ForegroundColor Green
} else {
    Write-Host "✗ FAIL: Request without API key should be rejected" -ForegroundColor Red
}

# Test 2: Request with invalid API key (should fail with 403)
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Test 2: Request with invalid API key" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

$response = curl -s -w "`n%{http_code}" -H "X-API-Key: invalid-key-12345" "$($ApiEndpoint)health"
$statusCode = $response[-1]
Write-Host "Status Code: $statusCode" -ForegroundColor $(if ($statusCode -eq "403") { "Green" } else { "Red" })

if ($statusCode -eq "403") {
    Write-Host "✓ PASS: Request with invalid API key was rejected" -ForegroundColor Green
} else {
    Write-Host "✗ FAIL: Request with invalid API key should be rejected" -ForegroundColor Red
}

# Test 3: Request with valid API key (should succeed)
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Test 3: Request with valid API key" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

$response = curl -s -i -H "X-API-Key: $ApiKey" "$($ApiEndpoint)health"
Write-Host $response

# Check for rate limit headers
if ($response -match "X-RateLimit-Limit") {
    Write-Host "✓ PASS: Rate limit headers present" -ForegroundColor Green
} else {
    Write-Host "⚠ WARNING: Rate limit headers not found" -ForegroundColor Yellow
}

# Test 4: Create a project with authentication
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Test 4: Create project with authentication" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

$projectData = @{
    name = "Test Project - Auth"
    description = "Testing API authentication"
    project_type = "api"
} | ConvertTo-Json

$response = curl -s -w "`n%{http_code}" -X POST -H "X-API-Key: $ApiKey" -H "Content-Type: application/json" -d $projectData "$($ApiEndpoint)api/projects"
$statusCode = $response[-1]
Write-Host "Status Code: $statusCode" -ForegroundColor $(if ($statusCode -eq "201") { "Green" } else { "Red" })

if ($statusCode -eq "201") {
    Write-Host "✓ PASS: Project created successfully with authentication" -ForegroundColor Green
    Write-Host $response[0..($response.Length-2)] -join "`n"
} else {
    Write-Host "✗ FAIL: Project creation failed" -ForegroundColor Red
    Write-Host $response[0..($response.Length-2)] -join "`n"
}

# Test 5: Check CloudWatch logs for authentication logging
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Test 5: Verify authentication logging" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "Checking CloudWatch logs for authentication attempts..." -ForegroundColor White
$logGroup = "/aws/lambda/agenticai-api-handler-prod"
$recentLogs = aws logs tail $logGroup --since 5m --format short 2>$null | Select-String "Authentication attempt"

if ($recentLogs) {
    Write-Host "✓ PASS: Authentication logging is working" -ForegroundColor Green
    Write-Host "Recent authentication logs:" -ForegroundColor White
    $recentLogs | Select-Object -First 3 | ForEach-Object { Write-Host $_ }
} else {
    Write-Host "⚠ WARNING: No authentication logs found (may need to wait a moment)" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Authentication Testing Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
