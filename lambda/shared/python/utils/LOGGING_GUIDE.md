# Structured Logging Guide

This guide explains how to use the structured logging utility in Lambda functions.

## Overview

The structured logger provides JSON-formatted logs with consistent fields across all Lambda functions. It automatically includes:

- Timestamp (ISO 8601 format)
- Log level (INFO, WARN, ERROR, DEBUG)
- Service name
- Request ID (from Lambda context)
- Environment
- Custom fields

## Quick Start

### Basic Usage

```python
from utils.logger import get_logger, log_lambda_event, log_lambda_response

# Create logger instance
logger = get_logger('my-service')

def lambda_handler(event, context):
    # Log Lambda invocation
    log_lambda_event(event, context, logger)
    
    # Set request ID for tracking
    logger.set_request_id(context.aws_request_id)
    
    # Log messages
    logger.info('Processing started', event_type='processing_started')
    
    try:
        # Your code here
        result = process_data(event)
        
        logger.info(
            'Processing completed',
            event_type='processing_completed',
            items_processed=len(result)
        )
        
        # Log response
        response = {'statusCode': 200, 'body': json.dumps(result)}
        log_lambda_response(response, context, logger)
        
        return response
        
    except Exception as e:
        logger.error(
            'Processing failed',
            event_type='processing_error',
            error=e
        )
        raise
```

## Log Levels

### INFO
Use for normal operational messages:

```python
logger.info(
    'Project created successfully',
    event_type='project_created',
    project_id='proj_123',
    user_id='user_456'
)
```

### WARN
Use for potential issues that don't prevent operation:

```python
logger.warn(
    'Rate limit approaching',
    event_type='rate_limit_warning',
    current_usage=850,
    limit=1000,
    percentage=85
)
```

### ERROR
Use for errors and exceptions:

```python
try:
    result = risky_operation()
except Exception as e:
    logger.error(
        'Operation failed',
        event_type='operation_error',
        error=e,
        operation='risky_operation'
    )
    raise
```

### DEBUG
Use for detailed diagnostic information (disabled in production):

```python
logger.debug(
    'Cache lookup',
    event_type='cache_lookup',
    cache_key='user_123',
    cache_hit=True
)
```

## Event Types

Use consistent event types across your application for easier log analysis:

### Common Event Types

- `lambda_invocation` - Lambda function started
- `lambda_response` - Lambda function completed
- `lambda_error` - Lambda function error
- `project_created` - New project created
- `plan_generated` - Plan generated
- `task_completed` - Task completed
- `db_query` - Database query
- `api_call` - External API call
- `validation_error` - Input validation failed

### Example

```python
logger.info(
    'Database query executed',
    event_type='db_query',
    table='projects',
    operation='get_item',
    duration_ms=45
)
```

## Custom Fields

Add any custom fields to provide context:

```python
logger.info(
    'Code generated',
    event_type='code_generated',
    project_id='proj_123',
    file_count=15,
    lines_of_code=1234,
    language='python',
    duration_ms=5678
)
```

## Request ID Tracking

Request IDs are automatically tracked across Lambda invocations:

```python
def lambda_handler(event, context):
    # Set request ID from Lambda context
    logger.set_request_id(context.aws_request_id)
    
    # All subsequent logs will include this request ID
    logger.info('Processing started')  # Includes request_id
    
    # Call another function
    process_data()  # Logs will include same request_id
```

## Log Output Format

Logs are output as JSON for easy parsing:

```json
{
  "timestamp": "2025-11-25T12:34:56.789Z",
  "level": "INFO",
  "service": "pm-agent",
  "environment": "prod",
  "message": "Project created successfully",
  "request_id": "abc-123-def-456",
  "event_type": "project_created",
  "project_id": "proj_123",
  "user_id": "user_456"
}
```

## CloudWatch Logs Integration

Logs are automatically sent to CloudWatch Logs with:

- Log group: `/aws/lambda/{function-name}`
- Retention: 7 days
- JSON format for easy querying

### Querying Logs in CloudWatch

Use CloudWatch Logs Insights to query structured logs:

```sql
# Find all errors
fields @timestamp, message, error_type, error_message
| filter level = "ERROR"
| sort @timestamp desc

# Find slow operations
fields @timestamp, message, duration_ms
| filter duration_ms > 1000
| sort duration_ms desc

# Track a specific request
fields @timestamp, message, event_type
| filter request_id = "abc-123-def-456"
| sort @timestamp asc

# Count events by type
stats count() by event_type
| sort count desc
```

## Best Practices

### 1. Use Consistent Event Types

Define event types as constants:

```python
# constants.py
EVENT_PROJECT_CREATED = 'project_created'
EVENT_PLAN_GENERATED = 'plan_generated'
EVENT_TASK_COMPLETED = 'task_completed'

# usage
logger.info('Project created', event_type=EVENT_PROJECT_CREATED)
```

### 2. Include Relevant Context

Always include IDs and relevant data:

```python
# Good
logger.info(
    'Task completed',
    event_type='task_completed',
    task_id='task_123',
    project_id='proj_456',
    duration_ms=1234
)

# Bad - missing context
logger.info('Task completed')
```

### 3. Log at Appropriate Levels

- INFO: Normal operations
- WARN: Potential issues
- ERROR: Actual errors
- DEBUG: Detailed diagnostics (dev only)

### 4. Don't Log Sensitive Data

Never log passwords, API keys, or PII:

```python
# Bad
logger.info('User logged in', password=user_password)

# Good
logger.info('User logged in', user_id=user_id)
```

### 5. Use Structured Fields

Use structured fields instead of string formatting:

```python
# Good
logger.info(
    'Processing items',
    event_type='processing',
    count=len(items),
    batch_id=batch_id
)

# Bad
logger.info(f'Processing {len(items)} items in batch {batch_id}')
```

## Performance Considerations

### Lazy Initialization

Initialize logger once per Lambda container:

```python
# At module level (outside handler)
logger = get_logger('my-service')

def lambda_handler(event, context):
    # Reuse logger instance
    logger.set_request_id(context.aws_request_id)
    logger.info('Processing started')
```

### Conditional Debug Logging

Debug logs are only processed if LOG_LEVEL=DEBUG:

```python
# This is efficient - only evaluated if debug enabled
logger.debug('Detailed data', data=expensive_operation())
```

## AWS Lambda Powertools Integration

The logger uses AWS Lambda Powertools for enhanced functionality:

- Automatic request ID injection
- Correlation ID tracking
- X-Ray trace ID integration
- Sampling for high-volume logs

### Environment Variables

Configure logging via environment variables:

```yaml
Environment:
  Variables:
    LOG_LEVEL: INFO  # DEBUG, INFO, WARN, ERROR
    POWERTOOLS_SERVICE_NAME: my-service
    POWERTOOLS_LOG_LEVEL: INFO
```

## Troubleshooting

### Logs Not Appearing in CloudWatch

1. Check IAM permissions for Lambda execution role
2. Verify log group exists: `/aws/lambda/{function-name}`
3. Check LOG_LEVEL environment variable

### Request ID Not Tracked

Ensure you call `set_request_id()` at the start of your handler:

```python
def lambda_handler(event, context):
    logger.set_request_id(context.aws_request_id)
    # Now all logs include request_id
```

### JSON Parsing Errors

Ensure all logged values are JSON-serializable:

```python
# Bad - datetime not serializable
logger.info('Event', timestamp=datetime.now())

# Good - convert to ISO string
logger.info('Event', timestamp=datetime.now().isoformat())
```

## Examples

### Complete Lambda Function

```python
from utils.logger import get_logger, log_lambda_event, log_lambda_response
import json

logger = get_logger('example-service')

def lambda_handler(event, context):
    # Log invocation
    log_lambda_event(event, context, logger)
    logger.set_request_id(context.aws_request_id)
    
    try:
        # Parse input
        body = json.loads(event.get('body', '{}'))
        project_id = body.get('project_id')
        
        logger.info(
            'Processing request',
            event_type='request_received',
            project_id=project_id
        )
        
        # Do work
        result = process_project(project_id)
        
        logger.info(
            'Request completed',
            event_type='request_completed',
            project_id=project_id,
            duration_ms=result['duration']
        )
        
        # Return response
        response = {
            'statusCode': 200,
            'body': json.dumps(result)
        }
        
        log_lambda_response(response, context, logger)
        return response
        
    except ValueError as e:
        logger.error(
            'Validation error',
            event_type='validation_error',
            error=e
        )
        return {
            'statusCode': 400,
            'body': json.dumps({'error': str(e)})
        }
        
    except Exception as e:
        logger.error(
            'Unexpected error',
            event_type='unexpected_error',
            error=e
        )
        raise
```

## Additional Resources

- [AWS Lambda Powertools Documentation](https://awslabs.github.io/aws-lambda-powertools-python/)
- [CloudWatch Logs Insights Query Syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html)
- [Structured Logging Best Practices](https://www.loggly.com/ultimate-guide/python-logging-basics/)
