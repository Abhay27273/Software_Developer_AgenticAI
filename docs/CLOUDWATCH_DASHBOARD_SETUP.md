# CloudWatch Dashboard Setup Guide

## Overview

This guide explains how to set up comprehensive CloudWatch monitoring for the AgenticAI production system. The dashboard provides real-time visibility into Lambda functions, API Gateway, DynamoDB, and SQS metrics.

## Prerequisites

- AWS CLI configured with appropriate credentials
- Python 3.8 or higher
- boto3 library installed (`pip install boto3`)
- AgenticAI stack deployed to AWS
- IAM permissions for CloudWatch dashboard creation

## Required IAM Permissions

Your AWS user/role needs the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutDashboard",
        "cloudwatch:GetDashboard",
        "cloudwatch:ListDashboards",
        "cloudwatch:DeleteDashboards",
        "cloudwatch:GetMetricStatistics",
        "cloudformation:DescribeStackResources"
      ],
      "Resource": "*"
    }
  ]
}
```

## Dashboard Setup

### Step 1: Run the Setup Script

```bash
# Using default settings (us-east-1, agenticai-stack)
python scripts/setup_cloudwatch_dashboard.py

# Or specify custom region and stack name
python scripts/setup_cloudwatch_dashboard.py us-west-2 my-stack-name
```

The script will:
1. Retrieve resource names from your CloudFormation stack
2. Create a CloudWatch dashboard named "AgenticAI-Production"
3. Configure 9 widgets with key metrics
4. Verify the dashboard was created successfully

### Step 2: Verify Dashboard

```bash
# Run the test script to verify dashboard configuration
python scripts/test_cloudwatch_dashboard.py

# Or specify custom region
python scripts/test_cloudwatch_dashboard.py us-west-2
```

The test script validates:
- Dashboard exists
- All 9 widgets are present
- Required metrics are configured
- Metric data can be retrieved
- Widget configuration is correct
- Dashboard layout is proper

### Step 3: View Dashboard

Access your dashboard at:
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=AgenticAI-Production
```

Replace `us-east-1` with your AWS region.

## Dashboard Layout

The dashboard is organized into 4 rows:

### Row 1: Lambda Metrics
- **Lambda Invocations**: Total invocations for all Lambda functions
- **Lambda Errors**: Error counts for all Lambda functions
- **Lambda Duration**: p50 and p95 duration percentiles

### Row 2: API Gateway Metrics
- **API Gateway Requests & Errors**: Total requests, 4XX errors, 5XX errors
- **API Gateway Latency**: p50, p95, p99 latency and integration latency

### Row 3: DynamoDB Metrics
- **DynamoDB Capacity Usage**: Read and write capacity consumption
- **DynamoDB Throttles**: Read and write throttle events

### Row 4: Queue and Concurrency Metrics
- **SQS Queue Metrics**: Message count and oldest message age
- **Lambda Concurrent Executions**: Concurrent execution count per function

## Metrics Reference

### Lambda Metrics

| Metric | Description | Unit | Period |
|--------|-------------|------|--------|
| Invocations | Number of times functions are invoked | Count | 5 min |
| Errors | Number of invocations that result in errors | Count | 5 min |
| Duration | Execution time (p50, p95, p99) | Milliseconds | 5 min |
| ConcurrentExecutions | Number of concurrent executions | Count | 5 min |

### API Gateway Metrics

| Metric | Description | Unit | Period |
|--------|-------------|------|--------|
| Count | Total API requests | Count | 5 min |
| 4XXError | Client-side errors | Count | 5 min |
| 5XXError | Server-side errors | Count | 5 min |
| Latency | End-to-end latency (p50, p95, p99) | Milliseconds | 5 min |
| IntegrationLatency | Backend integration latency | Milliseconds | 5 min |

### DynamoDB Metrics

| Metric | Description | Unit | Period |
|--------|-------------|------|--------|
| ConsumedReadCapacityUnits | Read capacity consumed | Units | 5 min |
| ConsumedWriteCapacityUnits | Write capacity consumed | Units | 5 min |
| ReadThrottleEvents | Read requests throttled | Count | 5 min |
| WriteThrottleEvents | Write requests throttled | Count | 5 min |

### SQS Metrics

| Metric | Description | Unit | Period |
|--------|-------------|------|--------|
| ApproximateNumberOfMessagesVisible | Messages in queue | Count | 5 min |
| ApproximateAgeOfOldestMessage | Age of oldest message | Seconds | 5 min |

## Customization

### Changing Time Range

In the AWS Console:
1. Open the dashboard
2. Use the time range selector in the top right
3. Choose from preset ranges or custom range

### Modifying Widgets

To modify widget configuration:
1. Edit `scripts/setup_cloudwatch_dashboard.py`
2. Update the relevant widget creation method
3. Re-run the setup script

### Adding New Widgets

To add new widgets:
1. Create a new widget method in the setup script
2. Add the widget to the dashboard body in `create_dashboard()`
3. Update the expected widget count in tests

## Troubleshooting

### Dashboard Not Found

**Error**: `ResourceNotFound: Dashboard 'AgenticAI-Production' not found`

**Solution**: Run the setup script to create the dashboard:
```bash
python scripts/setup_cloudwatch_dashboard.py
```

### No Metric Data

**Issue**: Widgets show "No data available"

**Possible Causes**:
1. Stack resources haven't been invoked yet
2. Incorrect resource names
3. Metrics not yet published (wait 5-10 minutes)

**Solution**: 
- Trigger some API requests to generate metrics
- Verify stack name is correct
- Wait for metrics to be published

### Permission Denied

**Error**: `AccessDeniedException: User is not authorized to perform: cloudwatch:PutDashboard`

**Solution**: Add required IAM permissions (see Prerequisites section)

### Stack Resources Not Found

**Warning**: `Could not get stack resources`

**Solution**: 
- Verify stack name is correct
- Ensure CloudFormation stack is deployed
- Check AWS credentials have CloudFormation read permissions

## Monitoring Best Practices

### Regular Review
- Check dashboard daily for anomalies
- Review error rates and latency trends
- Monitor capacity usage to avoid throttling

### Baseline Metrics
- Establish normal operating ranges for each metric
- Document expected values during peak and off-peak hours
- Use baselines to identify unusual patterns

### Alert Thresholds
- Set alarms based on dashboard metrics (see Task 2)
- Use percentiles (p95, p99) for latency alerts
- Monitor error rates as percentages, not absolute counts

### Cost Optimization
- Dashboard itself is free
- Metric storage follows CloudWatch pricing
- Use 5-minute periods to balance detail and cost

## Next Steps

After setting up the dashboard:

1. **Task 2**: Implement error alerting system
   - Create SNS topic for alerts
   - Configure CloudWatch alarms
   - Test alert delivery

2. **Task 3**: Implement performance monitoring
   - Add performance-specific alarms
   - Configure detailed metrics

3. **Regular Monitoring**: 
   - Review dashboard daily
   - Investigate anomalies
   - Adjust thresholds as needed

## Additional Resources

- [AWS CloudWatch Dashboards Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Dashboards.html)
- [CloudWatch Metrics Reference](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/aws-services-cloudwatch-metrics.html)
- [AWS Deployment Guide](./AWS_DEPLOYMENT_GUIDE.md)
- [AWS Operations Runbook](./AWS_OPERATIONS_RUNBOOK.md)

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review AWS CloudWatch documentation
3. Check CloudWatch Logs for detailed error messages
4. Contact your AWS administrator for permission issues
