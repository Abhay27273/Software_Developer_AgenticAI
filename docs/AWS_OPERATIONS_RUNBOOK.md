# AWS Operations Runbook

## Overview

This runbook provides operational procedures for managing the AI-powered Software Development Agentic System deployed on AWS. It covers daily operations, monitoring, incident response, backup/restore procedures, and maintenance tasks.

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Monitoring Procedures](#monitoring-procedures)
3. [Incident Response](#incident-response)
4. [Backup and Restore](#backup-and-restore)
5. [Maintenance Tasks](#maintenance-tasks)
6. [Performance Optimization](#performance-optimization)
7. [Cost Management](#cost-management)
8. [Security Operations](#security-operations)

## Daily Operations

### Morning Health Check

Perform these checks at the start of each day:

**1. Check System Status**
```bash
# Run automated health check
python scripts/verify_deployment.py

# Check API endpoint
curl https://your-api-endpoint.execute-api.us-east-1.amazonaws.com/prod/health
```

**2. Review CloudWatch Dashboard**
- Open AWS Console → CloudWatch → Dashboards → `agenticai-dashboard`
- Verify all metrics are within normal ranges:
  - API Gateway: Request count, error rate, latency
  - Lambda: Invocations, errors, duration, concurrent executions
  - DynamoDB: Read/write capacity, throttled requests
  - SQS: Messages sent/received, queue depth

**3. Check for Alarms**
```bash
# List active alarms
aws cloudwatch describe-alarms \
    --state-value ALARM \
    --query 'MetricAlarms[?Namespace==`AWS/Lambda` || Namespace==`AWS/DynamoDB`].[AlarmName,StateValue,StateReason]' \
    --output table
```

**4. Review Error Logs**
```bash
# Check Lambda errors in last 24 hours
aws logs filter-log-events \
    --log-group-name /aws/lambda/agenticai-stack-ApiHandler-XXXXX \
    --filter-pattern "ERROR" \
    --start-time $(date -u -d '24 hours ago' +%s)000
```

**5. Check Queue Depths**
```bash
# Check all SQS queues
for queue in pm dev qa ops; do
    echo "Queue: agenticai-$queue-queue"
    aws sqs get-queue-attributes \
        --queue-url $(aws sqs get-queue-url --queue-name agenticai-$queue-queue --query 'QueueUrl' --output text) \
        --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible \
        --query 'Attributes' \
        --output table
done
```


### Weekly Tasks

**1. Review Cost and Usage**
```bash
# Run cost monitoring script
python scripts/monitor_cost_limits.py

# Check AWS Cost Explorer
# AWS Console → Billing → Cost Explorer
```

**2. Check Dead Letter Queues**
```bash
# Check DLQ message counts
for queue in pm dev qa ops; do
    echo "DLQ: agenticai-$queue-dlq"
    aws sqs get-queue-attributes \
        --queue-url $(aws sqs get-queue-url --queue-name agenticai-$queue-dlq --query 'QueueUrl' --output text) \
        --attribute-names ApproximateNumberOfMessages
done
```

**3. Review DynamoDB Metrics**
- Check table size growth
- Review read/write capacity usage
- Check for throttled requests

**4. Verify Backups**
```bash
# List DynamoDB backups
aws dynamodb list-backups \
    --table-name agenticai-data \
    --time-range-lower-bound $(date -u -d '7 days ago' +%s) \
    --query 'BackupSummaries[*].[BackupName,BackupCreationDateTime,BackupStatus]' \
    --output table
```

### Monthly Tasks

**1. Security Review**
- Review IAM policies and roles
- Check for unused access keys
- Review CloudTrail logs for suspicious activity
- Update dependencies and patch vulnerabilities

**2. Performance Review**
- Analyze Lambda cold start times
- Review API Gateway latency metrics
- Identify optimization opportunities

**3. Cost Optimization**
- Review free tier usage
- Identify unused resources
- Optimize Lambda memory allocation

**4. Backup Verification**
- Test restore procedure
- Verify backup integrity
- Update disaster recovery documentation

## Monitoring Procedures

### CloudWatch Dashboards

**Primary Dashboard: agenticai-dashboard**

Widgets to monitor:
1. **API Gateway Metrics**
   - Request count (last 24h)
   - 4xx/5xx error rates
   - Latency (p50, p95, p99)

2. **Lambda Metrics**
   - Invocation count by function
   - Error rate by function
   - Duration by function
   - Concurrent executions
   - Throttles

3. **DynamoDB Metrics**
   - Read/Write capacity units consumed
   - Throttled requests
   - Table size
   - Item count

4. **SQS Metrics**
   - Messages sent/received
   - Queue depth
   - Age of oldest message
   - Dead letter queue messages

5. **Cost Tracking**
   - Estimated monthly cost
   - Free tier usage percentage

### Key Metrics and Thresholds

| Metric | Normal Range | Warning Threshold | Critical Threshold |
|--------|--------------|-------------------|-------------------|
| API Gateway 5xx Error Rate | < 0.1% | > 1% | > 5% |
| Lambda Error Rate | < 0.5% | > 2% | > 5% |
| Lambda Duration | < 50% timeout | > 70% timeout | > 80% timeout |
| DynamoDB Throttled Requests | 0 | > 5/5min | > 10/5min |
| SQS Queue Depth | < 100 | > 500 | > 1000 |
| DLQ Messages | 0 | > 0 | > 10 |
| Lambda Concurrent Executions | < 5 | > 8 | > 10 |
| Free Tier Usage | < 70% | > 80% | > 90% |

### Setting Up Custom Metrics

```python
# Example: Track custom business metrics
import boto3

cloudwatch = boto3.client('cloudwatch')

def track_project_creation():
    cloudwatch.put_metric_data(
        Namespace='AgenticAI/Business',
        MetricData=[{
            'MetricName': 'ProjectsCreated',
            'Value': 1,
            'Unit': 'Count',
            'Timestamp': datetime.utcnow()
        }]
    )
```

### Log Analysis

**Search for Errors**
```bash
# Search Lambda logs for errors
aws logs filter-log-events \
    --log-group-name /aws/lambda/agenticai-stack-DevAgentWorker-XXXXX \
    --filter-pattern "ERROR" \
    --start-time $(date -u -d '1 hour ago' +%s)000 \
    | jq '.events[].message'
```

**Search for Specific Patterns**
```bash
# Search for timeout errors
aws logs filter-log-events \
    --log-group-name /aws/lambda/agenticai-stack-DevAgentWorker-XXXXX \
    --filter-pattern "Task timed out" \
    --start-time $(date -u -d '24 hours ago' +%s)000
```

**Export Logs for Analysis**
```bash
# Export logs to S3 for detailed analysis
aws logs create-export-task \
    --log-group-name /aws/lambda/agenticai-stack-ApiHandler-XXXXX \
    --from $(date -u -d '7 days ago' +%s)000 \
    --to $(date -u +%s)000 \
    --destination agenticai-logs-archive \
    --destination-prefix lambda-logs/
```

## Incident Response

### Incident Severity Levels

**P1 - Critical**: System down, no workaround
**P2 - High**: Major functionality impaired
**P3 - Medium**: Minor functionality impaired, workaround available
**P4 - Low**: Cosmetic issue, no impact on functionality

### Incident Response Playbook

#### P1: API Gateway Returning 5xx Errors

**Symptoms**:
- API health check failing
- High 5xx error rate in CloudWatch
- Users unable to access system

**Investigation**:
```bash
# 1. Check API Gateway status
aws apigateway get-rest-apis

# 2. Check Lambda function status
aws lambda list-functions \
    --query 'Functions[?starts_with(FunctionName, `agenticai`)].State'

# 3. Check recent Lambda errors
aws logs tail /aws/lambda/agenticai-stack-ApiHandler-XXXXX --since 10m
```

**Resolution**:
```bash
# Option 1: Rollback to previous Lambda version
aws lambda update-alias \
    --function-name agenticai-stack-ApiHandler-XXXXX \
    --name live \
    --function-version <previous-version>

# Option 2: Redeploy from last known good commit
git checkout <last-good-commit>
sam build && sam deploy

# Option 3: Increase Lambda timeout/memory
# Update template.yaml and redeploy
```

**Post-Incident**:
- Document root cause
- Update monitoring to catch earlier
- Add preventive measures

#### P1: DynamoDB Throttling

**Symptoms**:
- `ProvisionedThroughputExceededException` errors
- Slow API responses
- Failed Lambda invocations

**Investigation**:
```bash
# Check DynamoDB metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/DynamoDB \
    --metric-name UserErrors \
    --dimensions Name=TableName,Value=agenticai-data \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Sum
```

**Resolution**:
```bash
# Option 1: Switch to on-demand billing (if not already)
aws dynamodb update-table \
    --table-name agenticai-data \
    --billing-mode PAY_PER_REQUEST

# Option 2: Implement exponential backoff in code
# (Should already be implemented)

# Option 3: Reduce request rate
# Temporarily disable non-critical features
```

#### P2: Lambda Function Timeout

**Symptoms**:
- `Task timed out after X seconds` errors
- Incomplete operations
- SQS messages returning to queue

**Investigation**:
```bash
# Check Lambda duration metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Duration \
    --dimensions Name=FunctionName,Value=agenticai-stack-DevAgentWorker-XXXXX \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average,Maximum

# Check X-Ray traces for bottlenecks
aws xray get-trace-summaries \
    --start-time $(date -u -d '1 hour ago' +%s) \
    --end-time $(date -u +%s) \
    --filter-expression 'service("agenticai-stack-DevAgentWorker")'
```

**Resolution**:
```bash
# Increase Lambda timeout
aws lambda update-function-configuration \
    --function-name agenticai-stack-DevAgentWorker-XXXXX \
    --timeout 900

# Increase Lambda memory (improves CPU)
aws lambda update-function-configuration \
    --function-name agenticai-stack-DevAgentWorker-XXXXX \
    --memory-size 3008
```

#### P2: High SQS Queue Depth

**Symptoms**:
- Messages accumulating in queue
- Delayed processing
- CloudWatch alarm triggered

**Investigation**:
```bash
# Check queue attributes
aws sqs get-queue-attributes \
    --queue-url YOUR_QUEUE_URL \
    --attribute-names All

# Check Lambda concurrency
aws lambda get-function-concurrency \
    --function-name agenticai-stack-DevAgentWorker-XXXXX
```

**Resolution**:
```bash
# Option 1: Increase Lambda concurrency
aws lambda put-function-concurrency \
    --function-name agenticai-stack-DevAgentWorker-XXXXX \
    --reserved-concurrent-executions 5

# Option 2: Increase batch size
aws lambda update-event-source-mapping \
    --uuid <mapping-uuid> \
    --batch-size 5

# Option 3: Purge queue if messages are stale
aws sqs purge-queue --queue-url YOUR_QUEUE_URL
```

#### P3: WebSocket Connection Issues

**Symptoms**:
- Clients unable to connect
- Frequent disconnections
- No real-time updates

**Investigation**:
```bash
# Check ECS service status
aws ecs describe-services \
    --cluster agenticai-cluster \
    --services agenticai-websocket

# Check ECS task logs
aws logs tail /ecs/agenticai-websocket --follow

# Check security group rules
aws ec2 describe-security-groups \
    --group-ids <security-group-id>
```

**Resolution**:
```bash
# Restart ECS service
aws ecs update-service \
    --cluster agenticai-cluster \
    --service agenticai-websocket \
    --force-new-deployment

# Scale up tasks if needed
aws ecs update-service \
    --cluster agenticai-cluster \
    --service agenticai-websocket \
    --desired-count 2
```

### Escalation Procedures

**Level 1**: On-call engineer
- Investigate and resolve using runbook
- Duration: 30 minutes

**Level 2**: Senior engineer
- Complex issues requiring deep system knowledge
- Duration: 1 hour

**Level 3**: AWS Support
- Infrastructure issues beyond application control
- Open support ticket via AWS Console

### Communication Templates

**Incident Notification**:
```
Subject: [P1] API Gateway Returning 5xx Errors

Status: Investigating
Impact: Users unable to access system
Start Time: 2025-11-25 10:30 UTC
ETA: 30 minutes

We are investigating high error rates on the API Gateway.
Updates will be provided every 15 minutes.
```

**Resolution Notification**:
```
Subject: [RESOLVED] API Gateway Returning 5xx Errors

Status: Resolved
Resolution: Rolled back to previous Lambda version
Duration: 25 minutes
Root Cause: Deployment introduced null pointer exception

Post-mortem will be published within 24 hours.
```

## Backup and Restore

### DynamoDB Backup Procedures

**On-Demand Backup**
```bash
# Create backup before major changes
aws dynamodb create-backup \
    --table-name agenticai-data \
    --backup-name agenticai-data-$(date +%Y%m%d-%H%M%S)

# List backups
aws dynamodb list-backups \
    --table-name agenticai-data

# Describe backup
aws dynamodb describe-backup \
    --backup-arn <backup-arn>
```

**Automated Backup Schedule**
```bash
# Point-in-Time Recovery is already enabled
# Verify PITR status
aws dynamodb describe-continuous-backups \
    --table-name agenticai-data
```

**Export to S3 (Weekly)**
```bash
# Export table to S3 for long-term archival
aws dynamodb export-table-to-point-in-time \
    --table-arn arn:aws:dynamodb:us-east-1:ACCOUNT_ID:table/agenticai-data \
    --s3-bucket agenticai-backups \
    --s3-prefix dynamodb-exports/$(date +%Y%m%d) \
    --export-format DYNAMODB_JSON
```

### DynamoDB Restore Procedures

**Restore from Backup**
```bash
# Restore to new table
aws dynamodb restore-table-from-backup \
    --target-table-name agenticai-data-restored \
    --backup-arn <backup-arn>

# Wait for restore to complete
aws dynamodb wait table-exists \
    --table-name agenticai-data-restored

# Verify data
aws dynamodb scan \
    --table-name agenticai-data-restored \
    --max-items 10

# Switch application to use restored table
# Update Lambda environment variables
aws lambda update-function-configuration \
    --function-name agenticai-stack-ApiHandler-XXXXX \
    --environment Variables={DYNAMODB_TABLE_NAME=agenticai-data-restored}
```

**Restore from Point-in-Time**
```bash
# Restore to specific timestamp (within last 35 days)
aws dynamodb restore-table-to-point-in-time \
    --source-table-name agenticai-data \
    --target-table-name agenticai-data-restored \
    --restore-date-time $(date -u -d '2 hours ago' +%Y-%m-%dT%H:%M:%S)
```

### S3 Backup Procedures

**Enable Versioning** (Already configured)
```bash
# Verify versioning is enabled
aws s3api get-bucket-versioning \
    --bucket agenticai-generated-code
```

**Restore Deleted File**
```bash
# List versions
aws s3api list-object-versions \
    --bucket agenticai-generated-code \
    --prefix projects/proj_123/

# Restore specific version
aws s3api copy-object \
    --bucket agenticai-generated-code \
    --copy-source agenticai-generated-code/projects/proj_123/main.py?versionId=VERSION_ID \
    --key projects/proj_123/main.py
```

**Cross-Region Replication** (Optional, costs extra)
```bash
# Set up replication to backup region
aws s3api put-bucket-replication \
    --bucket agenticai-generated-code \
    --replication-configuration file://replication-config.json
```

### Lambda Function Backup

**Version Control** (Primary backup method)
```bash
# All Lambda code is in Git repository
# Tag releases for easy rollback
git tag -a v1.0.0 -m "Production release 1.0.0"
git push origin v1.0.0

# Rollback to previous version
git checkout v1.0.0
sam build && sam deploy
```

**Export Function Code**
```bash
# Download function code
aws lambda get-function \
    --function-name agenticai-stack-ApiHandler-XXXXX \
    --query 'Code.Location' \
    --output text | xargs curl -o function-backup.zip
```

### Parameter Store Backup

**Export Parameters**
```bash
# Export all parameters
aws ssm get-parameters-by-path \
    --path /agenticai \
    --with-decryption \
    --recursive \
    --query 'Parameters[*].[Name,Value]' \
    --output json > parameter-store-backup.json

# Store securely (encrypted)
gpg --encrypt --recipient your-email@example.com parameter-store-backup.json
```

**Restore Parameters**
```bash
# Restore from backup
cat parameter-store-backup.json | jq -r '.[] | @tsv' | while IFS=$'\t' read -r name value; do
    aws ssm put-parameter \
        --name "$name" \
        --value "$value" \
        --type SecureString \
        --overwrite
done
```

### Disaster Recovery Testing

**Quarterly DR Test**
1. Create test AWS account
2. Deploy from scratch using deployment guide
3. Restore data from backups
4. Verify functionality
5. Document any issues
6. Update DR procedures

## Maintenance Tasks

### Lambda Function Updates

**Deploy New Version**
```bash
# Standard deployment
git pull origin main
sam build && sam deploy

# Deploy with alias for gradual rollout
sam deploy --parameter-overrides DeploymentPreference=Linear10PercentEvery1Minute
```

**Rollback**
```bash
# Rollback to previous version
aws lambda update-alias \
    --function-name agenticai-stack-DevAgentWorker-XXXXX \
    --name live \
    --function-version <previous-version>
```

### Dependency Updates

**Update Python Dependencies**
```bash
# Update requirements.txt
pip list --outdated
pip install --upgrade <package-name>
pip freeze > requirements.txt

# Test locally
pytest tests/

# Deploy
sam build && sam deploy
```

**Security Patches**
```bash
# Check for vulnerabilities
pip install safety
safety check

# Update vulnerable packages
pip install --upgrade <vulnerable-package>
```

### Log Retention Management

**Adjust Log Retention**
```bash
# Set retention to 7 days (free tier friendly)
for log_group in $(aws logs describe-log-groups --query 'logGroups[?starts_with(logGroupName, `/aws/lambda/agenticai`)].logGroupName' --output text); do
    aws logs put-retention-policy \
        --log-group-name $log_group \
        --retention-in-days 7
done
```

### Database Maintenance

**Analyze Table Usage**
```bash
# Get table statistics
aws dynamodb describe-table \
    --table-name agenticai-data \
    --query 'Table.[ItemCount,TableSizeBytes,CreationDateTime]'

# Check for hot partitions
aws cloudwatch get-metric-statistics \
    --namespace AWS/DynamoDB \
    --metric-name ConsumedReadCapacityUnits \
    --dimensions Name=TableName,Value=agenticai-data \
    --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Sum
```

**Clean Up Old Data**
```bash
# Delete old projects (implement TTL)
aws dynamodb update-time-to-live \
    --table-name agenticai-data \
    --time-to-live-specification "Enabled=true, AttributeName=ttl"
```

## Performance Optimization

### Lambda Optimization

**Analyze Cold Starts**
```bash
# Query X-Ray for cold start traces
aws xray get-trace-summaries \
    --start-time $(date -u -d '24 hours ago' +%s) \
    --end-time $(date -u +%s) \
    --filter-expression 'annotation.coldStart = true'
```

**Optimize Memory Allocation**
```bash
# Test different memory sizes
for memory in 512 1024 1536 2048; do
    aws lambda update-function-configuration \
        --function-name agenticai-stack-DevAgentWorker-XXXXX \
        --memory-size $memory
    
    # Run load test
    # Measure duration and cost
done
```

### DynamoDB Optimization

**Analyze Access Patterns**
```bash
# Enable DynamoDB Contributor Insights
aws dynamodb update-contributor-insights \
    --table-name agenticai-data \
    --contributor-insights-action ENABLE

# View top accessed items
aws dynamodb describe-contributor-insights \
    --table-name agenticai-data
```

**Optimize Queries**
- Use GSI for common query patterns
- Implement caching for frequently accessed data
- Use batch operations to reduce request count

## Cost Management

### Monitor Free Tier Usage

**Check Current Usage**
```bash
# Run cost monitoring script
python scripts/monitor_cost_limits.py
```

**Set Up Alerts**
```bash
# Create budget alert at 80% of free tier
aws budgets create-budget \
    --account-id $(aws sts get-caller-identity --query Account --output text) \
    --budget file://budget-config.json
```

### Cost Optimization Strategies

**1. Lambda**
- Reduce memory if not needed
- Optimize code to reduce duration
- Use reserved concurrency to limit costs

**2. DynamoDB**
- Use on-demand billing for variable workloads
- Implement caching to reduce reads
- Archive old data to S3

**3. S3**
- Enable lifecycle policies
- Use Intelligent-Tiering
- Compress files before upload

**4. CloudWatch**
- Reduce log retention period
- Filter logs before sending to CloudWatch
- Use metric filters instead of custom metrics

## Security Operations

### Security Monitoring

**Review CloudTrail Logs**
```bash
# Check for suspicious API calls
aws cloudtrail lookup-events \
    --lookup-attributes AttributeKey=EventName,AttributeValue=DeleteTable \
    --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S)
```

**Check IAM Access**
```bash
# List IAM users and last access
aws iam get-credential-report

# Check for unused access keys
aws iam list-access-keys --user-name agenticai-deployer
```

### Security Patching

**Update Lambda Runtimes**
```bash
# Check for deprecated runtimes
aws lambda list-functions \
    --query 'Functions[?Runtime==`python3.9`].[FunctionName,Runtime]'

# Update runtime in template.yaml
# Runtime: python3.11
sam build && sam deploy
```

**Rotate Secrets**
```bash
# Rotate Gemini API key
aws ssm put-parameter \
    --name "/agenticai/gemini-api-key" \
    --value "NEW_API_KEY" \
    --type "SecureString" \
    --overwrite

# Restart Lambda functions to pick up new value
aws lambda update-function-configuration \
    --function-name agenticai-stack-ApiHandler-XXXXX \
    --environment Variables={FORCE_REFRESH=true}
```

## Contact Information

**On-Call Engineer**: [Your contact info]
**Escalation**: [Senior engineer contact]
**AWS Support**: https://console.aws.amazon.com/support/

## Additional Resources

- [AWS Deployment Guide](AWS_DEPLOYMENT_GUIDE.md)
- [API Reference](AWS_API_REFERENCE.md)
- [CloudWatch Dashboard](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=agenticai-dashboard)
- [AWS Status Page](https://status.aws.amazon.com/)
