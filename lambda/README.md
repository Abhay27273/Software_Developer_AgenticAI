# Lambda Functions for AWS Deployment

This directory contains all Lambda functions and shared code for the serverless AWS deployment of the AI-powered Software Development Agentic System.

## Directory Structure

```
lambda/
├── api_handler/              # REST API handler
│   ├── app.py
│   └── requirements.txt
├── pm_agent/                 # PM agent worker
│   ├── worker.py
│   └── requirements.txt
├── dev_agent/                # Dev agent worker
│   ├── worker.py
│   └── requirements.txt
├── qa_agent/                 # QA agent worker
│   ├── worker.py
│   └── requirements.txt
├── ops_agent/                # Ops agent worker
│   ├── worker.py
│   └── requirements.txt
├── shared/                   # Shared Lambda layer
│   ├── python/
│   │   ├── models/
│   │   └── utils/
│   └── README.md
├── examples/                 # Example code and utilities
│   └── parameter_store_example.py
├── LAMBDA_FUNCTIONS_REFERENCE.md
└── README.md (this file)
```

## Quick Start

### Prerequisites

1. AWS Account with appropriate permissions
2. AWS CLI configured
3. SAM CLI installed
4. Python 3.11

### Setup

1. **Install dependencies for each function**:
```bash
cd lambda/api_handler && pip install -r requirements.txt
cd ../pm_agent && pip install -r requirements.txt
cd ../dev_agent && pip install -r requirements.txt
cd ../qa_agent && pip install -r requirements.txt
cd ../ops_agent && pip install -r requirements.txt
```

2. **Set up Parameter Store secrets**:
```bash
aws ssm put-parameter \
  --name /agenticai/gemini-api-key \
  --value "YOUR_API_KEY" \
  --type SecureString
```

3. **Deploy using SAM**:
```bash
cd ../..  # Back to project root
sam build
sam deploy --guided
```

## Lambda Functions Overview

### 1. API Handler
- **Purpose**: Handle REST API requests
- **Trigger**: API Gateway
- **Memory**: 512MB
- **Timeout**: 30s

### 2. PM Agent Worker
- **Purpose**: Generate project plans
- **Trigger**: SQS (PM Queue)
- **Memory**: 1024MB
- **Timeout**: 5 minutes

### 3. Dev Agent Worker
- **Purpose**: Generate and modify code
- **Trigger**: SQS (Dev Queue)
- **Memory**: 2048MB
- **Timeout**: 15 minutes

### 4. QA Agent Worker
- **Purpose**: Test and validate code
- **Trigger**: SQS (QA Queue)
- **Memory**: 1024MB
- **Timeout**: 10 minutes

### 5. Ops Agent Worker
- **Purpose**: Prepare deployments
- **Trigger**: SQS (Ops Queue)
- **Memory**: 512MB
- **Timeout**: 5 minutes

## Shared Layer

The `shared/` directory contains common code used by all Lambda functions:

- **Models**: Data models (ProjectContext, Task, Plan)
- **Utilities**: Helper functions (DynamoDB, S3, Response building)

The shared layer is automatically included in all Lambda functions via the SAM template.

## Development

### Local Testing

Test Lambda functions locally using SAM:

```bash
# Start local API
sam local start-api

# Invoke specific function
sam local invoke ApiHandler -e events/test-event.json

# Generate sample event
sam local generate-event apigateway aws-proxy > events/api-event.json
```

### Unit Testing

```bash
# Run tests
pytest tests/lambda/

# Run with coverage
pytest tests/lambda/ --cov=lambda --cov-report=html
```

### Adding a New Lambda Function

1. Create new directory: `lambda/new_function/`
2. Add `worker.py` or `app.py`
3. Add `requirements.txt`
4. Update `template.yaml` with function definition
5. Add to shared layer if needed
6. Write tests in `tests/lambda/test_new_function.py`

## Environment Variables

All Lambda functions use these environment variables:

- `DYNAMODB_TABLE_NAME` - DynamoDB table name
- `S3_BUCKET_NAME` - S3 bucket for storage
- `SQS_QUEUE_URL_*` - SQS queue URLs
- `LOG_LEVEL` - Logging level (INFO, DEBUG, ERROR)

Secrets are loaded from Parameter Store:
- `/agenticai/gemini-api-key`
- `/agenticai/github-token`

## Architecture

```
┌─────────────────┐
│  API Gateway    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  API Handler    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   SQS Queues    │
└────────┬────────┘
         │
    ┌────┴────┬────────┬────────┐
    ▼         ▼        ▼        ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│  PM   │ │  Dev  │ │  QA   │ │  Ops  │
│Worker │ │Worker │ │Worker │ │Worker │
└───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘
    │         │         │         │
    └─────────┴─────────┴─────────┘
              │
              ▼
    ┌──────────────────┐
    │ DynamoDB + S3    │
    └──────────────────┘
```

## Message Flow

1. **API Request** → API Handler
2. **Create Project** → PM Queue
3. **PM Worker** → Generate Plan → Dev Queue
4. **Dev Worker** → Generate Code → QA Queue
5. **QA Worker** → Test Code → Results to DynamoDB
6. **Ops Worker** → Prepare Deployment

## Error Handling

All Lambda functions implement:

1. **Structured Logging**: JSON-formatted logs
2. **Error Responses**: Standardized error format
3. **Retry Logic**: Automatic retries with exponential backoff
4. **Dead Letter Queues**: Failed messages sent to DLQ
5. **CloudWatch Alarms**: Alerts for errors and timeouts

## Monitoring

### CloudWatch Logs

Each function logs to its own log group:
- `/aws/lambda/api-handler`
- `/aws/lambda/pm-agent-worker`
- `/aws/lambda/dev-agent-worker`
- `/aws/lambda/qa-agent-worker`
- `/aws/lambda/ops-agent-worker`

### CloudWatch Metrics

Monitor these metrics:
- Invocations
- Errors
- Duration
- Throttles
- Concurrent Executions

### CloudWatch Alarms

Set up alarms for:
- Error rate > 5%
- Duration > 80% of timeout
- Throttles > 0
- DLQ messages > 0

## Security

### IAM Roles

Each Lambda function has its own IAM role with least-privilege permissions:

- **API Handler**: DynamoDB, S3, SQS (send)
- **PM Worker**: DynamoDB, S3, SQS (send/receive)
- **Dev Worker**: DynamoDB, S3, SQS (send/receive)
- **QA Worker**: DynamoDB, S3, SQS (receive)
- **Ops Worker**: DynamoDB, S3, SQS (receive)

### Secrets Management

Sensitive data is stored in Parameter Store:
```python
import boto3

ssm = boto3.client('ssm')
api_key = ssm.get_parameter(
    Name='/agenticai/gemini-api-key',
    WithDecryption=True
)['Parameter']['Value']
```

### Network Security

- All API calls use HTTPS
- API Gateway has throttling enabled
- Lambda functions can be placed in VPC if needed

## Performance Optimization

### Cold Start Reduction

1. **Provisioned Concurrency**: Keep functions warm
2. **Smaller Packages**: Minimize deployment size
3. **Lazy Loading**: Import heavy libraries only when needed
4. **Connection Reuse**: Initialize clients outside handler

### Memory Optimization

- API Handler: 512MB (fast responses)
- PM Worker: 1024MB (LLM calls)
- Dev Worker: 2048MB (code generation)
- QA Worker: 1024MB (testing)
- Ops Worker: 512MB (configuration)

### Timeout Configuration

- API Handler: 30s (user-facing)
- PM Worker: 5 minutes (planning)
- Dev Worker: 15 minutes (code generation)
- QA Worker: 10 minutes (testing)
- Ops Worker: 5 minutes (deployment prep)

## Cost Optimization

### Free Tier Usage

- Lambda: 1M requests/month
- API Gateway: 1M requests/month
- DynamoDB: 25GB storage
- S3: 5GB storage
- SQS: 1M requests/month

### Cost Reduction Tips

1. Use reserved concurrency to limit costs
2. Enable DynamoDB on-demand billing
3. Implement S3 lifecycle policies
4. Set CloudWatch Logs retention to 7 days
5. Monitor usage with AWS Budgets

## Troubleshooting

### Common Issues

**Lambda Timeout**
- Increase timeout in SAM template
- Optimize code for performance
- Check for infinite loops

**Memory Limit Exceeded**
- Increase memory allocation
- Optimize memory usage
- Check for memory leaks

**Permission Denied**
- Verify IAM role permissions
- Check resource policies
- Review CloudTrail logs

**DynamoDB Throttling**
- Enable auto-scaling
- Use on-demand billing
- Implement exponential backoff

**SQS Message Stuck**
- Check DLQ for failed messages
- Verify visibility timeout
- Review error logs

### Debug Commands

```bash
# View recent logs
aws logs tail /aws/lambda/api-handler --follow

# Get function configuration
aws lambda get-function-configuration --function-name api-handler

# Invoke function manually
aws lambda invoke \
  --function-name api-handler \
  --payload '{"test": "data"}' \
  response.json

# Check SQS queue
aws sqs get-queue-attributes \
  --queue-url QUEUE_URL \
  --attribute-names All
```

## Deployment

### Using SAM

```bash
# Build all functions
sam build

# Deploy to AWS
sam deploy --guided

# Deploy with specific parameters
sam deploy \
  --parameter-overrides \
    Environment=production \
    DynamoDBTableName=agenticai-data
```

### Using GitHub Actions

The CI/CD pipeline automatically deploys on push to main:

```yaml
- name: Deploy to AWS
  run: |
    sam build
    sam deploy --no-confirm-changeset
```

### Rollback

```bash
# List versions
aws lambda list-versions-by-function --function-name api-handler

# Update alias to previous version
aws lambda update-alias \
  --function-name api-handler \
  --name live \
  --function-version 2
```

## Testing

### Unit Tests

```bash
pytest tests/lambda/test_api_handler.py
pytest tests/lambda/test_pm_worker.py
pytest tests/lambda/test_dev_worker.py
pytest tests/lambda/test_qa_worker.py
pytest tests/lambda/test_ops_worker.py
```

### Integration Tests

```bash
pytest tests/integration/test_lambda_integration.py
```

### Load Tests

```bash
# Using Artillery
artillery run tests/load/lambda-load-test.yml
```

## Documentation

- [Lambda Functions Reference](./LAMBDA_FUNCTIONS_REFERENCE.md) - Detailed function documentation
- [Shared Layer README](./shared/README.md) - Shared code documentation
- [AWS Deployment Design](../.kiro/specs/aws-deployment/design.md) - Architecture design
- [Implementation Summary](../.kiro/specs/aws-deployment/TASK_3_LAMBDA_REFACTORING_SUMMARY.md) - Implementation details

## Support

For issues or questions:
1. Check CloudWatch Logs for errors
2. Review DLQ for failed messages
3. Verify IAM permissions
4. Check AWS service quotas
5. Consult the troubleshooting guide

## Contributing

When adding new Lambda functions:
1. Follow the existing structure
2. Add comprehensive error handling
3. Include unit tests
4. Update documentation
5. Add CloudWatch alarms
6. Test locally before deploying

## License

See project root LICENSE file.
