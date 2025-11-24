"""
AWS Systems Manager Parameter Store utility for Lambda functions.

This module provides helper functions to load secrets and configuration
from Parameter Store at Lambda function initialization.
"""

import os
import boto3
from functools import lru_cache
from typing import Dict, Optional


# Initialize SSM client (reused across Lambda invocations)
ssm_client = boto3.client('ssm')


@lru_cache(maxsize=32)
def get_parameter(name: str, with_decryption: bool = True) -> str:
    """
    Retrieve a parameter from Parameter Store with caching.
    
    Args:
        name: Parameter name (e.g., '/agenticai/prod/gemini-api-key')
        with_decryption: Whether to decrypt SecureString parameters
        
    Returns:
        Parameter value as string
        
    Raises:
        Exception: If parameter cannot be retrieved
    """
    try:
        response = ssm_client.get_parameter(
            Name=name,
            WithDecryption=with_decryption
        )
        return response['Parameter']['Value']
    except ssm_client.exceptions.ParameterNotFound:
        raise ValueError(f"Parameter not found: {name}")
    except Exception as e:
        raise Exception(f"Error retrieving parameter {name}: {str(e)}")


@lru_cache(maxsize=1)
def get_all_parameters(environment: Optional[str] = None) -> Dict[str, str]:
    """
    Retrieve all AgenticAI parameters for the specified environment.
    
    Args:
        environment: Environment name (dev, staging, prod). 
                    Defaults to ENVIRONMENT env var or 'prod'
        
    Returns:
        Dictionary of parameter names to values
    """
    if environment is None:
        environment = os.environ.get('ENVIRONMENT', 'prod')
    
    prefix = f'/agenticai/{environment}/'
    
    try:
        response = ssm_client.get_parameters_by_path(
            Path=prefix,
            Recursive=True,
            WithDecryption=True
        )
        
        parameters = {}
        for param in response['Parameters']:
            # Extract parameter name without prefix
            key = param['Name'].replace(prefix, '')
            parameters[key] = param['Value']
        
        return parameters
    except Exception as e:
        raise Exception(f"Error retrieving parameters for environment {environment}: {str(e)}")


def load_secrets() -> Dict[str, str]:
    """
    Load all required secrets for Lambda function initialization.
    
    This function should be called once at module level (outside the handler)
    to cache secrets across Lambda invocations.
    
    Returns:
        Dictionary with keys: gemini_api_key, jwt_secret, github_token (optional)
        
    Example:
        # At module level in Lambda function
        from shared.parameter_store import load_secrets
        
        SECRETS = load_secrets()
        
        def lambda_handler(event, context):
            gemini_key = SECRETS['gemini_api_key']
            # Use the key...
    """
    environment = os.environ.get('ENVIRONMENT', 'prod')
    prefix = f'/agenticai/{environment}'
    
    secrets = {}
    
    # Required parameters
    try:
        secrets['gemini_api_key'] = get_parameter(f'{prefix}/gemini-api-key')
        secrets['jwt_secret'] = get_parameter(f'{prefix}/jwt-secret')
    except Exception as e:
        raise Exception(f"Failed to load required secrets: {str(e)}")
    
    # Optional parameters
    try:
        secrets['github_token'] = get_parameter(f'{prefix}/github-token')
    except:
        secrets['github_token'] = None
    
    return secrets


def clear_cache():
    """
    Clear the parameter cache.
    
    Useful for testing or when parameters are updated and you need
    to force a refresh.
    """
    get_parameter.cache_clear()
    get_all_parameters.cache_clear()
