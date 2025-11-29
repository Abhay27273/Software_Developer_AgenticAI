# Task 2: Error Alerting System - Quick Deploy Guide

## 🚀 Quick Start

### 1. Deploy the Alerting System

```powershell
# Option A: Use the deployment script
.\scripts\deploy_alerting.ps1

# Option B: Manual deployment
sam build
sam deploy --no-confirm-changeset
```

### 2. Confirm Email Subscription

1. Check your email: `abhay.optimus.2727@gmail.com`
2. Look for: "AWS Notification - Subscription Confirmation"
3. Click: "Confirm subscription" link
4. ⚠️ **You won't receive alerts until you confirm!**

### 3. Test the System

```bash
python scripts/test_alerting.py
```

This will:
- ✅ Verify all 7 alarms are configured
- ✅ Check your email subscription
- ✅ Optionally send a test alert

## 📊 What Gets Deployed

### SNS Topic
- **Name:** `agenticai-alerts-prod`
- **Purpose:** Sends email notifications
- **Subscriber:** `abhay.optimus.2727@gmail.com`

### CloudWatch Alarms (7 total)

1. **Lambda Error Rate** - Triggers when errors > 5% over 5 minutes
2. **API Handler Failures** - Triggers on 3 consecutive failures
3. **PM Agent Failures** - Triggers on 3 consecutive failures
4. **Dev Agent Failures** - Triggers on 3 consecutive failures
5. **QA Agent Failures** - Triggers on 3 consecutive failures
6. **Ops Agent Failures** - Triggers on 3 consecutive failures
7. **API Gateway 5XX** - Triggers when 5XX errors > 10 over 5 minutes

## 🔧 Troubleshooting SSL Issue

If you get SSL certificate errors during deployment:

### Option 1: Use Trusted Certificates
```powershell
$env:AWS_CA_BUNDLE = "websocket_handler\trusted_certs.crt"
sam deploy --no-confirm-changeset
```

### Option 2: Update Certificates
```powershell
pip install --upgrade certifi
pip install --upgrade awscli
```

### Option 3: Deploy via AWS Console
1. Upload `.aws-sam/build` to S3 manually
2. Deploy via CloudFormation console

### Option 4: Different Network
- Try from home network (not corporate)
- Or use VPN

## ✅ Verification Checklist

After deployment:

- [ ] SNS topic exists: `agenticai-alerts-prod`
- [ ] Email subscription confirmed (not pending)
- [ ] 7 alarms created and enabled
- [ ] Test alarm sent successfully
- [ ] Email notification received

## 📧 What Alerts Look Like

**Subject:** `ALARM: "agenticai-lambda-error-rate-prod" in US East (N. Virginia)`

**Body:**
```
Your Amazon CloudWatch Alarm "agenticai-lambda-error-rate-prod" 
has entered the ALARM state because "Threshold Crossed: 5 errors 
in 5 minutes"

View in Console: https://console.aws.amazon.com/cloudwatch/...
```

## 🎯 Quick Commands

### Check Alarm Status
```bash
aws cloudwatch describe-alarms --alarm-name-prefix agenticai-
```

### Check SNS Subscription
```bash
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:us-east-1:379929762201:agenticai-alerts-prod
```

### Trigger Test Alarm
```bash
python scripts/test_alerting.py
# Select 'y' when prompted to trigger test alarm
```

### View Recent Lambda Errors
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/agenticai-api-handler-prod \
  --filter-pattern "ERROR" \
  --max-items 10
```

## 💰 Cost

**Total Cost:** $0/month

- CloudWatch Alarms: Free (first 10 alarms)
- SNS Email: Free (first 1,000 notifications)

## 📚 Full Documentation

See [ERROR_ALERTING_GUIDE.md](../../docs/ERROR_ALERTING_GUIDE.md) for:
- Complete architecture details
- Response procedures for each alarm
- Advanced troubleshooting
- Integration with other systems

## 🎉 Success!

Once deployed and tested, you'll have:
- ✅ Real-time error monitoring
- ✅ Email alerts for critical issues
- ✅ 7 different alarm types
- ✅ $0 additional cost
- ✅ Production-ready alerting system
