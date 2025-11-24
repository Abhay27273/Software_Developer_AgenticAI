"""
Example Lambda function demonstrating Parameter Store usage.

This example shows best practices for loading secrets from Parameter Store
in AWS Lambda functions.
"""

import json
from shared.parameter_store import load_secrets

# Load secrets once at module initialization (cached across invocations)
# This happens during Lambda cold start, not on every invocation
try:
    SECRETS = load_secrets()
    print("✓ Secrets loaded successfully")
except Exception as e:
    print(f"✗ Failed to load secrets: {str(e)}")
    # In production, you might want to fail fast here
    raise


def lambda_handler(event, context):
    """
    Example Lambda handler that uses Parameter Store secrets.
    
    Args:
        event: Lambda event object
        context: Lambda context object
        
    Returns:
        API Gateway response
    """
    try:
        # Access cached secrets (no API call to Parameter Store)
        gemini_api_key = SECRETS['gemini_api_key']
        jwt_secret = SECRETS['jwt_secret']
        github_token = SECRETS.get('github_token')  # Optional parameter
        
        # Example: Use the secrets in your business logic
        # (In real code, never log secrets!)
        print(f"Gemini API Key loaded: {'Yes' if gemini_api_key else 'No'}")
        print(f"JWT Secret loaded: {'Yes' if jwt_secret else 'No'}")
        print(f"GitHub Token loaded: {'Yes' if github_token else 'No'}")
        
        # Your business logic here
        result = {
            'message': 'Secrets loaded successfully',
            'has_gemini_key': bool(gemini_api_key),
            'has_jwt_secret': bool(jwt_secret),
            'has_github_token': bool(github_token)
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }
        
    except Exception as e:
        print(f"Error in handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }


# Alternative approach: Load individual parameters on-demand
def alternative_handler(event, context):
    """
    Alternative approach: Load parameters on-demand.
    
    This is less efficient but gives more control over when parameters are loaded.
    """
    from shared.parameter_store import get_parameter
    import os
    
    env = os.environ.get('ENVIRONMENT', 'prod')
    
    try:
        # Load specific parameter
        gemini_key = get_parameter(f'/agenticai/{env}/gemini-api-key')
        
        # Use the parameter
        # ...
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Success'})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
