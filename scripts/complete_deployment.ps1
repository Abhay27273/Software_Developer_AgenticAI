# Complete Deployment Script
# This script helps you finish the remaining deployment steps

param(
    [Parameter(Mandatory=$false)]
    [switch]$SetupGitHub = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$SetupMonitoring = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$All = $false
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Complete Your Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Show current status
Write-Host "✅ Already Deployed:" -ForegroundColor Green
Write-Host "  - Backend (Lambda, API Gateway, DynamoDB, SQS, S3)" -ForegroundColor White
Write-Host "  - Frontend (S3 static website)" -ForegroundColor White
Write-Host "  - API Key authentication" -ForegroundColor White
Write-Host "  - WebSocket errors fixed" -ForegroundColor White
Write-Host ""

Write-Host "🔄 What's Left (Optional):" -ForegroundColor Yellow
Write-Host "  1. GitHub CI/CD Automation (5 min)" -ForegroundColor White
Write-Host "  2. CloudWatch Monitoring Dashboard (10 min)" -ForegroundColor White
Write-Host "  3. WebSocket Handler (30-60 min, optional)" -ForegroundColor White
Write-Host "  4. CloudFront + HTTPS (20-30 min, optional)" -ForegroundColor White
Write-Host ""

if (-not $SetupGitHub -and -not $SetupMonitoring -and -not $All) {
    Write-Host "Usage:" -ForegroundColor Cyan
    Write-Host "  .\scripts\complete_deployment.ps1 -SetupGitHub" -ForegroundColor White
    Write-Host "  .\scripts\complete_deployment.ps1 -SetupMonitoring" -ForegroundColor White
    Write-Host "  .\scripts\complete_deployment.ps1 -All" -ForegroundColor White
    Write-Host ""
    Write-Host "Or follow the guides manually:" -ForegroundColor Cyan
    Write-Host "  - GitHub CI/CD: scripts\setup_github_secrets.md" -ForegroundColor White
    Write-Host "  - Monitoring: scripts\setup_monitoring_manual.md" -ForegroundColor White
    Write-Host "  - Full checklist: WHATS_LEFT_CHECKLIST.md" -ForegroundColor White
    Write-Host ""
    exit 0
}

# GitHub CI/CD Setup
if ($SetupGitHub -or $All) {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "1. GitHub CI/CD Setup" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "To enable automated deployments:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Go to your GitHub repository:" -ForegroundColor White
    Write-Host "   https://github.com/YOUR_USERNAME/YOUR_REPO/settings/secrets/actions" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "2. Click 'New repository secret'" -ForegroundColor White
    Write-Host ""
    Write-Host "3. Add these secrets:" -ForegroundColor White
    Write-Host "   Name: AWS_ACCESS_KEY_ID" -ForegroundColor Cyan
    Write-Host "   Value: [Your AWS Access Key]" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   Name: AWS_SECRET_ACCESS_KEY" -ForegroundColor Cyan
    Write-Host "   Value: [Your AWS Secret Key]" -ForegroundColor Gray
    Write-Host ""
    Write-Host "4. Test by pushing code:" -ForegroundColor White
    Write-Host "   git add ." -ForegroundColor Cyan
    Write-Host "   git commit -m 'test: trigger CI/CD'" -ForegroundColor Cyan
    Write-Host "   git push origin main" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "5. Check deployment:" -ForegroundColor White
    Write-Host "   https://github.com/YOUR_USERNAME/YOUR_REPO/actions" -ForegroundColor Cyan
    Write-Host ""
    
    $continue = Read-Host "Have you added the GitHub secrets? (y/n)"
    if ($continue -eq 'y' -or $continue -eq 'Y') {
        Write-Host "✅ GitHub CI/CD setup complete!" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Complete this step later using: scripts\setup_github_secrets.md" -ForegroundColor Yellow
    }
    Write-Host ""
}

# CloudWatch Monitoring Setup
if ($SetupMonitoring -or $All) {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "2. CloudWatch Monitoring Dashboard" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "To create a monitoring dashboard:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Open CloudWatch Console:" -ForegroundColor White
    Write-Host "   https://console.aws.amazon.com/cloudwatch/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "2. Click 'Dashboards' → 'Create dashboard'" -ForegroundColor White
    Write-Host ""
    Write-Host "3. Name: AgenticAI-Production" -ForegroundColor White
    Write-Host ""
    Write-Host "4. Add widgets for:" -ForegroundColor White
    Write-Host "   - API Gateway requests" -ForegroundColor Gray
    Write-Host "   - Lambda invocations & errors" -ForegroundColor Gray
    Write-Host "   - DynamoDB operations" -ForegroundColor Gray
    Write-Host "   - SQS queue depth" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Full guide: scripts\setup_monitoring_manual.md" -ForegroundColor Cyan
    Write-Host ""
    
    $openConsole = Read-Host "Open CloudWatch Console now? (y/n)"
    if ($openConsole -eq 'y' -or $openConsole -eq 'Y') {
        Start-Process "https://console.aws.amazon.com/cloudwatch/"
        Write-Host "✅ CloudWatch Console opened in browser" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Complete this step later using: scripts\setup_monitoring_manual.md" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "✅ Core Deployment: Complete" -ForegroundColor Green
Write-Host "   Your app is live and functional!" -ForegroundColor White
Write-Host ""

Write-Host "🔄 Optional Enhancements:" -ForegroundColor Yellow
Write-Host "   - GitHub CI/CD: See scripts\setup_github_secrets.md" -ForegroundColor White
Write-Host "   - Monitoring: See scripts\setup_monitoring_manual.md" -ForegroundColor White
Write-Host "   - WebSocket: See websocket_handler\README.md" -ForegroundColor White
Write-Host "   - CloudFront: See WHATS_LEFT_CHECKLIST.md" -ForegroundColor White
Write-Host ""

Write-Host "📚 Documentation:" -ForegroundColor Cyan
Write-Host "   - Quick Start: QUICK_START.md" -ForegroundColor White
Write-Host "   - Full Checklist: WHATS_LEFT_CHECKLIST.md" -ForegroundColor White
Write-Host "   - Deployment Summary: docs\DEPLOYMENT_COMPLETE_SUMMARY.md" -ForegroundColor White
Write-Host ""

Write-Host "🌐 Your Live App:" -ForegroundColor Cyan
Write-Host "   http://agenticai-frontend-379929762201.s3-website-us-east-1.amazonaws.com/" -ForegroundColor White
Write-Host ""

Write-Host "🎉 You're production-ready!" -ForegroundColor Green
Write-Host ""
