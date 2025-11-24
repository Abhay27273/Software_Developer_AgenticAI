"""
Ops Agent Worker Lambda Function

This Lambda function processes operations/deployment tasks from SQS queue.
It integrates the existing Ops agent logic for deployment and infrastructure management.

Requirements: 1.3, 2.2
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
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


def get_project_context(project_id: str) -> Dict[str, Any]:
    """Retrieve project context from DynamoDB."""
    try:
        response = table.get_item(
            Key={
                'PK': f'PROJECT#{project_id}',
                'SK': 'METADATA'
            }
        )
        
        if 'Item' not in response:
            raise ValueError(f'Project {project_id} not found')
        
        return response['Item']
    except Exception as e:
        logger.error(f"Error getting project context: {e}")
        raise


def get_project_files(project_id: str) -> Dict[str, str]:
    """Retrieve project files from DynamoDB."""
    try:
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


def detect_project_type(files: Dict[str, str]) -> str:
    """Detect project type from files."""
    file_names = set(files.keys())
    
    # Python projects
    if 'requirements.txt' in file_names or 'setup.py' in file_names:
        if 'app.py' in file_names or 'main.py' in file_names:
            return 'python-web'
        return 'python'
    
    # Node.js projects
    if 'package.json' in file_names:
        if 'index.html' in file_names or any('react' in f.lower() for f in file_names):
            return 'node-frontend'
        return 'node-backend'
    
    # Static sites
    if 'index.html' in file_names:
        return 'static'
    
    return 'unknown'


def generate_deployment_config(project: Dict[str, Any], files: Dict[str, str]) -> Dict[str, Any]:
    """Generate deployment configuration based on project type."""
    project_type = detect_project_type(files)
    
    config = {
        'project_id': project['id'],
        'project_name': project['name'],
        'project_type': project_type,
        'platform': 'aws-lambda',
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # Add platform-specific configuration
    if project_type == 'python-web':
        config['runtime'] = 'python3.11'
        config['handler'] = 'app.lambda_handler'
        config['memory'] = 512
        config['timeout'] = 30
    elif project_type == 'node-backend':
        config['runtime'] = 'nodejs18.x'
        config['handler'] = 'index.handler'
        config['memory'] = 512
        config['timeout'] = 30
    elif project_type == 'static':
        config['platform'] = 's3-cloudfront'
        config['bucket'] = f"{project['id']}-static-site"
    
    return config


def create_deployment_package(project_id: str, files: Dict[str, str]) -> str:
    """Create deployment package and upload to S3."""
    try:
        # Create a zip-like structure in S3
        deployment_id = f"deploy_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Upload each file to S3 under deployment folder
        for file_path, content in files.items():
            s3_key = f'deployments/{project_id}/{deployment_id}/{file_path}'
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_key,
                Body=content,
                ContentType='text/plain'
            )
        
        logger.info(f"Created deployment package: {deployment_id}")
        return deployment_id
        
    except Exception as e:
        logger.error(f"Error creating deployment package: {e}")
        raise


def save_deployment_record(project_id: str, deployment_id: str, config: Dict[str, Any], 
                          status: str = 'pending') -> None:
    """Save deployment record to DynamoDB."""
    try:
        deployment_item = {
            'PK': f'PROJECT#{project_id}',
            'SK': f'DEPLOY#{deployment_id}',
            'EntityType': 'Deployment',
            'id': deployment_id,
            'project_id': project_id,
            'config': config,
            'status': status,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        table.put_item(Item=deployment_item)
        logger.info(f"Saved deployment record: {deployment_id}")
        
    except Exception as e:
        logger.error(f"Error saving deployment record: {e}")
        raise


def update_deployment_status(project_id: str, deployment_id: str, status: str, 
                            details: Optional[Dict[str, Any]] = None) -> None:
    """Update deployment status in DynamoDB."""
    try:
        update_expr = 'SET #status = :status, updated_at = :updated_at'
        expr_values = {
            ':status': status,
            ':updated_at': datetime.utcnow().isoformat()
        }
        
        if details:
            update_expr += ', details = :details'
            expr_values[':details'] = details
        
        table.update_item(
            Key={
                'PK': f'PROJECT#{project_id}',
                'SK': f'DEPLOY#{deployment_id}'
            },
            UpdateExpression=update_expr,
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues=expr_values
        )
        
        logger.info(f"Updated deployment {deployment_id} status to {status}")
        
    except Exception as e:
        logger.error(f"Error updating deployment status: {e}")


def generate_deployment_instructions(config: Dict[str, Any]) -> str:
    """Generate deployment instructions for the user."""
    project_type = config.get('project_type', 'unknown')
    
    instructions = f"""
# Deployment Instructions for {config['project_name']}

## Project Type: {project_type}
## Platform: {config['platform']}

### Deployment Configuration
"""
    
    if config['platform'] == 'aws-lambda':
        instructions += f"""
- Runtime: {config.get('runtime', 'N/A')}
- Handler: {config.get('handler', 'N/A')}
- Memory: {config.get('memory', 512)} MB
- Timeout: {config.get('timeout', 30)} seconds

### Deployment Steps
1. Package your application code
2. Create Lambda function with the specified configuration
3. Configure API Gateway for HTTP endpoints
4. Set up environment variables
5. Deploy and test

### AWS CLI Commands
```bash
# Create Lambda function
aws lambda create-function \\
  --function-name {config['project_name']} \\
  --runtime {config.get('runtime', 'python3.11')} \\
  --handler {config.get('handler', 'app.handler')} \\
  --memory-size {config.get('memory', 512)} \\
  --timeout {config.get('timeout', 30)} \\
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-execution-role \\
  --zip-file fileb://deployment.zip
```
"""
    elif config['platform'] == 's3-cloudfront':
        instructions += f"""
- Bucket: {config.get('bucket', 'N/A')}

### Deployment Steps
1. Create S3 bucket
2. Enable static website hosting
3. Upload files to S3
4. Configure CloudFront distribution (optional)
5. Set up custom domain (optional)

### AWS CLI Commands
```bash
# Create S3 bucket
aws s3 mb s3://{config.get('bucket', 'my-bucket')}

# Enable static website hosting
aws s3 website s3://{config.get('bucket', 'my-bucket')} \\
  --index-document index.html

# Upload files
aws s3 sync ./build s3://{config.get('bucket', 'my-bucket')}
```
"""
    
    return instructions


def process_deployment_task(message_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a deployment task.
    
    This function:
    1. Retrieves project and files
    2. Generates deployment configuration
    3. Creates deployment package
    4. Saves deployment record
    5. Generates deployment instructions
    """
    try:
        action = message_body.get('action')
        project_id = message_body.get('project_id')
        
        if not project_id:
            raise ValueError('project_id is required')
        
        logger.info(f"Processing deployment task for project {project_id}")
        
        # Get project context
        project = get_project_context(project_id)
        
        # Get project files
        files = get_project_files(project_id)
        
        if not files:
            raise ValueError(f'No files found for project {project_id}')
        
        # Generate deployment configuration
        config = generate_deployment_config(project, files)
        
        # Create deployment package
        deployment_id = create_deployment_package(project_id, files)
        
        # Save deployment record
        save_deployment_record(project_id, deployment_id, config, status='ready')
        
        # Generate deployment instructions
        instructions = generate_deployment_instructions(config)
        
        # Save instructions to S3
        s3_key = f'deployments/{project_id}/{deployment_id}/DEPLOYMENT_INSTRUCTIONS.md'
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=instructions,
            ContentType='text/markdown'
        )
        
        # Update project with deployment info
        table.update_item(
            Key={
                'PK': f'PROJECT#{project_id}',
                'SK': 'METADATA'
            },
            UpdateExpression='SET deployment_config = :config, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':config': config,
                ':updated_at': datetime.utcnow().isoformat()
            }
        )
        
        logger.info(f"Completed deployment preparation for project {project_id}")
        
        return {
            'success': True,
            'project_id': project_id,
            'deployment_id': deployment_id,
            'platform': config['platform'],
            'status': 'ready'
        }
        
    except Exception as e:
        logger.error(f"Error processing deployment task: {e}", exc_info=True)
        raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for Ops Agent worker.
    
    Processes SQS messages containing deployment tasks.
    """
    logger.info(f"Ops Agent worker invoked with {len(event.get('Records', []))} messages")
    
    results = []
    errors = []
    
    for record in event.get('Records', []):
        try:
            # Parse message body
            message_body = json.loads(record['body'])
            
            # Process the task
            result = process_deployment_task(message_body)
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
    
    logger.info(f"Ops Agent worker completed: {response}")
    
    # If there were errors, raise exception to trigger retry/DLQ
    if errors:
        raise Exception(f"Failed to process {len(errors)} messages")
    
    return response
