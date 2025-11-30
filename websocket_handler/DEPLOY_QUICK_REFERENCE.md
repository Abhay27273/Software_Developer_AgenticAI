# WebSocket ECS Deployment - Quick Reference

## One-Command Deployment

```powershell
cd websocket_handler
.\deploy-ecs.ps1
```

## Essential Commands

### Deploy
```powershell
.\deploy-ecs.ps1 -Environment prod -AwsRegion us-east-1
```

### Check Status
```powershell
aws ecs describe-services --cluster agenticai-cluster-prod --services agenticai-websocket-prod --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

### View Logs
```powershell
aws logs tail /ecs/agenticai-websocket-prod --follow
```

### Get Endpoint
```powershell
aws cloudformation describe-stacks --stack-name agenticai-websocket-stack --query "Stacks[0].Outputs[?OutputKey=='WebSocketEndpoint'].OutputValue" --output text
```

### Update Service
```powershell
# After code changes
docker build -t agenticai-websocket:latest .
$repoUri = aws cloudformation describe-stacks --stack-name agenticai-websocket-stack --query "Stacks[0].Outputs[?OutputKey=='WebSocketRepositoryUri'].OutputValue" --output text
aws ecr get-login-password | docker login --username AWS --password-stdin $repoUri
docker tag agenticai-websocket:latest "${repoUri}:latest"
docker push "${repoUri}:latest"
aws ecs update-service --cluster agenticai-cluster-prod --service agenticai-websocket-prod --force-new-deployment
```

### Scale Service
```powershell
aws ecs update-service --cluster agenticai-cluster-prod --service agenticai-websocket-prod --desired-count 2
```

### Restart Service
```powershell
aws ecs update-service --cluster agenticai-cluster-prod --service agenticai-websocket-prod --force-new-deployment
```

## Test Connection

### Using wscat
```bash
npm install -g wscat
wscat -c ws://your-alb-dns/ws
```

### Using Python
```python
import asyncio, websockets, json

async def test():
    async with websockets.connect("ws://your-alb-dns/ws") as ws:
        print(await ws.recv())  # Welcome message
        await ws.send(json.dumps({"action": "ping"}))
        print(await ws.recv())  # Pong response

asyncio.run(test())
```

## Troubleshooting

### Service won't start
```powershell
# Check task logs
$taskArn = aws ecs list-tasks --cluster agenticai-cluster-prod --service-name agenticai-websocket-prod --query 'taskArns[0]' --output text
aws ecs describe-tasks --cluster agenticai-cluster-prod --tasks $taskArn
aws logs tail /ecs/agenticai-websocket-prod --since 10m
```

### Health checks failing
```powershell
# Check target health
$tgArn = aws elbv2 describe-target-groups --names agenticai-tg-prod --query 'TargetGroups[0].TargetGroupArn' --output text
aws elbv2 describe-target-health --target-group-arn $tgArn
```

### Can't connect
```powershell
# Verify ALB DNS
aws elbv2 describe-load-balancers --names agenticai-alb-prod --query 'LoadBalancers[0].DNSName' --output text

# Test health endpoint
curl http://your-alb-dns/health
```

## Cleanup
```powershell
aws ecs update-service --cluster agenticai-cluster-prod --service agenticai-websocket-prod --desired-count 0
aws ecs delete-service --cluster agenticai-cluster-prod --service agenticai-websocket-prod --force
aws cloudformation delete-stack --stack-name agenticai-websocket-stack
```

## Cost
- **Fargate**: ~$15/month (1 task)
- **ALB**: ~$16/month
- **Total**: ~$32/month

## Files Created
- `ecs-template.yaml` - CloudFormation template
- `deploy-ecs.ps1` - Deployment script
- `ECS_DEPLOYMENT_GUIDE.md` - Full documentation
- `requirements.txt` - Python dependencies
- `server.py` - WebSocket server (updated with health check)
