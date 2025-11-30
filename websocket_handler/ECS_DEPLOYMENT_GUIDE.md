# WebSocket Handler - ECS Deployment Guide

## Overview

This guide walks you through deploying the WebSocket handler to AWS ECS Fargate with Application Load Balancer.

## Architecture

```
Internet → ALB (Port 80/443) → ECS Fargate Tasks (Port 8080) → WebSocket Server
                                      ↓
                                  DynamoDB + SQS
```

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **Docker** installed and running
3. **Main AgenticAI stack** deployed (`agenticai-stack`)
4. **VPC with at least 2 subnets** (for ALB)

## Quick Deployment

### Option 1: Automated Deployment (Recommended)

```powershell
cd websocket_handler
.\deploy-ecs.ps1 -Environment prod -AwsRegion us-east-1
```

This script will:
1. Get parameters from main stack
2. Detect VPC and subnets
3. Deploy CloudFormation stack
4. Build and push Docker image
5. Update ECS service

### Option 2: Manual Deployment

#### Step 1: Deploy Infrastructure

```powershell
# Get parameters from main stack
$mainStack = "agenticai-stack"
$outputs = aws cloudformation describe-stacks --stack-name $mainStack --query "Stacks[0].Outputs" --output json | ConvertFrom-Json

$dataTable = ($outputs | Where-Object { $_.OutputKey -eq "DataTableName" }).OutputValue
$pmQueue = ($outputs | Where-Object { $_.OutputKey -eq "PMQueueUrl" }).OutputValue
$devQueue = ($outputs | Where-Object { $_.OutputKey -eq "DevQueueUrl" }).OutputValue
$qaQueue = ($outputs | Where-Object { $_.OutputKey -eq "QAQueueUrl" }).OutputValue
$opsQueue = ($outputs | Where-Object { $_.OutputKey -eq "OpsQueueUrl" }).OutputValue

# Get VPC and Subnets
$vpcId = aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text
$subnets = aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpcId" --query "Subnets[0:2].SubnetId" --output text

# Deploy stack
aws cloudformation deploy `
    --template-file ecs-template.yaml `
    --stack-name agenticai-websocket-stack `
    --parameter-overrides `
        Environment=prod `
        VpcId=$vpcId `
        SubnetIds=$subnets `
        DataTableName=$dataTable `
        PMQueueUrl=$pmQueue `
        DevQueueUrl=$devQueue `
        QAQueueUrl=$qaQueue `
        OpsQueueUrl=$opsQueue `
    --capabilities CAPABILITY_NAMED_IAM `
    --region us-east-1
```

#### Step 2: Build and Push Docker Image

```powershell
# Get ECR repository URI
$repoUri = aws cloudformation describe-stacks `
    --stack-name agenticai-websocket-stack `
    --query "Stacks[0].Outputs[?OutputKey=='WebSocketRepositoryUri'].OutputValue" `
    --output text

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $repoUri

# Build image
docker build -t agenticai-websocket:latest .

# Tag and push
docker tag agenticai-websocket:latest "${repoUri}:latest"
docker push "${repoUri}:latest"
```

#### Step 3: Deploy to ECS

```powershell
# Get cluster and service names
$cluster = aws cloudformation describe-stacks `
    --stack-name agenticai-websocket-stack `
    --query "Stacks[0].Outputs[?OutputKey=='ECSClusterName'].OutputValue" `
    --output text

$service = aws cloudformation describe-stacks `
    --stack-name agenticai-websocket-stack `
    --query "Stacks[0].Outputs[?OutputKey=='WebSocketServiceName'].OutputValue" `
    --output text

# Force new deployment
aws ecs update-service `
    --cluster $cluster `
    --service $service `
    --force-new-deployment
```

## Verification

### 1. Check Service Status

```powershell
aws ecs describe-services `
    --cluster agenticai-cluster-prod `
    --services agenticai-websocket-prod `
    --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

### 2. View Logs

```powershell
# Tail logs in real-time
aws logs tail /ecs/agenticai-websocket-prod --follow

# Get recent logs
aws logs tail /ecs/agenticai-websocket-prod --since 1h
```

### 3. Test WebSocket Connection

Get the endpoint:
```powershell
$endpoint = aws cloudformation describe-stacks `
    --stack-name agenticai-websocket-stack `
    --query "Stacks[0].Outputs[?OutputKey=='WebSocketEndpoint'].OutputValue" `
    --output text

Write-Host "WebSocket Endpoint: $endpoint"
```

Test with wscat:
```bash
npm install -g wscat
wscat -c $endpoint
```

Or use Python:
```python
import asyncio
import websockets
import json

async def test():
    uri = "ws://your-alb-dns/ws"
    async with websockets.connect(uri) as ws:
        # Wait for welcome message
        msg = await ws.recv()
        print(f"Connected: {msg}")
        
        # Send ping
        await ws.send(json.dumps({"action": "ping"}))
        response = await ws.recv()
        print(f"Pong: {response}")

asyncio.run(test())
```

## Configuration

### Environment Variables

The ECS task automatically receives these environment variables:

- `AWS_REGION` - AWS region
- `DYNAMODB_TABLE_NAME` - DynamoDB table name
- `SQS_QUEUE_URL_PM` - PM agent queue URL
- `SQS_QUEUE_URL_DEV` - Dev agent queue URL
- `SQS_QUEUE_URL_QA` - QA agent queue URL
- `SQS_QUEUE_URL_OPS` - Ops agent queue URL
- `WEBSOCKET_PORT` - Port (8080)
- `WEBSOCKET_HOST` - Host (0.0.0.0)

### Scaling Configuration

The service is configured with auto-scaling:

- **Min tasks**: 1
- **Max tasks**: 4
- **Target CPU**: 70%
- **Scale out cooldown**: 60 seconds
- **Scale in cooldown**: 300 seconds

To manually scale:
```powershell
aws ecs update-service `
    --cluster agenticai-cluster-prod `
    --service agenticai-websocket-prod `
    --desired-count 2
```

### Resource Allocation

Current configuration:
- **CPU**: 512 (0.5 vCPU)
- **Memory**: 1024 MB (1 GB)

To modify, update the TaskDefinition in `ecs-template.yaml`:
```yaml
Cpu: '1024'      # 1 vCPU
Memory: '2048'   # 2 GB
```

## Monitoring

### CloudWatch Metrics

View metrics in CloudWatch console or CLI:

```powershell
# CPU Utilization
aws cloudwatch get-metric-statistics `
    --namespace AWS/ECS `
    --metric-name CPUUtilization `
    --dimensions Name=ServiceName,Value=agenticai-websocket-prod Name=ClusterName,Value=agenticai-cluster-prod `
    --start-time (Get-Date).AddHours(-1).ToUniversalTime() `
    --end-time (Get-Date).ToUniversalTime() `
    --period 300 `
    --statistics Average

# Memory Utilization
aws cloudwatch get-metric-statistics `
    --namespace AWS/ECS `
    --metric-name MemoryUtilization `
    --dimensions Name=ServiceName,Value=agenticai-websocket-prod Name=ClusterName,Value=agenticai-cluster-prod `
    --start-time (Get-Date).AddHours(-1).ToUniversalTime() `
    --end-time (Get-Date).ToUniversalTime() `
    --period 300 `
    --statistics Average
```

### CloudWatch Alarms

The stack creates these alarms:
- **High CPU**: Triggers when CPU > 80% for 10 minutes
- **High Memory**: Triggers when memory > 80% for 10 minutes

### Container Insights

Container Insights is enabled on the cluster. View detailed metrics in CloudWatch console:
1. Go to CloudWatch → Container Insights
2. Select ECS Clusters
3. Choose `agenticai-cluster-prod`

## Troubleshooting

### Service Won't Start

**Check task status:**
```powershell
$tasks = aws ecs list-tasks --cluster agenticai-cluster-prod --service-name agenticai-websocket-prod --query 'taskArns[0]' --output text
aws ecs describe-tasks --cluster agenticai-cluster-prod --tasks $tasks
```

**Common issues:**
1. **Image pull error**: Verify ECR repository exists and has images
2. **Environment variables**: Check task definition has correct values
3. **IAM permissions**: Verify task role has DynamoDB and SQS permissions
4. **Security groups**: Ensure ECS security group allows traffic from ALB

### Health Checks Failing

**Check ALB target health:**
```powershell
$tgArn = aws cloudformation describe-stacks `
    --stack-name agenticai-websocket-stack `
    --query "Stacks[0].Resources[?LogicalResourceId=='TargetGroup'].PhysicalResourceId" `
    --output text

aws elbv2 describe-target-health --target-group-arn $tgArn
```

**Common issues:**
1. **Port mismatch**: Verify container port 8080 matches target group
2. **Health check path**: Ensure `/health` endpoint responds with 200
3. **Security group**: Check ECS security group allows traffic from ALB on port 8080

### Connection Issues

**Test from within VPC:**
```powershell
# Get task private IP
$taskArn = aws ecs list-tasks --cluster agenticai-cluster-prod --service-name agenticai-websocket-prod --query 'taskArns[0]' --output text
$taskDetails = aws ecs describe-tasks --cluster agenticai-cluster-prod --tasks $taskArn --query 'tasks[0].attachments[0].details' --output json | ConvertFrom-Json
$privateIp = ($taskDetails | Where-Object { $_.name -eq "privateIPv4Address" }).value

# Test connection (from EC2 instance in same VPC)
curl http://${privateIp}:8080/health
```

### High Memory Usage

**Check memory metrics:**
```powershell
aws cloudwatch get-metric-statistics `
    --namespace AWS/ECS `
    --metric-name MemoryUtilization `
    --dimensions Name=ServiceName,Value=agenticai-websocket-prod Name=ClusterName,Value=agenticai-cluster-prod `
    --start-time (Get-Date).AddHours(-1).ToUniversalTime() `
    --end-time (Get-Date).ToUniversalTime() `
    --period 60 `
    --statistics Maximum,Average
```

**Solutions:**
1. Increase task memory in task definition
2. Check for memory leaks in logs
3. Implement connection limits
4. Review active connection count

## Updating the Service

### Update Code

```powershell
# Make code changes
# Build and push new image
docker build -t agenticai-websocket:latest .
docker tag agenticai-websocket:latest "${repoUri}:latest"
docker push "${repoUri}:latest"

# Force new deployment
aws ecs update-service `
    --cluster agenticai-cluster-prod `
    --service agenticai-websocket-prod `
    --force-new-deployment
```

### Update Infrastructure

```powershell
# Modify ecs-template.yaml
# Redeploy stack
aws cloudformation deploy `
    --template-file ecs-template.yaml `
    --stack-name agenticai-websocket-stack `
    --capabilities CAPABILITY_NAMED_IAM
```

## Cost Optimization

### Current Costs (Estimated)

- **ECS Fargate**: ~$15/month (1 task, 0.5 vCPU, 1GB RAM)
- **ALB**: ~$16/month (base cost)
- **Data Transfer**: Variable based on usage
- **CloudWatch Logs**: ~$0.50/GB ingested

**Total**: ~$32/month + data transfer

### Optimization Tips

1. **Use Fargate Spot**: Save up to 70% (add to capacity provider strategy)
2. **Reduce log retention**: Change from 7 days to 3 days
3. **Right-size resources**: Monitor and adjust CPU/memory
4. **Use single ALB**: Share ALB with other services

## Security

### Network Security

- ALB security group allows HTTP/HTTPS from internet
- ECS security group only allows traffic from ALB
- Tasks run in private subnets (if available)

### IAM Permissions

Task role has minimal permissions:
- DynamoDB: GetItem, PutItem, UpdateItem, Query, Scan
- SQS: SendMessage, ReceiveMessage, DeleteMessage

### SSL/TLS

To enable HTTPS:

1. **Get SSL certificate** (ACM or import)
2. **Add HTTPS listener** to ALB:
```yaml
ALBListenerHTTPS:
  Type: AWS::ElasticLoadBalancingV2::Listener
  Properties:
    LoadBalancerArn: !Ref ApplicationLoadBalancer
    Port: 443
    Protocol: HTTPS
    Certificates:
      - CertificateArn: arn:aws:acm:region:account:certificate/id
    DefaultActions:
      - Type: forward
        TargetGroupArn: !Ref TargetGroup
```

## Cleanup

To remove all resources:

```powershell
# Delete ECS service
aws ecs update-service `
    --cluster agenticai-cluster-prod `
    --service agenticai-websocket-prod `
    --desired-count 0

aws ecs delete-service `
    --cluster agenticai-cluster-prod `
    --service agenticai-websocket-prod `
    --force

# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name agenticai-websocket-stack

# Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name agenticai-websocket-stack
```

## Next Steps

1. **Add SSL/TLS**: Configure HTTPS listener on ALB
2. **Add Authentication**: Implement JWT token validation
3. **Add Rate Limiting**: Implement connection limits per IP
4. **Add Monitoring Dashboard**: Create CloudWatch dashboard
5. **Add CI/CD**: Automate deployments with GitHub Actions

## Support

For issues:
1. Check CloudWatch logs: `/ecs/agenticai-websocket-prod`
2. Review ECS service events
3. Verify security group rules
4. Check IAM permissions
5. Test connectivity from within VPC
