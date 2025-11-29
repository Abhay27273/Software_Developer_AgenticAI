"""
Rate Limit Headers Utility

Provides utilities for adding rate limit information to API responses.
This helps clients understand their usage limits and remaining quota.

Requirements: 6.3
"""

import boto3
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger()

# Initialize AWS clients
apigateway = boto3.client('apigateway')


def get_usage_info(api_key_id: str, usage_plan_id: str) -> Dict[str, Any]:
    """
    Get current usage information for an API key.
    
    Args:
        api_key_id: The API key ID
        usage_plan_id: The usage plan ID
        
    Returns:
        Dictionary with usage information including limit, remaining, and reset time
    """
    try:
        # Get current date for usage query
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # Get usage data from API Gateway
        response = apigateway.get_usage(
            usagePlanId=usage_plan_id,
            keyId=api_key_id,
            startDate=today,
            endDate=today
        )
        
        # Extract usage information
        items = response.get('items', {})
        
        # Get the first (and typically only) item for today
        usage_data = {}
        for date_key, date_usage in items.items():
            # date_usage is a list of [requests_used, ...]
            if date_usage:
                usage_data = {
                    'date': date_key,
                    'requests_used': sum(date_usage[0]) if isinstance(date_usage[0], list) else date_usage[0][0]
                }
                break
        
        requests_used = usage_data.get('requests_used', 0) if usage_data else 0
        
        # Get usage plan details for limits
        usage_plan = apigateway.get_usage_plan(usagePlanId=usage_plan_id)
        
        # Extract rate limit (requests per hour)
        rate_limit = usage_plan.get('quota', {}).get('limit', 1000)
        
        # Calculate remaining requests
        remaining = max(0, rate_limit - requests_used)
        
        # Calculate reset time (next hour)
        now = datetime.now(timezone.utc)
        next_hour = now.replace(minute=0, second=0, microsecond=0)
        if now.minute > 0 or now.second > 0:
            next_hour = next_hour.replace(hour=now.hour + 1)
        reset_timestamp = int(next_hour.timestamp())
        
        return {
            'limit': rate_limit,
            'remaining': remaining,
            'reset': reset_timestamp,
            'used': requests_used
        }
        
    except Exception as e:
        logger.warning(f"Error getting usage info: {e}")
        # Return default values if we can't get usage info
        return {
            'limit': 1000,
            'remaining': 1000,
            'reset': int(datetime.now(timezone.utc).timestamp()) + 3600,
            'used': 0
        }


def add_rate_limit_headers(
    response: Dict[str, Any],
    api_key_id: Optional[str] = None,
    usage_plan_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add rate limit headers to an API Gateway response.
    
    Args:
        response: The API Gateway response dictionary
        api_key_id: The API key ID (optional, for detailed usage info)
        usage_plan_id: The usage plan ID (optional, for detailed usage info)
        
    Returns:
        Updated response with rate limit headers
    """
    # Get usage info if we have the necessary IDs
    if api_key_id and usage_plan_id:
        usage_info = get_usage_info(api_key_id, usage_plan_id)
    else:
        # Use default values
        usage_info = {
            'limit': 1000,
            'remaining': 1000,
            'reset': int(datetime.now(timezone.utc).timestamp()) + 3600
        }
    
    # Ensure headers dict exists
    if 'headers' not in response:
        response['headers'] = {}
    
    # Add rate limit headers
    response['headers']['X-RateLimit-Limit'] = str(usage_info['limit'])
    response['headers']['X-RateLimit-Remaining'] = str(usage_info['remaining'])
    response['headers']['X-RateLimit-Reset'] = str(usage_info['reset'])
    
    return response


def check_rate_limit(api_key_id: str, usage_plan_id: str) -> bool:
    """
    Check if the API key has exceeded its rate limit.
    
    Args:
        api_key_id: The API key ID
        usage_plan_id: The usage plan ID
        
    Returns:
        True if within rate limit, False if exceeded
    """
    try:
        usage_info = get_usage_info(api_key_id, usage_plan_id)
        return usage_info['remaining'] > 0
    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")
        # Allow request if we can't check (fail open)
        return True
