#!/usr/bin/env pwsh
# Script to delete a stack in ROLLBACK_COMPLETE state and redeploy

$StackName = "agenticai-stack"
$Region = "us-east-1"

Write-Host "Checking stack status..." -ForegroundColor Yellow
$stackStatus = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query 'Stacks[0].StackStatus' --output text 2>$null

if ($stackStatus -eq "ROLLBACK_COMPLETE") {
    Write-Host "Stack is in ROLLBACK_COMPLETE state. Deleting..." -ForegroundColor Yellow
    aws cloudformation delete-stack --stack-name $StackName --region $Region
    
    Write-Host "Waiting for stack deletion to complete..." -ForegroundColor Yellow
    aws cloudformation wait stack-delete-complete --stack-name $StackName --region $Region
    
    Write-Host "Stack deleted successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Now you can redeploy with:" -ForegroundColor Cyan
    Write-Host "  sam deploy --guided" -ForegroundColor White
    Write-Host "or" -ForegroundColor Cyan
    Write-Host "  sam deploy" -ForegroundColor White
} elseif ($null -eq $stackStatus) {
    Write-Host "Stack does not exist. You can deploy with:" -ForegroundColor Green
    Write-Host "  sam deploy --guided" -ForegroundColor White
} else {
    Write-Host "Stack is in $stackStatus state." -ForegroundColor Yellow
    Write-Host "This script only handles ROLLBACK_COMPLETE state." -ForegroundColor Yellow
}
