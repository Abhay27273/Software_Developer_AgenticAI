# CloudWatch Monitoring Scripts

## Overview

This directory contains scripts for setting up and testing CloudWatch monitoring infrastructure for the AgenticAI production system.

## Scripts

### 1. setup_cloudwatch_dashboard.py

Creates a comprehensive CloudWatch dashboard with metrics for Lambda, API Gateway, DynamoDB, and SQS.

**Usage**:
```bash
# Default (us-east-1, agenticai-stack)
python scripts/setup_cloudwatch_dashboard.py

# Custom region and stack
python scripts/setup_cloudwatch_dashboard.py us-west-2 my-stack-name
```

**What it does**:
- Retrieves resource names from CloudFormation stack
- Creates 9 dashboard widgets with key metrics
- Configures 5-minute granularity for all metrics
- Verifies dashboard creation

**Output**:
- Dashboard name: `AgenticAI-Production`
- Console URL for viewing dashboard
- Verification status

### 2. test_cloudwatch_dashboard.py

Tests that the CloudWatch dashboard is configured correctly and can retrieve metrics.

**Usage**:
```bash
# Default (us-east-1)
python scripts/test_cloudwatch_dashboard.py

# Custom region
python scripts/test_cloudwatch_dashboard.py us-west-2
```

**What it tests**:
- Dashboard exists
- All 9 widgets are present
- Required metrics are configured
- Metric data can be retrieved
- Widget configuration is correct
- Dashboard layout is proper

**Exit codes**:
- 0: All tests passed
- 1: One or more tests failed

## Quick Start

### Option 1: Automated Setup (Recommended)

**Windows (PowerShell)**:
```powershell
.\scripts\setup_monitoring.ps1
```

**Linux/Mac (Bash)**:
```bash
./scripts/setup_monitoring.sh
```

The automated script will:
- Check prerequisites (Python, boto3, AWS credentials)
- Create the CloudWatch dashboard
- Verify the configuration
- Provide next steps

### Option 2: Manual Setup

```bash
# 1. Set up the dashboard
python scripts/setup_cloudwatch_dashboard.py

# 2. Verify it works
python scripts/test_cloudwatch_dashboard.py

# 3. View in AWS Console
# URL will be printed by the scripts
```

## Requirements

- Python 3.8+
- boto3 library
- AWS credentials configured
- CloudFormation stack deployed
- IAM permissions for CloudWatch

## IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutDashboard",
        "cloudwatch:GetDashboard",
        "cloudwatch:GetMetricStatistics",
        "cloudformation:DescribeStackResources"
      ],
      "Resource": "*"
    }
  ]
}
```

## Dashboard Metrics

### Lambda Metrics
- Invocations (all functions)
- Errors (all functions)
- Duration p50, p95 (all functions)
- Concurrent Executions (all functions)

### API Gateway Metrics
- Total Requests
- 4XX Errors
- 5XX Errors
- Latency p50, p95, p99
- Integration Latency

### DynamoDB Metrics
- Read Capacity Units
- Write Capacity Units
- Read Throttles
- Write Throttles

### SQS Metrics
- Messages in Queue
- Oldest Message Age

## Troubleshooting

### Dashboard Not Created

**Error**: Script completes but dashboard not visible

**Solution**:
1. Check AWS region matches your stack
2. Verify IAM permissions
3. Check CloudWatch console for error messages

### No Metric Data

**Issue**: Dashboard shows "No data available"

**Solution**:
1. Wait 5-10 minutes for metrics to populate
2. Trigger some API requests to generate metrics
3. Verify resource names are correct

### Stack Resources Not Found

**Warning**: "Could not get stack resources"

**Solution**:
1. Verify stack name is correct
2. Ensure stack is fully deployed
3. Check CloudFormation permissions

## Next Steps

After setting up the dashboard:

1. **Task 2**: Set up error alerting
   - Create SNS topic
   - Configure CloudWatch alarms
   - Test alert delivery

2. **Regular Monitoring**:
   - Review dashboard daily
   - Set up automated alerts
   - Document baseline metrics

3. **Customization**:
   - Add custom metrics
   - Adjust time ranges
   - Create additional dashboards

## Related Documentation

- [CloudWatch Dashboard Setup Guide](../docs/CLOUDWATCH_DASHBOARD_SETUP.md)
- [AWS Deployment Guide](../docs/AWS_DEPLOYMENT_GUIDE.md)
- [AWS Operations Runbook](../docs/AWS_OPERATIONS_RUNBOOK.md)
- [Production Hardening Tasks](../.kiro/specs/production-hardening/tasks.md)
