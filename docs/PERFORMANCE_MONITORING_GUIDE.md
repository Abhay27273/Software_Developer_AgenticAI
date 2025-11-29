# Performance Monitoring Guide

## Overview

This guide explains how to use the performance monitoring features implemented for the AgenticAI system.

## Quick Start

### Deploy Performance Monitoring

```bash
# 1. Create performance alarms
python scripts/setup_performance_alarms.py

# 2. Update dashboard with performance widgets
python scripts/setup_cloudwatch_dashboard.py

# 3. Verify deployment
python scripts/test_alerting.py
```

## Performance Alarms

### Lambda Duration Alarms

**Purpose**: Alert when Lambda functions take longer than 10 seconds to execute

**Alarms Created**:
- `agenticai-apihandlerfunction-duration-prod`
- `agenticai-pmagentfunction-duration-prod`
- `agenticai-devagentfunction-duration-prod`
- `agenticai-qaagentfunction-duration-prod`
- `agenticai-opsagentfunction-duration-prod`

**Threshold**: 10,000 milliseconds (10 seconds)
**Evaluation**: 1 minute period, 1 evaluation period
**Action**: SNS notification to agenticai-alerts

**When It Triggers**:
- Function execution exceeds 10 seconds
- Potential timeout issues
- Performance degradation

**Response Actions**:
1. Check CloudWatch Logs for the specific function
2. Review function memory allocation
3. Analyze code for performance bottlenecks
4. Check external API/database latency
5. Consider increasing timeout or optimizing code

### API Gateway Latency Alarm

**Purpose**: Alert when API response times are consistently slow

**Alarm Name**: `agenticai-api-gateway-latency-prod`

**Threshold**: 3,000 milliseconds (3 seconds)
**Evaluation**: 1 minute period, 5 evaluation periods (5 consecutive minutes)
**Action**: SNS notification to agenticai-alerts

**When It Triggers**:
- API latency exceeds 3 seconds for 5 consecutive minutes
- Sustained performance issues
- System-wide slowdown

**Response Actions**:
1. Check API Gateway metrics in dashboard
2. Review Lambda function performance
3. Check DynamoDB throttling
4. Verify SQS queue depth
5. Investigate external dependencies
6. Consider scaling resources

## Dashboard Widgets

### Lambda Cold Start Metrics

**Location**: Row 3, Left Widget

**What It Shows**:
- Maximum duration for each Lambda function
- Indicates cold start frequency and impact
- 1-minute granularity for real-time monitoring

**How to Use**:
- Spikes indicate cold starts
- Consistent high values suggest optimization needed
- Compare across functions to identify issues

**Optimization Tips**:
- Increase memory allocation (faster cold starts)
- Use provisioned concurrency for critical functions
- Optimize initialization code
- Reduce package size
- Keep functions warm with scheduled invocations

### API Response Time Percentiles

**Location**: Row 3, Right Widget

**What It Shows**:
- p50 (median): 50% of requests are faster than this
- p95: 95% of requests are faster than this
- p99: 99% of requests are faster than this
- Integration p95: Backend integration latency

**How to Use**:
- p50 shows typical user experience
- p95 shows experience for most users
- p99 shows worst-case scenarios
- Large gaps between percentiles indicate inconsistent performance

**Performance Targets**:
- p50 < 500ms: Excellent
- p95 < 1000ms: Good
- p99 < 3000ms: Acceptable
- Above 3000ms: Needs attention

## Monitoring Best Practices

### Daily Checks

1. **Review Dashboard**:
   - Check for any red threshold violations
   - Look for unusual patterns or spikes
   - Verify all metrics are reporting data

2. **Check Alarm Status**:
   - Navigate to CloudWatch > Alarms
   - Ensure all alarms are in OK state
   - Investigate any ALARM states

3. **Review Performance Trends**:
   - Compare current performance to baseline
   - Identify gradual degradation
   - Plan capacity adjustments

### Weekly Analysis

1. **Percentile Analysis**:
   - Review p95 and p99 trends
   - Identify performance regressions
   - Correlate with deployment changes

2. **Cold Start Analysis**:
   - Calculate cold start frequency
   - Measure cold start impact
   - Identify optimization opportunities

3. **Capacity Planning**:
   - Review concurrent execution trends
   - Check for approaching limits
   - Plan scaling adjustments

### Alert Response

**When You Receive a Performance Alert**:

1. **Acknowledge**: Confirm receipt and begin investigation
2. **Assess Impact**: Check dashboard for scope and severity
3. **Investigate**: Review logs and metrics for root cause
4. **Mitigate**: Take immediate action to restore performance
5. **Document**: Record incident details and resolution
6. **Follow-up**: Implement preventive measures

## Performance Optimization

### Lambda Optimization

**Memory Allocation**:
- Start with 512MB, adjust based on metrics
- More memory = faster CPU = faster cold starts
- Monitor cost vs. performance tradeoff

**Code Optimization**:
- Minimize initialization code
- Use connection pooling
- Cache frequently accessed data
- Optimize dependencies

**Concurrency**:
- Set reserved concurrency for critical functions
- Use provisioned concurrency for predictable load
- Monitor throttling metrics

### API Gateway Optimization

**Caching**:
- Enable API Gateway caching for read-heavy endpoints
- Set appropriate TTL values
- Monitor cache hit rates

**Request Validation**:
- Validate requests at API Gateway level
- Reduce Lambda invocations for invalid requests
- Use request/response models

**Throttling**:
- Set appropriate rate limits
- Protect backend from overload
- Monitor throttled requests

## Troubleshooting

### High Lambda Duration

**Symptoms**:
- Duration alarm triggered
- Slow API responses
- Timeout errors

**Diagnosis**:
```bash
# Check CloudWatch Logs
aws logs tail /aws/lambda/function-name --follow

# Check function metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=function-name \
  --start-time 2025-11-29T00:00:00Z \
  --end-time 2025-11-29T23:59:59Z \
  --period 300 \
  --statistics Average,Maximum
```

**Solutions**:
- Increase memory allocation
- Optimize code performance
- Reduce external API calls
- Use async processing where possible

### High API Latency

**Symptoms**:
- API latency alarm triggered
- Slow user experience
- Increased error rates

**Diagnosis**:
```bash
# Check API Gateway metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Latency \
  --dimensions Name=ApiName,Value=agenticai-api \
  --start-time 2025-11-29T00:00:00Z \
  --end-time 2025-11-29T23:59:59Z \
  --period 300 \
  --statistics p50,p95,p99
```

**Solutions**:
- Check Lambda performance
- Review DynamoDB throttling
- Verify SQS queue depth
- Enable API Gateway caching
- Scale backend resources

### Frequent Cold Starts

**Symptoms**:
- High maximum duration spikes
- Inconsistent response times
- User complaints about slow initial requests

**Diagnosis**:
- Review cold start metrics widget
- Check concurrent execution patterns
- Analyze invocation frequency

**Solutions**:
- Increase memory allocation
- Use provisioned concurrency
- Implement keep-warm strategy
- Optimize initialization code
- Reduce package size

## Metrics Reference

### Lambda Metrics

| Metric | Description | Good Value | Alert Threshold |
|--------|-------------|------------|-----------------|
| Duration (Average) | Average execution time | < 1000ms | > 10000ms |
| Duration (Maximum) | Cold start indicator | < 3000ms | > 10000ms |
| Errors | Failed invocations | 0 | > 5% |
| Throttles | Rate limited invocations | 0 | > 0 |
| Concurrent Executions | Simultaneous invocations | < 100 | > 900 |

### API Gateway Metrics

| Metric | Description | Good Value | Alert Threshold |
|--------|-------------|------------|-----------------|
| Latency (p50) | Median response time | < 500ms | - |
| Latency (p95) | 95th percentile | < 1000ms | - |
| Latency (p99) | 99th percentile | < 2000ms | - |
| Latency (Average) | Average response time | < 1000ms | > 3000ms (5 min) |
| 5XXError | Server errors | 0 | > 10 (5 min) |

## AWS Console Navigation

### View Performance Alarms
1. Open AWS Console
2. Navigate to CloudWatch
3. Click "Alarms" > "All alarms"
4. Filter by "agenticai-" prefix
5. Look for "-duration-" and "-latency-" alarms

### View Performance Dashboard
1. Open AWS Console
2. Navigate to CloudWatch
3. Click "Dashboards"
4. Select "AgenticAI-Production"
5. Scroll to Row 3 for performance widgets

### View Alarm History
1. Navigate to CloudWatch > Alarms
2. Click on specific alarm
3. View "History" tab
4. Review state changes and reasons

## Integration with Other Monitoring

### Error Alerting
- Performance alarms complement error alarms
- Both send to same SNS topic
- Coordinate response for related issues

### Cost Monitoring
- High duration = higher costs
- Monitor cost impact of performance issues
- Balance performance vs. cost

### Health Checks
- Canaries test end-to-end performance
- Complement metric-based monitoring
- Provide user perspective

## Additional Resources

- [AWS Lambda Performance Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [API Gateway Performance](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html)
- [CloudWatch Metrics](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/working_with_metrics.html)

## Support

For issues or questions:
1. Check CloudWatch Logs for detailed error messages
2. Review this guide for troubleshooting steps
3. Consult AWS Operations Runbook
4. Contact system administrator

---

**Last Updated**: November 29, 2025
**Version**: 1.0
**Related**: AWS_OPERATIONS_RUNBOOK.md, CLOUDWATCH_DASHBOARD_SETUP.md
