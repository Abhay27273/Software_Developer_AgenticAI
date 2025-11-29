# API Authentication - Quick Start

## Overview

The AgenticAI API now requires authentication using API keys. All endpoints (except `/health`) require a valid API key in the `X-API-Key` header.

## Getting Your API Key

After deployment, retrieve your API key:

```powershell
# Get API key ID
$apiKeyId = aws cloudformation describe-stacks --stack-name agenticai-stack --query "Stacks[0].Outputs[?OutputKey=='ApiKeyId'].OutputValue" --output text

# Get API key value
$apiKey = aws apigateway get-api-key --api-key $apiKeyId --include-value --query "value" --output text

Write-Host "Your API Key: $apiKey"
```

## Using the API

Include your API key in all requests:

```bash
curl -H "X-API-Key: YOUR_API_KEY" https://your-api-endpoint.com/api/projects
```

## Rate Limits

- **Limit:** 1000 requests per hour
- **Burst:** 2000 requests
- **Reset:** Every hour

Check your remaining quota in response headers:
- `X-RateLimit-Limit`: Total allowed per hour
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Error Codes

- **401 Unauthorized**: Missing API key
- **403 Forbidden**: Invalid API key
- **429 Too Many Requests**: Rate limit exceeded

## Example Response

```json
HTTP/1.1 200 OK
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 995
X-RateLimit-Reset: 1638360000

{
  "success": true,
  "projects": [...]
}
```

## Security

- Store your API key securely
- Never commit API keys to version control
- Use environment variables or secrets management
- Rotate keys regularly (every 90 days recommended)

## Need Help?

See the complete guide: [API Authentication Guide](./API_AUTHENTICATION_GUIDE.md)
