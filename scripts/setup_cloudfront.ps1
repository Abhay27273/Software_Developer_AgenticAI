# CloudFront + HTTPS Setup Script
# This script helps you set up CloudFront distribution for your S3 website

param(
    [Parameter(Mandatory=$false)]
    [string]$BucketName = "agenticai-frontend-379929762201",
    
    [Parameter(Mandatory=$false)]
    [string]$CustomDomain = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun = $false
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CloudFront + HTTPS Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$Region = "us-east-1"
$S3WebsiteEndpoint = "$BucketName.s3-website-$Region.amazonaws.com"

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  S3 Bucket: $BucketName" -ForegroundColor White
Write-Host "  S3 Website: http://$S3WebsiteEndpoint" -ForegroundColor White
Write-Host "  Region: $Region" -ForegroundColor White

if ($CustomDomain) {
    Write-Host "  Custom Domain: $CustomDomain" -ForegroundColor White
} else {
    Write-Host "  Custom Domain: None (will use CloudFront domain)" -ForegroundColor White
}
Write-Host ""

# Check if AWS CLI is available
try {
    $awsVersion = aws --version 2>&1
    Write-Host "✓ AWS CLI: $awsVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: AWS CLI not installed" -ForegroundColor Red
    Write-Host "Install from: https://aws.amazon.com/cli/" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

if ($DryRun) {
    Write-Host "🔍 DRY RUN MODE - No changes will be made" -ForegroundColor Yellow
    Write-Host ""
}

# Step 1: Create CloudFront Origin Access Identity (OAI)
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 1: Create Origin Access Identity" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Creating CloudFront Origin Access Identity..." -ForegroundColor Yellow

if (-not $DryRun) {
    try {
        $oaiResult = aws cloudfront create-cloud-front-origin-access-identity `
            --cloud-front-origin-access-identity-config `
            "CallerReference=$(Get-Date -Format 'yyyyMMddHHmmss'),Comment=OAI for AgenticAI S3 bucket" `
            --output json 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            $oai = $oaiResult | ConvertFrom-Json
            $oaiId = $oai.CloudFrontOriginAccessIdentity.Id
            Write-Host "✓ OAI Created: $oaiId" -ForegroundColor Green
        } else {
            Write-Host "⚠️ OAI might already exist or error occurred" -ForegroundColor Yellow
            Write-Host "Continuing with manual setup..." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠️ Error creating OAI: $_" -ForegroundColor Yellow
        Write-Host "You may need to create it manually in AWS Console" -ForegroundColor Yellow
    }
} else {
    Write-Host "Would create Origin Access Identity" -ForegroundColor Gray
}

Write-Host ""

# Step 2: Create CloudFront Distribution Configuration
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 2: Create Distribution Config" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$distributionConfig = @"
{
  "CallerReference": "agenticai-$(Get-Date -Format 'yyyyMMddHHmmss')",
  "Comment": "AgenticAI Frontend Distribution",
  "Enabled": true,
  "DefaultRootObject": "index.html",
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "S3-$BucketName",
        "DomainName": "$S3WebsiteEndpoint",
        "CustomOriginConfig": {
          "HTTPPort": 80,
          "HTTPSPort": 443,
          "OriginProtocolPolicy": "http-only"
        }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-$BucketName",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {
      "Quantity": 2,
      "Items": ["GET", "HEAD"],
      "CachedMethods": {
        "Quantity": 2,
        "Items": ["GET", "HEAD"]
      }
    },
    "ForwardedValues": {
      "QueryString": false,
      "Cookies": {
        "Forward": "none"
      }
    },
    "MinTTL": 0,
    "DefaultTTL": 86400,
    "MaxTTL": 31536000,
    "Compress": true
  },
  "CustomErrorResponses": {
    "Quantity": 1,
    "Items": [
      {
        "ErrorCode": 404,
        "ResponsePagePath": "/index.html",
        "ResponseCode": "200",
        "ErrorCachingMinTTL": 300
      }
    ]
  },
  "PriceClass": "PriceClass_100",
  "ViewerCertificate": {
    "CloudFrontDefaultCertificate": true
  }
}
"@

$configFile = "cloudfront-config.json"
$distributionConfig | Out-File -FilePath $configFile -Encoding UTF8

Write-Host "✓ Distribution config created: $configFile" -ForegroundColor Green
Write-Host ""

# Step 3: Instructions for manual setup
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 3: Create CloudFront Distribution" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Due to CloudFront complexity, please complete setup in AWS Console:" -ForegroundColor Yellow
Write-Host ""

Write-Host "1. Open CloudFront Console:" -ForegroundColor White
Write-Host "   https://console.aws.amazon.com/cloudfront/" -ForegroundColor Cyan
Write-Host ""

Write-Host "2. Click 'Create Distribution'" -ForegroundColor White
Write-Host ""

Write-Host "3. Configure Origin:" -ForegroundColor White
Write-Host "   - Origin Domain: $S3WebsiteEndpoint" -ForegroundColor Cyan
Write-Host "   - Protocol: HTTP only" -ForegroundColor Cyan
Write-Host "   - Name: S3-$BucketName" -ForegroundColor Cyan
Write-Host ""

Write-Host "4. Configure Default Cache Behavior:" -ForegroundColor White
Write-Host "   - Viewer Protocol Policy: Redirect HTTP to HTTPS" -ForegroundColor Cyan
Write-Host "   - Allowed HTTP Methods: GET, HEAD" -ForegroundColor Cyan
Write-Host "   - Cache Policy: CachingOptimized" -ForegroundColor Cyan
Write-Host "   - Compress objects: Yes" -ForegroundColor Cyan
Write-Host ""

Write-Host "5. Configure Settings:" -ForegroundColor White
Write-Host "   - Price Class: Use Only North America and Europe" -ForegroundColor Cyan
Write-Host "   - Default Root Object: index.html" -ForegroundColor Cyan
Write-Host ""

Write-Host "6. Configure Custom Error Responses:" -ForegroundColor White
Write-Host "   - Error Code: 404" -ForegroundColor Cyan
Write-Host "   - Response Page Path: /index.html" -ForegroundColor Cyan
Write-Host "   - HTTP Response Code: 200" -ForegroundColor Cyan
Write-Host ""

if ($CustomDomain) {
    Write-Host "7. Configure Custom Domain (Optional):" -ForegroundColor White
    Write-Host "   - Alternate Domain Names (CNAMEs): $CustomDomain" -ForegroundColor Cyan
    Write-Host "   - SSL Certificate: Request or import certificate" -ForegroundColor Cyan
    Write-Host ""
}

Write-Host "8. Click 'Create Distribution'" -ForegroundColor White
Write-Host ""

Write-Host "⏳ Distribution creation takes 15-20 minutes" -ForegroundColor Yellow
Write-Host ""

$openConsole = Read-Host "Open CloudFront Console now? (y/n)"
if ($openConsole -eq 'y' -or $openConsole -eq 'Y') {
    Start-Process "https://console.aws.amazon.com/cloudfront/"
    Write-Host "✓ CloudFront Console opened in browser" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Next Steps" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "After distribution is created:" -ForegroundColor Yellow
Write-Host ""

Write-Host "1. Get CloudFront Domain:" -ForegroundColor White
Write-Host "   - Copy the 'Distribution domain name' (e.g., d1234abcd.cloudfront.net)" -ForegroundColor Cyan
Write-Host ""

Write-Host "2. Test HTTPS Access:" -ForegroundColor White
Write-Host "   https://YOUR_DISTRIBUTION.cloudfront.net" -ForegroundColor Cyan
Write-Host ""

Write-Host "3. Update API Calls (if needed):" -ForegroundColor White
Write-Host "   - Update CORS in API Gateway to allow CloudFront domain" -ForegroundColor Cyan
Write-Host ""

if ($CustomDomain) {
    Write-Host "4. Configure DNS:" -ForegroundColor White
    Write-Host "   - Add CNAME record: $CustomDomain → YOUR_DISTRIBUTION.cloudfront.net" -ForegroundColor Cyan
    Write-Host ""
}

Write-Host "📚 Full guide: docs/CLOUDFRONT_SETUP_GUIDE.md" -ForegroundColor Cyan
Write-Host ""

Write-Host "🎉 Setup instructions complete!" -ForegroundColor Green
Write-Host ""
