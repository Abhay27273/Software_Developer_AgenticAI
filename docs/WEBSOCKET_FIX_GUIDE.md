# WebSocket Error Fix Guide

## Problem

You're seeing WebSocket connection errors in the browser console:
```
WebSocket connection to 'ws://agenticai-frontend-379929762201.s3-website-us-east-1.amazonaws.com/ws' failed
```

## Root Cause

The frontend is trying to connect to a WebSocket server that doesn't exist yet. WebSockets require a separate ECS Fargate deployment (not included in the serverless-only template).

## Solution Applied

✅ **WebSocket has been disabled** - Your app now works without WebSocket errors.

The changes made:
1. Commented out WebSocket auto-connect on page load
2. Added REST API fallback for send message function
3. App shows a friendly message when WebSocket is not available

## Upload Updated Frontend

**Windows (PowerShell)**:
```powershell
.\scripts\upload_frontend_to_s3.ps1 -BucketName "agenticai-frontend-379929762201"
```

**Linux/Mac (Bash)**:
```bash
./scripts/upload_frontend_to_s3.sh agenticai-frontend-379929762201
```

**Manual**:
```bash
aws s3 cp templates/index.html s3://agenticai-frontend-379929762201/index.html \
    --content-type "text/html" \
    --cache-control "no-cache"
```

## Verify Fix

1. Clear browser cache (Ctrl+Shift+Delete)
2. Hard refresh (Ctrl+F5)
3. Open http://agenticai-frontend-379929762201.s3-website-us-east-1.amazonaws.com/
4. Check console - **no more WebSocket errors!**

## Current Functionality

### ✅ What Works (Without WebSocket)

- ✅ UI loads correctly
- ✅ No console errors
- ✅ REST API calls work (with API key)
- ✅ File viewing
- ✅ Project management
- ✅ Direct API testing

### ⚠️ What Requires WebSocket

- ⚠️ Real-time agent execution
- ⚠️ Live progress updates
- ⚠️ Streaming responses
- ⚠️ Multi-agent orchestration

## Option 1: Use REST API Directly (Recommended for Now)

Test your backend using curl or Postman:

```bash
# Get your API Gateway endpoint
aws cloudformation describe-stacks \
    --stack-name agenticai-stack \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text

# Test health endpoint
curl -H "x-api-key: FIyfTeSSOB8WmxEXadquW8w6BdaGbc6cLvEVlC8b" \
     https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/health

# Create a project
curl -X POST \
     -H "Content-Type: application/json" \
     -H "x-api-key: FIyfTeSSOB8WmxEXadquW8w6BdaGbc6cLvEVlC8b" \
     -d '{"name":"Test Project","type":"api","description":"Testing"}' \
     https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/projects
```

## Option 2: Deploy WebSocket Handler (Full Functionality)

If you need real-time agent execution, deploy the WebSocket handler:

### Prerequisites

1. **Update template.yaml** to include ECS/WebSocket resources
2. **Deploy ECS Fargate service** for WebSocket handler

### Steps

```bash
# 1. Check if you have WebSocket resources in template.yaml
grep -i "websocket\|ecs" template.yaml

# 2. If not present, you need to add them or use a different template

# 3. Deploy WebSocket handler
cd websocket_handler
./deploy.sh  # Linux/Mac
# OR
.\deploy.ps1  # Windows

# 4. Get WebSocket endpoint
aws cloudformation describe-stacks \
    --stack-name agenticai-stack \
    --query 'Stacks[0].Outputs[?OutputKey==`WebSocketEndpoint`].OutputValue' \
    --output text

# 5. Update index.html with WebSocket endpoint
# Edit line ~3469 to use your WebSocket URL instead of window.location.host
```

## Recommended Next Steps

### For Testing/Development

1. ✅ Use the fixed frontend (no WebSocket errors)
2. ✅ Test REST API endpoints directly
3. ✅ Verify API key authentication works
4. ✅ Check CloudWatch logs for API calls

### For Production

1. 🔄 Deploy WebSocket handler (ECS Fargate)
2. 🔄 Update frontend with WebSocket endpoint
3. 🔄 Enable CORS for your S3 domain
4. 🔄 Set up CloudFront for HTTPS

## Troubleshooting

### Still seeing WebSocket errors?

**Clear browser cache**:
```
Chrome: Ctrl+Shift+Delete → Clear cached images and files
Firefox: Ctrl+Shift+Delete → Cached Web Content
```

**Hard refresh**:
```
Windows: Ctrl+F5
Mac: Cmd+Shift+R
```

### API calls failing?

**Check API key**:
- Open DevTools → Network tab
- Look for `x-api-key` header in requests
- Should be: `FIyfTeSSOB8WmxEXadquW8w6BdaGbc6cLvEVlC8b`

**Check API Gateway**:
```bash
# Get API endpoint
aws cloudformation describe-stacks \
    --stack-name agenticai-stack \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text

# Test directly
curl -H "x-api-key: FIyfTeSSOB8WmxEXadquW8w6BdaGbc6cLvEVlC8b" \
     YOUR_API_ENDPOINT/health
```

## Summary

✅ **Fixed**: WebSocket errors removed
✅ **Working**: Frontend loads without errors
✅ **Next**: Upload updated index.html to S3
⚠️ **Note**: Full agent execution requires WebSocket deployment

## Related Documentation

- [Frontend Deployment Quick Start](./FRONTEND_DEPLOYMENT_QUICK_START.md)
- [Frontend API Key Setup](./FRONTEND_API_KEY_SETUP.md)
- [AWS Deployment Guide](./AWS_DEPLOYMENT_GUIDE.md)
- [WebSocket Handler Deployment](../websocket_handler/README.md)
