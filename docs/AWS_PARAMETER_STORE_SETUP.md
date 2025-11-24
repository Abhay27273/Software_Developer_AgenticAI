# AWS Parameter Store Setup Guide

## Overview

AWS Systems Manager Parameter Store is used to securely store and manage sensitive configuration data such as API keys, tokens, and secrets. This guide explains how to set up and manage parameters for the AgenticAI system.

## Required Parameters

The following parameters must be configured before deploying the application:

| Parameter Name | Type | Description | Required |
|---------------|------|-------------|----------|
| `/agenticai/{env}/gemini-api-key` | SecureString | Google Gemini API key for LLM operations | Yes |
| `/agenticai/{env}/jwt-secret` | SecureString | JWT secret for authentication tokens | Yes |
| `/agenticai/{env}/github-token` | SecureString | GitHub personal access token (for repo operations) | No |

Where `{env}` is one of: `dev`, `staging`, or `prod`

## Setup Methods

### Method 1: Automated Setup (Recommended)

Use the provided Python script to interactively set up all parameters:

```bash
# Install boto3 if not already installed
pip install boto3

# Run the setup script
python scripts/setup_parameter_store.py --environment prod --region us-east-1
```

The script will:
1. Prompt you for each required secret
2. Generate a random JWT secret if not provided
3. Create all parameters in Parameter Store
4. Display a summary of created parameters

### Method 2: Manual Setup via AWS CLI

Create parameters manually using the AWS CLI:

```bash
# Set environment and region
ENV=prod
REGION=us-east-1

# Create Gemini API Key
aws ssm put-parameter \
    --name "/agenticai/${ENV}/gemini-api-key" \
    --value "YOUR_GEMINI_API_KEY" \
    --type "SecureString" \
    --description "Google Gemini API key for LLM operations" \
    --region ${REGION}

# Create JWT Secret
aws ssm put-parameter \
    --name "/agenticai/${ENV}/jwt-secret" \
    --value "YOUR_JWT_SECRET" \
    --type "SecureString" \
    --description "JWT secret for authentication tokens" \
    --region ${REGION}

# Create GitHub Token (optional)
aws ssm put-parameter \
    --name "/agenticai/${ENV}/github-token" \
    --value "YOUR_GITHUB_TOKEN" \
    --type "SecureString" \
    --description "GitHub personal access token" \
    --region ${REGION}
```

### Method 3: AWS Console

1. Navigate to AWS Systems Manager → Parameter Store
2. Click "Create parameter"
3. Enter parameter details:
   - Name: `/agenticai/prod/gemini-api-key`
   - Type: SecureString
   - Value: Your API key
4. Click "Create parameter"
5. Repeat for other parameters

## Accessing Parameters in Lambda Functions

### Method 1: Using the Shared Parameter Store Utility (Recommended)

The shared Lambda layer provides a convenient utility for loading parameters with caching:

```python
# lambda/api_handler/app.py
from shared.parameter_store import load_secrets

# Load secrets once at module initialization (cached across invocations)
SECRETS = load_secrets()

def lambda_handler(event, context):
    # Use cached secrets
    gemini_api_key = SECRETS['gemini_api_key']
    jwt_secret = SECRETS['jwt_secret']
    github_token = SECRETS.get('github_token')  # Optional parameter
    
    # Your handler logic...
    return {
        'statusCode': 200,
        'body': 'Success'
    }
```

**Benefits:**
- Automatic caching reduces Parameter Store API calls
- Improved cold start performance
- Consistent error handling
- Type-safe parameter access

### Method 2: Direct boto3 Access

For custom use cases, you can access Parameter Store directly:

```python
import boto3
import os

ssm = boto3.client('ssm')

def get_parameter(name):
    """Retrieve a parameter from Parameter Store."""
    try:
        response = ssm.get_parameter(
            Name=name,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error retrieving parameter {name}: {str(e)}")
        raise

# Usage in Lambda function
def lambda_handler(event, context):
    env = os.environ.get('ENVIRONMENT', 'prod')
    gemini_api_key = get_parameter(f'/agenticai/{env}/gemini-api-key')
    
    # Use the API key
    # ...
```

### Caching Best Practices

Load parameters at module level (outside the handler) to cache them across Lambda invocations:

```python
# ✅ Good: Load once at module level
from shared.parameter_store import load_secrets
SECRETS = load_secrets()

def lambda_handler(event, context):
    api_key = SECRETS['gemini_api_key']
    # ...

# ❌ Bad: Load on every invocation
def lambda_handler(event, context):
    secrets = load_secrets()  # Slow, makes API call every time
    api_key = secrets['gemini_api_key']
    # ...
```

## Updating Parameters

To update an existing parameter:

```bash
aws ssm put-parameter \
    --name "/agenticai/prod/gemini-api-key" \
    --value "NEW_API_KEY" \
    --type "SecureString" \
    --overwrite \
    --region us-east-1
```

**Note:** Lambda functions cache parameter values. After updating a parameter, you may need to:
1. Wait for the Lambda function to be invoked again (cold start)
2. Or manually update the Lambda environment variable to force a restart

## Security Best Practices

1. **Use SecureString Type**: Always use `SecureString` type for sensitive data. This encrypts the parameter using AWS KMS.

2. **Least Privilege IAM**: Lambda execution roles should only have permission to read specific parameters:
   ```json
   {
     "Effect": "Allow",
     "Action": [
       "ssm:GetParameter",
       "ssm:GetParameters"
     ],
     "Resource": "arn:aws:ssm:*:*:parameter/agenticai/*"
   }
   ```

3. **Never Commit Secrets**: Never commit API keys or secrets to Git. Use `.env.example` for documentation only.

4. **Rotate Secrets Regularly**: Periodically update API keys and secrets, especially after team member changes.

5. **Use Different Parameters per Environment**: Keep separate parameters for dev, staging, and prod environments.

## Troubleshooting

### Error: "Parameter not found"

**Cause**: The parameter doesn't exist or the name is incorrect.

**Solution**: 
- Verify the parameter name matches exactly (case-sensitive)
- Check the AWS region
- Run the setup script to create missing parameters

### Error: "Access Denied"

**Cause**: Lambda execution role doesn't have permission to read parameters.

**Solution**:
- Verify the IAM role has `ssm:GetParameter` permission
- Check the resource ARN in the IAM policy matches your parameter path

### Error: "KMS key not found"

**Cause**: The KMS key used for encryption was deleted.

**Solution**:
- Create a new parameter with a new KMS key
- Or use the default AWS managed key

## Cost Considerations

- **Standard Parameters**: Free (up to 10,000 parameters)
- **Advanced Parameters**: $0.05 per parameter per month
- **API Calls**: Free tier includes 10,000 Parameter Store API calls per month

For this application, we use Standard parameters which are completely free within AWS Free Tier limits.

## Verification

To verify that all parameters are set up correctly:

```bash
# Verify parameters using the script
python scripts/setup_parameter_store.py --environment prod --verify-only

# Or manually check with AWS CLI
aws ssm get-parameters-by-path \
    --path "/agenticai/prod" \
    --with-decryption \
    --region us-east-1
```

## Testing

Unit tests for the Parameter Store utility are available:

```bash
# Install test dependencies
pip install pytest moto boto3

# Run tests
pytest tests/test_parameter_store.py -v
```

## Performance Considerations

### Caching

The shared utility uses `@lru_cache` to cache parameter values:

- **Cache Duration**: For the lifetime of the Lambda container (typically 5-15 minutes)
- **Cache Size**: Up to 32 parameters (configurable)
- **Benefits**: Reduces API calls, improves performance, lowers costs

### Cold Start Impact

Loading parameters adds ~100-200ms to Lambda cold start time:

- Load at module level to cache across invocations
- Use `load_secrets()` for all required parameters at once
- Avoid loading parameters inside the handler function

### Cost Optimization

- **Free Tier**: 10,000 Parameter Store API calls per month
- **Caching**: Reduces API calls by ~95% (only on cold starts)
- **Estimated Cost**: $0/month for typical usage with caching

## Additional Resources

- [AWS Parameter Store Documentation](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- [AWS KMS Encryption](https://docs.aws.amazon.com/kms/latest/developerguide/overview.html)
- [IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
