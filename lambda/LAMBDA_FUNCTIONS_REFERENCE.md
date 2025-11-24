# Lambda Functions Reference Guide

## Overview

This document provides a quick reference for all Lambda functions in the AWS deployment architecture.

## Lambda Functions

### 1. API Handler (`lambda/api_handler/`)

**Purpose**: Handle all REST API requests from API Gateway

**Trigger**: API Gateway (REST API)

**Configuration**:
- Runtime: Python 3.11
- Memory: 512MB
- Timeout: 30 seconds
- Concurrency: 10 (reserved)

**Environment Variables**:
- `DYNAMODB_TABLE_NAME` - DynamoDB table name
- `S3_BUCKET_NAME` - S3 bucket for file storage
- `SQS_QUEUE_URL_PM` - PM agent queue URL
- `SQS_QUEUE_URL_DEV` - Dev agent queue URL
- `SQS_QUEUE_URL_QA` - QA agent queue URL
- `SQS_QUEUE_URL_OPS` - Ops agent queue URL

**Endpoints**:
```
POST   /api/projects              - Create project
GET    /api/projects              - List projects
GET    /api/projects/{id}         - Get project
PUT    /api/projects/{id}         - Update project
DELETE /api/projects/{id}         - Delete project
POST   /api/projects/{id}/modify  - Request modification
GET    /api/templates             - List templates
GET    /api/templates/{id}        - Get template
GET    /health                    - Health check
```

**IAM Permissions Required**:
- DynamoDB: GetItem, PutItem, UpdateItem, DeleteItem, Query
- S3: GetObject, PutObject, DeleteObject, ListBucket
- SQS: SendMessage
- SSM: GetParameter

---

### 2. PM Agent Worker (`lambda/pm_agent/`)

**Purpose**: Process planning tasks and generate implementation plans

**Trigger**: SQS (PM Queue)

**Configuration**:
- Runtime: Python 3.11
- Memory: 1024MB
- Timeout: 300 seconds (5 minutes)
- Concurrency: 2
- Batch Size: 1

**Environment Variables**:
- `DYNAMODB_TABLE_NAME` - DynamoDB table name
- `S3_BUCKET_NAME` - S3 bucket for file storage
- `SQS_QUEUE_URL_DEV` - Dev agent queue URL

**Message Format**:
```json
{
  "action": "generate_plan",
  "project_id": "proj_20251124_120000",
  "timestamp": "2025-11-24T12:00:00Z"
}
```

**Workflow**:
1. Retrieve project context from DynamoDB
2. Call Gemini API to generate plan
3. Parse plan and extract tasks
4. Save plan to DynamoDB and S3
5. Send tasks to Dev queue
6. Update project status

**IAM Permissions Required**:
- DynamoDB: GetItem, PutItem, UpdateItem, Query
- S3: PutObject
- SQS: SendMessage, ReceiveMessage, DeleteMessage
- SSM: GetParameter

---

### 3. Dev Agent Worker (`lambda/dev_agent/`)

**Purpose**: Generate and modify code based on tasks

**Trigger**: SQS (Dev Queue)

**Configuration**:
- Runtime: Python 3.11
- Memory: 2048MB (2GB)
- Timeout: 900 seconds (15 minutes)
- Concurrency: 2
- Batch Size: 1

**Environment Variables**:
- `DYNAMODB_TABLE_NAME` - DynamoDB table name
- `S3_BUCKET_NAME` - S3 bucket for file storage
- `SQS_QUEUE_URL_QA` - QA agent queue URL

**Message Formats**:

Code Generation:
```json
{
  "action": "implement_task",
  "project_id": "proj_20251124_120000",
  "plan_id": "plan_20251124_120100",
  "task": {
    "title": "Create API endpoints",
    "description": "Implement REST API endpoints"
  },
  "timestamp": "2025-11-24T12:00:00Z"
}
```

Code Modification:
```json
{
  "action": "modify_project",
  "project_id": "proj_20251124_120000",
  "modification_id": "mod_20251124_120500",
  "request": "Add user authentication",
  "timestamp": "2025-11-24T12:05:00Z"
}
```

**Workflow**:
1. Retrieve project context and existing files
2. Call Gemini API for code generation
3. Extract code files from LLM response
4. Save generated code to DynamoDB and S3
5. Send to QA queue for testing
6. Update modification status (if applicable)

**IAM Permissions Required**:
- DynamoDB: GetItem, PutItem, UpdateItem, Query
- S3: GetObject, PutObject
- SQS: SendMessage, ReceiveMessage, DeleteMessage
- SSM: GetParameter

---

### 4. QA Agent Worker (`lambda/qa_agent/`)

**Purpose**: Test and validate generated code

**Trigger**: SQS (QA Queue)

**Configuration**:
- Runtime: Python 3.11
- Memory: 1024MB
- Timeout: 600 seconds (10 minutes)
- Concurrency: 2
- Batch Size: 1

**Environment Variables**:
- `DYNAMODB_TABLE_NAME` - DynamoDB table name
- `S3_BUCKET_NAME` - S3 bucket for file storage
- `SQS_QUEUE_URL_DEV` - Dev agent queue URL (for feedback)

**Message Format**:
```json
{
  "action": "test_code",
  "project_id": "proj_20251124_120000",
  "task": {
    "title": "Test API endpoints"
  },
  "files": ["main.py", "api.py"],
  "timestamp": "2025-11-24T12:10:00Z"
}
```

**Workflow**:
1. Retrieve code files from DynamoDB
2. Run static analysis and syntax checks
3. Analyze code quality metrics
4. Generate test report
5. Save results to DynamoDB and S3
6. Update project quality scores

**Test Types**:
- Syntax checking (Python, JavaScript, TypeScript)
- Static code analysis
- Code quality metrics
- Documentation coverage
- Test coverage detection

**IAM Permissions Required**:
- DynamoDB: GetItem, PutItem, UpdateItem, Query
- S3: GetObject, PutObject
- SQS: ReceiveMessage, DeleteMessage

---

### 5. Ops Agent Worker (`lambda/ops_agent/`)

**Purpose**: Prepare projects for deployment

**Trigger**: SQS (Ops Queue)

**Configuration**:
- Runtime: Python 3.11
- Memory: 512MB
- Timeout: 300 seconds (5 minutes)
- Concurrency: 1
- Batch Size: 1

**Environment Variables**:
- `DYNAMODB_TABLE_NAME` - DynamoDB table name
- `S3_BUCKET_NAME` - S3 bucket for file storage

**Message Format**:
```json
{
  "action": "prepare_deployment",
  "project_id": "proj_20251124_120000",
  "timestamp": "2025-11-24T12:15:00Z"
}
```

**Workflow**:
1. Retrieve project context and files
2. Detect project type
3. Generate deployment configuration
4. Create deployment package
5. Save to S3
6. Generate deployment instructions
7. Update project with deployment info

**Supported Platforms**:
- AWS Lambda (Python, Node.js)
- S3 + CloudFront (Static sites)

**IAM Permissions Required**:
- DynamoDB: GetItem, PutItem, UpdateItem, Query
- S3: GetObject, PutObject, ListBucket

---

## Shared Lambda Layer

**Name**: `agenticai-shared`

**Location**: `lambda/shared/python/`

**Contents**:
- Models: ProjectContext, Task, Plan
- Utilities: DynamoDBHelper, S3Helper, ResponseBuilder

**Usage in Lambda Functions**:
```python
from models import ProjectContext, ProjectType, ProjectStatus
from utils import DynamoDBHelper, S3Helper, ResponseBuilder

# Use shared utilities
db = DynamoDBHelper(os.environ['DYNAMODB_TABLE_NAME'])
s3 = S3Helper(os.environ['S3_BUCKET_NAME'])
```

**Compatible Runtimes**: Python 3.11

---

## SQS Queues

### PM Queue
- **Name**: `agenticai-pm-queue`
- **Visibility Timeout**: 360 seconds
- **Message Retention**: 4 days
- **DLQ**: `agenticai-pm-dlq`

### Dev Queue
- **Name**: `agenticai-dev-queue`
- **Visibility Timeout**: 960 seconds
- **Message Retention**: 4 days
- **DLQ**: `agenticai-dev-dlq`

### QA Queue
- **Name**: `agenticai-qa-queue`
- **Visibility Timeout**: 660 seconds
- **Message Retention**: 4 days
- **DLQ**: `agenticai-qa-dlq`

### Ops Queue
- **Name**: `agenticai-ops-queue`
- **Visibility Timeout**: 360 seconds
- **Message Retention**: 4 days
- **DLQ**: `agenticai-ops-dlq`

---

## DynamoDB Table

**Name**: `agenticai-data`

**Primary Key**:
- Partition Key: `PK` (String)
- Sort Key: `SK` (String)

**Global Secondary Indexes**:
- GSI1: `GSI1PK` + `GSI1SK` (Query by owner)
- GSI2: `GSI2PK` + `GSI2SK` (Query by status)

**Access Patterns**:
- Projects: `PROJECT#{id}` / `METADATA`
- Files: `PROJECT#{id}` / `FILE#{path}`
- Plans: `PROJECT#{id}` / `PLAN#{id}`
- Modifications: `PROJECT#{id}` / `MOD#{id}`
- Templates: `TEMPLATE#{id}` / `METADATA`

---

## S3 Bucket

**Name**: `agenticai-generated-code`

**Structure**:
```
projects/{project_id}/
plans/{project_id}/
deployments/{project_id}/
test_results/{project_id}/
templates/{template_id}/
```

---

## Parameter Store

**Secrets**:
- `/agenticai/gemini-api-key` - Gemini API key
- `/agenticai/github-token` - GitHub token (optional)
- `/agenticai/jwt-secret` - JWT secret (optional)

---

## Monitoring

### CloudWatch Logs

Each Lambda function logs to:
- `/aws/lambda/api-handler`
- `/aws/lambda/pm-agent-worker`
- `/aws/lambda/dev-agent-worker`
- `/aws/lambda/qa-agent-worker`
- `/aws/lambda/ops-agent-worker`

### CloudWatch Metrics

Key metrics to monitor:
- Lambda invocations
- Lambda errors
- Lambda duration
- SQS queue depth
- DynamoDB throttled requests

### CloudWatch Alarms

Recommended alarms:
- Lambda error rate > 5%
- Lambda duration > 80% of timeout
- SQS DLQ messages > 0
- DynamoDB throttled requests > 10

---

## Deployment

### Using SAM CLI

```bash
# Build
sam build

# Deploy
sam deploy --guided

# Update function
sam deploy --no-confirm-changeset
```

### Using AWS CLI

```bash
# Update function code
aws lambda update-function-code \
  --function-name api-handler \
  --zip-file fileb://function.zip

# Update environment variables
aws lambda update-function-configuration \
  --function-name api-handler \
  --environment Variables={KEY=VALUE}
```

---

## Testing

### Local Testing

```bash
# Invoke function locally
sam local invoke ApiHandler -e events/api-event.json

# Start local API
sam local start-api
```

### Integration Testing

```python
import boto3

# Send test message to SQS
sqs = boto3.client('sqs')
sqs.send_message(
    QueueUrl='https://sqs.us-east-1.amazonaws.com/123456789/agenticai-dev-queue',
    MessageBody=json.dumps({
        'action': 'implement_task',
        'project_id': 'test_project'
    })
)
```

---

## Troubleshooting

### Common Issues

1. **Lambda Timeout**: Increase timeout or optimize code
2. **Memory Limit**: Increase memory allocation
3. **DynamoDB Throttling**: Enable auto-scaling or use on-demand billing
4. **SQS Message Stuck**: Check DLQ for failed messages
5. **Permission Denied**: Verify IAM role permissions

### Debug Commands

```bash
# View logs
aws logs tail /aws/lambda/api-handler --follow

# Check function configuration
aws lambda get-function-configuration --function-name api-handler

# List SQS messages
aws sqs receive-message --queue-url QUEUE_URL

# Check DynamoDB item
aws dynamodb get-item --table-name agenticai-data --key '{"PK":{"S":"PROJECT#123"},"SK":{"S":"METADATA"}}'
```

---

## Cost Optimization

### Free Tier Limits
- Lambda: 1M requests/month, 400,000 GB-seconds
- API Gateway: 1M requests/month
- DynamoDB: 25GB storage, 25 WCU/RCU
- S3: 5GB storage, 20,000 GET, 2,000 PUT
- SQS: 1M requests/month

### Optimization Tips
1. Use Lambda reserved concurrency to limit costs
2. Enable DynamoDB on-demand billing
3. Implement S3 lifecycle policies
4. Use CloudWatch Logs retention policies
5. Monitor usage with AWS Budgets

---

## Security Best Practices

1. **Least Privilege**: Grant minimal IAM permissions
2. **Encryption**: Enable encryption at rest and in transit
3. **Secrets Management**: Use Parameter Store for sensitive data
4. **API Security**: Implement API keys and throttling
5. **Logging**: Enable CloudTrail for audit logs
6. **Network Security**: Use VPC for sensitive workloads
7. **Input Validation**: Validate all user inputs
8. **Error Handling**: Don't expose sensitive info in errors

---

## Support

For issues or questions:
1. Check CloudWatch Logs for error details
2. Review DLQ for failed messages
3. Verify IAM permissions
4. Check AWS service quotas
5. Review deployment documentation
