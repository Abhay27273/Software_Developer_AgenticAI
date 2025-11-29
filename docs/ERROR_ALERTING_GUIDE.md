# Error Alerting System Guide

## Overview

The AgenticAI system includes a comprehensive error alerting system that monitors Lambda functions and API Gateway for errors and sends notifications via email when issues are detected.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   CloudWatch Alarms                      │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Lambda Error Rate Alarm                                 │
│  ├─ Threshold: > 5% errors over 5 minutes               │
│  └─ Monitors: All Lambda functions                       │
│                                                           │
│  Lambda Consecutive Failures Alarms                      │
│  ├─ Threshold: 3 consecutive failures                    │
│  └─ Monitors: Each Lambda function individually          │
│                                                           │
│  API Gateway 5XX Error Alarm                             │
│  ├─ Threshold: > 10 errors over 5 minutes               │
│  └─ Monitors: API Gateway                                │
│                                                           │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    SNS Topic                             │
│              agenticai-alerts-prod                       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  Email Notification                      │
│            (Administrator Email)                         │
└─────────────────────────────────────────────────────────┘
```

## Configured Alarms

### 1. Lambda Error Rate Alarm

**Name:** `agenticai-lambda-error-rate-prod`

**Description:** Triggers when Lambda error rate exceeds 5% over a 5-minute period

**Metric:** `AWS/Lambda` - `Errors`

**Threshold:** > 5 errors in 5 minutes

**Use Case:** Detects when Lambda functions are experiencing elevated error rates

### 2. Lambda Consecutive Failures Alarms

**Names:**
- `agenticai-api-handler-consecutive-failures-prod`
- `agenticai-pm-agent-consecutive-failures-prod`
- `agenticai-dev-agent-consecutive-failures-prod`
- `agenticai-qa-agent-consecutive-failures-prod`
- `agenticai-ops-agent-consecutive-failures-prod`

**Description:** Triggers when a Lambda function fails 3 consecutive times

**Metric:** `AWS/Lambda` - `Errors`

**Threshold:** >= 1 error per minute for 3 consecutive minutes

**Use Case:** Detects when a specific Lambda function is consistently failing

### 3. API Gateway 5XX Error Alarm

**Name:** `agenticai-api-gateway-5xx-errors-prod`

**Description:** Triggers when API Gateway returns more than 10 5XX errors in 5 minutes

**Metric:** `AWS/ApiGateway` - `5XXError`

**Threshold:** > 10 errors in 5 minutes

**Use Case:** Detects when the API Gateway is experiencing server-side errors

## Deployment

### Prerequisites

1. AWS CLI configured with appropriate credentials
2. SAM CLI installed
3. Valid administrator email address

### Deploy Alerting Infrastructure

```powershell
# Run the deployment script
.\scripts\deploy_alerting.ps1
```

This will:
1. Build the SAM application
2. Deploy the SNS topic and CloudWatch alarms
3. Send a subscription confirmation email

### Confirm Email Subscription

After deployment:

1. Check your email inbox for a message from AWS Notifications
2. Subject: "AWS Notification - Subscription Confirmation"
3. Click the "Confirm subscription" link in the email
4. You should see a confirmation page in your browser

**Important:** You will not receive alerts until you confirm the subscription!

## Testing

### Verify Configuration

```bash
# Run the test script
python scripts/test_alerting.py
```

This script will:
1. Verify all alarms are configured correctly
2. Check SNS subscription status
3. List all configured alarms
4. Optionally trigger a test alarm

### Manual Testing

You can manually trigger an alarm for testing:

```python
import boto3

cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')

cloudwatch.set_alarm_state(
    AlarmName='agenticai-lambda-error-rate-prod',
    StateValue='ALARM',
    StateReason='Manual test'
)
```

## Email Notification Format

When an alarm triggers, you'll receive an email with:

**Subject:** `ALARM: "<alarm-name>" in US East (N. Virginia)`

**Body:**
```
You are receiving this email because your Amazon CloudWatch Alarm 
"agenticai-lambda-error-rate-prod" in the US East (N. Virginia) 
region has entered the ALARM state, because "Threshold Crossed: 
5 errors in 5 minutes" at "Friday 28 November, 2025 17:30:00 UTC".

View this alarm in the AWS Management Console:
https://console.aws.amazon.com/cloudwatch/...

Alarm Details:
- Name: agenticai-lambda-error-rate-prod
- Description: Lambda error rate exceeded 5% over 5 minutes
- State Change: OK -> ALARM
- Reason: Threshold Crossed: 5 errors in 5 minutes
- Timestamp: 2025-11-28T17:30:00.000Z
```

## Responding to Alerts

### Lambda Error Rate Alert

**Immediate Actions:**
1. Check CloudWatch Logs for the affected Lambda function
2. Look for error patterns in recent invocations
3. Check if there was a recent deployment

**Investigation:**
```bash
# View recent Lambda errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/agenticai-api-handler-prod \
  --start-time $(date -d '10 minutes ago' +%s)000 \
  --filter-pattern "ERROR"
```

### Lambda Consecutive Failures Alert

**Immediate Actions:**
1. Check if the Lambda function is still failing
2. Review the most recent error logs
3. Consider rolling back recent changes

**Investigation:**
```bash
# Get Lambda function details
aws lambda get-function \
  --function-name agenticai-api-handler-prod

# Check recent invocations
aws lambda get-function-event-invoke-config \
  --function-name agenticai-api-handler-prod
```

### API Gateway 5XX Error Alert

**Immediate Actions:**
1. Check API Gateway logs
2. Verify Lambda function health
3. Check for DynamoDB or S3 issues

**Investigation:**
```bash
# View API Gateway logs
aws logs filter-log-events \
  --log-group-name API-Gateway-Execution-Logs_<api-id>/prod \
  --start-time $(date -d '10 minutes ago' +%s)000 \
  --filter-pattern "5XX"
```

## Alarm Management

### View Alarm Status

```bash
# List all alarms
aws cloudwatch describe-alarms \
  --alarm-name-prefix agenticai-

# Get specific alarm details
aws cloudwatch describe-alarms \
  --alarm-names agenticai-lambda-error-rate-prod
```

### Disable an Alarm

```bash
aws cloudwatch disable-alarm-actions \
  --alarm-names agenticai-lambda-error-rate-prod
```

### Enable an Alarm

```bash
aws cloudwatch enable-alarm-actions \
  --alarm-names agenticai-lambda-error-rate-prod
```

### Update Alarm Threshold

Edit `template.yaml` and redeploy:

```yaml
LambdaErrorRateAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    Threshold: 10  # Changed from 5 to 10
```

Then redeploy:
```powershell
.\scripts\deploy_alerting.ps1
```

## Troubleshooting

### Not Receiving Emails

**Problem:** Alarms are triggering but no emails are received

**Solutions:**
1. Verify email subscription is confirmed
   ```bash
   aws sns list-subscriptions-by-topic \
     --topic-arn <topic-arn>
   ```

2. Check spam/junk folder

3. Verify alarm has actions configured
   ```bash
   aws cloudwatch describe-alarms \
     --alarm-names agenticai-lambda-error-rate-prod
   ```

### False Positive Alarms

**Problem:** Alarms triggering when there are no real issues

**Solutions:**
1. Adjust alarm thresholds in `template.yaml`
2. Increase evaluation periods
3. Change the statistic (Sum vs Average)

### Alarm Not Triggering

**Problem:** Errors occurring but alarm not triggering

**Solutions:**
1. Verify alarm is enabled
2. Check alarm configuration matches metric dimensions
3. Verify sufficient data points exist

## Best Practices

1. **Confirm Subscriptions Immediately:** Always confirm SNS subscriptions right after deployment

2. **Test Regularly:** Run the test script monthly to ensure alerts are working

3. **Document Response Procedures:** Create runbooks for each alarm type

4. **Monitor Alarm History:** Review CloudWatch alarm history weekly

5. **Adjust Thresholds:** Fine-tune alarm thresholds based on actual system behavior

6. **Multiple Recipients:** Add multiple email subscriptions for redundancy

7. **Integration:** Consider integrating with PagerDuty, Slack, or other alerting systems

## Cost Considerations

**CloudWatch Alarms:**
- First 10 alarms: Free
- Additional alarms: $0.10 per alarm per month
- Current configuration: 7 alarms = Free

**SNS:**
- First 1,000 email notifications: Free
- Additional emails: $2.00 per 100,000 notifications
- Expected cost: $0/month (well within free tier)

**Total Expected Cost:** $0/month

## Next Steps

1. Deploy the alerting infrastructure
2. Confirm email subscription
3. Run the test script
4. Create response procedures for each alarm type
5. Consider adding more alarms for:
   - DynamoDB throttling
   - SQS queue depth
   - Lambda duration
   - API Gateway latency

## Related Documentation

- [CloudWatch Dashboard Setup](CLOUDWATCH_DASHBOARD_SETUP.md)
- [AWS Operations Runbook](AWS_OPERATIONS_RUNBOOK.md)
- [AWS Deployment Guide](AWS_DEPLOYMENT_GUIDE.md)
