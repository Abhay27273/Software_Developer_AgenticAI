# Task 5: API Authentication - Quick Reference

## Quick Deploy

```powershell
# Deploy authentication
.\scripts\deploy_authentication.ps1
```

This script will:
1. Build the SAM application
2. Deploy to AWS
3. Retrieve and display the API key
4. Save the API key to .env file

## Quick Test

```powershell
# Test authentication
.\scripts\test_authentication.ps1
```

This will run 5 tests:
1. Request without API key (should fail)
2. Request with invalid API key (should fail)
3. Request with valid API key (should succeed)
4. Create project with authentication
5. Verify authentication logging

## Manual Testing

### Get API Key

```powershell
# Get API key ID from stack
$apiKeyId = aws cloudformation describe-stacks --stack-name agenticai-stack --query "Stacks[0].Outputs[?OutputKey=='ApiKeyId'].OutputValue" --output text

# Get API key value
$apiKey = aws apigateway get-api-key --api-key $apiKeyId --include-value --query "value" --output text

Write-Host "API Key: $apiKey"
```

### Test Endpoints

```bash
# Health check (should work with API key)
curl -H "X-API-Key: YOUR_KEY" https://your-api.execute-api.us-east-1.amazonaws.com/prod/health

# List projects
curl -H "X-API-Key: YOUR_KEY" https://your-api.execute-api.us-east-1.amazonaws.com/prod/api/projects

# Create project
curl -X POST -H "X-API-Key: YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"name":"Test","project_type":"api"}' \
  https://your-api.execute-api.us-east-1.amazonaws.com/prod/api/projects
```

### Check Rate Limit Headers

```bash
curl -i -H "X-API-Key: YOUR_KEY" https://your-api.execute-api.us-east-1.amazonaws.com/prod/health
```

Look for:
- `X-RateLimit-Limit: 1000`
- `X-RateLimit-Remaining: 999`
- `X-RateLimit-Reset: 1638360000`

## View Logs

```bash
# Tail logs
aws logs tail /aws/lambda/agenticai-api-handler-prod --follow

# View recent authentication attempts
aws logs tail /aws/lambda/agenticai-api-handler-prod --since 5m | grep "Authentication attempt"

# View rate limit violations
aws logs tail /aws/lambda/agenticai-api-handler-prod --since 5m | grep "Rate limit violation"
```

## CloudWatch Logs Insights Queries

### Authentication Failures

```sql
fields @timestamp, api_key_id, source_ip, path, result
| filter @message like /Authentication attempt/
| filter result != "success"
| sort @timestamp desc
| limit 100
```

### Rate Limit Violations

```sql
fields @timestamp, api_key_id
| filter @message like /Rate limit violation/
| stats count() by api_key_id
| sort count desc
```

### Top API Consumers

```sql
fields @timestamp, api_key_id, path
| filter @message like /Authentication attempt/
| filter result = "success"
| stats count() by api_key_id
| sort count desc
```

## Common Issues

### Issue: API key not working

**Solution:**
```bash
# Check if key is enabled
aws apigateway get-api-key --api-key <KEY_ID>

# Check usage plan association
aws apigateway get-usage-plan-keys --usage-plan-id <USAGE_PLAN_ID>
```

### Issue: Rate limit headers missing

**Solution:**
- Check Lambda logs for errors
- Verify rate_limit_headers.py is in Lambda layer
- Ensure API key ID is being passed to create_response

### Issue: 403 Forbidden on all requests

**Solution:**
```bash
# Verify API key is associated with stage
aws apigateway get-api-keys --include-values

# Check usage plan
aws apigateway get-usage-plan --usage-plan-id <USAGE_PLAN_ID>
```

## Key Management

### Create Additional API Key

```bash
# Create key
aws apigateway create-api-key \
  --name "agenticai-api-key-user2" \
  --enabled

# Associate with usage plan
aws apigateway create-usage-plan-key \
  --usage-plan-id <USAGE_PLAN_ID> \
  --key-id <NEW_KEY_ID> \
  --key-type API_KEY
```

### Disable API Key

```bash
aws apigateway update-api-key \
  --api-key <KEY_ID> \
  --patch-operations op=replace,path=/enabled,value=false
```

### Delete API Key

```bash
aws apigateway delete-api-key --api-key <KEY_ID>
```

## Monitoring

### Check Current Usage

```bash
aws apigateway get-usage \
  --usage-plan-id <USAGE_PLAN_ID> \
  --key-id <KEY_ID> \
  --start-date $(date +%Y-%m-%d) \
  --end-date $(date +%Y-%m-%d)
```

### Update Rate Limits

```bash
aws apigateway update-usage-plan \
  --usage-plan-id <USAGE_PLAN_ID> \
  --patch-operations \
    op=replace,path=/throttle/rateLimit,value=2000 \
    op=replace,path=/throttle/burstLimit,value=4000
```

## Files Modified

- `template.yaml` - Added API key, usage plan, and authentication
- `lambda/api_handler/app.py` - Added authentication logging and rate limit headers
- `lambda/shared/python/utils/rate_limit_headers.py` - Rate limit utilities

## Files Created

- `scripts/deploy_authentication.ps1` - Deployment script
- `scripts/test_authentication.ps1` - Test script
- `docs/API_AUTHENTICATION_GUIDE.md` - Complete documentation
- `.kiro/specs/production-hardening/TASK_5_API_AUTHENTICATION_SUMMARY.md` - Summary

## Requirements Satisfied

- ✓ 1.1: 401 for missing API key
- ✓ 1.2: Valid keys work
- ✓ 1.3: 403 for invalid keys
- ✓ 1.4: Multiple keys supported
- ✓ 1.5: Authentication logging
- ✓ 6.1: 1000 req/hour limit
- ✓ 6.2: 429 for rate limit
- ✓ 6.3: Rate limit headers
- ✓ 6.4: Hourly reset
- ✓ 6.5: Violation logging

## Next Task

Task 6: Implement Backup and Recovery
- Enable DynamoDB PITR
- Enable S3 versioning
- Create recovery procedures
