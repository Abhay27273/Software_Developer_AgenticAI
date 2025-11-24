"""
Integration tests for API Handler Lambda Function.

These tests use moto to mock AWS services (DynamoDB, S3, SQS, SSM).

Requirements: 1.3, 2.2
"""

import pytest
import json
import os
import sys
import importlib
from datetime import datetime
from unittest.mock import patch, MagicMock
from moto import mock_aws
import boto3

# Add project root to Python path so lambda module can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Helper function to import lambda modules (lambda is a Python keyword)
def import_lambda_module(module_path):
    """Import a lambda module using importlib to avoid keyword conflict."""
    return importlib.import_module(module_path)


@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture
def mock_dynamodb_table(aws_credentials):
    """Create a mocked DynamoDB table."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Create table
        table = dynamodb.create_table(
            TableName='agenticai-data',
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI2PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI2SK', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'GSI1',
                    'KeySchema': [
                        {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                },
                {
                    'IndexName': 'GSI2',
                    'KeySchema': [
                        {'AttributeName': 'GSI2PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI2SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                }
            ],
            BillingMode='PROVISIONED',
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        
        yield table


@pytest.fixture
def mock_s3_bucket(aws_credentials):
    """Create a mocked S3 bucket."""
    with mock_aws():
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket='agenticai-generated-code')
        yield s3


@pytest.fixture
def mock_sqs_queues(aws_credentials):
    """Create mocked SQS queues."""
    with mock_aws():
        sqs = boto3.client('sqs', region_name='us-east-1')
        
        # Create queues
        pm_queue = sqs.create_queue(QueueName='agenticai-pm-queue')
        dev_queue = sqs.create_queue(QueueName='agenticai-dev-queue')
        qa_queue = sqs.create_queue(QueueName='agenticai-qa-queue')
        ops_queue = sqs.create_queue(QueueName='agenticai-ops-queue')
        
        yield {
            'pm': pm_queue['QueueUrl'],
            'dev': dev_queue['QueueUrl'],
            'qa': qa_queue['QueueUrl'],
            'ops': ops_queue['QueueUrl']
        }


@pytest.fixture
def mock_ssm_params(aws_credentials):
    """Create mocked SSM parameters."""
    with mock_aws():
        ssm = boto3.client('ssm', region_name='us-east-1')
        
        # Create parameters
        ssm.put_parameter(
            Name='/agenticai/gemini-api-key',
            Value='test-gemini-key',
            Type='SecureString'
        )
        
        yield ssm


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.function_name = 'api-handler'
    context.memory_limit_in_mb = 512
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:api-handler'
    context.aws_request_id = 'test-request-id-123'
    return context


@pytest.fixture
def api_handler_env(mock_sqs_queues):
    """Set up environment variables for API handler."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code',
        'SQS_QUEUE_URL_PM': mock_sqs_queues['pm'],
        'SQS_QUEUE_URL_DEV': mock_sqs_queues['dev'],
        'SQS_QUEUE_URL_QA': mock_sqs_queues['qa'],
        'SQS_QUEUE_URL_OPS': mock_sqs_queues['ops']
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


# ============================================================================
# PROJECT MANAGEMENT TESTS
# ============================================================================

def test_create_project_success(mock_dynamodb_table, mock_s3_bucket, api_handler_env, lambda_context):
    """Test successful project creation."""
    app_module = import_lambda_module('lambda.api_handler.app')
    lambda_handler = app_module.lambda_handler
    
    event = {
        'httpMethod': 'POST',
        'path': '/api/projects',
        'body': json.dumps({
            'name': 'Test Project',
            'description': 'A test project',
            'project_type': 'api',
            'owner_id': 'user123'
        }),
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 201
    body = json.loads(response['body'])
    assert body['success'] is True
    assert body['project']['name'] == 'Test Project'
    assert body['project']['type'] == 'api'
    assert 'id' in body['project']


def test_create_project_invalid_type(mock_dynamodb_table, api_handler_env, lambda_context):
    """Test project creation with invalid type."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    event = {
        'httpMethod': 'POST',
        'path': '/api/projects',
        'body': json.dumps({
            'name': 'Test Project',
            'project_type': 'invalid_type'
        }),
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['success'] is False
    assert 'VALIDATION_ERROR' in body['error']['code']


def test_create_project_missing_name(mock_dynamodb_table, api_handler_env, lambda_context):
    """Test project creation without name."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    event = {
        'httpMethod': 'POST',
        'path': '/api/projects',
        'body': json.dumps({
            'project_type': 'api'
        }),
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['success'] is False


def test_get_project_success(mock_dynamodb_table, api_handler_env, lambda_context):
    """Test successful project retrieval."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    # First create a project
    project_id = 'proj_test_123'
    mock_dynamodb_table.put_item(Item={
        'PK': f'PROJECT#{project_id}',
        'SK': 'METADATA',
        'EntityType': 'Project',
        'id': project_id,
        'name': 'Test Project',
        'type': 'api',
        'status': 'active'
    })
    
    # Now retrieve it
    event = {
        'httpMethod': 'GET',
        'path': f'/api/projects/{project_id}',
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert body['project']['id'] == project_id
    assert body['project']['name'] == 'Test Project'


def test_get_project_not_found(mock_dynamodb_table, api_handler_env, lambda_context):
    """Test retrieving non-existent project."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/projects/nonexistent_id',
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 404
    body = json.loads(response['body'])
    assert body['success'] is False


def test_list_projects(mock_dynamodb_table, api_handler_env, lambda_context):
    """Test listing projects."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    # Create test projects
    for i in range(3):
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#proj_{i}',
            'SK': 'METADATA',
            'GSI1PK': 'OWNER#user123',
            'GSI1SK': f'PROJECT#2025-11-24T12:00:0{i}Z',
            'EntityType': 'Project',
            'id': f'proj_{i}',
            'name': f'Project {i}',
            'type': 'api',
            'status': 'active',
            'owner_id': 'user123'
        })
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/projects',
        'queryStringParameters': {'owner_id': 'user123'}
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert body['count'] == 3


def test_update_project(mock_dynamodb_table, api_handler_env, lambda_context):
    """Test updating a project."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    # Create a project
    project_id = 'proj_test_update'
    mock_dynamodb_table.put_item(Item={
        'PK': f'PROJECT#{project_id}',
        'SK': 'METADATA',
        'EntityType': 'Project',
        'id': project_id,
        'name': 'Original Name',
        'type': 'api',
        'status': 'active'
    })
    
    # Update it
    event = {
        'httpMethod': 'PUT',
        'path': f'/api/projects/{project_id}',
        'body': json.dumps({
            'name': 'Updated Name',
            'description': 'New description'
        }),
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert body['project']['name'] == 'Updated Name'


def test_delete_project(mock_dynamodb_table, mock_s3_bucket, api_handler_env, lambda_context):
    """Test deleting a project."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    # Create a project
    project_id = 'proj_test_delete'
    mock_dynamodb_table.put_item(Item={
        'PK': f'PROJECT#{project_id}',
        'SK': 'METADATA',
        'EntityType': 'Project',
        'id': project_id,
        'name': 'To Delete',
        'type': 'api'
    })
    
    # Delete it
    event = {
        'httpMethod': 'DELETE',
        'path': f'/api/projects/{project_id}',
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True


# ============================================================================
# MODIFICATION TESTS
# ============================================================================

def test_request_modification(mock_dynamodb_table, mock_sqs_queues, api_handler_env, lambda_context):
    """Test requesting a project modification."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    # Create a project first
    project_id = 'proj_test_mod'
    mock_dynamodb_table.put_item(Item={
        'PK': f'PROJECT#{project_id}',
        'SK': 'METADATA',
        'EntityType': 'Project',
        'id': project_id,
        'name': 'Test Project',
        'type': 'api'
    })
    
    # Request modification
    event = {
        'httpMethod': 'POST',
        'path': f'/api/projects/{project_id}/modify',
        'body': json.dumps({
            'request': 'Add user authentication',
            'requested_by': 'user123'
        }),
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 201
    body = json.loads(response['body'])
    assert body['success'] is True
    assert 'modification' in body
    assert body['modification']['request'] == 'Add user authentication'
    
    # Verify message was sent to SQS
    sqs = boto3.client('sqs', region_name='us-east-1')
    messages = sqs.receive_message(QueueUrl=mock_sqs_queues['dev'])
    assert 'Messages' in messages


def test_request_modification_missing_request(mock_dynamodb_table, api_handler_env, lambda_context):
    """Test modification request without request text."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    event = {
        'httpMethod': 'POST',
        'path': '/api/projects/proj_123/modify',
        'body': json.dumps({}),
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['success'] is False


# ============================================================================
# TEMPLATE TESTS
# ============================================================================

def test_list_templates(mock_dynamodb_table, api_handler_env, lambda_context):
    """Test listing templates."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    # Create test templates
    for i in range(2):
        mock_dynamodb_table.put_item(Item={
            'PK': f'TEMPLATE#template_{i}',
            'SK': 'METADATA',
            'EntityType': 'Template',
            'id': f'template_{i}',
            'name': f'Template {i}',
            'category': 'api'
        })
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/templates',
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True


def test_get_template(mock_dynamodb_table, api_handler_env, lambda_context):
    """Test retrieving a specific template."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    # Create a template
    template_id = 'rest-api-fastapi'
    mock_dynamodb_table.put_item(Item={
        'PK': f'TEMPLATE#{template_id}',
        'SK': 'METADATA',
        'EntityType': 'Template',
        'id': template_id,
        'name': 'REST API with FastAPI',
        'category': 'api'
    })
    
    event = {
        'httpMethod': 'GET',
        'path': f'/api/templates/{template_id}',
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert body['template']['id'] == template_id


def test_get_template_not_found(mock_dynamodb_table, api_handler_env, lambda_context):
    """Test retrieving non-existent template."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/templates/nonexistent',
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 404
    body = json.loads(response['body'])
    assert body['success'] is False


# ============================================================================
# GENERAL TESTS
# ============================================================================

def test_health_check(api_handler_env, lambda_context):
    """Test health check endpoint."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    event = {
        'httpMethod': 'GET',
        'path': '/health',
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert body['status'] == 'healthy'


def test_cors_options(api_handler_env, lambda_context):
    """Test CORS OPTIONS request."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    event = {
        'httpMethod': 'OPTIONS',
        'path': '/api/projects',
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 200
    assert 'Access-Control-Allow-Origin' in response['headers']


def test_invalid_json_body(api_handler_env, lambda_context):
    """Test handling of invalid JSON in request body."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    event = {
        'httpMethod': 'POST',
        'path': '/api/projects',
        'body': 'invalid json {',
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'INVALID_JSON' in body['error']['code']


def test_not_found_endpoint(api_handler_env, lambda_context):
    """Test accessing non-existent endpoint."""
    lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/nonexistent',
        'queryStringParameters': None
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response['statusCode'] == 404
    body = json.loads(response['body'])
    assert body['success'] is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
