# WebSocket Handler Deployment Checklist

Use this checklist to ensure a successful deployment of the WebSocket handler to AWS ECS Fargate.

## Pre-Deployment

### Infrastructure Setup

- [ ] AWS account created and configured
- [ ] AWS CLI installed and configured (`aws configure`)
- [ ] SAM CLI installed (`pip install aws-sam-cli`)
- [ ] Docker installed and running
- [ ] Git repository set up with GitHub Actions

### CloudFormation Stack

- [ ] Main CloudFormation stack deployed (`sam deploy`)
- [ ] DynamoDB table created
- [ ] SQS queues created (PM, Dev, QA, Ops)
- [ ] VPC and networking resources created
- [ ] ECS cluster created
- [ ] ECR repository created
- [ ] Security groups configured

### Environment Variables

- [ ] `AWS_REGION` set (default: us-east-1)
- [ ] `DYNAMODB_TABLE_NAME` available from stack outputs
- [ ] `SQS_QUEUE_URL_PM` available from stack outputs
- [ ] `SQS_QUEUE_URL_DEV` available from stack outputs
- [ ] `SQS_QUEUE_URL_QA` available from stack outputs
- [ ] `SQS_QUEUE_URL_OPS` available from stack outputs

### IAM Permissions

- [ ] ECS task execution role created
- [ ] ECS task role created with SQS and DynamoDB permissions
- [ ] ECR push/pull permissions configured
- [ ] CloudWatch Logs permissions configured

## Local Testing

### Unit Tests

- [ ] Python 3.11 installed
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Unit tests pass (`pytest test_server.py -v`)
- [ ] Code coverage acceptable (>80%)

### Docker Build

- [ ] Docker image builds successfully (`docker build -t test .`)
- [ ] Docker image runs locally (`docker run -p 8080:8080 test`)
- [ ] Health check passes
- [ ] No security vulnerabilities in image

### Integration Tests

- [ ] Server starts without errors
- [ ] WebSocket connections accepted
- [ ] Ping/pong works
- [ ] Subscribe/unsubscribe works
- [ ] Message forwarding to SQS works (if AWS configured)
- [ ] Integration tests pass (`python integration_test.py ws://localhost:8080`)

## Deployment

### Build and Push

- [ ] ECR login successful (`aws ecr get-login-password | docker login ...`)
- [ ] Docker image built with production tag
- [ ] Image pushed to ECR successfully
- [ ] Image tagged with both `latest` and timestamp

### ECS Service

- [ ] Task definition created/updated
- [ ] Service created/updated
- [ ] Desired count set to 1 (or more)
- [ ] Service deployment successful
- [ ] Tasks running and healthy
- [ ] Load balancer health checks passing

### Verification

- [ ] WebSocket endpoint accessible
- [ ] Can connect via WebSocket client
- [ ] Messages forwarded to SQS correctly
- [ ] CloudWatch logs showing activity
- [ ] No errors in logs
- [ ] Integration tests pass against production endpoint

## Post-Deployment

### Monitoring

- [ ] CloudWatch log group created (`/ecs/agenticai-websocket-{env}`)
- [ ] Logs streaming correctly
- [ ] CloudWatch alarms configured (optional)
- [ ] Metrics dashboard created (optional)

### Security

- [ ] Security group rules reviewed
- [ ] IAM roles follow least privilege
- [ ] No secrets in environment variables
- [ ] SSL/TLS configured (if using HTTPS/WSS)
- [ ] CORS policies configured

### Documentation

- [ ] Deployment documented
- [ ] WebSocket endpoint URL shared with team
- [ ] Monitoring procedures documented
- [ ] Incident response plan created

### Performance

- [ ] Connection capacity tested
- [ ] Latency acceptable (<100ms)
- [ ] Memory usage within limits
- [ ] CPU usage within limits
- [ ] Auto-scaling configured (if needed)

## Rollback Plan

In case of deployment failure:

- [ ] Previous Docker image tag identified
- [ ] Rollback command prepared:
  ```bash
  aws ecs update-service \
    --cluster agenticai-cluster-prod \
    --service agenticai-websocket-prod \
    --task-definition agenticai-websocket-prod:PREVIOUS_VERSION
  ```
- [ ] Team notified of rollback procedure
- [ ] Post-mortem scheduled

## Maintenance

### Regular Tasks

- [ ] Review CloudWatch logs weekly
- [ ] Check for security updates monthly
- [ ] Update dependencies quarterly
- [ ] Review and optimize costs monthly
- [ ] Test disaster recovery procedures quarterly

### Scaling Considerations

- [ ] Monitor connection count
- [ ] Plan for horizontal scaling if needed
- [ ] Consider multi-region deployment for HA
- [ ] Review and adjust resource limits

## Troubleshooting

### Common Issues

- [ ] Connection refused → Check security group and ALB
- [ ] High latency → Check task resources and network
- [ ] Memory issues → Increase task memory allocation
- [ ] SQS errors → Verify IAM permissions and queue URLs
- [ ] Health check failures → Review health check configuration

### Debug Commands

```bash
# View service status
aws ecs describe-services --cluster CLUSTER --services SERVICE

# View task logs
aws logs tail /ecs/agenticai-websocket-prod --follow

# Check task health
aws ecs describe-tasks --cluster CLUSTER --tasks TASK_ARN

# Force new deployment
aws ecs update-service --cluster CLUSTER --service SERVICE --force-new-deployment
```

## Sign-Off

- [ ] Development team approves
- [ ] QA team approves
- [ ] Operations team approves
- [ ] Security team approves (if required)
- [ ] Deployment documented in change log

---

**Deployment Date:** _______________

**Deployed By:** _______________

**Version/Tag:** _______________

**Notes:**
