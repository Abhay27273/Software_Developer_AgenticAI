"""
QA Agent Worker Lambda Function

This Lambda function processes QA/testing tasks from SQS queue.
It integrates the existing QA agent logic for code testing and validation.

Requirements: 1.3, 2.2
"""

import json
import os
import logging
import tempfile
import subprocess
from datetime import datetime
from typing import Dict, Any, List
import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')
ssm_client = boto3.client('ssm')

# Environment variables
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'agenticai-data')
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'agenticai-generated-code')
SQS_QUEUE_URL_DEV = os.environ.get('SQS_QUEUE_URL_DEV', '')
GEMINI_API_KEY = None  # Will be loaded from Parameter Store

# DynamoDB table
table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def get_secret(name: str) -> str:
    """Retrieve secret from Parameter Store."""
    try:
        response = ssm_client.get_parameter(
            Name=f'/agenticai/{name}',
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except ClientError as e:
        logger.error(f"Error retrieving secret {name}: {e}")
        raise


def initialize_api_key():
    """Initialize API key from Parameter Store (lazy loading)."""
    global GEMINI_API_KEY
    if GEMINI_API_KEY is None:
        GEMINI_API_KEY = get_secret('gemini-api-key')
        os.environ['GEMINI_API_KEY'] = GEMINI_API_KEY


def get_project_files(project_id: str, file_names: List[str] = None) -> Dict[str, str]:
    """Retrieve project files from DynamoDB."""
    try:
        if file_names:
            # Get specific files
            files = {}
            for file_name in file_names:
                response = table.get_item(
                    Key={
                        'PK': f'PROJECT#{project_id}',
                        'SK': f'FILE#{file_name}'
                    }
                )
                if 'Item' in response:
                    files[file_name] = response['Item'].get('content', '')
            return files
        else:
            # Get all files
            response = table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk_prefix)',
                ExpressionAttributeValues={
                    ':pk': f'PROJECT#{project_id}',
                    ':sk_prefix': 'FILE#'
                }
            )
            
            files = {}
            for item in response.get('Items', []):
                file_path = item['file_path']
                files[file_path] = item.get('content', '')
            
            return files
    except Exception as e:
        logger.error(f"Error getting project files: {e}")
        return {}


def run_syntax_check(file_path: str, content: str) -> Dict[str, Any]:
    """Run syntax check on code file."""
    issues = []
    
    try:
        # Determine file type
        if file_path.endswith('.py'):
            # Python syntax check
            try:
                compile(content, file_path, 'exec')
            except SyntaxError as e:
                issues.append({
                    'type': 'syntax_error',
                    'file': file_path,
                    'line': e.lineno,
                    'message': str(e)
                })
        
        elif file_path.endswith('.js') or file_path.endswith('.ts'):
            # JavaScript/TypeScript - basic check
            # In production, you would use a proper linter
            if 'function(' in content and not content.count('(') == content.count(')'):
                issues.append({
                    'type': 'syntax_error',
                    'file': file_path,
                    'message': 'Mismatched parentheses'
                })
        
    except Exception as e:
        logger.error(f"Error checking syntax for {file_path}: {e}")
        issues.append({
            'type': 'check_error',
            'file': file_path,
            'message': str(e)
        })
    
    return {
        'file': file_path,
        'passed': len(issues) == 0,
        'issues': issues
    }


def run_static_analysis(files: Dict[str, str]) -> List[Dict[str, Any]]:
    """Run static analysis on code files."""
    results = []
    
    for file_path, content in files.items():
        result = run_syntax_check(file_path, content)
        results.append(result)
    
    return results


def analyze_code_quality(files: Dict[str, str]) -> Dict[str, Any]:
    """Analyze code quality metrics."""
    metrics = {
        'total_files': len(files),
        'total_lines': 0,
        'avg_file_size': 0,
        'has_documentation': False,
        'has_tests': False
    }
    
    for file_path, content in files.items():
        lines = content.split('\n')
        metrics['total_lines'] += len(lines)
        
        # Check for documentation
        if 'README' in file_path or '"""' in content or '/*' in content:
            metrics['has_documentation'] = True
        
        # Check for tests
        if 'test_' in file_path or '_test' in file_path or 'spec.' in file_path:
            metrics['has_tests'] = True
    
    if metrics['total_files'] > 0:
        metrics['avg_file_size'] = metrics['total_lines'] / metrics['total_files']
    
    return metrics


def generate_test_report(project_id: str, test_results: List[Dict[str, Any]], 
                        quality_metrics: Dict[str, Any]) -> str:
    """Generate a comprehensive test report."""
    passed_tests = sum(1 for r in test_results if r.get('passed', False))
    total_tests = len(test_results)
    
    report = {
        'project_id': project_id,
        'timestamp': datetime.utcnow().isoformat(),
        'summary': {
            'total_tests': total_tests,
            'passed': passed_tests,
            'failed': total_tests - passed_tests,
            'pass_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0
        },
        'test_results': test_results,
        'quality_metrics': quality_metrics,
        'status': 'passed' if passed_tests == total_tests else 'failed'
    }
    
    return report


def save_test_results(project_id: str, report: Dict[str, Any]):
    """Save test results to DynamoDB and S3."""
    try:
        # Save to DynamoDB
        test_id = f"test_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        test_item = {
            'PK': f'PROJECT#{project_id}',
            'SK': f'TEST#{test_id}',
            'EntityType': 'TestResult',
            'id': test_id,
            'project_id': project_id,
            'timestamp': datetime.utcnow().isoformat(),
            'status': report['status'],
            'summary': report['summary'],
            'quality_metrics': report['quality_metrics']
        }
        
        table.put_item(Item=test_item)
        
        # Save full report to S3
        s3_key = f'test_results/{project_id}/{test_id}.json'
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(report, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"Saved test results for project {project_id}")
    except Exception as e:
        logger.error(f"Error saving test results: {e}")


def process_testing_task(message_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a testing task.
    
    This function:
    1. Retrieves code files
    2. Runs static analysis and syntax checks
    3. Analyzes code quality
    4. Generates test report
    5. Saves results
    """
    try:
        action = message_body.get('action')
        project_id = message_body.get('project_id')
        file_names = message_body.get('files')
        
        if not project_id:
            raise ValueError('project_id is required')
        
        logger.info(f"Processing testing task for project {project_id}")
        
        # Get project files
        files = get_project_files(project_id, file_names)
        
        if not files:
            raise ValueError(f'No files found for project {project_id}')
        
        logger.info(f"Testing {len(files)} files")
        
        # Run static analysis
        test_results = run_static_analysis(files)
        
        # Analyze code quality
        quality_metrics = analyze_code_quality(files)
        
        # Generate test report
        report = generate_test_report(project_id, test_results, quality_metrics)
        
        # Save test results
        save_test_results(project_id, report)
        
        # Update project with test results
        table.update_item(
            Key={
                'PK': f'PROJECT#{project_id}',
                'SK': 'METADATA'
            },
            UpdateExpression='SET test_coverage = :coverage, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':coverage': report['summary']['pass_rate'] / 100,
                ':updated_at': datetime.utcnow().isoformat()
            }
        )
        
        logger.info(f"Completed testing for project {project_id}: {report['status']}")
        
        return {
            'success': True,
            'project_id': project_id,
            'status': report['status'],
            'pass_rate': report['summary']['pass_rate'],
            'tests_run': report['summary']['total_tests']
        }
        
    except Exception as e:
        logger.error(f"Error processing testing task: {e}", exc_info=True)
        raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for QA Agent worker.
    
    Processes SQS messages containing testing tasks.
    """
    logger.info(f"QA Agent worker invoked with {len(event.get('Records', []))} messages")
    
    results = []
    errors = []
    
    for record in event.get('Records', []):
        try:
            # Parse message body
            message_body = json.loads(record['body'])
            
            # Process the task
            result = process_testing_task(message_body)
            results.append(result)
            
            logger.info(f"Successfully processed message: {record['messageId']}")
            
        except Exception as e:
            error_msg = f"Error processing message {record.get('messageId')}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append({
                'messageId': record.get('messageId'),
                'error': str(e)
            })
    
    # Return summary
    response = {
        'processed': len(results),
        'errors': len(errors),
        'results': results
    }
    
    if errors:
        response['error_details'] = errors
    
    logger.info(f"QA Agent worker completed: {response}")
    
    # If there were errors, raise exception to trigger retry/DLQ
    if errors:
        raise Exception(f"Failed to process {len(errors)} messages")
    
    return response
