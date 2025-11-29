"""
Structured logging utility for Lambda functions.

This module provides a structured JSON logger with request ID tracking
and consistent formatting across all Lambda functions.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional
from aws_lambda_powertools import Logger
from aws_lambda_powertools.logging import correlation_paths

# Initialize AWS Lambda Powertools Logger
logger = Logger(
    service=os.getenv('POWERTOOLS_SERVICE_NAME', 'agenticai'),
    level=os.getenv('LOG_LEVEL', 'INFO')
)


class StructuredLogger:
    """
    Structured logger that outputs JSON-formatted logs with consistent fields.
    
    This logger automatically includes:
    - Timestamp (ISO 8601 format)
    - Log level
    - Service name
    - Request ID (from Lambda context)
    - Environment
    - Custom fields
    """
    
    def __init__(self, service_name: str = None):
        """
        Initialize the structured logger.
        
        Args:
            service_name: Name of the service (defaults to POWERTOOLS_SERVICE_NAME env var)
        """
        self.service_name = service_name or os.getenv('POWERTOOLS_SERVICE_NAME', 'agenticai')
        self.environment = os.getenv('ENVIRONMENT', 'prod')
        self.request_id = None
        
        # Configure standard Python logger as fallback
        self.fallback_logger = logging.getLogger(self.service_name)
        self.fallback_logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))
        
        if not self.fallback_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.fallback_logger.addHandler(handler)
    
    def set_request_id(self, request_id: str):
        """
        Set the request ID for tracking across Lambda invocations.
        
        Args:
            request_id: AWS request ID from Lambda context
        """
        self.request_id = request_id
    
    def _format_log(
        self,
        level: str,
        message: str,
        event_type: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Format log entry as structured JSON.
        
        Args:
            level: Log level (INFO, WARN, ERROR, DEBUG)
            message: Log message
            event_type: Type of event being logged
            **kwargs: Additional fields to include in log
            
        Returns:
            Dictionary with structured log data
        """
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level,
            'service': self.service_name,
            'environment': self.environment,
            'message': message
        }
        
        if self.request_id:
            log_entry['request_id'] = self.request_id
        
        if event_type:
            log_entry['event_type'] = event_type
        
        # Add custom fields
        for key, value in kwargs.items():
            if value is not None:
                log_entry[key] = value
        
        return log_entry
    
    def _log(self, level: str, message: str, event_type: Optional[str] = None, **kwargs):
        """
        Internal method to log a message.
        
        Args:
            level: Log level
            message: Log message
            event_type: Type of event
            **kwargs: Additional fields
        """
        log_entry = self._format_log(level, message, event_type, **kwargs)
        log_message = json.dumps(log_entry)
        
        # Log using appropriate level
        log_level = getattr(logging, level.upper(), logging.INFO)
        self.fallback_logger.log(log_level, log_message)
    
    def info(self, message: str, event_type: Optional[str] = None, **kwargs):
        """
        Log an INFO level message.
        
        Args:
            message: Log message
            event_type: Type of event
            **kwargs: Additional fields
        """
        self._log('INFO', message, event_type, **kwargs)
    
    def warn(self, message: str, event_type: Optional[str] = None, **kwargs):
        """
        Log a WARN level message.
        
        Args:
            message: Log message
            event_type: Type of event
            **kwargs: Additional fields
        """
        self._log('WARN', message, event_type, **kwargs)
    
    def error(self, message: str, event_type: Optional[str] = None, error: Exception = None, **kwargs):
        """
        Log an ERROR level message.
        
        Args:
            message: Log message
            event_type: Type of event
            error: Exception object (if applicable)
            **kwargs: Additional fields
        """
        if error:
            kwargs['error_type'] = type(error).__name__
            kwargs['error_message'] = str(error)
        
        self._log('ERROR', message, event_type, **kwargs)
    
    def debug(self, message: str, event_type: Optional[str] = None, **kwargs):
        """
        Log a DEBUG level message.
        
        Args:
            message: Log message
            event_type: Type of event
            **kwargs: Additional fields
        """
        self._log('DEBUG', message, event_type, **kwargs)


def get_logger(service_name: str = None) -> StructuredLogger:
    """
    Get a structured logger instance.
    
    Args:
        service_name: Name of the service
        
    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(service_name)


def log_lambda_event(event: Dict[str, Any], context: Any, logger_instance: StructuredLogger = None):
    """
    Log Lambda invocation event with context.
    
    Args:
        event: Lambda event object
        context: Lambda context object
        logger_instance: Logger instance (creates new one if not provided)
    """
    if logger_instance is None:
        logger_instance = get_logger()
    
    # Set request ID from context
    if hasattr(context, 'aws_request_id'):
        logger_instance.set_request_id(context.aws_request_id)
    
    # Log invocation
    logger_instance.info(
        'Lambda function invoked',
        event_type='lambda_invocation',
        function_name=context.function_name if hasattr(context, 'function_name') else None,
        function_version=context.function_version if hasattr(context, 'function_version') else None,
        memory_limit_mb=context.memory_limit_in_mb if hasattr(context, 'memory_limit_in_mb') else None,
        remaining_time_ms=context.get_remaining_time_in_millis() if hasattr(context, 'get_remaining_time_in_millis') else None
    )


def log_lambda_response(response: Any, context: Any, logger_instance: StructuredLogger = None):
    """
    Log Lambda function response.
    
    Args:
        response: Lambda response object
        context: Lambda context object
        logger_instance: Logger instance (creates new one if not provided)
    """
    if logger_instance is None:
        logger_instance = get_logger()
    
    # Set request ID from context
    if hasattr(context, 'aws_request_id'):
        logger_instance.set_request_id(context.aws_request_id)
    
    # Log response
    logger_instance.info(
        'Lambda function completed',
        event_type='lambda_response',
        status_code=response.get('statusCode') if isinstance(response, dict) else None,
        remaining_time_ms=context.get_remaining_time_in_millis() if hasattr(context, 'get_remaining_time_in_millis') else None
    )


def log_error(error: Exception, context: Any, logger_instance: StructuredLogger = None):
    """
    Log Lambda function error.
    
    Args:
        error: Exception object
        context: Lambda context object
        logger_instance: Logger instance (creates new one if not provided)
    """
    if logger_instance is None:
        logger_instance = get_logger()
    
    # Set request ID from context
    if hasattr(context, 'aws_request_id'):
        logger_instance.set_request_id(context.aws_request_id)
    
    # Log error
    logger_instance.error(
        'Lambda function error',
        event_type='lambda_error',
        error=error,
        function_name=context.function_name if hasattr(context, 'function_name') else None
    )


# Example usage patterns
def example_usage():
    """
    Example usage of the structured logger.
    """
    # Create logger
    log = get_logger('my-service')
    
    # Set request ID (typically from Lambda context)
    log.set_request_id('abc-123-def-456')
    
    # Log different levels
    log.info('Processing started', event_type='processing_started', user_id='user_123')
    log.warn('Rate limit approaching', event_type='rate_limit_warning', current_usage=850, limit=1000)
    log.error('Database connection failed', event_type='db_error', error=Exception('Connection timeout'))
    log.debug('Debug information', event_type='debug', data={'key': 'value'})
    
    # Log with custom fields
    log.info(
        'Project created',
        event_type='project_created',
        project_id='proj_123',
        project_name='My Project',
        user_id='user_456',
        duration_ms=1234
    )


if __name__ == '__main__':
    example_usage()
