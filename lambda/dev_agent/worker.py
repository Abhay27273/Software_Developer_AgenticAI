"""
Dev Agent Worker Lambda Function

This Lambda function processes development tasks from SQS queue.
It integrates the existing Dev agent logic for code generation and implementation.

Configured for 15-minute timeout and 2GB memory for complex code generation tasks.

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
SQS_QUEUE_URL_QA = os.environ.get('SQS_QUEUE_URL_QA', '')
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


def call_gemini_api(prompt: str, system_prompt: str, model: str = 'gemini-2.0-flash-exp') -> str:
    """
    Call Gemini API for code generation.
    
    Uses gemini-2.0-flash-exp for high-quality code generation.
    """
    import google.generativeai as genai
    
    initialize_api_key()
    genai.configure(api_key=GEMINI_API_KEY)
    
    model_instance = genai.GenerativeModel(
        model_name=model,
        system_instruction=system_prompt
    )
    
    response = model_instance.generate_content(prompt)
    return response.text


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
    """Retrieve existing project files from DynamoDB."""
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


def save_generated_code(project_id: str, files: Dict[str, str]):
    """Save generated code files to DynamoDB and S3."""
    try:
        # Save to DynamoDB
        for file_path, content in files.items():
            file_item = {
                'PK': f'PROJECT#{project_id}',
                'SK': f'FILE#{file_path}',
                'EntityType': 'ProjectFile',
                'file_path': file_path,
                'content': content,
                'size': len(content),
                'last_modified': datetime.utcnow().isoformat()
            }
            table.put_item(Item=file_item)
        
        # Save to S3 for backup
        for file_path, content in files.items():
            s3_key = f'projects/{project_id}/{file_path}'
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_key,
                Body=content,
                ContentType='text/plain'
            )
        
        logger.info(f"Saved {len(files)} files for project {project_id}")
    except Exception as e:
        logger.error(f"Error saving generated code: {e}")
        raise


def extract_code_from_response(response_text: str) -> Dict[str, str]:
    """
    Extract code files from LLM response.
    
    Parses code blocks and file paths from the LLM's response.
    """
    files = {}
    current_file = None
    current_content = []
    in_code_block = False
    
    lines = response_text.split('\n')
    
    for line in lines:
        # Check for file path markers
        if line.startswith('File:') or line.startswith('# File:'):
            if current_file and current_content:
                files[current_file] = '\n'.join(current_content)
            current_file = line.split(':', 1)[1].strip()
            current_content = []
            in_code_block = False
        
        # Check for code block markers
        elif line.strip().startswith('```'):
            in_code_block = not in_code_block
            if not in_code_block and current_file:
                # End of code block
                continue
        
        # Collect code content
        elif in_code_block and current_file:
            current_content.append(line)
    
    # Save last file
    if current_file and current_content:
        files[current_file] = '\n'.join(current_content)
    
    return files


def process_code_generation_task(message_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a code generation task.
    
    This function:
    1. Retrieves project and task context
    2. Generates code using LLM
    3. Saves generated code to DynamoDB and S3
    4. Sends to QA queue for testing
    """
    try:
        action = message_body.get('action')
        project_id = message_body.get('project_id')
        task = message_body.get('task', {})
        
        if not project_id:
            raise ValueError('project_id is required')
        
        logger.info(f"Processing code generation for project {project_id}")
        
        # Get project context
        project = get_project_context(project_id)
        
        # Get existing files
        existing_files = get_project_files(project_id)
        
        # Build context for LLM
        system_prompt = """You are an expert software developer AI agent.
        Generate high-quality, production-ready code based on the task requirements.
        Include proper error handling, documentation, and follow best practices.
        Format your response with clear file paths and code blocks."""
        
        user_prompt = f"""
        Project: {project.get('name')}
        Type: {project.get('type')}
        Description: {project.get('description')}
        
        Task: {task.get('title', 'Code generation')}
        Details: {task.get('description', '')}
        
        Existing files:
        {', '.join(existing_files.keys()) if existing_files else 'None'}
        
        Generate the necessary code files to implement this task.
        """
        
        logger.info("Calling LLM for code generation")
        llm_response = call_gemini_api(user_prompt, system_prompt)
        
        # Extract code files from response
        generated_files = extract_code_from_response(llm_response)
        
        if not generated_files:
            logger.warning("No code files extracted from LLM response")
            # Try to save the raw response as a single file
            generated_files = {'generated_code.txt': llm_response}
        
        # Save generated code
        save_generated_code(project_id, generated_files)
        
        # Send to QA queue for testing
        qa_message = {
            'action': 'test_code',
            'project_id': project_id,
            'task': task,
            'files': list(generated_files.keys()),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL_QA,
            MessageBody=json.dumps(qa_message)
        )
        
        logger.info(f"Sent code to QA queue for project {project_id}")
        
        return {
            'success': True,
            'project_id': project_id,
            'files_generated': len(generated_files),
            'file_names': list(generated_files.keys())
        }
        
    except Exception as e:
        logger.error(f"Error processing code generation task: {e}", exc_info=True)
        raise


def process_modification_task(message_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a code modification task.
    
    Modifies existing code based on user request.
    """
    try:
        project_id = message_body.get('project_id')
        modification_id = message_body.get('modification_id')
        request = message_body.get('request')
        
        if not all([project_id, modification_id, request]):
            raise ValueError('project_id, modification_id, and request are required')
        
        logger.info(f"Processing modification {modification_id} for project {project_id}")
        
        # Get project context
        project = get_project_context(project_id)
        
        # Get existing files
        existing_files = get_project_files(project_id)
        
        if not existing_files:
            raise ValueError('No existing files to modify')
        
        # Build context for LLM
        system_prompt = """You are an expert software developer AI agent.
        Modify the existing code based on the user's request.
        Maintain code quality and ensure backward compatibility where possible."""
        
        files_context = '\n\n'.join([
            f"File: {path}\n```\n{content}\n```"
            for path, content in existing_files.items()
        ])
        
        user_prompt = f"""
        Project: {project.get('name')}
        
        Modification Request: {request}
        
        Existing Code:
        {files_context}
        
        Modify the code to implement the requested changes.
        Return the complete modified files.
        """
        
        logger.info("Calling LLM for code modification")
        llm_response = call_gemini_api(user_prompt, system_prompt)
        
        # Extract modified files
        modified_files = extract_code_from_response(llm_response)
        
        if not modified_files:
            raise ValueError('No modified files extracted from LLM response')
        
        # Save modified code
        save_generated_code(project_id, modified_files)
        
        # Update modification status
        table.update_item(
            Key={
                'PK': f'PROJECT#{project_id}',
                'SK': f'MOD#{modification_id}'
            },
            UpdateExpression='SET #status = :status, applied_at = :applied_at, modified_files = :files',
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':status': 'completed',
                ':applied_at': datetime.utcnow().isoformat(),
                ':files': list(modified_files.keys())
            }
        )
        
        logger.info(f"Completed modification {modification_id}")
        
        return {
            'success': True,
            'project_id': project_id,
            'modification_id': modification_id,
            'files_modified': len(modified_files)
        }
        
    except Exception as e:
        logger.error(f"Error processing modification task: {e}", exc_info=True)
        # Update modification status to error
        if project_id and modification_id:
            table.update_item(
                Key={
                    'PK': f'PROJECT#{project_id}',
                    'SK': f'MOD#{modification_id}'
                },
                UpdateExpression='SET #status = :status',
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': 'error'
                }
            )
        raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for Dev Agent worker.
    
    Processes SQS messages containing development tasks.
    Configured for 15-minute timeout and 2GB memory.
    """
    logger.info(f"Dev Agent worker invoked with {len(event.get('Records', []))} messages")
    
    results = []
    errors = []
    
    for record in event.get('Records', []):
        try:
            # Parse message body
            message_body = json.loads(record['body'])
            action = message_body.get('action')
            
            # Route to appropriate handler
            if action == 'implement_task':
                result = process_code_generation_task(message_body)
            elif action == 'modify_project':
                result = process_modification_task(message_body)
            else:
                raise ValueError(f'Unknown action: {action}')
            
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
    
    logger.info(f"Dev Agent worker completed: {response}")
    
    # If there were errors, raise exception to trigger retry/DLQ
    if errors:
        raise Exception(f"Failed to process {len(errors)} messages")
    
    return response
