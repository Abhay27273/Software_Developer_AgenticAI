# WebSocket Handler - Quick Start Guide

## Prerequisites

- Docker installed
- AWS CLI configured
- AWS account with appropriate permissions
- CloudFormation stack deployed (for production)

## Local Development

### 1. Install Dependencies

```bash
cd websocket_handler
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
# Required
export SQS_QUEUE_URL_PM=https://sqs.us-east-1.amazonaws.com/123456789/agenticai-pm-queue-prod
export SQS_QUEUE_URL_DEV=https://sqs.us-east-1.amazonaws.com/123456789/agenticai-dev-queue-prod
export SQS_QUEUE_URL_QA=https://sqs.us-east-1.amazonaws.com/123456789/agenticai-qa-queue-prod
export SQS_QUEUE_URL_OPS=https://sqs.us-east-1.amazonaws.com/123456789/agenticai-ops-queue-prod
export DYNAMODB_TABLE_NAME=agenticai-data-prod

# Optional
export AWS_REGION=us-east-1
export WEBSOCKET_PORT=8080
```

### 3. Run Server

```bash
python server.py
```

Server will start on `ws://localhost:8080`

## Docker Development

### Using Docker Compose

```bash
# Create .env file with your AWS credentials
cat > .env << EOF
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
DYNAMODB_TABLE_NAME=agenticai-data-prod
SQS_QUEUE_URL_PM=https://sqs.us-east-1.amazonaws.com/123456789/agenticai-pm-queue-prod
SQS_QUEUE_URL_DEV=https://sqs.us-east-1.amazonaws.com/123456789/agenticai-dev-queue-prod
SQS_QUEUE_URL_QA=https://sqs.us-east-1.amazonaws.com/123456789/agenticai-qa-queue-prod
SQS_QUEUE_URL_OPS=https://sqs.us-east-1.amazonaws.com/123456789/agenticai-ops-queue-prod
EOF

# Start container
docker-compose up
```

### Manual Docker Build

```bash
# Build image
docker build -t agenticai-websocket:latest .

# Run container
docker run -p 8080:8080 \
  -e AWS_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=your_access_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret_key \
  -e DYNAMODB_TABLE_NAME=agenticai-data-prod \
  -e SQS_QUEUE_URL_PM=https://... \
  -e SQS_QUEUE_URL_DEV=https://... \
  -e SQS_QUEUE_URL_QA=https://... \
  -e SQS_QUEUE_URL_OPS=https://... \
  agenticai-websocket:latest
```

## Production Deployment

### 1. Deploy Infrastructure

```bash
# From project root
sam build
sam deploy --guided
```

### 2. Deploy WebSocket Handler

**Linux/Mac:**
```bash
cd websocket_handler
chmod +x deploy.sh
./deploy.sh prod
```

**Windows:**
```powershell
cd websocket_handler
.\deploy.ps1 -Environment prod
```

### 3. Verify Deployment

```bash
# Get WebSocket endpoint
aws cloudformation describe-stacks \
  --stack-name agenticai-stack \
  --query "Stacks[0].Outputs[?OutputKey=='WebSocketEndpoint'].OutputValue" \
  --output text

# Check ECS service status
aws ecs describe-services \
  --cluster agenticai-cluster-prod \
  --services agenticai-websocket-prod
```

## Testing WebSocket Connection

### Browser Console

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://your-alb-endpoint/ws?project_id=proj_123');

// Handle connection open
ws.onopen = () => {
  console.log('Connected to WebSocket');
  
  // Send ping
  ws.send(JSON.stringify({action: 'ping'}));
};

// Handle incoming messages
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

// Handle errors
ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

// Handle connection close
ws.onclose = () => {
  console.log('Disconnected from WebSocket');
};

// Subscribe to project updates
ws.send(JSON.stringify({
  action: 'subscribe',
  project_id: 'proj_123'
}));

// Forward message to SQS
ws.send(JSON.stringify({
  action: 'forward',
  type: 'dev',
  message_id: 'msg_123',
  project_id: 'proj_123',
  data: {
    task: 'generate_code',
    parameters: {
      language: 'python',
      framework: 'fastapi'
    }
  }
}));
```

### Python Client

```python
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8080/ws?project_id=proj_123"
    
    async with websockets.connect(uri) as websocket:
        # Wait for connection message
        response = await websocket.recv()
        print(f"Connected: {response}")
        
        # Send ping
        await websocket.send(json.dumps({"action": "ping"}))
        response = await websocket.recv()
        print(f"Ping response: {response}")
        
        # Subscribe to project
        await websocket.send(json.dumps({
            "action": "subscribe",
            "project_id": "proj_123"
        }))
        response = await websocket.recv()
        print(f"Subscribe response: {response}")
        
        # Keep connection alive
        while True:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=30)
                print(f"Received: {message}")
            except asyncio.TimeoutError:
                # Send ping to keep alive
                await websocket.send(json.dumps({"action": "ping"}))

asyncio.run(test_websocket())
```

## Monitoring

### View Logs

```bash
# Tail logs in real-time
aws logs tail /ecs/agenticai-websocket-prod --follow

# Get recent logs
aws logs tail /ecs/agenticai-websocket-prod --since 1h
```

### Check Service Health

```bash
# ECS service status
aws ecs describe-services \
  --cluster agenticai-cluster-prod \
  --services agenticai-websocket-prod \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Health:healthCheckGracePeriodSeconds}'

# Task status
aws ecs list-tasks \
  --cluster agenticai-cluster-prod \
  --service-name agenticai-websocket-prod

# Get task details
TASK_ARN=$(aws ecs list-tasks --cluster agenticai-cluster-prod --service-name agenticai-websocket-prod --query 'taskArns[0]' --output text)
aws ecs describe-tasks --cluster agenticai-cluster-prod --tasks $TASK_ARN
```

### CloudWatch Metrics

```bash
# Get CPU utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=agenticai-websocket-prod Name=ClusterName,Value=agenticai-cluster-prod \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

## Troubleshooting

### Connection Refused

**Problem**: Cannot connect to WebSocket

**Solutions**:
1. Check if service is running: `docker ps` or `aws ecs list-tasks`
2. Verify port is exposed: `netstat -an | grep 8080`
3. Check security group allows inbound traffic on port 8080
4. Verify ALB health checks are passing

### Environment Variables Missing

**Problem**: Server fails to start with missing environment variable error

**Solutions**:
1. Check all required variables are set
2. For Docker: verify `.env` file or `-e` flags
3. For ECS: check task definition environment variables
4. Verify Parameter Store values exist

### SQS Message Forwarding Fails

**Problem**: Messages not reaching SQS queues

**Solutions**:
1. Verify IAM role has SQS SendMessage permission
2. Check queue URLs are correct
3. Verify queues exist in the same region
4. Check CloudWatch logs for error messages

### High Memory Usage

**Problem**: Container using too much memory

**Solutions**:
1. Check number of active connections
2. Review CloudWatch logs for memory leaks
3. Consider increasing task memory allocation
4. Implement connection limits

## Common Commands

```bash
# Restart ECS service
aws ecs update-service \
  --cluster agenticai-cluster-prod \
  --service agenticai-websocket-prod \
  --force-new-deployment

# Scale service
aws ecs update-service \
  --cluster agenticai-cluster-prod \
  --service agenticai-websocket-prod \
  --desired-count 2

# Stop all tasks
aws ecs update-service \
  --cluster agenticai-cluster-prod \
  --service agenticai-websocket-prod \
  --desired-count 0

# View container logs
docker logs -f agenticai-websocket

# Build and test locally
docker build -t test . && docker run -p 8080:8080 test
```

## Next Steps

1. **Configure SSL/TLS**: Add HTTPS listener to ALB
2. **Add Authentication**: Implement JWT token validation
3. **Enable Auto-scaling**: Configure ECS service auto-scaling
4. **Set up Alarms**: Create CloudWatch alarms for errors and high usage
5. **Load Testing**: Test with multiple concurrent connections

## Support

For issues or questions:
1. Check CloudWatch logs: `/ecs/agenticai-websocket-prod`
2. Review ECS service events
3. Verify IAM permissions
4. Check security group rules
5. Consult README.md for detailed documentation
