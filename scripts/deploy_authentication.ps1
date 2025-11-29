# Deploy API Authentication
# This script deploys the API authentication changes and retrieves the API key

Write-Host "Deploying API Authentication..." -ForegroundColor Cyan

# Build and deploy SAM application
Write-Host "`nBuilding SAM application..." -ForegroundColor Yellow
sam build

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`nDeploying to AWS..." -ForegroundColor Yellow
sam deploy --no-confirm-changeset

if ($LASTEXITCODE -ne 0) {
    Write-Host "Deployment failed!" -ForegroundColor Red
    exit 1
}

# Get stack outputs
Write-Host "`nRetrieving stack outputs..." -ForegroundColor Yellow
$stackName = "agenticai-stack"
$outputs = aws cloudformation describe-stacks --stack-name $stackName --query "Stacks[0].Outputs" --output json | ConvertFrom-Json

# Extract API endpoint and API key ID
$apiEndpoint = ($outputs | Where-Object { $_.OutputKey -eq "ApiEndpoint" }).OutputValue
$apiKeyId = ($outputs | Where-Object { $_.OutputKey -eq "ApiKeyId" }).OutputValue

Write-Host "`nAPI Endpoint: $apiEndpoint" -ForegroundColor Green

# Retrieve the actual API key value
Write-Host "`nRetrieving API key value..." -ForegroundColor Yellow
$apiKeyValue = aws apigateway get-api-key --api-key $apiKeyId --include-value --query "value" --output text

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "API Authentication Deployed Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nAPI Endpoint: $apiEndpoint" -ForegroundColor White
Write-Host "API Key ID: $apiKeyId" -ForegroundColor White
Write-Host "API Key Value: $apiKeyValue" -ForegroundColor Yellow
Write-Host "`nIMPORTANT: Save the API key value securely!" -ForegroundColor Red
Write-Host "`nTo test the API with authentication:" -ForegroundColor Cyan
Write-Host "curl -H `"X-API-Key: $apiKeyValue`" $apiEndpoint/health" -ForegroundColor White

# Save API key to .env file for local testing
Write-Host "`nSaving API key to .env file..." -ForegroundColor Yellow
$envFile = ".env"
$envContent = Get-Content $envFile -Raw

if ($envContent -match "API_KEY=") {
    $envContent = $envContent -replace "API_KEY=.*", "API_KEY=$apiKeyValue"
} else {
    $envContent += "`nAPI_KEY=$apiKeyValue"
}

Set-Content -Path $envFile -Value $envContent
Write-Host "API key saved to .env file" -ForegroundColor Green

Write-Host "`nDeployment complete!" -ForegroundColor Green
