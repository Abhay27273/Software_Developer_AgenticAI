# WebSocket Handler for ECS Fargate

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
