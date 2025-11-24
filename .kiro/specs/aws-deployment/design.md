# AWS Deployment Design Document

## Overview

This document outlines the architecture and implementation strategy for deploying the AI-powered Software Development Agentic System to AWS using free tier services. The system will be transformed from a traditional server-based application to a serverless, event-driven architecture optimized for AWS Lambda, API Gateway, DynamoDB, and SQS.

### Current Architecture

The application is currently built as a monolithic FastAPI application with:
- **Web Server**: FastAPI with Uvicorn (WebSocket support)
- **Database**: PostgreSQL with asyncpg
- **Queue**: In-memory task queue (with Redis option)
- **File Storage**: Local filesystem
- **Agents**: PM, Dev, QA, and Ops agents running in-process
- **Real-time Communication**: WebSocket connections for streaming updates

### Target AWS Architecture

The deployment will leverage AWS Free Tier services:
- **API Gateway**: REST and WebSocket APIs (1M requests/month free)
- **Lambda Functions**: Serverless compute (1M requests/month free)
- **DynamoDB**: NoSQL database (25GB storage, 25 WCU/RCU free forever)
- **SQS**: Distributed task queue (1M requests/month free)
- **S3**: File storage (5GB free)
- **CloudWatch**: Logging and monitoring
- **Systems Manager Parameter Store**: Secrets management
- **ECS Fargate** (optional): For long-running WebSocket connections

## Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Browser                           │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ HTTPS
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CloudFront (Optional)                       │
│                    CDN for Static Assets                         │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       API Gateway                                │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │   REST API       │         │  WebSocket API   │             │
│  │  /api/projects   │         │  /ws             │             │
│  │  /api/templates  │         │                  │             │
│  └────────┬─────────┘         └────────┬─────────┘             │
└───────────┼──────────────────────────────┼───────────────────────┘
            │                              │
            │                              │ (WebSocket connections)
            │                              ▼
            │                    ┌──────────────────────┐
            │                    │   ECS Fargate        │
            │                    │   WebSocket Handler  │
            │                    │   (1 container)      │
            │                    └──────────┬───────────┘
            │                               │
            ▼                               │
┌─────────────────────────────────────────────────────────────────┐
│                      Lambda Functions                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   API        │  │   PM Agent   │  │   Dev Agent  │          │
│  │   Handler    │  │   Worker     │  │   Worker     │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   QA Agent   │  │   Ops Agent  │  │   File       │          │
│  │   Worker     │  │   Worker     │  │   Handler    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          │                  ▼                  │
          │         ┌──────────────────┐        │
          │         │       SQS        │        │
          │         │  ┌────────────┐  │        │
          │         │  │ Dev Queue  │  │        │
          │         │  ├────────────┤  │        │
          │         │  │ QA Queue   │  │        │
          │         │  ├────────────┤  │        │
          │         │  │ Ops Queue  │  │        │
          │         │  └────────────┘  │        │
          │         └──────────────────┘        │
          │                                     │
          ▼                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Data Layer                               │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │    DynamoDB      │         │        S3        │             │
│  │  ┌────────────┐  │         │  ┌────────────┐  │             │
│  │  │ Projects   │  │         │  │ Generated  │  │             │
│  │  ├────────────┤  │         │  │   Code     │  │             │
│  │  │Modifications│ │         │  ├────────────┤  │             │
│  │  ├────────────┤  │         │  │  Plans     │  │             │
│  │  │ Templates  │  │         │  └────────────┘  │             │
│  │  └────────────┘  │         └──────────────────┘             │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   CloudWatch     │
                    │  Logs & Metrics  │
                    └──────────────────┘
```

### Architecture Decisions


**1. Serverless-First Approach**
- Use Lambda for all compute workloads to stay within free tier
- Lambda's 15-minute timeout is sufficient for most agent tasks
- For longer tasks, use SQS + Lambda chaining

**2. Database Migration: PostgreSQL → DynamoDB**
- DynamoDB offers 25GB free storage forever (vs PostgreSQL requiring RDS/EC2)
- Single-table design pattern for cost efficiency
- Use DynamoDB Streams for event-driven updates

**3. WebSocket Handling Strategy**
- API Gateway WebSocket API for connection management
- Small ECS Fargate container (0.25 vCPU, 0.5GB RAM) for persistent connections
- Falls within free tier limits with minimal usage

**4. File Storage: Local Filesystem → S3**
- S3 provides 5GB free storage
- Lambda can write directly to S3
- Pre-signed URLs for client downloads

**5. Queue System: In-Memory → SQS**
- SQS provides 1M requests/month free
- Native integration with Lambda
- Built-in retry and DLQ support

## Components and Interfaces

### 1. API Gateway Configuration

#### REST API Endpoints

```yaml
/api/projects:
  POST: Create project → Lambda: api-handler
  GET: List projects → Lambda: api-handler
  
/api/projects/{id}:
  GET: Get project → Lambda: api-handler
  PUT: Update project → Lambda: api-handler
  DELETE: Delete project → Lambda: api-handler

/api/projects/{id}/modify:
  POST: Request modification → Lambda: api-handler → SQS

/api/templates:
  GET: List templates → Lambda: api-handler
  POST: Create template → Lambda: api-handler

/api/projects/{id}/docs:
  GET: Get documentation → Lambda: api-handler

/health:
  GET: Health check → Lambda: health-check
```

#### WebSocket API Routes

```yaml
$connect: Handle new connection → ECS Fargate
$disconnect: Handle disconnection → ECS Fargate
$default: Handle messages → ECS Fargate
```

### 2. Lambda Functions


#### Function: api-handler
- **Runtime**: Python 3.11
- **Memory**: 512MB
- **Timeout**: 30 seconds
- **Trigger**: API Gateway REST API
- **Purpose**: Handle all REST API requests
- **Environment Variables**:
  - `DYNAMODB_TABLE_NAME`
  - `S3_BUCKET_NAME`
  - `SQS_QUEUE_URL_DEV`
  - `SQS_QUEUE_URL_QA`
  - `SQS_QUEUE_URL_OPS`
  - `GEMINI_API_KEY` (from Parameter Store)

#### Function: pm-agent-worker
- **Runtime**: Python 3.11
- **Memory**: 1024MB
- **Timeout**: 300 seconds (5 minutes)
- **Trigger**: SQS (PM Queue)
- **Purpose**: Execute PM agent tasks (planning)
- **Concurrency**: 2 (free tier limit)

#### Function: dev-agent-worker
- **Runtime**: Python 3.11
- **Memory**: 2048MB
- **Timeout**: 900 seconds (15 minutes)
- **Trigger**: SQS (Dev Queue)
- **Purpose**: Execute Dev agent tasks (code generation)
- **Concurrency**: 2

#### Function: qa-agent-worker
- **Runtime**: Python 3.11
- **Memory**: 1024MB
- **Timeout**: 600 seconds (10 minutes)
- **Trigger**: SQS (QA Queue)
- **Purpose**: Execute QA agent tasks (testing)
- **Concurrency**: 2

#### Function: ops-agent-worker
- **Runtime**: Python 3.11
- **Memory**: 512MB
- **Timeout**: 300 seconds (5 minutes)
- **Trigger**: SQS (Ops Queue)
- **Purpose**: Execute Ops agent tasks (deployment)
- **Concurrency**: 1

#### Function: file-handler
- **Runtime**: Python 3.11
- **Memory**: 256MB
- **Timeout**: 60 seconds
- **Trigger**: API Gateway (file operations)
- **Purpose**: Generate pre-signed URLs, list files

### 3. ECS Fargate WebSocket Service

```yaml
Service: websocket-handler
Task Definition:
  CPU: 256 (.25 vCPU)
  Memory: 512MB
  Container:
    Image: websocket-handler:latest
    Port: 8080
    Environment:
      - DYNAMODB_TABLE_NAME
      - API_GATEWAY_ENDPOINT
      - SQS_QUEUE_URLS
```

**Container Responsibilities**:
- Maintain WebSocket connections
- Broadcast real-time updates to connected clients
- Forward messages to SQS queues
- Handle connection lifecycle

### 4. SQS Queues


#### PM Agent Queue
- **Name**: `agenticai-pm-queue`
- **Visibility Timeout**: 360 seconds
- **Message Retention**: 4 days
- **DLQ**: `agenticai-pm-dlq`

#### Dev Agent Queue
- **Name**: `agenticai-dev-queue`
- **Visibility Timeout**: 960 seconds (16 minutes)
- **Message Retention**: 4 days
- **DLQ**: `agenticai-dev-dlq`

#### QA Agent Queue
- **Name**: `agenticai-qa-queue`
- **Visibility Timeout**: 660 seconds (11 minutes)
- **Message Retention**: 4 days
- **DLQ**: `agenticai-qa-dlq`

#### Ops Agent Queue
- **Name**: `agenticai-ops-queue`
- **Visibility Timeout**: 360 seconds
- **Message Retention**: 4 days
- **DLQ**: `agenticai-ops-dlq`

### 5. DynamoDB Tables

#### Single Table Design

**Table Name**: `agenticai-data`

**Primary Key**:
- Partition Key (PK): String
- Sort Key (SK): String

**Global Secondary Indexes**:
1. **GSI1**: `GSI1PK` (PK) + `GSI1SK` (SK) - For querying by owner
2. **GSI2**: `GSI2PK` (PK) + `GSI2SK` (SK) - For querying by status/type

**Access Patterns**:

```
# Projects
PK: PROJECT#<project_id>
SK: METADATA
Attributes: name, type, status, owner_id, created_at, updated_at, ...

# Project Files
PK: PROJECT#<project_id>
SK: FILE#<file_path>
Attributes: content, size, last_modified

# Modifications
PK: PROJECT#<project_id>
SK: MOD#<modification_id>
Attributes: request, status, impact_analysis, applied_at, ...

# Templates
PK: TEMPLATE#<template_id>
SK: METADATA
Attributes: name, category, description, tech_stack, ...

# Template Files
PK: TEMPLATE#<template_id>
SK: FILE#<file_path>
Attributes: content, is_template, variables

# Query by Owner (GSI1)
GSI1PK: OWNER#<owner_id>
GSI1SK: PROJECT#<created_at>

# Query by Status (GSI2)
GSI2PK: STATUS#<status>
GSI2SK: PROJECT#<project_id>
```

**Capacity Settings**:
- Billing Mode: On-Demand (stays within free tier for low traffic)
- Point-in-Time Recovery: Enabled
- Encryption: AWS managed keys

## Data Models

### DynamoDB Item Structures


#### Project Item

```python
{
    "PK": "PROJECT#proj_20251124_120000",
    "SK": "METADATA",
    "GSI1PK": "OWNER#user123",
    "GSI1SK": "PROJECT#2025-11-24T12:00:00Z",
    "GSI2PK": "STATUS#active",
    "GSI2SK": "PROJECT#proj_20251124_120000",
    "EntityType": "Project",
    "id": "proj_20251124_120000",
    "name": "Todo API",
    "type": "api",
    "status": "active",
    "owner_id": "user123",
    "description": "REST API for todo management",
    "dependencies": ["fastapi", "sqlalchemy"],
    "environment_vars": {
        "DATABASE_URL": "***",
        "API_KEY": "***"
    },
    "deployment_config": {
        "platform": "aws",
        "region": "us-east-1"
    },
    "test_coverage": 0.85,
    "security_score": 0.92,
    "performance_score": 0.88,
    "created_at": "2025-11-24T12:00:00Z",
    "updated_at": "2025-11-24T12:00:00Z",
    "ttl": 1735689600  # Optional: Auto-delete after 30 days of inactivity
}
```

#### Project File Item

```python
{
    "PK": "PROJECT#proj_20251124_120000",
    "SK": "FILE#main.py",
    "EntityType": "ProjectFile",
    "file_path": "main.py",
    "content": "from fastapi import FastAPI...",
    "size": 1024,
    "last_modified": "2025-11-24T12:00:00Z"
}
```

#### Modification Item

```python
{
    "PK": "PROJECT#proj_20251124_120000",
    "SK": "MOD#mod_20251124_120500",
    "EntityType": "Modification",
    "id": "mod_20251124_120500",
    "project_id": "proj_20251124_120000",
    "request": "Add user authentication",
    "requested_by": "user123",
    "requested_at": "2025-11-24T12:05:00Z",
    "status": "pending",
    "impact_analysis": {
        "risk_level": "medium",
        "affected_files": ["main.py", "auth.py"],
        "estimated_time": "2 hours"
    },
    "applied_at": null,
    "modified_files": {},
    "test_results": {}
}
```

#### Template Item

```python
{
    "PK": "TEMPLATE#rest-api-fastapi",
    "SK": "METADATA",
    "EntityType": "Template",
    "id": "rest-api-fastapi",
    "name": "REST API with FastAPI",
    "description": "Production-ready REST API",
    "category": "api",
    "required_vars": ["project_name", "db_name"],
    "optional_vars": ["project_description"],
    "tech_stack": ["FastAPI", "PostgreSQL"],
    "complexity": "medium",
    "estimated_setup_time": 15,
    "tags": ["api", "rest", "fastapi"],
    "created_at": "2025-11-24T12:00:00Z",
    "updated_at": "2025-11-24T12:00:00Z"
}
```

### S3 Bucket Structure

```
agenticai-generated-code/
├── projects/
│   ├── proj_20251124_120000/
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── README.md
│   └── proj_20251124_130000/
│       └── ...
├── plans/
│   ├── plan_123.json
│   └── plan_456.json
└── templates/
    ├── rest-api-fastapi/
    │   ├── main.py
    │   └── requirements.txt
    └── web-app-react/
        └── ...
```

## Error Handling


### Lambda Error Handling

**Retry Strategy**:
- Automatic retries: 2 attempts
- Exponential backoff: 1s, 2s, 4s
- Failed messages → Dead Letter Queue (DLQ)

**Error Types**:

1. **Transient Errors** (Retry)
   - DynamoDB throttling
   - Network timeouts
   - Rate limit errors from LLM APIs

2. **Permanent Errors** (Send to DLQ)
   - Invalid input data
   - Missing required parameters
   - Authentication failures

3. **Timeout Errors**
   - Lambda timeout approaching → Save state to DynamoDB
   - Enqueue continuation task to SQS
   - Resume from saved state

**Error Response Format**:

```python
{
    "success": False,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid project type",
        "details": {
            "field": "project_type",
            "allowed_values": ["api", "web", "mobile", "data", "microservice"]
        }
    },
    "request_id": "abc-123-def",
    "timestamp": "2025-11-24T12:00:00Z"
}
```

### DynamoDB Error Handling

**Throttling**:
- Implement exponential backoff with jitter
- Use batch operations where possible
- Monitor CloudWatch for throttling metrics

**Conditional Writes**:
- Use condition expressions to prevent race conditions
- Handle `ConditionalCheckFailedException` gracefully

**Transaction Failures**:
- Implement idempotency tokens
- Retry transactional writes up to 3 times

### WebSocket Error Handling

**Connection Errors**:
- Automatic reconnection with exponential backoff
- Client-side connection state management
- Fallback to polling if WebSocket unavailable

**Message Delivery**:
- Message acknowledgment system
- Retry failed messages up to 3 times
- Store undelivered messages in DynamoDB for later retrieval

## Testing Strategy

### Unit Tests

**Lambda Functions**:
```python
# tests/lambda/test_api_handler.py
def test_create_project():
    event = {
        "httpMethod": "POST",
        "path": "/api/projects",
        "body": json.dumps({
            "name": "Test Project",
            "type": "api"
        })
    }
    response = lambda_handler(event, {})
    assert response["statusCode"] == 201
```

**DynamoDB Operations**:
```python
# tests/dynamodb/test_project_store.py
@pytest.mark.asyncio
async def test_save_project():
    store = DynamoDBProjectStore()
    project = ProjectContext(name="Test", type="api")
    await store.save_context(project)
    loaded = await store.load_context(project.id)
    assert loaded.name == "Test"
```

### Integration Tests

**API Gateway + Lambda**:
```python
# tests/integration/test_api_endpoints.py
def test_project_crud_flow():
    # Create
    response = requests.post(f"{API_URL}/api/projects", json={...})
    assert response.status_code == 201
    project_id = response.json()["project"]["id"]
    
    # Read
    response = requests.get(f"{API_URL}/api/projects/{project_id}")
    assert response.status_code == 200
    
    # Update
    response = requests.put(f"{API_URL}/api/projects/{project_id}", json={...})
    assert response.status_code == 200
    
    # Delete
    response = requests.delete(f"{API_URL}/api/projects/{project_id}")
    assert response.status_code == 200
```

**SQS + Lambda**:
```python
# tests/integration/test_agent_workers.py
def test_dev_agent_execution():
    # Send message to SQS
    sqs.send_message(
        QueueUrl=DEV_QUEUE_URL,
        MessageBody=json.dumps({
            "task_id": "task_123",
            "project_id": "proj_123",
            "action": "generate_code"
        })
    )
    
    # Wait for Lambda to process
    time.sleep(10)
    
    # Verify result in DynamoDB
    result = dynamodb.get_item(...)
    assert result["status"] == "completed"
```

### End-to-End Tests


**Complete User Flow**:
```python
# tests/e2e/test_project_creation_flow.py
def test_complete_project_creation():
    # 1. Create project from template
    response = requests.post(f"{API_URL}/api/projects/from-template", json={
        "template_id": "rest-api-fastapi",
        "project_name": "My API",
        "variables": {"db_name": "mydb"}
    })
    project_id = response.json()["project"]["id"]
    
    # 2. Connect WebSocket
    ws = websocket.create_connection(f"{WS_URL}?project_id={project_id}")
    
    # 3. Request modification
    response = requests.post(
        f"{API_URL}/api/projects/{project_id}/modify",
        json={"request": "Add user authentication"}
    )
    
    # 4. Receive real-time updates via WebSocket
    updates = []
    for _ in range(5):
        msg = json.loads(ws.recv())
        updates.append(msg)
    
    # 5. Verify completion
    assert any(u["type"] == "modification_complete" for u in updates)
    
    # 6. Download generated files
    response = requests.get(f"{API_URL}/api/projects/{project_id}/files")
    assert "main.py" in response.json()["files"]
```

### Load Testing

**Objectives**:
- Verify free tier limits are respected
- Test auto-scaling behavior
- Identify bottlenecks

**Tools**: Locust, Artillery

**Scenarios**:
1. **Steady Load**: 10 requests/second for 10 minutes
2. **Burst Load**: 100 requests in 10 seconds
3. **Concurrent Users**: 50 simultaneous WebSocket connections

## Security

### IAM Roles and Policies

#### Lambda Execution Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/agenticai-data",
        "arn:aws:dynamodb:*:*:table/agenticai-data/index/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::agenticai-generated-code",
        "arn:aws:s3:::agenticai-generated-code/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:*:*:agenticai-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/agenticai/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

#### ECS Task Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "execute-api:ManageConnections",
        "execute-api:Invoke"
      ],
      "Resource": "arn:aws:execute-api:*:*:*/@connections/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage"
      ],
      "Resource": "arn:aws:sqs:*:*:agenticai-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:Query"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/agenticai-data"
    }
  ]
}
```

### Secrets Management

**AWS Systems Manager Parameter Store**:

```
/agenticai/gemini-api-key (SecureString)
/agenticai/github-token (SecureString)
/agenticai/jwt-secret (SecureString)
```

**Access Pattern**:
```python
import boto3

ssm = boto3.client('ssm')

def get_secret(name):
    response = ssm.get_parameter(
        Name=f'/agenticai/{name}',
        WithDecryption=True
    )
    return response['Parameter']['Value']

# Usage in Lambda
GEMINI_API_KEY = get_secret('gemini-api-key')
```

### API Security


**API Gateway Configuration**:

1. **HTTPS Only**: Enforce TLS 1.2+
2. **CORS**: Restrict to allowed origins
3. **Throttling**: 100 requests/second per API key
4. **Request Validation**: JSON schema validation
5. **API Keys**: Required for all endpoints (except health check)

**Rate Limiting**:
```python
# API Gateway Usage Plan
{
    "throttle": {
        "rateLimit": 100,  # requests per second
        "burstLimit": 200  # max concurrent requests
    },
    "quota": {
        "limit": 100000,  # requests per month
        "period": "MONTH"
    }
}
```

### Data Encryption

**At Rest**:
- DynamoDB: AWS managed encryption keys
- S3: AES-256 encryption
- Parameter Store: KMS encryption

**In Transit**:
- HTTPS/TLS for all API calls
- WSS (WebSocket Secure) for WebSocket connections

## Monitoring and Logging

### CloudWatch Dashboards

**Dashboard: System Overview**

Widgets:
1. **API Gateway Metrics**
   - Request count (last 24h)
   - 4xx/5xx error rates
   - Latency (p50, p95, p99)

2. **Lambda Metrics**
   - Invocation count by function
   - Error rate by function
   - Duration by function
   - Concurrent executions

3. **DynamoDB Metrics**
   - Read/Write capacity units consumed
   - Throttled requests
   - Table size

4. **SQS Metrics**
   - Messages sent/received
   - Queue depth
   - Age of oldest message

5. **Cost Tracking**
   - Estimated monthly cost
   - Free tier usage percentage

### CloudWatch Alarms

**Critical Alarms** (SNS notification):

```yaml
Lambda Error Rate:
  Metric: Errors
  Threshold: > 5% of invocations
  Period: 5 minutes
  Action: SNS topic

Lambda Duration:
  Metric: Duration
  Threshold: > 80% of timeout
  Period: 5 minutes
  Action: SNS topic

DynamoDB Throttling:
  Metric: UserErrors
  Threshold: > 10 in 5 minutes
  Period: 5 minutes
  Action: SNS topic

SQS DLQ Messages:
  Metric: ApproximateNumberOfMessagesVisible
  Threshold: > 0
  Period: 1 minute
  Action: SNS topic

Free Tier Limit:
  Metric: Custom (Lambda invocations)
  Threshold: > 800,000 (80% of 1M)
  Period: 1 day
  Action: SNS topic
```

### Logging Strategy

**Log Levels**:
- ERROR: Failures requiring immediate attention
- WARN: Potential issues, degraded performance
- INFO: Important business events
- DEBUG: Detailed diagnostic information (disabled in production)

**Structured Logging**:
```python
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def log_event(level, event_type, message, **kwargs):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "event_type": event_type,
        "message": message,
        "request_id": kwargs.get("request_id"),
        "user_id": kwargs.get("user_id"),
        **kwargs
    }
    logger.log(getattr(logging, level), json.dumps(log_entry))

# Usage
log_event("INFO", "project_created", "New project created", 
          project_id="proj_123", user_id="user_456")
```

**Log Retention**:
- Production: 7 days (free tier limit)
- Development: 3 days

### Distributed Tracing

**AWS X-Ray Integration**:
- Enable X-Ray tracing on all Lambda functions
- Trace API Gateway → Lambda → DynamoDB → S3 calls
- Identify performance bottlenecks

```python
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()

@xray_recorder.capture('process_task')
def process_task(task_data):
    # Function automatically traced
    pass
```

## Deployment Strategy


### Infrastructure as Code

**AWS SAM Template** (`template.yaml`):

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: AI-powered Software Development Agentic System

Globals:
  Function:
    Runtime: python3.11
    Timeout: 30
    MemorySize: 512
    Environment:
      Variables:
        DYNAMODB_TABLE_NAME: !Ref DataTable
        S3_BUCKET_NAME: !Ref CodeBucket
        LOG_LEVEL: INFO

Resources:
  # API Gateway
  RestApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: prod
      Cors:
        AllowOrigin: "'*'"
        AllowHeaders: "'*'"
      Auth:
        ApiKeyRequired: true
      ThrottleSettings:
        RateLimit: 100
        BurstLimit: 200

  # Lambda Functions
  ApiHandler:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: lambda/api_handler/
      Handler: app.lambda_handler
      Events:
        ApiEvent:
          Type: Api
          Properties:
            RestApiId: !Ref RestApi
            Path: /api/{proxy+}
            Method: ANY
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref DataTable
        - S3CrudPolicy:
            BucketName: !Ref CodeBucket
        - SQSSendMessagePolicy:
            QueueName: !GetAtt DevQueue.QueueName

  DevAgentWorker:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: lambda/dev_agent/
      Handler: worker.lambda_handler
      Timeout: 900
      MemorySize: 2048
      Events:
        SQSEvent:
          Type: SQS
          Properties:
            Queue: !GetAtt DevQueue.Arn
            BatchSize: 1
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref DataTable
        - S3CrudPolicy:
            BucketName: !Ref CodeBucket

  # DynamoDB Table
  DataTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: agenticai-data
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: PK
          AttributeType: S
        - AttributeName: SK
          AttributeType: S
        - AttributeName: GSI1PK
          AttributeType: S
        - AttributeName: GSI1SK
          AttributeType: S
      KeySchema:
        - AttributeName: PK
          KeyType: HASH
        - AttributeName: SK
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: GSI1
          KeySchema:
            - AttributeName: GSI1PK
              KeyType: HASH
            - AttributeName: GSI1SK
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true

  # S3 Bucket
  CodeBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: agenticai-generated-code
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      LifecycleConfiguration:
        Rules:
          - Id: DeleteOldFiles
            Status: Enabled
            ExpirationInDays: 90

  # SQS Queues
  DevQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: agenticai-dev-queue
      VisibilityTimeout: 960
      MessageRetentionPeriod: 345600
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt DevDLQ.Arn
        maxReceiveCount: 3

  DevDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: agenticai-dev-dlq
      MessageRetentionPeriod: 1209600

Outputs:
  ApiEndpoint:
    Description: API Gateway endpoint URL
    Value: !Sub 'https://${RestApi}.execute-api.${AWS::Region}.amazonaws.com/prod'
  
  DataTableName:
    Description: DynamoDB table name
    Value: !Ref DataTable
```

### CI/CD Pipeline

**GitHub Actions Workflow** (`.github/workflows/deploy.yml`):

```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  AWS_REGION: us-east-1
  SAM_TEMPLATE: template.yaml

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      
      - name: Run unit tests
        run: pytest tests/unit --cov=lambda --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install SAM CLI
        run: |
          pip install aws-sam-cli
      
      - name: Build SAM application
        run: sam build --template ${{ env.SAM_TEMPLATE }}
      
      - name: Deploy to AWS
        run: |
          sam deploy \
            --no-confirm-changeset \
            --no-fail-on-empty-changeset \
            --stack-name agenticai-stack \
            --capabilities CAPABILITY_IAM \
            --region ${{ env.AWS_REGION }}
      
      - name: Run integration tests
        run: |
          export API_ENDPOINT=$(aws cloudformation describe-stacks \
            --stack-name agenticai-stack \
            --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
            --output text)
          pytest tests/integration
```

### Deployment Phases


**Phase 1: Infrastructure Setup** (Manual, one-time)
1. Create AWS account
2. Set up IAM user with programmatic access
3. Configure AWS CLI
4. Create S3 bucket for SAM artifacts
5. Store secrets in Parameter Store

**Phase 2: Initial Deployment** (Automated via SAM)
1. Deploy DynamoDB table
2. Deploy S3 bucket
3. Deploy SQS queues
4. Deploy Lambda functions
5. Deploy API Gateway
6. Configure CloudWatch alarms

**Phase 3: Continuous Deployment** (Automated via GitHub Actions)
1. Run tests on every push
2. Deploy to AWS on main branch merge
3. Run integration tests post-deployment
4. Rollback on failure

### Blue-Green Deployment

**Lambda Versioning**:
```yaml
DevAgentWorker:
  Type: AWS::Serverless::Function
  Properties:
    AutoPublishAlias: live
    DeploymentPreference:
      Type: Linear10PercentEvery1Minute
      Alarms:
        - !Ref DevAgentErrorAlarm
```

**Rollback Strategy**:
- Automatic rollback if error rate > 5%
- Manual rollback via AWS Console or CLI
- Keep last 3 versions for quick rollback

## Migration Plan

### Phase 1: Database Migration (PostgreSQL → DynamoDB)

**Step 1: Create DynamoDB Adapter**
```python
# utils/dynamodb_adapter.py
class DynamoDBProjectStore:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table('agenticai-data')
    
    async def save_context(self, project: ProjectContext):
        # Convert project to DynamoDB items
        items = self._project_to_items(project)
        
        # Batch write
        with self.table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)
    
    async def load_context(self, project_id: str):
        # Query all items for project
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'PROJECT#{project_id}')
        )
        
        # Convert items to project
        return self._items_to_project(response['Items'])
```

**Step 2: Dual-Write Pattern**
- Write to both PostgreSQL and DynamoDB
- Read from PostgreSQL (primary)
- Verify DynamoDB writes
- Duration: 1 week

**Step 3: Switch Read Source**
- Read from DynamoDB (primary)
- Keep PostgreSQL as backup
- Monitor for discrepancies
- Duration: 1 week

**Step 4: Remove PostgreSQL**
- Stop writing to PostgreSQL
- Archive PostgreSQL data
- Remove PostgreSQL dependencies

### Phase 2: Code Refactoring

**Lambda Function Structure**:
```
lambda/
├── api_handler/
│   ├── app.py
│   ├── requirements.txt
│   └── utils/
├── dev_agent/
│   ├── worker.py
│   ├── requirements.txt
│   └── agents/
├── qa_agent/
│   ├── worker.py
│   ├── requirements.txt
│   └── agents/
└── shared/
    ├── models/
    ├── utils/
    └── __init__.py
```

**Shared Layer**:
```yaml
SharedLayer:
  Type: AWS::Serverless::LayerVersion
  Properties:
    LayerName: agenticai-shared
    ContentUri: lambda/shared/
    CompatibleRuntimes:
      - python3.11
```

### Phase 3: WebSocket Migration

**Option A: API Gateway WebSocket API + Lambda**
- Pros: Fully serverless, no container management
- Cons: 10-minute connection limit, complex state management

**Option B: ECS Fargate (Recommended)**
- Pros: Persistent connections, simpler code
- Cons: Requires container, slightly higher cost (still within free tier)

**Implementation**:
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY websocket_handler/ .

CMD ["python", "server.py"]
```

```python
# websocket_handler/server.py
import asyncio
import websockets
import boto3

sqs = boto3.client('sqs')

async def handler(websocket, path):
    async for message in websocket:
        # Forward to SQS
        sqs.send_message(
            QueueUrl=os.getenv('SQS_QUEUE_URL'),
            MessageBody=message
        )
```

## Cost Optimization

### Free Tier Limits


**AWS Free Tier (12 months)**:
- Lambda: 1M requests/month, 400,000 GB-seconds compute
- API Gateway: 1M API calls/month
- DynamoDB: 25GB storage, 25 WCU, 25 RCU (forever free)
- S3: 5GB storage, 20,000 GET requests, 2,000 PUT requests
- SQS: 1M requests/month
- CloudWatch: 10 custom metrics, 10 alarms, 5GB logs
- ECS Fargate: 750 hours/month (t2.micro equivalent)

**Estimated Monthly Usage** (moderate traffic):
- Lambda invocations: ~500,000 (50% of limit)
- API Gateway calls: ~500,000 (50% of limit)
- DynamoDB: ~10GB storage, ~15 WCU/RCU (60% of limit)
- S3: ~2GB storage (40% of limit)
- SQS: ~300,000 messages (30% of limit)
- ECS Fargate: ~500 hours (67% of limit)

**Cost if exceeding free tier**:
- Lambda: $0.20 per 1M requests + $0.0000166667 per GB-second
- API Gateway: $3.50 per 1M requests
- DynamoDB: $0.25 per GB/month (on-demand)
- S3: $0.023 per GB/month
- SQS: $0.40 per 1M requests

**Estimated cost after free tier**: ~$5-10/month for moderate usage

### Cost Monitoring

**CloudWatch Custom Metric**:
```python
import boto3

cloudwatch = boto3.client('cloudwatch')

def track_usage(service, metric_name, value):
    cloudwatch.put_metric_data(
        Namespace='AgenticAI/Usage',
        MetricData=[{
            'MetricName': metric_name,
            'Value': value,
            'Unit': 'Count',
            'Dimensions': [
                {'Name': 'Service', 'Value': service}
            ]
        }]
    )

# Track Lambda invocations
track_usage('Lambda', 'Invocations', 1)
```

**Budget Alert**:
```yaml
Budget:
  Type: AWS::Budgets::Budget
  Properties:
    Budget:
      BudgetName: agenticai-monthly-budget
      BudgetLimit:
        Amount: 10
        Unit: USD
      TimeUnit: MONTHLY
      BudgetType: COST
    NotificationsWithSubscribers:
      - Notification:
          NotificationType: ACTUAL
          ComparisonOperator: GREATER_THAN
          Threshold: 80
        Subscribers:
          - SubscriptionType: EMAIL
            Address: your-email@example.com
```

### Optimization Strategies

1. **Lambda Cold Start Reduction**
   - Use provisioned concurrency for critical functions (costs extra)
   - Keep functions warm with CloudWatch Events (5-minute ping)
   - Optimize package size (< 50MB)

2. **DynamoDB Optimization**
   - Use single-table design to reduce table count
   - Implement caching layer (ElastiCache or in-memory)
   - Use batch operations to reduce request count

3. **S3 Optimization**
   - Enable S3 Intelligent-Tiering
   - Compress files before upload
   - Use lifecycle policies to delete old files

4. **API Gateway Optimization**
   - Enable caching (costs extra, but reduces Lambda invocations)
   - Use request validation to reject invalid requests early
   - Implement client-side caching

## Performance Considerations

### Lambda Performance

**Cold Start Mitigation**:
```python
# Lazy import heavy libraries
def lambda_handler(event, context):
    # Import only when needed
    if event['action'] == 'generate_code':
        from agents.dev_agent import DevAgent
        agent = DevAgent()
        return agent.execute(event)
```

**Connection Pooling**:
```python
# Reuse connections across invocations
import boto3

# Initialize outside handler
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('agenticai-data')

def lambda_handler(event, context):
    # Reuse table connection
    response = table.get_item(Key={'PK': event['project_id']})
```

### DynamoDB Performance

**Batch Operations**:
```python
# Instead of multiple PutItem calls
with table.batch_writer() as batch:
    for item in items:
        batch.put_item(Item=item)
```

**Parallel Queries**:
```python
import asyncio

async def get_project_data(project_id):
    tasks = [
        get_project_metadata(project_id),
        get_project_files(project_id),
        get_project_modifications(project_id)
    ]
    return await asyncio.gather(*tasks)
```

### API Gateway Performance

**Response Caching**:
```yaml
RestApi:
  Type: AWS::Serverless::Api
  Properties:
    CacheClusterEnabled: true
    CacheClusterSize: '0.5'  # Smallest size
    MethodSettings:
      - ResourcePath: /api/templates
        HttpMethod: GET
        CachingEnabled: true
        CacheTtlInSeconds: 300
```

## Disaster Recovery

### Backup Strategy

**DynamoDB**:
- Point-in-Time Recovery: Enabled (35 days)
- On-demand backups: Before major deployments
- Cross-region replication: Optional (costs extra)

**S3**:
- Versioning: Enabled
- Cross-region replication: Optional
- Lifecycle policy: Archive to Glacier after 90 days

**Lambda**:
- Version control: Git repository
- SAM template: Infrastructure as code
- Deployment packages: Stored in S3

### Recovery Procedures

**Scenario 1: Lambda Function Failure**
1. Identify failed version via CloudWatch
2. Rollback to previous version: `aws lambda update-alias --function-name dev-agent --name live --function-version 2`
3. Investigate root cause
4. Deploy fix

**Scenario 2: DynamoDB Data Corruption**
1. Stop all writes to table
2. Restore from Point-in-Time Recovery: `aws dynamodb restore-table-to-point-in-time`
3. Verify data integrity
4. Resume operations

**Scenario 3: Complete Region Failure**
1. Failover to backup region (if configured)
2. Update DNS to point to backup region
3. Restore data from backups
4. Resume operations in backup region

## Documentation Requirements

### Deployment Guide

**Contents**:
1. Prerequisites (AWS account, CLI, SAM CLI)
2. Initial setup steps
3. Configuration instructions
4. Deployment commands
5. Verification steps
6. Troubleshooting guide

### Operations Runbook

**Contents**:
1. Monitoring dashboards
2. Common alerts and responses
3. Scaling procedures
4. Backup and restore procedures
5. Incident response playbook

### API Documentation

**Contents**:
1. Endpoint reference
2. Authentication
3. Request/response formats
4. Error codes
5. Rate limits
6. Code examples

## Success Criteria

1. ✅ All services running within AWS Free Tier limits
2. ✅ API response time < 500ms (p95)
3. ✅ Lambda cold start < 3 seconds
4. ✅ 99.9% uptime
5. ✅ Zero data loss
6. ✅ Automated deployment via CI/CD
7. ✅ Comprehensive monitoring and alerting
8. ✅ Complete documentation
9. ✅ All tests passing (unit, integration, e2e)
10. ✅ Security best practices implemented
