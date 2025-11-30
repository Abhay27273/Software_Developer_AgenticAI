# Frontend API Key Setup

## Summary

The `index.html` file has been updated to include API key authentication for all backend API calls.

## Changes Made

### 1. API Key Configuration Added

Added API key constant and helper function at the beginning of the JavaScript section:

```javascript
// API CONFIGURATION
const API_KEY = 'FIyfTeSSOB8WmxEXadquW8w6BdaGbc6cLvEVlC8b'; // Your API key

// Helper function to get headers with API key
function getApiHeaders(additionalHeaders = {}) {
    return {
        'Content-Type': 'application/json',
        'x-api-key': API_KEY,
        ...additionalHeaders
    };
}
```

### 2. Updated Fetch Calls

All fetch calls now include the API key in headers:

#### `/api/qa_report` (Line ~2782)
```javascript
const response = await fetch('/api/qa_report', {
    headers: getApiHeaders()
});
```

#### `/api/project/archived` (Line ~3343)
```javascript
const response = await fetch('/api/project/archived', {
    headers: getApiHeaders()
});
```

#### `/api/files` (Line ~3415)
```javascript
const response = await fetch('/api/files', {
    headers: getApiHeaders()
});
```

## Testing

To test the API key integration:

1. **Upload to S3**:
   ```bash
   aws s3 cp templates/index.html s3://your-bucket-name/index.html
   ```

2. **Test in Browser**:
   - Open your S3 website URL
   - Open browser DevTools (F12) → Network tab
   - Interact with the application
   - Verify requests include `x-api-key` header

3. **Verify API Gateway**:
   - Check CloudWatch Logs for API Gateway
   - Confirm requests are authenticated successfully
   - No 403 Forbidden errors

## Security Notes

⚠️ **Important**: The API key is currently hardcoded in the frontend JavaScript. This means:

- ✅ **Good for**: Development, testing, internal tools
- ❌ **Not ideal for**: Public-facing production applications

### For Production

Consider these alternatives:

1. **Environment-based Configuration**:
   ```javascript
   const API_KEY = window.ENV?.API_KEY || 'default-key';
   ```

2. **Backend Proxy**: 
   - Frontend calls your backend without API key
   - Backend adds API key when calling AWS API Gateway

3. **Cognito Authentication**:
   - Use AWS Cognito for user authentication
   - Generate temporary credentials per user

## Next Steps

1. ✅ Upload updated `index.html` to S3
2. ✅ Test API calls in browser
3. ✅ Verify CloudWatch logs show authenticated requests
4. 🔄 Consider implementing Cognito for production (optional)

## Related Files

- `templates/index.html` - Frontend with API key
- `lambda/api_handler/app.py` - Backend API handler
- `template.yaml` - API Gateway configuration with API key requirement
- `docs/API_AUTHENTICATION_GUIDE.md` - Complete authentication setup guide
