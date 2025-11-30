# WebSocket Handler - ECS Fargate Deployment

## 🚀 Quick Start

Deploy to AWS ECS in one command:

```powershell
cd websocket_handler
.\deploy-ecs.ps1
```

That's it! Your WebSocket service will be running in ~10 minutes.

## 📋 What You Get

- **Production-ready WebSocket server** running on ECS Fargate
- **Application Load Balancer** with health checks
- **Auto-scaling** (1-4 tasks based on CPU)
- **CloudWatch monitoring** with logs and alarms
- **Secure networking** with security groups
- **Cost-optimized** (~$32/month)

## 📁 Files Overview

| File | Purpose |
|------|---------|
| `deploy-ecs.ps1` | 🎯 **START HERE** - One-command deployment |
| `ecs-template.yaml` | CloudFormation infrastructure template |
| `test-connection.ps1` | Verify deployment and connection |
| `test-websocket.py` | Python test client |
| `server.py` | WebSocket server application |
| `Dockerfile` | Container image definition |
| `requirements.txt` | Python dependencies |
| `ECS_DEPLOYMENT_GUIDE.md` | 📖 Complete documentation |
| `DEPLOY_QUICK_REFERENCE.md` | ⚡ Quick command reference |
| `DEPLOYMENT_SUMMARY.md` | 📝 Overview and architecture |

## 🎯 Deployment Steps

### 1. Deploy Infrastructure & Application

```powershell
.\deploy-ecs.ps1
```

This script automatically:
- ✓ Gets parameters from your main stack
- ✓ Detects VPC and subnets
- ✓ Deploys CloudFormation stack
- ✓ Builds Docker image
- ✓ Pushes to ECR
- ✓ Starts ECS service

### 2. Verify Deployment

```powershell
.\test-connection.ps1
```

This checks:
- ✓ Health endpoint responds
- ✓ ECS service is running
- ✓ ALB targets are healthy
- ✓ Logs are being generated

### 3. Test WebSocket Connection

Get your endpoint:
```powershell
$endpoint = aws cloudformation describe-stacks --stack-name agenticai-websocket-stack --query "Stacks[0].Outputs[?OutputKey=='WebSocketEndpoint'].OutputValue" --output text
Write-Host "Endpoint: $endpoint"
```

Test with Python:
```powershell
python test-websocket.py $endpoint
```

Or use wscat:
```bash
npm install -g wscat
wscat -c $endpoint
```

## 🏗️ Architecture

```
Internet
   ↓
Application Load Balancer (Port 80)
   ↓
ECS Fargate Tasks (Port 8080)
   ├─→ DynamoDB (project data)
   ├─→ SQS Queues (message forwarding)
   └─→ CloudWatch (logs & metrics)
```

## 🔧 Common Operations

### View Logs
```powershell
aws logs tail /ecs/agenticai-websocket-prod --follow
```

### Scale Service
```powershell
aws ecs update-service --cluster agenticai-cluster-prod --service agenticai-websocket-prod --desired-count 2
```

### Update Code
```powershell
# Make changes to server.py
.\deploy-ecs.ps1  # Rebuilds and redeploys
```

### Restart Service
```powershell
aws ecs update-service --cluster agenticai-cluster-prod --service agenticai-websocket-prod --force-new-deployment
```

## 📊 Monitoring

### CloudWatch Metrics
- CPU Utilization
- Memory Utilization
- Active Connections
- Request Count

### CloudWatch Alarms
- High CPU (>80%)
- High Memory (>80%)

### View Metrics
```powershell
# CPU usage
aws cloudwatch get-metric-statistics --namespace AWS/ECS --metric-name CPUUtilization --dimensions Name=ServiceName,Value=agenticai-websocket-prod Name=ClusterName,Value=agenticai-cluster-prod --start-time (Get-Date).AddHours(-1).ToUniversalTime() --end-time (Get-Date).ToUniversalTime() --period 300 --statistics Average
```

## 💰 Cost Estimate

| Resource | Monthly Cost |
|----------|--------------|
| ECS Fargate (1 task) | ~$15 |
| Application Load Balancer | ~$16 |
| CloudWatch Logs | ~$1 |
| **Total** | **~$32** |

## 🔒 Security

- ✓ ECS tasks in private subnets (if available)
- ✓ Security groups restrict traffic (ALB → ECS only)
- ✓ IAM roles with minimal permissions
- ✓ Container runs as non-root user
- ✓ SSL/TLS ready (add certificate to ALB)

## 🐛 Troubleshooting

### Service Won't Start
```powershell
# Check logs
aws logs tail /ecs/agenticai-websocket-prod --since 10m

# Check task status
$taskArn = aws ecs list-tasks --cluster agenticai-cluster-prod --service-name agenticai-websocket-prod --query 'taskArns[0]' --output text
aws ecs describe-tasks --cluster agenticai-cluster-prod --tasks $taskArn
```

### Health Checks Failing
```powershell
# Test health endpoint
$albDns = aws cloudformation describe-stacks --stack-name agenticai-websocket-stack --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDNS'].OutputValue" --output text
curl http://$albDns/health
```

### Can't Connect
```powershell
# Check target health
$tgArn = aws elbv2 describe-target-groups --names agenticai-tg-prod --query 'TargetGroups[0].TargetGroupArn' --output text
aws elbv2 describe-target-health --target-group-arn $tgArn
```

## 📚 Documentation

- **`ECS_DEPLOYMENT_GUIDE.md`** - Comprehensive guide with detailed instructions
- **`DEPLOY_QUICK_REFERENCE.md`** - Quick command reference
- **`DEPLOYMENT_SUMMARY.md`** - Architecture and overview

## 🎓 Next Steps

### Immediate
1. ✓ Deploy: `.\deploy-ecs.ps1`
2. ✓ Test: `.\test-connection.ps1`
3. ✓ Connect: `python test-websocket.py <endpoint>`

### Optional Enhancements
- [ ] Add SSL/TLS certificate to ALB
- [ ] Implement JWT authentication
- [ ] Add rate limiting per IP
- [ ] Create CloudWatch dashboard
- [ ] Set up CI/CD pipeline
- [ ] Enable ALB access logs
- [ ] Add custom domain name

## 🆘 Support

Having issues? Check these in order:

1. **Logs**: `aws logs tail /ecs/agenticai-websocket-prod --follow`
2. **Service Status**: `aws ecs describe-services --cluster agenticai-cluster-prod --services agenticai-websocket-prod`
3. **Target Health**: Run `.\test-connection.ps1`
4. **Documentation**: See `ECS_DEPLOYMENT_GUIDE.md`

## 📝 WebSocket Handler for ECS Fargate

This WebSocket server handles persistent connections for real-time updates in the AI-powered Software Development Agentic System.

## 📚 Documentation

- **[Quick Start Guide](QUICK_START.md)** - Get started quickly with local development and deployment
- **[API Reference](#message-protocol)** - Complete message protocol documentation
- **[Deployment Guide](#deployment)** - Production deployment instructions
- **[Testing Guide](#testing)** - How to test the WebSocket handler

## Features

- **Connection Management**: Handles multiple concurrent WebSocket connections
- **Project Subscriptions**: Clients can subscribe to specific project updates
- **Message Broadcasting**: Broadcast messages to all clients or project-specific clients
- **SQS Integration**: Forward messages to appropriate SQS queues for agent processing
- **Health Monitoring**: Built-in ping/pong for connection health checks
- **Graceful Shutdown**: Handles SIGTERM and SIGINT signals properly

## Architecture

```
Client Browser
    ↓ WebSocket
WebSocket Server (ECS Fargate)
    ↓ Forward messages
SQS Queues (PM, Dev, QA, Ops)
    ↓ Trigger
Lambda Functions (Agent Workers)
```

## Environment Variables

Required environment variables:

- `SQS_QUEUE_URL_PM`: URL for PM agent queue
- `SQS_QUEUE_URL_DEV`: URL for Dev agent queue
- `SQS_QUEUE_URL_QA`: URL for QA agent queue
- `SQS_QUEUE_URL_OPS`: URL for Ops agent queue
- `DYNAMODB_TABLE_NAME`: Name of the DynamoDB table
- `AWS_REGION`: AWS region (default: us-east-1)
- `WEBSOCKET_PORT`: Port to listen on (default: 8080)
- `WEBSOCKET_HOST`: Host to bind to (default: 0.0.0.0)

## Message Protocol

### Client → Server Messages

#### Subscribe to Project
```json
{
  "action": "subscribe",
  "project_id": "proj_123"
}
```

#### Unsubscribe from Project
```json
{
  "action": "unsubscribe",
  "project_id": "proj_123"
}
```

#### Forward Message to SQS
```json
{
  "action": "forward",
  "type": "dev",
  "message_id": "msg_123",
  "project_id": "proj_123",
  "data": {
    "task": "generate_code",
    "parameters": {}
  }
}
```

#### Ping
```json
{
  "action": "ping"
}
```

### Server → Client Messages

#### Connection Established
```json
{
  "type": "connected",
  "message": "WebSocket connection established",
  "timestamp": "2025-11-24T12:00:00Z"
}
```

#### Subscription Confirmed
```json
{
  "type": "subscription_confirmed",
  "project_id": "proj_123"
}
```

#### Broadcast Message
```json
{
  "type": "project_updated",
  "project_id": "proj_123",
  "data": {
    "status": "completed",
    "files": ["main.py", "test.py"]
  }
}
```

#### Error
```json
{
  "type": "error",
  "message": "Error description"
}
```

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SQS_QUEUE_URL_PM=https://sqs.us-east-1.amazonaws.com/123456789/pm-queue
export SQS_QUEUE_URL_DEV=https://sqs.us-east-1.amazonaws.com/123456789/dev-queue
export SQS_QUEUE_URL_QA=https://sqs.us-east-1.amazonaws.com/123456789/qa-queue
export SQS_QUEUE_URL_OPS=https://sqs.us-east-1.amazonaws.com/123456789/ops-queue
export DYNAMODB_TABLE_NAME=agenticai-data
export AWS_REGION=us-east-1

# Run server
python server.py
```

## Testing

### Unit Tests

Run unit tests with pytest:

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest test_server.py -v

# Run with coverage
pytest test_server.py -v --cov=server --cov-report=html
```

### Integration Tests

Test against a running server:

```bash
# Start server in one terminal
python server.py

# Run integration tests in another terminal
python integration_test.py ws://localhost:8080
```

### Manual Testing

Use the browser console or a WebSocket client:

```javascript
const ws = new WebSocket('ws://localhost:8080/ws?project_id=proj_123');
ws.onopen = () => ws.send(JSON.stringify({action: 'ping'}));
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

## Docker Build

```bash
# Build image
docker build -t websocket-handler:latest .

# Run container
docker run -p 8080:8080 \
  -e SQS_QUEUE_URL_PM=$SQS_QUEUE_URL_PM \
  -e SQS_QUEUE_URL_DEV=$SQS_QUEUE_URL_DEV \
  -e SQS_QUEUE_URL_QA=$SQS_QUEUE_URL_QA \
  -e SQS_QUEUE_URL_OPS=$SQS_QUEUE_URL_OPS \
  -e DYNAMODB_TABLE_NAME=$DYNAMODB_TABLE_NAME \
  -e AWS_REGION=$AWS_REGION \
  websocket-handler:latest
```

## ECS Fargate Deployment

The WebSocket handler is deployed as an ECS Fargate service with:
- **CPU**: 0.25 vCPU (256 units)
- **Memory**: 0.5 GB (512 MB)
- **Port**: 8080
- **Health Check**: TCP on port 8080

See `template.yaml` for the complete ECS task definition.

## Monitoring

The server logs all connection events, message forwarding, and errors to stdout, which are captured by CloudWatch Logs.

Key metrics to monitor:
- Active connection count
- Message forwarding rate
- Error rate
- Connection duration

## Security

- All WebSocket connections should use WSS (WebSocket Secure) in production
- IAM role provides access to SQS and DynamoDB
- No hardcoded credentials
- Input validation on all client messages

## Requirements

Implements requirement 1.7 from the AWS deployment specification:
- Persistent WebSocket connections for real-time updates
- Message forwarding to SQS queues
- Connection management and broadcasting
