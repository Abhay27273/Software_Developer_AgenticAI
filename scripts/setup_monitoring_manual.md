# Manual CloudWatch Monitoring Setup

## Quick Setup (AWS Console)

### Step 1: Create Dashboard

1. **Open CloudWatch Console**
   ```
   https://console.aws.amazon.com/cloudwatch/
   ```

2. **Create Dashboard**
   - Click "Dashboards" in left menu
   - Click "Create dashboard"
   - Name: `AgenticAI-Production`
   - Click "Create dashboard"

### Step 2: Add Widgets

#### Widget 1: API Gateway Requests

1. Click "Add widget"
2. Select "Line" chart
3. Click "Metrics"
4. Select "API Gateway" → "By API Name"
5. Select your API metrics:
   - `Count` (total requests)
   - `4XXError` (client errors)
   - `5XXError` (server errors)
6. Click "Create widget"

#### Widget 2: Lambda Invocations

1. Click "Add widget"
2. Select "Number"
3. Select "Lambda" → "By Function Name"
4. Select all your Lambda functions:
   - `agenticai-stack-ApiHandler`
   - `agenticai-stack-PMAgentWorker`
   - `agenticai-stack-DevAgentWorker`
   - `agenticai-stack-QAAgentWorker`
   - `agenticai-stack-OpsAgentWorker`
5. Metric: `Invocations`
6. Statistic: `Sum`
7. Period: `5 minutes`
8. Click "Create widget"

#### Widget 3: Lambda Errors

1. Click "Add widget"
2. Select "Line" chart
3. Select "Lambda" → "By Function Name"
4. Select all functions
5. Metric: `Errors`
6. Click "Create widget"

#### Widget 4: Lambda Duration

1. Click "Add widget"
2. Select "Line" chart
3. Select "Lambda" → "By Function Name"
4. Select all functions
5. Metric: `Duration`
6. Statistic: `Average`
7. Click "Create widget"

#### Widget 5: DynamoDB Operations

1. Click "Add widget"
2. Select "Number"
3. Select "DynamoDB" → "Table Metrics"
4. Select your table: `agenticai-data`
5. Metrics:
   - `ConsumedReadCapacityUnits`
   - `ConsumedWriteCapacityUnits`
6. Click "Create widget"

#### Widget 6: SQS Queue Depth

1. Click "Add widget"
2. Select "Line" chart
3. Select "SQS" → "Queue Metrics"
4. Select all your queues:
   - `agenticai-pm-queue`
   - `agenticai-dev-queue`
   - `agenticai-qa-queue`
   - `agenticai-ops-queue`
5. Metric: `ApproximateNumberOfMessagesVisible`
6. Click "Create widget"

### Step 3: Save Dashboard

1. Click "Save dashboard"
2. Your dashboard is now live!

## Quick View Commands (CLI)

If you prefer CLI, use these commands:

### View Lambda Metrics

```bash
# Get Lambda invocation count (last hour)
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value=agenticai-stack-ApiHandler \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Sum

# Get Lambda errors
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Errors \
    --dimensions Name=FunctionName,Value=agenticai-stack-ApiHandler \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Sum
```

### View API Gateway Metrics

```bash
# Get API request count
aws cloudwatch get-metric-statistics \
    --namespace AWS/ApiGateway \
    --metric-name Count \
    --dimensions Name=ApiName,Value=agenticai-api \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Sum
```

### View CloudWatch Logs

```bash
# Tail Lambda logs
aws logs tail /aws/lambda/agenticai-stack-ApiHandler --follow

# Search for errors
aws logs filter-log-events \
    --log-group-name /aws/lambda/agenticai-stack-ApiHandler \
    --filter-pattern "ERROR" \
    --start-time $(($(date +%s) - 3600))000
```

## Set Up Alarms (Optional)

### High Error Rate Alarm

```bash
aws cloudwatch put-metric-alarm \
    --alarm-name agenticai-high-error-rate \
    --alarm-description "Alert when Lambda error rate is high" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 2 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=FunctionName,Value=agenticai-stack-ApiHandler
```

### High Latency Alarm

```bash
aws cloudwatch put-metric-alarm \
    --alarm-name agenticai-high-latency \
    --alarm-description "Alert when Lambda duration is high" \
    --metric-name Duration \
    --namespace AWS/Lambda \
    --statistic Average \
    --period 300 \
    --evaluation-periods 2 \
    --threshold 5000 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=FunctionName,Value=agenticai-stack-ApiHandler
```

## Dashboard URL

After creating, your dashboard will be available at:
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=AgenticAI-Production
```

## What to Monitor

### Normal Operation
- ✅ API Gateway 2XX responses > 95%
- ✅ Lambda errors < 1%
- ✅ Lambda duration < 3000ms average
- ✅ DynamoDB throttles = 0
- ✅ SQS queue depth < 100

### Warning Signs
- ⚠️ 4XX errors increasing (client issues)
- ⚠️ 5XX errors > 1% (server issues)
- ⚠️ Lambda duration increasing (performance degradation)
- ⚠️ SQS queue depth growing (backlog)

### Critical Issues
- 🚨 5XX errors > 5% (major outage)
- 🚨 Lambda errors > 10% (code issues)
- 🚨 DynamoDB throttles (capacity exceeded)
- 🚨 SQS queue depth > 1000 (system overload)
