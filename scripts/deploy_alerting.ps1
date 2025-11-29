# Deploy Alerting Infrastructure
# This script deploys the SNS topic and CloudWatch alarms for error alerting

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AgenticAI - Deploy Alerting System" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if AWS CLI is installed
Write-Host "Checking AWS CLI..." -ForegroundColor Yellow
try {
    $awsVersion = aws --version 2>&1
    Write-Host "✓ AWS CLI found: $awsVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ AWS CLI not found. Please install AWS CLI first." -ForegroundColor Red
    exit 1
}

# Check if SAM CLI is installed
Write-Host "Checking SAM CLI..." -ForegroundColor Yellow
try {
    $samVersion = sam --version 2>&1
    Write-Host "✓ SAM CLI found: $samVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ SAM CLI not found. Please install SAM CLI first." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Building SAM application..." -ForegroundColor Yellow
sam build

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Build failed" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Build successful" -ForegroundColor Green
Write-Host ""

Write-Host "Deploying to AWS..." -ForegroundColor Yellow
Write-Host "This will create/update:" -ForegroundColor Cyan
Write-Host "  - SNS Topic: agenticai-alerts-prod" -ForegroundColor White
Write-Host "  - CloudWatch Alarms for Lambda errors" -ForegroundColor White
Write-Host "  - CloudWatch Alarms for API Gateway errors" -ForegroundColor White
Write-Host ""

sam deploy --no-confirm-changeset

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Deployment failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✓ Deployment successful!" -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Next Steps" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Check your email for SNS subscription confirmation" -ForegroundColor Yellow
Write-Host "2. Click the confirmation link in the email" -ForegroundColor Yellow
Write-Host "3. Run the test script to verify alerts:" -ForegroundColor Yellow
Write-Host "   python scripts/test_alerting.py" -ForegroundColor White
Write-Host ""
