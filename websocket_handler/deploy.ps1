# Deployment script for WebSocket Handler to ECS Fargate (PowerShell)

param(
    [string]$Environment = "prod",
    [string]$AwsRegion = $env:AWS_REGION ?? "us-east-1"
)

$ErrorActionPreference = "Stop"

$StackName = "agenticai-stack"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "WebSocket Handler Deployment" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor Cyan
Write-Host "Region: $AwsRegion" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Get ECR repository URI from CloudFormation stack
Write-Host "Getting ECR repository URI..." -ForegroundColor Yellow
$RepositoryUri = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query "Stacks[0].Outputs[?OutputKey=='WebSocketRepositoryUri'].OutputValue" `
    --output text `
    --region $AwsRegion

if ([string]::IsNullOrEmpty($RepositoryUri)) {
    Write-Host "Error: Could not get ECR repository URI from stack" -ForegroundColor Red
    exit 1
}

Write-Host "Repository URI: $RepositoryUri" -ForegroundColor Green

# Login to ECR
Write-Host "Logging in to ECR..." -ForegroundColor Yellow
$LoginPassword = aws ecr get-login-password --region $AwsRegion
$LoginPassword | docker login --username AWS --password-stdin $RepositoryUri

# Build Docker image
Write-Host "Building Docker image..." -ForegroundColor Yellow
docker build -t agenticai-websocket:latest .

# Tag image
Write-Host "Tagging image..." -ForegroundColor Yellow
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
docker tag agenticai-websocket:latest "${RepositoryUri}:latest"
docker tag agenticai-websocket:latest "${RepositoryUri}:${Timestamp}"

# Push image to ECR
Write-Host "Pushing image to ECR..." -ForegroundColor Yellow
docker push "${RepositoryUri}:latest"
docker push "${RepositoryUri}:${Timestamp}"

# Update ECS service to use new image
Write-Host "Updating ECS service..." -ForegroundColor Yellow
$ClusterName = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query "Stacks[0].Outputs[?OutputKey=='ECSClusterName'].OutputValue" `
    --output text `
    --region $AwsRegion

$ServiceName = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query "Stacks[0].Outputs[?OutputKey=='WebSocketServiceName'].OutputValue" `
    --output text `
    --region $AwsRegion

aws ecs update-service `
    --cluster $ClusterName `
    --service $ServiceName `
    --force-new-deployment `
    --region $AwsRegion

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host "Cluster: $ClusterName" -ForegroundColor Cyan
Write-Host "Service: $ServiceName" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Get WebSocket endpoint
$WebSocketEndpoint = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query "Stacks[0].Outputs[?OutputKey=='WebSocketEndpoint'].OutputValue" `
    --output text `
    --region $AwsRegion

Write-Host "WebSocket Endpoint: $WebSocketEndpoint" -ForegroundColor Green
Write-Host ""
Write-Host "Monitor deployment status:" -ForegroundColor Yellow
Write-Host "aws ecs describe-services --cluster $ClusterName --services $ServiceName --region $AwsRegion" -ForegroundColor White
