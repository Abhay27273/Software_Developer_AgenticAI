# 🔧 Live Preview Fix Guide

## Issue: Blank Live Preview

The live preview is blank because there are **two different preview systems** that might be conflicting:

### 1. Ops Agent Live Preview (Deployment URL)
- **Location:** Ops Agent panel → "Live Preview" section
- **Purpose:** Shows the deployed application URL
- **Element ID:** `ops-live-preview`
- **How it works:** 
  - Ops Agent deploys to a platform (Render, Railway, etc.)
  - Gets deployment URL
  - Updates iframe with: `<iframe src="deployment_url"></iframe>`

### 2. File Viewer Live Preview (HTML Files)
- **Location:** File viewer panel → "Live Preview" button
- **Purpose:** Shows HTML file content directly
- **Element ID:** `live-preview-iframe`
- **How it works:**
  - User selects an HTML file
  - Clicks "Live Preview" button
  - Content is written directly to iframe

---

## 🔍 Diagnosis Steps

### Step 1: Check Which Preview You're Using

**For Ops Agent Preview:**
```javascript
// In browser console:
document.getElementById('ops-live-preview').innerHTML
// Should show: <iframe src="https://..."></iframe>
```

**For File Viewer Preview:**
```javascript
// In browser console:
document.getElementById('live-preview-iframe').src
// Should show: about:blank or empty
```

### Step 2: Check Deployment Status

**In browser console:**
```javascript
// Check if deployment info exists
console.log(window.app.deploymentInfo);
// Should show: { deployUrl: "https://...", ... }
```

**In Python logs:**
```bash
# Look for these messages:
✅ Deployed to Render: https://...
✅ Ops Agent: Deployment completed
```

### Step 3: Check for Errors

**Browser Console:**
- Press F12
- Look for errors (red text)
- Common issues:
  - CORS errors (deployment blocks iframe)
  - Mixed content (HTTPS page loading HTTP iframe)
  - CSP violations (Content Security Policy)

---

## 🛠️ Quick Fixes

### Fix 1: Ops Agent Preview Not Showing

**Problem:** Deployment URL not being set

**Solution:**
```javascript
// Add this to browser console to manually test:
const testUrl = "https://example.com";
document.getElementById('ops-live-preview').innerHTML = 
  `<iframe src="${testUrl}" title="Live Preview" style="width:100%;height:500px;border:none;"></iframe>`;
```

**Permanent Fix in `templates/index.html`:**
```javascript
// Find updateOpsLivePreview method (around line 2507)
updateOpsLivePreview(url) {
    if (!this.opsLivePreview || !url) {
        console.warn('⚠️ No preview URL or element');
        return;
    }
    
    console.log('🔄 Updating live preview with URL:', url);
    
    // Add error handling
    this.opsLivePreview.innerHTML = `
        <iframe 
            src="${url}" 
            title="Live Preview"
            style="width:100%;height:500px;border:none;"
            onerror="console.error('Failed to load preview')"
            onload="console.log('Preview loaded successfully')"
        ></iframe>
    `;
}
```

### Fix 2: File Viewer Preview Not Showing

**Problem:** HTML content not being written to iframe

**Solution:**
```javascript
// Find refreshLivePreview method (around line 3385)
refreshLivePreview() {
    console.log('🔄 Refreshing live preview...');
    
    const code = this.codeViewer.textContent;
    if (!code || !code.trim()) {
        console.warn('⚠️ No code to preview');
        return;
    }
    
    const iframe = this.livePreviewIframe;
    if (!iframe) {
        console.error('❌ Preview iframe not found');
        return;
    }
    
    try {
        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        iframeDoc.open();
        iframeDoc.write(code);
        iframeDoc.close();
        console.log('✅ Live preview refreshed');
    } catch (error) {
        console.error('❌ Failed to refresh preview:', error);
    }
}
```

### Fix 3: CORS Issues

**Problem:** Deployed site blocks iframe embedding

**Solution 1 - Add X-Frame-Options header to deployed app:**
```python
# In your deployed app (e.g., main.py)
@app.middleware("http")
async def add_frame_options(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "ALLOWALL"  # Or "SAMEORIGIN"
    return response
```

**Solution 2 - Open in new tab instead:**
```javascript
// In templates/index.html, add a button:
<button onclick="window.open(deploymentUrl, '_blank')">
    Open in New Tab
</button>
```

---

## 🧪 Testing

### Test 1: Manual Preview Test
```javascript
// In browser console:
const testHtml = `
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
    <h1>Hello World!</h1>
    <p>If you see this, the preview works!</p>
</body>
</html>
`;

const iframe = document.getElementById('live-preview-iframe');
const doc = iframe.contentDocument;
doc.open();
doc.write(testHtml);
doc.close();
```

### Test 2: Check Deployment URL
```javascript
// In browser console after deployment:
fetch('/api/deployment-status')
    .then(r => r.json())
    .then(data => {
        console.log('Deployment status:', data);
        if (data.statistics && data.statistics.ops_completed > 0) {
            console.log('✅ Deployment completed');
        } else {
            console.log('⚠️ No deployment yet');
        }
    });
```

---

## 📝 Checklist

Before reporting "blank preview":

- [ ] Check browser console for errors
- [ ] Verify deployment completed (check Ops Agent panel)
- [ ] Check if deployment URL exists (`window.app.deploymentInfo`)
- [ ] Try opening deployment URL in new tab
- [ ] Check if HTML file is selected (for file viewer preview)
- [ ] Try manual preview test (see above)
- [ ] Check network tab for failed requests
- [ ] Verify iframe element exists in DOM

---

## 🎯 Most Likely Causes

### 1. No Deployment Yet (90% of cases)
**Symptom:** Preview is blank, no URL in Ops panel
**Fix:** Run a complete workflow (PM → Dev → QA → Ops)

### 2. CORS Blocking (5% of cases)
**Symptom:** Console shows "Refused to display in a frame"
**Fix:** Add X-Frame-Options header or open in new tab

### 3. Wrong Preview Type (3% of cases)
**Symptom:** Looking at wrong preview panel
**Fix:** Check both Ops panel and File Viewer panel

### 4. JavaScript Error (2% of cases)
**Symptom:** Console shows JavaScript errors
**Fix:** Check console, fix errors in index.html

---

## 🚀 Quick Debug Commands

```javascript
// Run these in browser console:

// 1. Check if preview elements exist
console.log('Ops preview:', document.getElementById('ops-live-preview'));
console.log('File preview:', document.getElementById('live-preview-iframe'));

// 2. Check deployment info
console.log('Deployment:', window.app?.deploymentInfo);

// 3. Check current file
console.log('Current file:', window.app?.currentFile);

// 4. Force update preview
if (window.app?.deploymentInfo?.deployUrl) {
    document.getElementById('ops-live-preview').innerHTML = 
        `<iframe src="${window.app.deploymentInfo.deployUrl}"></iframe>`;
}

// 5. Test file preview
const testCode = '<h1>Test</h1>';
const iframe = document.getElementById('live-preview-iframe');
iframe.contentDocument.write(testCode);
```

---

## 📞 Still Not Working?

If preview is still blank after trying all fixes:

1. **Check Python logs** for deployment errors
2. **Check browser console** for JavaScript errors
3. **Try different browser** (Chrome, Firefox, Edge)
4. **Disable browser extensions** (ad blockers can interfere)
5. **Check if port 7860 is accessible**
6. **Verify WebSocket connection** (check Network tab)

---

**Last Updated:** November 21, 2024
**Status:** Diagnostic guide complete
**Next Action:** Run diagnosis steps and apply appropriate fix
