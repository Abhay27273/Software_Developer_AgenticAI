# Deployment Quick Fix Guide

## Problem: Stuck Deployment (2+ Hours)

If your CloudFormation deployment is stuck on ECS/VPC resources like:
- `WebSocketService`
- `WebSocketALB`
- `WebSocketListener`
- `VPC`, `Subnet`, `InternetGateway`

**You're using the wrong template!**

## Solution: Use Serverless-Only Template

### Step 1: Delete Stuck Stack

```bash
# Via AWS Console
# Go to CloudFormation → Stacks → agenticai-stack → Delete

# OR via CLI
aws cloudformation delete-stack --stack-name agenticai-stack --region us-east-1

# Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name agenticai-stack --region us-east-1
```

### Step 2: Verify Template is Serverless-Only

Your `template.yaml` should:
- ✅ Have ~15-20 resources (not 50+)
- ✅ Include: Lambda, API Gateway, DynamoDB, SQS, S3, IAM
- ❌ NOT include: VPC, ECS, ALB, Fargate, Container

Quick check:
```bash
# Should return nothing
grep -E "VPC|ECS|LoadBalancer|Fargate" template.yaml
```

### Step 3: Clean and Redeploy

```bash
# Clear build cache
rm -rf .aws-sam

# Rebuild
sam build

# Deploy
sam deploy
```

**Expected deployment time: 5-10 minutes** (not 30+ minutes!)

## What Changed?

The simplified template removes:
- VPC and networking (subnets, internet gateway, route tables)
- ECS Fargate cluster and service
- Application Load Balancer
- WebSocket container handler

**Result**: 
- Faster deployment (5-10 min vs 30+ min)
- Simpler architecture
- Lower cost
- Easier to debug

## Do You Need WebSocket Support?

The serverless-only template uses REST API (included). For most use cases, this is sufficient.

If you specifically need WebSocket support, you can:
1. Deploy the serverless-only template first (fast)
2. Add WebSocket handler separately later (optional)

See `websocket_handler/README.md` for separate WebSocket deployment.

## Verification

After successful deployment, verify:

```bash
# Check stack status
aws cloudformation describe-stacks --stack-name agenticai-stack --query 'Stacks[0].StackStatus'
# Should return: CREATE_COMPLETE

# Get API endpoint
aws cloudformation describe-stacks \
    --stack-name agenticai-stack \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text

# Test health endpoint
curl $(aws cloudformation describe-stacks --stack-name agenticai-stack --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text)/health
```

Expected response:
```json
{"status":"healthy","timestamp":"2025-11-26T..."}
```

## Next Steps

Continue with the deployment guide at **Step 4: Verification**:
- Test API endpoints
- Verify Lambda functions
- Check DynamoDB table
- Run integration tests

See `docs/AWS_DEPLOYMENT_GUIDE.md` for complete instructions.
