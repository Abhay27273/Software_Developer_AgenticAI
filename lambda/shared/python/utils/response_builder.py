"""
Response builder utilities for Lambda functions.
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime


class ResponseBuilder:
    """
    Helper class for building standardized API Gateway responses.
    """
    
    @staticmethod
    def success(
        status_code: int,
        data: Dict[str, Any],
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build a success response.
        
        Args:
            status_code: HTTP status code
            data: Response data
            message: Optional success message
            
        Returns:
            API Gateway response dictionary
        """
        body = {
            'success': True,
            **data
        }
        
        if message:
            body['message'] = message
        
        return {
            'statusCode': status_code,
            'headers': ResponseBuilder._get_headers(),
            'body': json.dumps(body)
        }
    
    @staticmethod
    def error(
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build an error response.
        
        Args:
            status_code: HTTP status code
            error_code: Application error code
            message: Error message
            details: Optional error details
            
        Returns:
            API Gateway response dictionary
        """
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
        
        return {
            'statusCode': status_code,
            'headers': ResponseBuilder._get_headers(),
            'body': json.dumps(error_body)
        }
    
    @staticmethod
    def cors_response() -> Dict[str, Any]:
        """
        Build a CORS preflight response.
        
        Returns:
            API Gateway CORS response
        """
        return {
            'statusCode': 200,
            'headers': ResponseBuilder._get_headers(),
            'body': json.dumps({})
        }
    
    @staticmethod
    def _get_headers() -> Dict[str, str]:
        """
        Get standard response headers.
        
        Returns:
            Dictionary of HTTP headers
        """
        return {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Api-Key',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY'
        }
