# Upload Frontend to S3
# This script uploads the updated index.html with API key to your S3 bucket

param(
    [Parameter(Mandatory=$false)]
    [string]$BucketName = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun = $false
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Frontend S3 Upload Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get bucket name if not provided
if ([string]::IsNullOrEmpty($BucketName)) {
    Write-Host "Enter your S3 bucket name (e.g., my-agenticai-frontend):" -ForegroundColor Yellow
    $BucketName = Read-Host
}

# Validate bucket name
if ([string]::IsNullOrEmpty($BucketName)) {
    Write-Host "❌ Error: Bucket name is required" -ForegroundColor Red
    exit 1
}

Write-Host "📦 Bucket: $BucketName" -ForegroundColor Green
Write-Host ""

# Check if index.html exists
$indexPath = "templates/index.html"
if (-not (Test-Path $indexPath)) {
    Write-Host "❌ Error: $indexPath not found" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Found: $indexPath" -ForegroundColor Green

# Check if AWS CLI is installed
try {
    $awsVersion = aws --version 2>&1
    Write-Host "✓ AWS CLI: $awsVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: AWS CLI not installed" -ForegroundColor Red
    Write-Host "Install from: https://aws.amazon.com/cli/" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Dry run mode
if ($DryRun) {
    Write-Host "🔍 DRY RUN MODE - No files will be uploaded" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Would upload:" -ForegroundColor Cyan
    Write-Host "  $indexPath → s3://$BucketName/index.html" -ForegroundColor White
    Write-Host ""
    Write-Host "Run without -DryRun to actually upload" -ForegroundColor Yellow
    exit 0
}

# Confirm upload
Write-Host "Ready to upload index.html to S3" -ForegroundColor Cyan
Write-Host "  Source: $indexPath" -ForegroundColor White
Write-Host "  Destination: s3://$BucketName/index.html" -ForegroundColor White
Write-Host ""
$confirm = Read-Host "Continue? (y/n)"

if ($confirm -ne 'y' -and $confirm -ne 'Y') {
    Write-Host "❌ Upload cancelled" -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "📤 Uploading to S3..." -ForegroundColor Cyan

# Upload with proper content type and cache control
aws s3 cp $indexPath "s3://$BucketName/index.html" `
    --content-type "text/html" `
    --cache-control "no-cache, no-store, must-revalidate" `
    --metadata-directive REPLACE

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Upload successful!" -ForegroundColor Green
    Write-Host ""
    
    # Get bucket website endpoint
    Write-Host "🌐 Getting website endpoint..." -ForegroundColor Cyan
    $websiteConfig = aws s3api get-bucket-website --bucket $BucketName 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        $endpoint = "http://$BucketName.s3-website-us-east-1.amazonaws.com"
        Write-Host "✓ Website URL: $endpoint" -ForegroundColor Green
        Write-Host ""
        Write-Host "🎉 Frontend deployed successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Cyan
        Write-Host "  1. Open: $endpoint" -ForegroundColor White
        Write-Host "  2. Open browser DevTools (F12) → Network tab" -ForegroundColor White
        Write-Host "  3. Verify 'x-api-key' header is present in API requests" -ForegroundColor White
    } else {
        Write-Host "⚠️ Upload successful, but couldn't get website endpoint" -ForegroundColor Yellow
        Write-Host "Check your S3 bucket configuration" -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ Upload failed" -ForegroundColor Red
    Write-Host "Check AWS credentials and bucket permissions" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Upload Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
