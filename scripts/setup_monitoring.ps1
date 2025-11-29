# CloudWatch Monitoring Setup - Quick Start Script
# This script sets up CloudWatch monitoring for AgenticAI production system

param(
    [string]$Region = "us-east-1",
    [string]$StackName = "agenticai-stack"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CloudWatch Monitoring Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Region: $Region"
Write-Host "  Stack Name: $StackName"
Write-Host ""

# Check if Python is available
Write-Host "Checking prerequisites..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✓ Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python not found. Please install Python 3.8+" -ForegroundColor Red
    exit 1
}

# Check if boto3 is installed
Write-Host "  Checking boto3..." -ForegroundColor Yellow
$boto3Check = python -c "import boto3; print(boto3.__version__)" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ boto3: $boto3Check" -ForegroundColor Green
} else {
    Write-Host "  ✗ boto3 not found. Installing..." -ForegroundColor Yellow
    pip install boto3
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ✗ Failed to install boto3" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ boto3 installed" -ForegroundColor Green
}

# Check AWS credentials
Write-Host "  Checking AWS credentials..." -ForegroundColor Yellow
$awsCheck = aws sts get-caller-identity 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ AWS credentials configured" -ForegroundColor Green
} else {
    Write-Host "  ✗ AWS credentials not configured" -ForegroundColor Red
    Write-Host "    Run: aws configure" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 1: Creating CloudWatch Dashboard" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

python scripts/setup_cloudwatch_dashboard.py $Region $StackName

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "✗ Dashboard creation failed" -ForegroundColor Red
    Write-Host "  Check the error messages above" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 2: Verifying Dashboard" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

python scripts/test_cloudwatch_dashboard.py $Region

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "⚠ Dashboard verification had issues" -ForegroundColor Yellow
    Write-Host "  The dashboard may still work, check AWS Console" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "✓ Monitoring Setup Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. View dashboard in AWS Console" -ForegroundColor White
Write-Host "     https://$Region.console.aws.amazon.com/cloudwatch/home?region=$Region#dashboards:name=AgenticAI-Production" -ForegroundColor Cyan
Write-Host ""
Write-Host "  2. Trigger some API requests to generate metrics" -ForegroundColor White
Write-Host ""
Write-Host "  3. Proceed to Task 2: Implement error alerting" -ForegroundColor White
Write-Host "     See: .kiro/specs/production-hardening/tasks.md" -ForegroundColor Cyan
Write-Host ""
Write-Host "Documentation:" -ForegroundColor Yellow
Write-Host "  - Setup Guide: docs/CLOUDWATCH_DASHBOARD_SETUP.md" -ForegroundColor Cyan
Write-Host "  - Script README: scripts/README_CLOUDWATCH.md" -ForegroundColor Cyan
Write-Host ""
