# API Authentication Guide

## Overview

This guide describes the API authentication implementation for the AgenticAI system. The system uses API Gateway API Keys with usage plans to secure API endpoints and implement rate limiting.

## Features

- **API Key Authentication**: All API endpoints (except `/health`) require a valid API key
- **Rate Limiting**: 1000 requests per hour per API key with burst capacity of 2000
- **Rate Limit Headers**: Responses include rate limit information
- **Authentication Logging**: All authentication attempts are logged to CloudWatch
- **Rate Limit Violation Logging**: Rate limit violations are logged for monitoring

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ X-API-Key: <key>
       ▼
┌─────────────────┐
│  API Gateway    │
│  - Validates    │
│    API Key      │
│  - Enforces     │
│    Rate Limits  │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ Lambda Handler  │
│  - Logs Auth    │
│  - Adds Headers │
│  - Processes    │
│    Request      │
└─────────────────┘
```

## Requirements Implemented

- **Requirement 1.1**: Unauthorized requests return HTTP 401
- **Requirement 1.2**: Valid API keys allow request processing
- **Requirement 1.3**: Invalid API keys return HTTP 403
- **Requirement 1.4**: Support for multiple API keys via usage plans
- **Requirement 1.5**: Authentication logging to CloudWatch
- **Requirement 6.1**: Rate limit of 1000 requests per hour
- **Requirement 6.2**: Rate limit exceeded returns HTTP 429
- **Requirement 6.3**: Rate limit headers in responses
- **Requirement 6.4**: Hourly rate limit reset
- **Requirement 6.5**: Rate limit violation logging

## API Key Management

### Creating API Keys

API keys are created automatically during deployment via the SAM template:

```yaml
ApiKey:
  Type: AWS::ApiGateway::ApiKey
  Properties:
    Name: agenticai-api-key-prod
    Enabled: true
```

### Retrieving API Keys

To retrieve the API key value after deployment:

```powershell
# Get the API key ID from stack outputs
$apiKeyId = aws cloudformation describe-stacks --stack-name agenticai-stack --query "Stacks[0].Outputs[?OutputKey=='ApiKeyId'].OutputValue" --output text

# Get the API key value
$apiKeyValue = aws apigateway get-api-key --api-key $apiKeyId --include-value --query "value" --output text

Write-Host "API Key: $apiKeyValue"
```

### Creating Additional API Keys

To create additional API keys:

```bash
# Create a new API key
aws apigateway create-api-key \
  --name "agenticai-api-key-user2" \
  --enabled \
  --stage-keys restApiId=<API_ID>,stageName=prod

# Associate with usage plan
aws apigateway create-usage-plan-key \
  --usage-plan-id <USAGE_PLAN_ID> \
  --key-id <NEW_API_KEY_ID> \
  --key-type API_KEY
```

### Rotating API Keys

To rotate an API key:

1. Create a new API key
2. Associate it with the usage plan
3. Update clients with the new key
4. Disable the old key
5. Delete the old key after verification

```bash
# Disable old key
aws apigateway update-api-key --api-key <OLD_KEY_ID> --patch-operations op=replace,path=/enabled,value=false

# Delete old key (after verification)
aws apigateway delete-api-key --api-key <OLD_KEY_ID>
```

## Usage

### Making Authenticated Requests

Include the API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: YOUR_API_KEY" https://api.example.com/api/projects
```

### Response Headers

All successful responses include rate limit information:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 995
X-RateLimit-Reset: 1638360000
```

- `X-RateLimit-Limit`: Maximum requests allowed per hour
- `X-RateLimit-Remaining`: Requests remaining in current hour
- `X-RateLimit-Reset`: Unix timestamp when the limit resets

### Error Responses

#### Missing API Key (401)

```json
{
  "success": false,
  "error": {
    "code": "UNAUTHORIZED",
    "message": "API key is required",
    "timestamp": "2025-11-29T10:00:00.000Z"
  }
}
```

#### Invalid API Key (403)

```json
{
  "success": false,
  "error": {
    "code": "FORBIDDEN",
    "message": "Invalid API key",
    "timestamp": "2025-11-29T10:00:00.000Z"
  }
}
```

#### Rate Limit Exceeded (429)

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please try again later.",
    "timestamp": "2025-11-29T10:00:00.000Z"
  }
}
```

## Rate Limiting

### Configuration

Rate limits are configured in the SAM template:

```yaml
UsagePlan:
  Type: AWS::ApiGateway::UsagePlan
  Properties:
    Throttle:
      RateLimit: 1000      # Requests per hour
      BurstLimit: 2000     # Maximum burst capacity
    Quota:
      Limit: 1000          # Hourly quota
      Period: HOUR
```

### Monitoring Rate Limits

Check current usage via AWS CLI:

```bash
# Get usage for today
aws apigateway get-usage \
  --usage-plan-id <USAGE_PLAN_ID> \
  --key-id <API_KEY_ID> \
  --start-date $(date +%Y-%m-%d) \
  --end-date $(date +%Y-%m-%d)
```

### Adjusting Rate Limits

To modify rate limits:

1. Update the SAM template
2. Redeploy the stack

Or use AWS CLI:

```bash
aws apigateway update-usage-plan \
  --usage-plan-id <USAGE_PLAN_ID> \
  --patch-operations \
    op=replace,path=/throttle/rateLimit,value=2000 \
    op=replace,path=/throttle/burstLimit,value=4000
```

## Logging

### Authentication Logs

All authentication attempts are logged with the following information:

```json
{
  "timestamp": "2025-11-29T10:00:00.000Z",
  "request_id": "abc123",
  "api_key_id": "xyz789",
  "source_ip": "192.168.1.1",
  "user_agent": "curl/7.68.0",
  "method": "GET",
  "path": "/api/projects",
  "result": "success"
}
```

### Rate Limit Violation Logs

Rate limit violations are logged separately:

```json
{
  "timestamp": "2025-11-29T10:00:00.000Z",
  "api_key_id": "xyz789",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded"
}
```

### Querying Logs

Use CloudWatch Logs Insights to query authentication logs:

```sql
# Find all authentication failures
fields @timestamp, api_key_id, source_ip, path, result
| filter @message like /Authentication attempt/
| filter result != "success"
| sort @timestamp desc
| limit 100

# Find rate limit violations
fields @timestamp, api_key_id
| filter @message like /Rate limit violation/
| stats count() by api_key_id
| sort count desc
```

## Security Best Practices

1. **Store API Keys Securely**: Never commit API keys to version control
2. **Use Environment Variables**: Store keys in environment variables or secrets management
3. **Rotate Keys Regularly**: Rotate API keys every 90 days
4. **Monitor Usage**: Set up CloudWatch alarms for unusual usage patterns
5. **Limit Key Distribution**: Only create keys for authorized users/applications
6. **Use HTTPS Only**: Always use HTTPS for API requests
7. **Implement IP Whitelisting**: Consider adding IP restrictions for sensitive operations

## Troubleshooting

### API Key Not Working

1. Verify the API key is enabled:
   ```bash
   aws apigateway get-api-key --api-key <KEY_ID>
   ```

2. Check if the key is associated with the usage plan:
   ```bash
   aws apigateway get-usage-plan-keys --usage-plan-id <USAGE_PLAN_ID>
   ```

3. Verify the API Gateway stage has the correct configuration

### Rate Limit Issues

1. Check current usage:
   ```bash
   aws apigateway get-usage --usage-plan-id <USAGE_PLAN_ID> --key-id <KEY_ID>
   ```

2. Review CloudWatch logs for rate limit violations

3. Consider increasing rate limits if legitimate traffic is being throttled

### Authentication Logs Not Appearing

1. Check Lambda function has CloudWatch Logs permissions
2. Verify log group exists: `/aws/lambda/agenticai-api-handler-prod`
3. Check log retention settings
4. Review IAM role permissions

## Testing

### Deployment Script

Deploy authentication changes:

```powershell
.\scripts\deploy_authentication.ps1
```

### Test Script

Run authentication tests:

```powershell
.\scripts\test_authentication.ps1
```

This will test:
- Request without API key (should fail)
- Request with invalid API key (should fail)
- Request with valid API key (should succeed)
- Rate limit headers presence
- Authentication logging

## Integration with Existing Code

### Client-Side Integration

Update your API client to include the API key:

```python
import requests

API_ENDPOINT = "https://your-api.execute-api.us-east-1.amazonaws.com/prod/"
API_KEY = "your-api-key"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

response = requests.get(f"{API_ENDPOINT}api/projects", headers=headers)
```

### Rate Limit Handling

Implement rate limit handling in your client:

```python
import time

def make_request_with_retry(url, headers, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers)
        
        if response.status_code == 429:
            # Rate limited - check reset time
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            wait_time = max(0, reset_time - time.time())
            
            print(f"Rate limited. Waiting {wait_time} seconds...")
            time.sleep(wait_time + 1)
            continue
        
        return response
    
    raise Exception("Max retries exceeded")
```

## Monitoring and Alerts

### CloudWatch Metrics

Monitor these metrics:
- API Gateway 4XX errors (authentication failures)
- API Gateway 5XX errors (server errors)
- Lambda invocation count
- Lambda error count

### Recommended Alarms

1. **High Authentication Failure Rate**
   - Metric: API Gateway 4XX errors
   - Threshold: > 100 in 5 minutes
   - Action: Send SNS notification

2. **Unusual API Key Usage**
   - Metric: Custom metric from logs
   - Threshold: > 800 requests per hour per key
   - Action: Send SNS notification

3. **Multiple Rate Limit Violations**
   - Metric: Custom metric from logs
   - Threshold: > 10 violations in 5 minutes
   - Action: Send SNS notification

## Cost Considerations

- API Gateway API Keys: Free
- Usage Plans: Free
- CloudWatch Logs: $0.50 per GB ingested
- CloudWatch Logs storage: $0.03 per GB per month

Estimated monthly cost for authentication: $1-5 depending on traffic volume.

## References

- [AWS API Gateway API Keys](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-key-source.html)
- [AWS API Gateway Usage Plans](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-usage-plans.html)
- [Rate Limiting Best Practices](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html)
