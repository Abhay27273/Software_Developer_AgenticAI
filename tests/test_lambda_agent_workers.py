"""
Integration tests for Agent Worker Lambda Functions.

These tests use moto to mock AWS services and test PM, Dev, QA, and Ops agent workers.

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
        
        table = dynamodb.create_table(
            TableName='agenticai-data',
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
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
        
        dev_queue = sqs.create_queue(QueueName='agenticai-dev-queue')
        qa_queue = sqs.create_queue(QueueName='agenticai-qa-queue')
        
        yield {
            'dev': dev_queue['QueueUrl'],
            'qa': qa_queue['QueueUrl']
        }


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.function_name = 'test-worker'
    context.memory_limit_in_mb = 1024
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-worker'
    context.aws_request_id = 'test-request-id-123'
    return context


# ============================================================================
# PM AGENT WORKER TESTS
# ============================================================================

def test_pm_agent_process_planning_task(mock_dynamodb_table, mock_s3_bucket, mock_sqs_queues, lambda_context):
    """Test PM agent processing a planning task."""
    # Set up environment
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code',
        'SQS_QUEUE_URL_DEV': mock_sqs_queues['dev']
    }
    
    with patch.dict(os.environ, env_vars):
        # Create a test project
        project_id = 'proj_test_123'
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': 'METADATA',
            'EntityType': 'Project',
            'id': project_id,
            'name': 'Test Project',
            'type': 'api',
            'description': 'A test API project',
            'status': 'pending'
        })
        
        # Mock the LLM call
        mock_llm_response = """
        Task 1: Set up project structure
        Create the basic directory structure and configuration files.
        
        Task 2: Implement API endpoints
        Create REST API endpoints for CRUD operations.
        
        Task 3: Add authentication
        Implement JWT-based authentication.
        """
        
        with patch('lambda.pm_agent.worker.call_gemini_api', return_value=mock_llm_response):
            lambda_handler = import_lambda_module('lambda.pm_agent.worker').lambda_handler
            
            # Create SQS event
            event = {
                'Records': [
                    {
                        'messageId': 'msg-123',
                        'body': json.dumps({
                            'action': 'create_plan',
                            'project_id': project_id
                        })
                    }
                ]
            }
            
            response = lambda_handler(event, lambda_context)
            
            assert response['processed'] == 1
            assert response['errors'] == 0
            assert len(response['results']) == 1
            assert response['results'][0]['success'] is True
            assert response['results'][0]['project_id'] == project_id


def test_pm_agent_missing_project(mock_dynamodb_table, mock_sqs_queues, lambda_context):
    """Test PM agent with non-existent project."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code',
        'SQS_QUEUE_URL_DEV': mock_sqs_queues['dev']
    }
    
    with patch.dict(os.environ, env_vars):
        lambda_handler = import_lambda_module('lambda.pm_agent.worker').lambda_handler
        
        event = {
            'Records': [
                {
                    'messageId': 'msg-123',
                    'body': json.dumps({
                        'action': 'create_plan',
                        'project_id': 'nonexistent_project'
                    })
                }
            ]
        }
        
        with pytest.raises(Exception):
            lambda_handler(event, lambda_context)


# ============================================================================
# DEV AGENT WORKER TESTS
# ============================================================================

def test_dev_agent_code_generation(mock_dynamodb_table, mock_s3_bucket, mock_sqs_queues, lambda_context):
    """Test Dev agent generating code."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code',
        'SQS_QUEUE_URL_QA': mock_sqs_queues['qa']
    }
    
    with patch.dict(os.environ, env_vars):
        # Create a test project
        project_id = 'proj_dev_test'
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': 'METADATA',
            'EntityType': 'Project',
            'id': project_id,
            'name': 'Dev Test Project',
            'type': 'api',
            'description': 'Test project for dev agent'
        })
        
        # Mock LLM response with code
        mock_llm_response = """
        File: main.py
        ```python
        from fastapi import FastAPI
        
        app = FastAPI()
        
        @app.get("/")
        def read_root():
            return {"message": "Hello World"}
        ```
        
        File: requirements.txt
        ```
        fastapi==0.104.1
        uvicorn==0.24.0
        ```
        """
        
        with patch('lambda.dev_agent.worker.call_gemini_api', return_value=mock_llm_response):
            lambda_handler = import_lambda_module('lambda.dev_agent.worker').lambda_handler
            
            event = {
                'Records': [
                    {
                        'messageId': 'msg-456',
                        'body': json.dumps({
                            'action': 'implement_task',
                            'project_id': project_id,
                            'task': {
                                'title': 'Create FastAPI application',
                                'description': 'Set up basic FastAPI app'
                            }
                        })
                    }
                ]
            }
            
            response = lambda_handler(event, lambda_context)
            
            assert response['processed'] == 1
            assert response['errors'] == 0
            assert response['results'][0]['success'] is True
            assert response['results'][0]['files_generated'] > 0


def test_dev_agent_code_modification(mock_dynamodb_table, mock_s3_bucket, mock_sqs_queues, lambda_context):
    """Test Dev agent modifying existing code."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code',
        'SQS_QUEUE_URL_QA': mock_sqs_queues['qa']
    }
    
    with patch.dict(os.environ, env_vars):
        # Create project with existing files
        project_id = 'proj_mod_test'
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': 'METADATA',
            'EntityType': 'Project',
            'id': project_id,
            'name': 'Modification Test',
            'type': 'api'
        })
        
        # Add existing file
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': 'FILE#main.py',
            'EntityType': 'ProjectFile',
            'file_path': 'main.py',
            'content': 'print("Hello")'
        })
        
        # Add modification record
        mod_id = 'mod_123'
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': f'MOD#{mod_id}',
            'EntityType': 'Modification',
            'id': mod_id,
            'project_id': project_id,
            'request': 'Add error handling',
            'status': 'pending'
        })
        
        mock_llm_response = """
        File: main.py
        ```python
        try:
            print("Hello")
        except Exception as e:
            print(f"Error: {e}")
        ```
        """
        
        with patch('lambda.dev_agent.worker.call_gemini_api', return_value=mock_llm_response):
            lambda_handler = import_lambda_module('lambda.dev_agent.worker').lambda_handler
            
            event = {
                'Records': [
                    {
                        'messageId': 'msg-789',
                        'body': json.dumps({
                            'action': 'modify_project',
                            'project_id': project_id,
                            'modification_id': mod_id,
                            'request': 'Add error handling'
                        })
                    }
                ]
            }
            
            response = lambda_handler(event, lambda_context)
            
            assert response['processed'] == 1
            assert response['errors'] == 0


def test_dev_agent_invalid_action(mock_dynamodb_table, lambda_context):
    """Test Dev agent with invalid action."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code'
    }
    
    with patch.dict(os.environ, env_vars):
        lambda_handler = import_lambda_module('lambda.dev_agent.worker').lambda_handler
        
        event = {
            'Records': [
                {
                    'messageId': 'msg-invalid',
                    'body': json.dumps({
                        'action': 'invalid_action',
                        'project_id': 'proj_123'
                    })
                }
            ]
        }
        
        with pytest.raises(Exception):
            lambda_handler(event, lambda_context)


# ============================================================================
# QA AGENT WORKER TESTS
# ============================================================================

def test_qa_agent_test_code(mock_dynamodb_table, mock_s3_bucket, lambda_context):
    """Test QA agent testing code."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code'
    }
    
    with patch.dict(os.environ, env_vars):
        # Create project with files
        project_id = 'proj_qa_test'
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': 'METADATA',
            'EntityType': 'Project',
            'id': project_id,
            'name': 'QA Test Project',
            'type': 'api'
        })
        
        # Add valid Python file
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': 'FILE#main.py',
            'EntityType': 'ProjectFile',
            'file_path': 'main.py',
            'content': 'def hello():\n    return "Hello World"'
        })
        
        lambda_handler = import_lambda_module('lambda.qa_agent.worker').lambda_handler
        
        event = {
            'Records': [
                {
                    'messageId': 'msg-qa-1',
                    'body': json.dumps({
                        'action': 'test_code',
                        'project_id': project_id,
                        'files': ['main.py']
                    })
                }
            ]
        }
        
        response = lambda_handler(event, lambda_context)
        
        assert response['processed'] == 1
        assert response['errors'] == 0
        assert response['results'][0]['success'] is True
        assert 'pass_rate' in response['results'][0]


def test_qa_agent_syntax_error_detection(mock_dynamodb_table, mock_s3_bucket, lambda_context):
    """Test QA agent detecting syntax errors."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code'
    }
    
    with patch.dict(os.environ, env_vars):
        # Create project with invalid Python file
        project_id = 'proj_qa_error'
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': 'METADATA',
            'EntityType': 'Project',
            'id': project_id,
            'name': 'QA Error Test',
            'type': 'api'
        })
        
        # Add file with syntax error
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': 'FILE#bad.py',
            'EntityType': 'ProjectFile',
            'file_path': 'bad.py',
            'content': 'def broken(\n    return "missing closing paren"'
        })
        
        lambda_handler = import_lambda_module('lambda.qa_agent.worker').lambda_handler
        
        event = {
            'Records': [
                {
                    'messageId': 'msg-qa-2',
                    'body': json.dumps({
                        'action': 'test_code',
                        'project_id': project_id,
                        'files': ['bad.py']
                    })
                }
            ]
        }
        
        response = lambda_handler(event, lambda_context)
        
        assert response['processed'] == 1
        assert response['results'][0]['status'] == 'failed'


def test_qa_agent_no_files(mock_dynamodb_table, lambda_context):
    """Test QA agent with no files to test."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code'
    }
    
    with patch.dict(os.environ, env_vars):
        # Create project without files
        project_id = 'proj_qa_empty'
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': 'METADATA',
            'EntityType': 'Project',
            'id': project_id,
            'name': 'Empty Project',
            'type': 'api'
        })
        
        lambda_handler = import_lambda_module('lambda.qa_agent.worker').lambda_handler
        
        event = {
            'Records': [
                {
                    'messageId': 'msg-qa-3',
                    'body': json.dumps({
                        'action': 'test_code',
                        'project_id': project_id
                    })
                }
            ]
        }
        
        with pytest.raises(Exception):
            lambda_handler(event, lambda_context)


# ============================================================================
# OPS AGENT WORKER TESTS
# ============================================================================

def test_ops_agent_deployment_preparation(mock_dynamodb_table, mock_s3_bucket, lambda_context):
    """Test Ops agent preparing deployment."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code'
    }
    
    with patch.dict(os.environ, env_vars):
        # Create project with files
        project_id = 'proj_ops_test'
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': 'METADATA',
            'EntityType': 'Project',
            'id': project_id,
            'name': 'Ops Test Project',
            'type': 'api'
        })
        
        # Add project files
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': 'FILE#main.py',
            'EntityType': 'ProjectFile',
            'file_path': 'main.py',
            'content': 'from fastapi import FastAPI\napp = FastAPI()'
        })
        
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': 'FILE#requirements.txt',
            'EntityType': 'ProjectFile',
            'file_path': 'requirements.txt',
            'content': 'fastapi==0.104.1'
        })
        
        lambda_handler = import_lambda_module('lambda.ops_agent.worker').lambda_handler
        
        event = {
            'Records': [
                {
                    'messageId': 'msg-ops-1',
                    'body': json.dumps({
                        'action': 'prepare_deployment',
                        'project_id': project_id
                    })
                }
            ]
        }
        
        response = lambda_handler(event, lambda_context)
        
        assert response['processed'] == 1
        assert response['errors'] == 0
        assert response['results'][0]['success'] is True
        assert 'deployment_id' in response['results'][0]
        assert response['results'][0]['status'] == 'ready'


def test_ops_agent_detect_python_project(mock_dynamodb_table, mock_s3_bucket, lambda_context):
    """Test Ops agent detecting Python project type."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code'
    }
    
    with patch.dict(os.environ, env_vars):
        ops_module = import_lambda_module('lambda.ops_agent.worker')
        detect_project_type = ops_module.detect_project_type
        
        files = {
            'main.py': 'print("hello")',
            'requirements.txt': 'fastapi==0.104.1'
        }
        
        project_type = detect_project_type(files)
        assert project_type == 'python-web'


def test_ops_agent_detect_node_project(mock_dynamodb_table, lambda_context):
    """Test Ops agent detecting Node.js project type."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code'
    }
    
    with patch.dict(os.environ, env_vars):
        ops_module = import_lambda_module('lambda.ops_agent.worker')
        detect_project_type = ops_module.detect_project_type
        
        files = {
            'index.js': 'console.log("hello")',
            'package.json': '{"name": "test"}'
        }
        
        project_type = detect_project_type(files)
        assert project_type == 'node-backend'


def test_ops_agent_no_files(mock_dynamodb_table, lambda_context):
    """Test Ops agent with no files."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code'
    }
    
    with patch.dict(os.environ, env_vars):
        # Create project without files
        project_id = 'proj_ops_empty'
        mock_dynamodb_table.put_item(Item={
            'PK': f'PROJECT#{project_id}',
            'SK': 'METADATA',
            'EntityType': 'Project',
            'id': project_id,
            'name': 'Empty Project',
            'type': 'api'
        })
        
        lambda_handler = import_lambda_module('lambda.ops_agent.worker').lambda_handler
        
        event = {
            'Records': [
                {
                    'messageId': 'msg-ops-2',
                    'body': json.dumps({
                        'action': 'prepare_deployment',
                        'project_id': project_id
                    })
                }
            ]
        }
        
        with pytest.raises(Exception):
            lambda_handler(event, lambda_context)


# ============================================================================
# MULTI-MESSAGE TESTS
# ============================================================================

def test_multiple_messages_success(mock_dynamodb_table, mock_s3_bucket, lambda_context):
    """Test processing multiple SQS messages successfully."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code'
    }
    
    with patch.dict(os.environ, env_vars):
        # Create multiple projects
        for i in range(3):
            project_id = f'proj_multi_{i}'
            mock_dynamodb_table.put_item(Item={
                'PK': f'PROJECT#{project_id}',
                'SK': 'METADATA',
                'EntityType': 'Project',
                'id': project_id,
                'name': f'Project {i}',
                'type': 'api'
            })
            
            mock_dynamodb_table.put_item(Item={
                'PK': f'PROJECT#{project_id}',
                'SK': 'FILE#main.py',
                'EntityType': 'ProjectFile',
                'file_path': 'main.py',
                'content': f'# Project {i}'
            })
        
        lambda_handler = import_lambda_module('lambda.qa_agent.worker').lambda_handler
        
        event = {
            'Records': [
                {
                    'messageId': f'msg-{i}',
                    'body': json.dumps({
                        'action': 'test_code',
                        'project_id': f'proj_multi_{i}',
                        'files': ['main.py']
                    })
                }
                for i in range(3)
            ]
        }
        
        response = lambda_handler(event, lambda_context)
        
        assert response['processed'] == 3
        assert response['errors'] == 0


def test_multiple_messages_partial_failure(mock_dynamodb_table, lambda_context):
    """Test processing multiple messages with some failures."""
    env_vars = {
        'DYNAMODB_TABLE_NAME': 'agenticai-data',
        'S3_BUCKET_NAME': 'agenticai-generated-code'
    }
    
    with patch.dict(os.environ, env_vars):
        # Create only one project (others will fail)
        mock_dynamodb_table.put_item(Item={
            'PK': 'PROJECT#proj_exists',
            'SK': 'METADATA',
            'EntityType': 'Project',
            'id': 'proj_exists',
            'name': 'Existing Project',
            'type': 'api'
        })
        
        mock_dynamodb_table.put_item(Item={
            'PK': 'PROJECT#proj_exists',
            'SK': 'FILE#main.py',
            'EntityType': 'ProjectFile',
            'file_path': 'main.py',
            'content': '# Valid'
        })
        
        lambda_handler = import_lambda_module('lambda.qa_agent.worker').lambda_handler
        
        event = {
            'Records': [
                {
                    'messageId': 'msg-success',
                    'body': json.dumps({
                        'action': 'test_code',
                        'project_id': 'proj_exists',
                        'files': ['main.py']
                    })
                },
                {
                    'messageId': 'msg-fail',
                    'body': json.dumps({
                        'action': 'test_code',
                        'project_id': 'proj_nonexistent'
                    })
                }
            ]
        }
        
        with pytest.raises(Exception):
            response = lambda_handler(event, lambda_context)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
