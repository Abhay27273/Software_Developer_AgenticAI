"""
API Handler Lambda Function

This Lambda function handles all REST API requests from API Gateway.
It provides endpoints for project management, template operations, and modifications.

Requirements: 1.3, 2.2, 1.5, 6.3, 6.5
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
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
SQS_QUEUE_URL_PM = os.environ.get('SQS_QUEUE_URL_PM', '')
SQS_QUEUE_URL_DEV = os.environ.get('SQS_QUEUE_URL_DEV', '')
SQS_QUEUE_URL_QA = os.environ.get('SQS_QUEUE_URL_QA', '')
SQS_QUEUE_URL_OPS = os.environ.get('SQS_QUEUE_URL_OPS', '')

# DynamoDB table
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

# Import rate limit utilities (from Lambda layer)
try:
    from utils.rate_limit_headers import add_rate_limit_headers
except ImportError:
    # Fallback if not in Lambda environment
    def add_rate_limit_headers(response, api_key_id=None, usage_plan_id=None):
        return response


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


def create_response(status_code: int, body: Dict[str, Any], api_key_id: Optional[str] = None, usage_plan_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a standardized API Gateway response with rate limit headers."""
    response = {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-API-Key',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(body)
    }
    
    # Add rate limit headers if we have the necessary information
    if api_key_id and usage_plan_id:
        response = add_rate_limit_headers(response, api_key_id, usage_plan_id)
    
    return response


def create_error_response(status_code: int, error_code: str, message: str, details: Optional[Dict] = None, api_key_id: Optional[str] = None, usage_plan_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a standardized error response."""
    error_body = {
        'success': False,
        'error': {
            'code': error_code,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
    }
    if details:
        error_body['error']['details'] = details
    
    # Log rate limit violations
    if status_code == 429:
        rate_limit_log = {
            'timestamp': datetime.utcnow().isoformat(),
            'api_key_id': api_key_id if api_key_id else 'unknown',
            'error_code': error_code,
            'message': message
        }
        logger.warning(f"Rate limit violation: {json.dumps(rate_limit_log)}")
    
    return create_response(status_code, error_body, api_key_id, usage_plan_id)


# ============================================================================
# PROJECT MANAGEMENT ENDPOINTS
# ============================================================================

def create_project(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new project."""
    try:
        # Extract and validate parameters
        name = body.get('name')
        if not name:
            return create_error_response(400, 'VALIDATION_ERROR', 'Project name is required')
        
        description = body.get('description', '')
        project_type = body.get('project_type', 'other')
        owner_id = body.get('owner_id', 'default_user')
        
        # Validate project type
        valid_types = ['api', 'web', 'mobile', 'data', 'microservice', 'other']
        if project_type not in valid_types:
            return create_error_response(
                400,
                'VALIDATION_ERROR',
                f'Invalid project type. Must be one of: {valid_types}',
                {'field': 'project_type', 'allowed_values': valid_types}
            )
        
        # Generate project ID
        project_id = f"proj_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Create project item
        project_item = {
            'PK': f'PROJECT#{project_id}',
            'SK': 'METADATA',
            'GSI1PK': f'OWNER#{owner_id}',
            'GSI1SK': f'PROJECT#{datetime.utcnow().isoformat()}',
            'GSI2PK': 'STATUS#active',
            'GSI2SK': f'PROJECT#{project_id}',
            'EntityType': 'Project',
            'id': project_id,
            'name': name,
            'type': project_type,
            'status': 'active',
            'owner_id': owner_id,
            'description': description,
            'dependencies': [],
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Save to DynamoDB
        table.put_item(Item=project_item)
        
        logger.info(f"Created project: {project_id}")
        
        return create_response(201, {
            'success': True,
            'project': project_item,
            'message': f"Project '{name}' created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating project: {e}", exc_info=True)
        return create_error_response(500, 'INTERNAL_ERROR', str(e))


def get_project(project_id: str) -> Dict[str, Any]:
    """Get a project by ID."""
    try:
        response = table.get_item(
            Key={
                'PK': f'PROJECT#{project_id}',
                'SK': 'METADATA'
            }
        )
        
        if 'Item' not in response:
            return create_error_response(404, 'NOT_FOUND', f'Project {project_id} not found')
        
        return create_response(200, {
            'success': True,
            'project': response['Item']
        })
        
    except Exception as e:
        logger.error(f"Error getting project: {e}", exc_info=True)
        return create_error_response(500, 'INTERNAL_ERROR', str(e))


def list_projects(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """List projects with optional filtering."""
    try:
        owner_id = query_params.get('owner_id', 'default_user')
        status = query_params.get('status')
        limit = int(query_params.get('limit', 50))
        
        # Query by owner using GSI1
        query_kwargs = {
            'IndexName': 'GSI1',
            'KeyConditionExpression': 'GSI1PK = :owner',
            'ExpressionAttributeValues': {
                ':owner': f'OWNER#{owner_id}'
            },
            'Limit': limit
        }
        
        response = table.query(**query_kwargs)
        projects = response.get('Items', [])
        
        # Filter by status if provided
        if status:
            projects = [p for p in projects if p.get('status') == status]
        
        return create_response(200, {
            'success': True,
            'projects': projects,
            'count': len(projects)
        })
        
    except Exception as e:
        logger.error(f"Error listing projects: {e}", exc_info=True)
        return create_error_response(500, 'INTERNAL_ERROR', str(e))


def update_project(project_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Update a project."""
    try:
        # Build update expression
        update_expr = 'SET updated_at = :updated_at'
        expr_values = {':updated_at': datetime.utcnow().isoformat()}
        expr_names = {}
        
        if 'name' in body:
            update_expr += ', #name = :name'
            expr_values[':name'] = body['name']
            expr_names['#name'] = 'name'
        
        if 'description' in body:
            update_expr += ', description = :description'
            expr_values[':description'] = body['description']
        
        if 'status' in body:
            update_expr += ', #status = :status'
            expr_values[':status'] = body['status']
            expr_names['#status'] = 'status'
        
        # Build update_item parameters
        update_params = {
            'Key': {
                'PK': f'PROJECT#{project_id}',
                'SK': 'METADATA'
            },
            'UpdateExpression': update_expr,
            'ExpressionAttributeValues': expr_values,
            'ReturnValues': 'ALL_NEW'
        }
        
        # Only add ExpressionAttributeNames if we have any
        if expr_names:
            update_params['ExpressionAttributeNames'] = expr_names
        
        # Update DynamoDB
        response = table.update_item(**update_params)
        
        return create_response(200, {
            'success': True,
            'project': response['Attributes'],
            'message': 'Project updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating project: {e}", exc_info=True)
        return create_error_response(500, 'INTERNAL_ERROR', str(e))


def delete_project(project_id: str) -> Dict[str, Any]:
    """Delete a project."""
    try:
        # Delete project metadata
        table.delete_item(
            Key={
                'PK': f'PROJECT#{project_id}',
                'SK': 'METADATA'
            }
        )
        
        # Delete project files from S3
        try:
            s3_client.delete_objects(
                Bucket=S3_BUCKET_NAME,
                Delete={
                    'Objects': [
                        {'Key': f'projects/{project_id}/'}
                    ]
                }
            )
        except Exception as s3_error:
            logger.warning(f"Error deleting S3 files: {s3_error}")
        
        return create_response(200, {
            'success': True,
            'message': f'Project {project_id} deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting project: {e}", exc_info=True)
        return create_error_response(500, 'INTERNAL_ERROR', str(e))


# ============================================================================
# MODIFICATION ENDPOINTS
# ============================================================================

def request_modification(project_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Request a modification to a project."""
    try:
        request_text = body.get('request')
        if not request_text:
            return create_error_response(400, 'VALIDATION_ERROR', 'Modification request is required')
        
        # Generate modification ID
        mod_id = f"mod_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Create modification item
        modification_item = {
            'PK': f'PROJECT#{project_id}',
            'SK': f'MOD#{mod_id}',
            'EntityType': 'Modification',
            'id': mod_id,
            'project_id': project_id,
            'request': request_text,
            'requested_by': body.get('requested_by', 'default_user'),
            'requested_at': datetime.utcnow().isoformat(),
            'status': 'pending',
            'impact_analysis': {}
        }
        
        # Save to DynamoDB
        table.put_item(Item=modification_item)
        
        # Send message to Dev queue
        message = {
            'action': 'modify_project',
            'project_id': project_id,
            'modification_id': mod_id,
            'request': request_text,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL_DEV,
            MessageBody=json.dumps(message)
        )
        
        logger.info(f"Created modification request: {mod_id} for project {project_id}")
        
        return create_response(201, {
            'success': True,
            'modification': modification_item,
            'message': 'Modification request submitted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error requesting modification: {e}", exc_info=True)
        return create_error_response(500, 'INTERNAL_ERROR', str(e))


# ============================================================================
# TEMPLATE ENDPOINTS
# ============================================================================

def list_templates(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """List available templates."""
    try:
        category = query_params.get('category')
        
        # Scan for templates with filter
        scan_kwargs = {
            'FilterExpression': 'begins_with(PK, :template_prefix) AND SK = :metadata',
            'ExpressionAttributeValues': {
                ':template_prefix': 'TEMPLATE#',
                ':metadata': 'METADATA'
            }
        }
        
        response = table.scan(**scan_kwargs)
        templates = response.get('Items', [])
        
        # Filter by category if provided
        if category:
            templates = [t for t in templates if t.get('category') == category]
        
        return create_response(200, {
            'success': True,
            'templates': templates,
            'count': len(templates)
        })
        
    except Exception as e:
        logger.error(f"Error listing templates: {e}", exc_info=True)
        return create_error_response(500, 'INTERNAL_ERROR', str(e))


def get_template(template_id: str) -> Dict[str, Any]:
    """Get a template by ID."""
    try:
        response = table.get_item(
            Key={
                'PK': f'TEMPLATE#{template_id}',
                'SK': 'METADATA'
            }
        )
        
        if 'Item' not in response:
            return create_error_response(404, 'NOT_FOUND', f'Template {template_id} not found')
        
        return create_response(200, {
            'success': True,
            'template': response['Item']
        })
        
    except Exception as e:
        logger.error(f"Error getting template: {e}", exc_info=True)
        return create_error_response(500, 'INTERNAL_ERROR', str(e))


# ============================================================================
# HEALTH CHECK
# ============================================================================

def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    return create_response(200, {
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'api-handler'
    })


# ============================================================================
# LAMBDA HANDLER
# ============================================================================

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for API Gateway requests.
    
    Routes requests to appropriate handlers based on HTTP method and path.
    """
    try:
        # Extract authentication information
        request_context = event.get('requestContext', {})
        identity = request_context.get('identity', {})
        api_key_id = request_context.get('identity', {}).get('apiKeyId')
        source_ip = identity.get('sourceIp', 'unknown')
        user_agent = identity.get('userAgent', 'unknown')
        request_id = request_context.get('requestId', 'unknown')
        
        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        
        # Log authentication attempt
        auth_log = {
            'timestamp': datetime.utcnow().isoformat(),
            'request_id': request_id,
            'api_key_id': api_key_id if api_key_id else 'none',
            'source_ip': source_ip,
            'user_agent': user_agent,
            'method': http_method,
            'path': path,
            'result': 'success' if api_key_id else 'missing_key'
        }
        
        # Log authentication attempt
        logger.info(f"Authentication attempt: {json.dumps(auth_log)}")
        
        # Check if API key is present (API Gateway handles validation)
        if not api_key_id and path != '/health':
            # Log authentication failure
            auth_log['result'] = 'unauthorized'
            logger.warning(f"Authentication failed: {json.dumps(auth_log)}")
            return create_error_response(401, 'UNAUTHORIZED', 'API key is required')
        
        # Log request
        logger.info(f"Received request: {http_method} {path} from {source_ip}")
        
        query_params = event.get('queryStringParameters') or {}
        body = {}
        
        # Parse body if present
        if event.get('body'):
            try:
                body = json.loads(event['body'])
            except json.JSONDecodeError:
                return create_error_response(400, 'INVALID_JSON', 'Request body must be valid JSON')
        
        # Handle OPTIONS for CORS
        if http_method == 'OPTIONS':
            return create_response(200, {})
        
        # Route to handlers
        if path == '/health':
            return health_check()
        
        # Project endpoints
        elif path == '/api/projects':
            if http_method == 'POST':
                return create_project(body)
            elif http_method == 'GET':
                return list_projects(query_params)
        
        elif path.startswith('/api/projects/'):
            # Extract project_id
            parts = path.split('/')
            if len(parts) >= 4:
                project_id = parts[3]
                
                # Check for sub-resources
                if len(parts) == 4:
                    if http_method == 'GET':
                        return get_project(project_id)
                    elif http_method == 'PUT':
                        return update_project(project_id, body)
                    elif http_method == 'DELETE':
                        return delete_project(project_id)
                
                elif len(parts) >= 5 and parts[4] == 'modify':
                    if http_method == 'POST':
                        return request_modification(project_id, body)
        
        # Template endpoints
        elif path == '/api/templates':
            if http_method == 'GET':
                return list_templates(query_params)
        
        elif path.startswith('/api/templates/'):
            parts = path.split('/')
            if len(parts) >= 4:
                template_id = parts[3]
                if http_method == 'GET':
                    return get_template(template_id)
        
        # No matching route
        return create_error_response(404, 'NOT_FOUND', f'Endpoint not found: {http_method} {path}')
        
    except Exception as e:
        logger.error(f"Unhandled error in lambda_handler: {e}", exc_info=True)
        return create_error_response(500, 'INTERNAL_ERROR', 'An unexpected error occurred')
