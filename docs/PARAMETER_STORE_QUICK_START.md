# Parameter Store Quick Start Guide

This guide will help you set up AWS Parameter Store for the AgenticAI system in under 5 minutes.

## Prerequisites

- AWS account with appropriate permissions
- AWS CLI configured (`aws configure`)
- Python 3.11+ installed
- boto3 installed (`pip install boto3`)

## Quick Setup (3 Steps)

### Step 1: Run the Setup Script

```bash
python scripts/setup_parameter_store.py --environment prod --region us-east-1
```

You'll be prompted to enter:
1. **Gemini API Key** (required) - Get from https://aistudio.google.com/app/apikey
2. **GitHub Token** (optional) - For repository operations
3. **JWT Secret** (optional) - Auto-generated if not provided

### Step 2: Verify Parameters

```bash
python scripts/setup_parameter_store.py --environment prod --verify-only
```

Expected output:
```
✓ /agenticai/prod/gemini-api-key (SecureString)
✓ /agenticai/prod/jwt-secret (SecureString)
✓ /agenticai/prod/github-token (SecureString)
```

### Step 3: Deploy Your Application

```bash
sam build && sam deploy --guided
```

That's it! Your Lambda functions will automatically load secrets from Parameter Store.

## Usage in Lambda Functions

### Basic Usage

```python
from shared.parameter_store import load_secrets

# Load once at module level
SECRETS = load_secrets()

def lambda_handler(event, context):
    api_key = SECRETS['gemini_api_key']
    # Use the API key...
```

### Advanced Usage

```python
from shared.parameter_store import get_parameter

def lambda_handler(event, context):
    # Load specific parameter
    api_key = get_parameter('/agenticai/prod/gemini-api-key')
    # Use the API key...
```

## Common Commands

### Update a Parameter

```bash
aws ssm put-parameter \
    --name "/agenticai/prod/gemini-api-key" \
    --value "NEW_API_KEY" \
    --type "SecureString" \
    --overwrite
```

### List All Parameters

```bash
aws ssm get-parameters-by-path \
    --path "/agenticai/prod" \
    --region us-east-1
```

### Delete a Parameter

```bash
aws ssm delete-parameter \
    --name "/agenticai/prod/github-token"
```

## Multiple Environments

Set up different environments (dev, staging, prod):

```bash
# Development
python scripts/setup_parameter_store.py --environment dev

# Staging
python scripts/setup_parameter_store.py --environment staging

# Production
python scripts/setup_parameter_store.py --environment prod
```

Each environment has isolated parameters:
- `/agenticai/dev/*`
- `/agenticai/staging/*`
- `/agenticai/prod/*`

## Troubleshooting

### "Access Denied" Error

**Solution**: Ensure your AWS user has SSM permissions:

```bash
aws iam attach-user-policy \
    --user-name YOUR_USERNAME \
    --policy-arn arn:aws:iam::aws:policy/AmazonSSMFullAccess
```

### "Parameter Not Found" in Lambda

**Solution**: Check the ENVIRONMENT variable:

```bash
aws lambda get-function-configuration \
    --function-name your-function-name \
    --query 'Environment.Variables.ENVIRONMENT'
```

### Parameters Not Loading

**Solution**: Verify IAM role has Parameter Store access:

```bash
# Check Lambda execution role
aws iam get-role-policy \
    --role-name agenticai-lambda-role-prod \
    --policy-name ParameterStoreAccess
```

## Security Best Practices

1. ✅ Use SecureString for all sensitive data
2. ✅ Separate parameters by environment
3. ✅ Use least privilege IAM policies
4. ✅ Rotate secrets regularly
5. ✅ Never commit secrets to Git
6. ✅ Never log secret values

## Cost

- **Standard Parameters**: FREE (up to 10,000)
- **API Calls**: FREE (10,000/month)
- **With Caching**: ~$0/month for typical usage

## Next Steps

- Read the [full documentation](AWS_PARAMETER_STORE_SETUP.md)
- See [Lambda integration examples](../lambda/shared/README.md)
- Review [security best practices](AWS_PARAMETER_STORE_SETUP.md#security-best-practices)

## Support

For issues or questions:
1. Check the [troubleshooting guide](AWS_PARAMETER_STORE_SETUP.md#troubleshooting)
2. Review AWS CloudWatch logs
3. Verify IAM permissions
