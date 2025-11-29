#!/usr/bin/env pwsh
# Script to set up API Gateway CloudWatch Logs role (one-time setup per AWS account)

$Region = "us-east-1"

Write-Host "Setting up API Gateway CloudWatch Logs role..." -ForegroundColor Yellow
Write-Host ""

# Check if role already exists
$existingRoleArn = aws apigateway get-account --region $Region --query 'cloudwatchRoleArn' --output text 2>$null

if ($existingRoleArn -and $existingRoleArn -ne "None" -and $existingRoleArn -ne "") {
    Write-Host "API Gateway CloudWatch Logs role is already configured:" -ForegroundColor Green
    Write-Host "  Role ARN: $existingRoleArn" -ForegroundColor White
    Write-Host ""
    Write-Host "You can now deploy your stack with: sam deploy" -ForegroundColor Cyan
    exit 0
}

Write-Host "Creating IAM role for API Gateway CloudWatch Logs..." -ForegroundColor Yellow

# Create trust policy file with proper JSON
@'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "",
      "Effect": "Allow",
      "Principal": {
        "Service": "apigateway.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
'@ | Out-File -FilePath "api-gateway-trust-policy.json" -Encoding ASCII -NoNewline

try {
    # Create the IAM role
    Write-Host "Creating IAM role 'APIGatewayCloudWatchLogsRole'..." -ForegroundColor Yellow
    $roleOutput = aws iam create-role `
        --role-name APIGatewayCloudWatchLogsRole `
        --assume-role-policy-document file://api-gateway-trust-policy.json `
        --description "Allows API Gateway to push logs to CloudWatch Logs" 2>&1

    if ($LASTEXITCODE -ne 0) {
        if ($roleOutput -like "*EntityAlreadyExists*") {
            Write-Host "Role already exists, retrieving ARN..." -ForegroundColor Yellow
            $roleArn = aws iam get-role --role-name APIGatewayCloudWatchLogsRole --query 'Role.Arn' --output text
        } else {
            Write-Host "Error creating role: $roleOutput" -ForegroundColor Red
            exit 1
        }
    } else {
        $roleArn = ($roleOutput | ConvertFrom-Json).Role.Arn
        Write-Host "IAM role created successfully!" -ForegroundColor Green
    }

    Write-Host "Role ARN: $roleArn" -ForegroundColor White

    # Attach the managed policy
    Write-Host "Attaching CloudWatch Logs policy..." -ForegroundColor Yellow
    aws iam attach-role-policy `
        --role-name APIGatewayCloudWatchLogsRole `
        --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs" 2>&1 | Out-Null

    Write-Host "Policy attached successfully!" -ForegroundColor Green

    # Wait a moment for IAM to propagate
    Write-Host "Waiting for IAM role to propagate..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10

    # Set the role in API Gateway account settings
    Write-Host "Configuring API Gateway account settings..." -ForegroundColor Yellow
    aws apigateway update-account `
        --region $Region `
        --patch-operations "op=replace,path=/cloudwatchRoleArn,value=$roleArn" | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "SUCCESS! API Gateway CloudWatch Logs role configured!" -ForegroundColor Green
        Write-Host "  Role ARN: $roleArn" -ForegroundColor White
        Write-Host ""
        Write-Host "You can now deploy your stack with: sam deploy" -ForegroundColor Cyan
    } else {
        Write-Host ""
        Write-Host "Failed to update API Gateway account settings." -ForegroundColor Red
        Write-Host "You may need to manually set the role ARN in the AWS Console:" -ForegroundColor Yellow
        Write-Host "  1. Go to API Gateway console" -ForegroundColor White
        Write-Host "  2. Click 'Settings' in the left menu" -ForegroundColor White
        Write-Host "  3. Enter this ARN in 'CloudWatch log role ARN': $roleArn" -ForegroundColor White
    }
}
finally {
    # Clean up temp file
    if (Test-Path "api-gateway-trust-policy.json") {
        Remove-Item "api-gateway-trust-policy.json"
    }
}
