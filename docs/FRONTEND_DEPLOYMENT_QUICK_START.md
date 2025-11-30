# Frontend Deployment Quick Start

## ✅ What's Been Done

Your `index.html` file has been updated with API key authentication:

1. **API Key Added**: `FIyfTeSSOB8WmxEXadquW8w6BdaGbc6cLvEVlC8b`
2. **All Fetch Calls Updated**: Now include `x-api-key` header
3. **Helper Function Created**: `getApiHeaders()` for consistent header management

## 🚀 Deploy to S3 (3 Steps)

### Step 1: Upload to S3

**Windows (PowerShell)**:
```powershell
.\scripts\upload_frontend_to_s3.ps1 -BucketName "your-bucket-name"
```

**Linux/Mac (Bash)**:
```bash
chmod +x scripts/upload_frontend_to_s3.sh
./scripts/upload_frontend_to_s3.sh your-bucket-name
```

**Manual Upload**:
```bash
aws s3 cp templates/index.html s3://your-bucket-name/index.html \
    --content-type "text/html" \
    --cache-control "no-cache, no-store, must-revalidate"
```

### Step 2: Verify Upload

```bash
# Check file exists
aws s3 ls s3://your-bucket-name/index.html

# Get website URL
echo "http://your-bucket-name.s3-website-us-east-1.amazonaws.com"
```

### Step 3: Test in Browser

1. Open your S3 website URL
2. Open DevTools (F12) → Network tab
3. Interact with the app (create project, view files, etc.)
4. Verify requests show `x-api-key` header

## 🔍 Troubleshooting

### Issue: 403 Forbidden

**Cause**: API key not being sent or invalid

**Solution**:
1. Check browser DevTools → Network → Request Headers
2. Verify `x-api-key: FIyfTeSSOB8WmxEXadquW8w6BdaGbc6cLvEVlC8b` is present
3. Clear browser cache (Ctrl+Shift+Delete)
4. Hard refresh (Ctrl+F5)

### Issue: CORS Error

**Cause**: API Gateway CORS not configured for your S3 domain

**Solution**:
```bash
# Update API Gateway CORS settings
aws apigateway update-rest-api \
    --rest-api-id YOUR_API_ID \
    --patch-operations \
        op=replace,path=/cors/allowOrigins,value='["http://your-bucket-name.s3-website-us-east-1.amazonaws.com"]'
```

Or update in `template.yaml`:
```yaml
Cors:
  AllowOrigins:
    - "http://your-bucket-name.s3-website-us-east-1.amazonaws.com"
  AllowHeaders:
    - "Content-Type"
    - "x-api-key"
```

### Issue: Old Version Cached

**Cause**: Browser or CloudFront caching old version

**Solution**:
```bash
# Upload with no-cache headers (already done by script)
aws s3 cp templates/index.html s3://your-bucket-name/index.html \
    --cache-control "no-cache, no-store, must-revalidate"

# Clear browser cache
# Chrome: Ctrl+Shift+Delete → Clear cached images and files
# Firefox: Ctrl+Shift+Delete → Cached Web Content
```

## 📋 Verification Checklist

- [ ] `index.html` uploaded to S3
- [ ] S3 website hosting enabled
- [ ] Bucket policy allows public read access
- [ ] Website URL accessible in browser
- [ ] DevTools shows `x-api-key` header in requests
- [ ] API calls return 200 OK (not 403 Forbidden)
- [ ] CloudWatch logs show authenticated requests

## 🔐 Security Notes

### Current Setup (Development)
- ✅ API key hardcoded in frontend
- ✅ Good for: Testing, internal tools, demos
- ⚠️ Not ideal for: Public production apps

### Production Recommendations

1. **Use Cognito** (Recommended):
   ```javascript
   // Get temporary credentials per user
   const credentials = await Auth.currentCredentials();
   ```

2. **Backend Proxy**:
   ```javascript
   // Frontend → Your Backend → AWS API Gateway
   fetch('/api/proxy/projects', { ... })
   ```

3. **Environment Variables**:
   ```javascript
   const API_KEY = window.ENV?.API_KEY || 'fallback-key';
   ```

## 📚 Related Documentation

- [Frontend API Key Setup](./FRONTEND_API_KEY_SETUP.md) - Detailed changes made
- [API Authentication Guide](./API_AUTHENTICATION_GUIDE.md) - Complete auth setup
- [AWS Deployment Guide](./AWS_DEPLOYMENT_GUIDE.md) - Full deployment process
- [S3 Static Website Hosting](https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteHosting.html)

## 🎯 Next Steps

After deploying frontend:

1. **Test End-to-End**:
   - Create a project
   - View generated files
   - Check agent outputs
   - Download project files

2. **Set Up CI/CD** (Optional):
   - Add frontend deployment to GitHub Actions
   - Auto-deploy on push to `main` branch
   - See `.github/workflows/deploy.yml` for reference

3. **Add CloudFront** (Optional):
   - HTTPS support
   - Better performance
   - Custom domain
   - See [CloudFront Setup Guide](./CLOUDFRONT_SETUP.md)

4. **Monitor Usage**:
   - Check CloudWatch logs
   - Monitor API Gateway metrics
   - Track costs with AWS Cost Explorer

## 🆘 Need Help?

- Check CloudWatch Logs: `/aws/apigateway/agenticai-api`
- Review API Gateway metrics in AWS Console
- Test API directly with curl:
  ```bash
  curl -H "x-api-key: FIyfTeSSOB8WmxEXadquW8w6BdaGbc6cLvEVlC8b" \
       https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/api/projects
  ```
