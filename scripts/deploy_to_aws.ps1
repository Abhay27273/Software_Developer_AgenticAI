# AWS Deployment Script for AgenticAI
# This script deploys the complete stack to AWS using SAM CLI

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('dev', 'staging', 'prod')]
    [string]$Environment = 'dev',
    
    [Parameter(Mandatory=$false)]
    [string]$BudgetEmail = '',
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipTests = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$Guided = $false
)

$ErrorActionPreference = "Stop"

# Color output functions
function Write-Success { param($Message) Write-Host $Message -ForegroundColor Green }
function Write-Info { param($Message) Write-Host $Message -ForegroundColor Cyan }
function Write-Warning { param($Message) Write-Host $Message -ForegroundColor Yellow }
function Write-Error { param($Message) Write-Host $Message -ForegroundColor Red }

Write-Info "========================================="
Write-Info "AgenticAI AWS Deployment Script"
Write-Info "Environment: $Environment"
Write-Info "========================================="

# Check prerequisites
Write-Info "`nChecking prerequisites..."

# Check AWS CLI
try {
    $awsVersion = aws --version 2>&1
    Write-Success "✓ AWS CLI installed: $awsVersion"
} catch {
    Write-Error "✗ AWS CLI not found. Please install AWS CLI first."
    exit 1
}

# Check SAM CLI
try {
    $samVersion = sam --version 2>&1
    Write-Success "✓ SAM CLI installed: $samVersion"
} catch {
    Write-Error "✗ SAM CLI not found. Please install SAM CLI first."
    Write-Info "Install with: pip install aws-sam-cli"
    exit 1
}

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Success "✓ Python installed: $pythonVersion"
} catch {
    Write-Error "✗ Python not found. Please install Python 3.11 or higher."
    exit 1
}

# Check Docker (required for SAM build)
try {
    $dockerVersion = docker --version 2>&1
    Write-Success "✓ Docker installed: $dockerVersion"
} catch {
    Write-Warning "✗ Docker not found. SAM build may fail without Docker."
}

# Verify AWS credentials
Write-Info "`nVerifying AWS credentials..."
try {
    $identity = aws sts get-caller-identity --output json | ConvertFrom-Json
    Write-Success "✓ AWS credentials configured"
    Write-Info "  Account: $($identity.Account)"
    Write-Info "  User: $($identity.Arn)"
} catch {
    Write-Error "✗ AWS credentials not configured. Run 'aws configure' first."
    exit 1
}

# Get budget email if not provided
if ([string]::IsNullOrEmpty($BudgetEmail)) {
    $BudgetEmail = Read-Host "Enter email address for budget alerts"
    if ([string]::IsNullOrEmpty($BudgetEmail)) {
        Write-Error "Budget email is required."
        exit 1
    }
}

# Validate email format
if ($BudgetEmail -notmatch '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$') {
    Write-Error "Invalid email address format."
    exit 1
}

# Run tests unless skipped
if (-not $SkipTests) {
    Write-Info "`nRunning tests..."
    try {
        python -m pytest tests/test_lambda_api_handler.py tests/test_lambda_agent_workers.py -v
        Write-Success "✓ Tests passed"
    } catch {
        Write-Error "✗ Tests failed. Fix tests before deploying."
        Write-Info "Use -SkipTests flag to skip tests (not recommended)."
        exit 1
    }
} else {
    Write-Warning "⚠ Skipping tests (not recommended for production)"
}

# Build SAM application unless skipped
if (-not $SkipBuild) {
    Write-Info "`nBuilding SAM application..."
    try {
        sam build --template template.yaml
        Write-Success "✓ SAM build completed"
    } catch {
        Write-Error "✗ SAM build failed"
        exit 1
    }
} else {
    Write-Warning "⚠ Skipping build (using existing .aws-sam directory)"
}

# Deploy to AWS
Write-Info "`nDeploying to AWS..."
$stackName = "agenticai-stack-$Environment"

if ($Guided) {
    Write-Info "Running guided deployment..."
    sam deploy --guided `
        --stack-name $stackName `
        --parameter-overrides "Environment=$Environment BudgetAlertEmail=$BudgetEmail" `
        --capabilities CAPABILITY_NAMED_IAM `
        --region us-east-1
} else {
    Write-Info "Running automated deployment..."
    
    # Check if samconfig.toml exists
    if (-not (Test-Path "samconfig.toml")) {
        Write-Warning "samconfig.toml not found. Running guided deployment..."
        sam deploy --guided `
            --stack-name $stackName `
            --parameter-overrides "Environment=$Environment BudgetAlertEmail=$BudgetEmail" `
            --capabilities CAPABILITY_NAMED_IAM `
            --region us-east-1
    } else {
        sam deploy `
            --stack-name $stackName `
            --parameter-overrides "Environment=$Environment BudgetAlertEmail=$BudgetEmail" `
            --capabilities CAPABILITY_NAMED_IAM `
            --region us-east-1 `
            --no-confirm-changeset `
            --no-fail-on-empty-changeset
    }
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "✗ Deployment failed"
    exit 1
}

Write-Success "`n✓ Deployment completed successfully!"

# Get stack outputs
Write-Info "`nRetrieving stack outputs..."
try {
    $outputs = aws cloudformation describe-stacks `
        --stack-name $stackName `
        --query 'Stacks[0].Outputs' `
        --output json | ConvertFrom-Json
    
    Write-Success "`nStack Outputs:"
    Write-Success "=============="
    foreach ($output in $outputs) {
        Write-Info "$($output.OutputKey): $($output.OutputValue)"
    }
    
    # Save outputs to file
    $outputsFile = "deployment-outputs-$Environment.json"
    $outputs | ConvertTo-Json -Depth 10 | Out-File $outputsFile
    Write-Info "`nOutputs saved to: $outputsFile"
    
} catch {
    Write-Warning "Could not retrieve stack outputs"
}

# Next steps
Write-Info "`n========================================="
Write-Info "Next Steps:"
Write-Info "========================================="
Write-Info "1. Set up Parameter Store secrets:"
Write-Info "   python scripts/setup_parameter_store.py --environment $Environment"
Write-Info ""
Write-Info "2. Build and deploy WebSocket handler:"
Write-Info "   cd websocket_handler"
Write-Info "   .\deploy.ps1 -Environment $Environment"
Write-Info ""
Write-Info "3. Run integration tests:"
Write-Info "   python scripts/run_integration_tests.py --environment $Environment"
Write-Info ""
Write-Info "4. Monitor deployment:"
Write-Info "   - CloudWatch Dashboard: https://console.aws.amazon.com/cloudwatch"
Write-Info "   - Lambda Functions: https://console.aws.amazon.com/lambda"
Write-Info "   - DynamoDB Tables: https://console.aws.amazon.com/dynamodb"
Write-Info "========================================="

Write-Success "`n✓ Deployment script completed!"
