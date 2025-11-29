# Task 5: API Authentication - Deployment Checklist

## Pre-Deployment

- [x] All code changes completed
- [x] SAM template updated with API key resources
- [x] Lambda handler updated with authentication logging
- [x] Rate limit headers utility created
- [x] Deployment scripts created
- [x] Test scripts created
- [x] Documentation completed
- [x] No syntax errors in modified files

## Deployment Steps

### 1. Review Changes

```bash
# Review modified files
git diff template.yaml
git diff lambda/api_handler/app.py
git diff lambda/shared/python/utils/rate_limit_headers.py
```

### 2. Build Application

```powershell
sam build
```

**Expected Output:**
- Build successful
- All Lambda functions built
- Shared layer built

### 3. Deploy to AWS

```powershell
sam deploy --no-confirm-changeset
```

**Expected Output:**
- Stack update initiated
- Resources created/updated:
  - ApiKey
  - UsagePlan
  - UsagePlanKey
  - ApiKeyParameter
- Stack update complete

### 4. Retrieve API Key

```powershell
# Get API key ID
$apiKeyId = aws cloudformation describe-stacks --stack-name agenticai-stack --query "Stacks[0].Outputs[?OutputKey=='ApiKeyId'].OutputValue" --output text

# Get API key value
$apiKey = aws apigateway get-api-key --api-key $apiKeyId --include-value --query "value" --output text

Write-Host "API Key: $apiKey"
```

**Expected Output:**
- API key ID displayed
- API key value displayed (save this securely!)

### 5. Update Environment Variables

```powershell
# Add to .env file
Add-Content .env "`nAPI_KEY=$apiKey"
```

## Post-Deployment Verification

### 1. Test Without API Key

```bash
curl https://your-api-endpoint.com/api/projects
```

**Expected:** 401 or 403 error

### 2. Test With Invalid API Key

```bash
curl -H "X-API-Key: invalid-key" https://your-api-endpoint.com/api/projects
```

**Expected:** 403 Forbidden

### 3. Test With Valid API Key

```bash
curl -H "X-API-Key: YOUR_KEY" https://your-api-endpoint.com/health
```

**Expected:** 200 OK with rate limit headers

### 4. Verify Rate Limit Headers

```bash
curl -i -H "X-API-Key: YOUR_KEY" https://your-api-endpoint.com/health
```

**Expected Headers:**
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: <timestamp>
```

### 5. Check CloudWatch Logs

```bash
aws logs tail /aws/lambda/agenticai-api-handler-prod --since 5m
```

**Expected:** Authentication attempt logs visible

### 6. Run Automated Tests

```powershell
.\scripts\test_authentication.ps1
```

**Expected:** All tests pass

## Verification Checklist

- [ ] API key created successfully
- [ ] Usage plan configured correctly
- [ ] API Gateway requires API key
- [ ] Requests without key are rejected (401/403)
- [ ] Requests with invalid key are rejected (403)
- [ ] Requests with valid key succeed (200)
- [ ] Rate limit headers present in responses
- [ ] Authentication logs visible in CloudWatch
- [ ] Rate limit violations logged (if triggered)
- [ ] API key stored in Parameter Store
- [ ] API key saved to .env file

## Rollback Procedure

If issues occur:

### 1. Identify Issue

Check CloudWatch logs:
```bash
aws logs tail /aws/lambda/agenticai-api-handler-prod --since 10m
```

### 2. Quick Fix Options

**Option A: Disable API Key Requirement (Emergency)**
```bash
# Temporarily disable API key requirement
aws apigateway update-method \
  --rest-api-id <API_ID> \
  --resource-id <RESOURCE_ID> \
  --http-method ANY \
  --patch-operations op=replace,path=/apiKeyRequired,value=false
```

**Option B: Rollback Deployment**
```bash
# Revert to previous version
git checkout HEAD~1 template.yaml lambda/api_handler/app.py
sam build && sam deploy
```

### 3. Verify Rollback

```bash
# Test API is accessible
curl https://your-api-endpoint.com/health
```

## Monitoring Setup

### 1. Create CloudWatch Alarm for Auth Failures

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name agenticai-auth-failures \
  --alarm-description "High authentication failure rate" \
  --metric-name 4XXError \
  --namespace AWS/ApiGateway \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions <SNS_TOPIC_ARN>
```

### 2. Set Up Log Insights Queries

Save these queries in CloudWatch Logs Insights:

**Authentication Failures:**
```sql
fields @timestamp, api_key_id, source_ip, path, result
| filter @message like /Authentication attempt/
| filter result != "success"
| sort @timestamp desc
```

**Rate Limit Violations:**
```sql
fields @timestamp, api_key_id
| filter @message like /Rate limit violation/
| stats count() by api_key_id
```

## Documentation Updates

- [x] API Authentication Guide created
- [x] Quick Reference created
- [x] Deployment Checklist created
- [x] Authentication README created
- [x] Task Summary created

## Client Updates Required

### Update API Clients

All API clients must be updated to include API key:

**Python:**
```python
headers = {"X-API-Key": "YOUR_API_KEY"}
response = requests.get(url, headers=headers)
```

**JavaScript:**
```javascript
const headers = {"X-API-Key": "YOUR_API_KEY"};
fetch(url, {headers});
```

**cURL:**
```bash
curl -H "X-API-Key: YOUR_API_KEY" https://api-endpoint.com/api/projects
```

## Communication Plan

### Internal Team

- [ ] Notify team of authentication requirement
- [ ] Share API key securely (use secrets management)
- [ ] Update internal documentation
- [ ] Schedule training session if needed

### External Users (if applicable)

- [ ] Send notification email about authentication
- [ ] Provide migration guide
- [ ] Set grace period for transition
- [ ] Offer support for integration

## Success Criteria

- [x] All subtasks completed
- [ ] Deployment successful
- [ ] All tests passing
- [ ] No errors in CloudWatch logs
- [ ] Rate limiting working correctly
- [ ] Authentication logging functional
- [ ] Documentation complete
- [ ] Team notified
- [ ] Monitoring configured

## Next Steps

After successful deployment:

1. **Monitor for 24 hours**
   - Watch CloudWatch logs
   - Check for authentication failures
   - Monitor rate limit violations

2. **Review Usage Patterns**
   - Analyze API usage
   - Adjust rate limits if needed
   - Identify top consumers

3. **Implement Key Rotation**
   - Create rotation schedule
   - Document rotation procedure
   - Set up automation

4. **Move to Next Task**
   - Task 6: Implement Backup and Recovery
   - Enable DynamoDB PITR
   - Configure S3 versioning

## Support

If you encounter issues:

1. Check CloudWatch logs
2. Review [API Authentication Guide](../docs/API_AUTHENTICATION_GUIDE.md)
3. Run test script: `.\scripts\test_authentication.ps1`
4. Check [Quick Reference](./TASK_5_QUICK_REFERENCE.md)

## Notes

- API keys are stored in Parameter Store at `/agenticai/prod/api-key`
- Rate limits can be adjusted in SAM template
- Authentication logs are in `/aws/lambda/agenticai-api-handler-prod`
- Usage data available via API Gateway console

---

**Deployment Date:** _________________

**Deployed By:** _________________

**API Key ID:** _________________

**Verification Status:** _________________

**Issues Encountered:** _________________

**Resolution:** _________________
