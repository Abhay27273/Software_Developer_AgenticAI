# Complete ECS Deployment Script for WebSocket Handler
# This script deploys the WebSocket handler to AWS ECS Fargate

param(
    [string]$Environment = "prod",
    [string]$AwsRegion = "us-east-1",
    [string]$StackName = "agenticai-websocket-stack"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "WebSocket Handler - ECS Deployment" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor Cyan
Write-Host "Region: $AwsRegion" -ForegroundColor Cyan
Write-Host "Stack: $StackName" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Step 1: Get parameters from main stack
Write-Host "`n[1/6] Getting parameters from main stack..." -ForegroundColor Yellow

$mainStackName = "agenticai-stack"
$outputs = aws cloudformation describe-stacks --stack-name $mainStackName --query "Stacks[0].Outputs" --output json | ConvertFrom-Json

$dataTableName = ($outputs | Where-Object { $_.OutputKey -eq "DataTableName" }).OutputValue
$pmQueueUrl = ($outputs | Where-Object { $_.OutputKey -eq "PMQueueUrl" }).OutputValue
$devQueueUrl = ($outputs | Where-Object { $_.OutputKey -eq "DevQueueUrl" }).OutputValue
$qaQueueUrl = ($outputs | Where-Object { $_.OutputKey -eq "QAQueueUrl" }).OutputValue
$opsQueueUrl = ($outputs | Where-Object { $_.OutputKey -eq "OpsQueueUrl" }).OutputValue

Write-Host "  DynamoDB Table: $dataTableName" -ForegroundColor Green
Write-Host "  PM Queue: $pmQueueUrl" -ForegroundColor Green
Write-Host "  Dev Queue: $devQueueUrl" -ForegroundColor Green
Write-Host "  QA Queue: $qaQueueUrl" -ForegroundColor Green
Write-Host "  Ops Queue: $opsQueueUrl" -ForegroundColor Green

# Step 2: Get VPC and Subnet information
Write-Host "`n[2/6] Getting VPC and Subnet information..." -ForegroundColor Yellow

# Get default VPC
$vpcId = aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text

if ([string]::IsNullOrEmpty($vpcId)) {
    Write-Host "  No default VPC found. Getting first available VPC..." -ForegroundColor Yellow
    $vpcId = aws ec2 describe-vpcs --query "Vpcs[0].VpcId" --output text
}

Write-Host "  VPC ID: $vpcId" -ForegroundColor Green

# Get subnets (need at least 2 for ALB)
$subnets = aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpcId" --query "Subnets[*].SubnetId" --output json | ConvertFrom-Json

if ($subnets.Count -lt 2) {
    Write-Host "  Error: Need at least 2 subnets for ALB" -ForegroundColor Red
    exit 1
}

$subnetIds = $subnets[0..1] -join ","
Write-Host "  Subnet IDs: $subnetIds" -ForegroundColor Green

# Step 3: Deploy CloudFormation stack
Write-Host "`n[3/6] Deploying CloudFormation stack..." -ForegroundColor Yellow

$templateFile = "ecs-template.yaml"

aws cloudformation deploy `
    --template-file $templateFile `
    --stack-name $StackName `
    --parameter-overrides `
        Environment=$Environment `
        VpcId=$vpcId `
        SubnetIds=$subnetIds `
        DataTableName=$dataTableName `
        PMQueueUrl=$pmQueueUrl `
        DevQueueUrl=$devQueueUrl `
        QAQueueUrl=$qaQueueUrl `
        OpsQueueUrl=$opsQueueUrl `
    --capabilities CAPABILITY_NAMED_IAM `
    --region $AwsRegion

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Error: CloudFormation deployment failed" -ForegroundColor Red
    exit 1
}

Write-Host "  CloudFormation stack deployed successfully" -ForegroundColor Green

# Step 4: Get ECR repository URI
Write-Host "`n[4/6] Getting ECR repository URI..." -ForegroundColor Yellow

$repositoryUri = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query "Stacks[0].Outputs[?OutputKey=='WebSocketRepositoryUri'].OutputValue" `
    --output text `
    --region $AwsRegion

Write-Host "  Repository URI: $repositoryUri" -ForegroundColor Green

# Step 5: Build and push Docker image
Write-Host "`n[5/6] Building and pushing Docker image..." -ForegroundColor Yellow

# Login to ECR
Write-Host "  Logging in to ECR..." -ForegroundColor White
$loginPassword = aws ecr get-login-password --region $AwsRegion
$loginPassword | docker login --username AWS --password-stdin $repositoryUri

# Build image
Write-Host "  Building Docker image..." -ForegroundColor White
docker build -t agenticai-websocket:latest .

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Error: Docker build failed" -ForegroundColor Red
    exit 1
}

# Tag image
Write-Host "  Tagging image..." -ForegroundColor White
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
docker tag agenticai-websocket:latest "${repositoryUri}:latest"
docker tag agenticai-websocket:latest "${repositoryUri}:${timestamp}"

# Push image
Write-Host "  Pushing image to ECR..." -ForegroundColor White
docker push "${repositoryUri}:latest"
docker push "${repositoryUri}:${timestamp}"

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Error: Docker push failed" -ForegroundColor Red
    exit 1
}

Write-Host "  Docker image pushed successfully" -ForegroundColor Green

# Step 6: Update ECS service
Write-Host "`n[6/6] Updating ECS service..." -ForegroundColor Yellow

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

aws ecs update-service `
    --cluster $clusterName `
    --service $serviceName `
    --force-new-deployment `
    --region $AwsRegion | Out-Null

Write-Host "  ECS service updated" -ForegroundColor Green

# Get WebSocket endpoint
$webSocketEndpoint = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query "Stacks[0].Outputs[?OutputKey=='WebSocketEndpoint'].OutputValue" `
    --output text `
    --region $AwsRegion

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Cluster: $clusterName" -ForegroundColor White
Write-Host "Service: $serviceName" -ForegroundColor White
Write-Host "WebSocket Endpoint: $webSocketEndpoint" -ForegroundColor White
Write-Host "`nMonitor deployment:" -ForegroundColor Yellow
Write-Host "  aws ecs describe-services --cluster $clusterName --services $serviceName --region $AwsRegion" -ForegroundColor White
Write-Host "`nView logs:" -ForegroundColor Yellow
Write-Host "  aws logs tail /ecs/agenticai-websocket-$Environment --follow --region $AwsRegion" -ForegroundColor White
Write-Host "`nTest connection:" -ForegroundColor Yellow
Write-Host "  wscat -c $webSocketEndpoint" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor Cyan
