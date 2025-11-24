# Lambda Integration Tests

This directory contains integration tests for AWS Lambda functions using moto for AWS service mocking.

## Test Files

- `test_lambda_api_handler.py` - Tests for API Handler Lambda function
- `test_lambda_agent_workers.py` - Tests for PM, Dev, QA, and Ops Agent Worker Lambda functions

## Requirements

The tests require the following dependencies:

```bash
pip install pytest moto[dynamodb,s3,sqs,ssm] boto3
```

Or install from requirements.txt:

```bash
pip install -r requirements.txt
```

## Running the Tests

### Run all Lambda tests:

```bash
pytest tests/test_lambda_api_handler.py tests/test_lambda_agent_workers.py -v
```

### Run API Handler tests only:

```bash
pytest tests/test_lambda_api_handler.py -v
```

### Run Agent Worker tests only:

```bash
pytest tests/test_lambda_agent_workers.py -v
```

### Run specific test:

```bash
pytest tests/test_lambda_api_handler.py::test_create_project_success -v
```

## Test Coverage

### API Handler Tests (`test_lambda_api_handler.py`)

**Project Management:**
- ✓ Create project with valid data
- ✓ Create project with invalid type
- ✓ Create project without required name
- ✓ Get project by ID
- ✓ Get non-existent project (404)
- ✓ List projects with filtering
- ✓ Update project
- ✓ Delete project

**Modifications:**
- ✓ Request modification
- ✓ Request modification without request text

**Templates:**
- ✓ List templates
- ✓ Get template by ID
- ✓ Get non-existent template (404)

**General:**
- ✓ Health check endpoint
- ✓ CORS OPTIONS handling
- ✓ Invalid JSON body handling
- ✓ 404 for non-existent endpoints

### Agent Worker Tests (`test_lambda_agent_workers.py`)

**PM Agent Worker:**
- ✓ Process planning task successfully
- ✓ Handle missing project error

**Dev Agent Worker:**
- ✓ Generate code from task
- ✓ Modify existing code
- ✓ Handle invalid action

**QA Agent Worker:**
- ✓ Test code successfully
- ✓ Detect syntax errors
- ✓ Handle missing files

**Ops Agent Worker:**
- ✓ Prepare deployment
- ✓ Detect Python project type
- ✓ Detect Node.js project type
- ✓ Handle missing files

**Multi-Message Processing:**
- ✓ Process multiple messages successfully
- ✓ Handle partial failures

## Test Architecture

The tests use **moto** to mock AWS services:

- **DynamoDB**: Mocked table with GSI indexes for project/template storage
- **S3**: Mocked bucket for file storage
- **SQS**: Mocked queues for agent communication
- **SSM**: Mocked Parameter Store for secrets

### Fixtures

- `aws_credentials` - Sets up mock AWS credentials
- `mock_dynamodb_table` - Creates mocked DynamoDB table with proper schema
- `mock_s3_bucket` - Creates mocked S3 bucket
- `mock_sqs_queues` - Creates mocked SQS queues for all agents
- `mock_ssm_params` - Creates mocked SSM parameters
- `lambda_context` - Mock Lambda context object
- `api_handler_env` - Environment variables for API handler

## Troubleshooting

### Import Errors

If you encounter import errors with the `lambda` module (Python keyword conflict), the tests use `importlib.import_module()` to work around this:

```python
import importlib
app_module = importlib.import_module('lambda.api_handler.app')
lambda_handler = app_module.lambda_handler
```

### Missing Dependencies

If tests fail with missing module errors:

```bash
pip install moto[dynamodb,s3,sqs,ssm] boto3 pytest
```

### AWS Credentials

The tests automatically set mock AWS credentials. No real AWS credentials are needed.

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Run Lambda Integration Tests
  run: |
    pip install -r requirements.txt
    pytest tests/test_lambda_api_handler.py tests/test_lambda_agent_workers.py -v --cov=lambda
```

## Requirements Coverage

These tests satisfy the following requirements from the AWS deployment spec:

- **Requirement 1.3**: Lambda functions for API endpoints and agent workers
- **Requirement 2.2**: Automated testing in CI/CD pipeline

## Next Steps

After these integration tests pass:

1. Deploy Lambda functions to AWS using SAM
2. Run end-to-end tests against live AWS environment
3. Set up CloudWatch monitoring and alarms
4. Configure CI/CD pipeline for automated deployment
