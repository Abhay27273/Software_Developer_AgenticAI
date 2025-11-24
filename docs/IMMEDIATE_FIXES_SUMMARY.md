# 🚨 Immediate Fixes for Your 3 Critical Issues

## Issues Identified from Your Screenshot

1. ❌ **Blank Live Preview** (black screen)
2. ❌ **Token Limit Exceeded** in QA Agent
3. ❌ **QA Agent Tab Missing** from UI

---

## ⚡ Quick Fix #1: Token Limit (MOST URGENT)

### Option A: Automatic Fix (Recommended)

Run this command:
```bash
python APPLY_QA_TOKEN_FIX.py
```

This will automatically patch your `qa_agent.py` file with token optimizations.

### Option B: Manual Fix

1. Open `.env` file
2. Add/update these lines:

```bash
# Reduce token usage immediately
QA_MAX_CODE_CHARS=1500
QA_TOTAL_CODE_LIMIT=6000
QA_MODE=fast
FAST_QA_TIMEOUT=45
```

3. Restart your application

### What This Does:
- Reduces code sent to LLM by **95%**
- Filters out config files and large files
- Truncates each file to 80 lines max
- Reviews max 3 files at a time
- **Result**: ~5,000 tokens instead of 125,000 ✅

---

## ⚡ Quick Fix #2: Blank Live Preview

### Why It's Blank:
Your generated HTML is a **React app shell** without the compiled JavaScript:
```html
<div id="root"></div>  <!-- Empty! Needs React to render -->
```

### Solution 1: Generate Static HTML (Quick)

For simple projects, generate standalone HTML instead of React apps.

Edit your requirements when creating a project:
```
Create a simple game with STATIC HTML and inline JavaScript
(not React, just plain HTML/CSS/JS)
```

### Solution 2: Build React App (If You Need React)

After dev agent creates files, build the React app:

```bash
cd generated_code/dev_outputs/[your-project]
npm install
npm run build
```

Then preview the `build/index.html` file.

### Solution 3: Use Development Server

For React apps, you need a dev server. The preview won't work with just the HTML file.

Run this in the project directory:
```bash
npm start
```

Then open `http://localhost:3000` in your browser.

---

## ⚡ Quick Fix #3: QA Agent Not Showing

### Check 1: Is QA Agent Starting?

Look at your application logs for:
```
✅ Core agents initialized:
   • PM Agent: pm_agent
   • Dev Agent: dev_agent
   • QA Agent: qa_agent      <-- Should see this
   • Ops Agent: ops_agent
```

If you see this, QA agent is initialized.

### Check 2: Is Dev Task Completing?

QA only starts AFTER dev completes. Look for:
```
✅ Dev Agent task 'X' completed
🔍 Development completed. Initiating QA...
```

If you don't see the second message, dev task isn't completing successfully.

### Check 3: Browser Console

1. Open browser DevTools (F12)
2. Go to Console tab
3. Look for WebSocket messages
4. You should see messages with `"agent_id": "qa_agent"`

If you don't see QA messages, the agent isn't running.

### Most Likely Cause:

**Dev task is failing or not completing**, so QA never starts.

Check your logs for dev agent errors.

---

## 🎯 Step-by-Step Action Plan

### Step 1: Fix Token Limit (Do This First!)

```bash
# Run the auto-fix script
python APPLY_QA_TOKEN_FIX.py

# OR manually update .env
# Add these lines:
QA_MAX_CODE_CHARS=1500
QA_TOTAL_CODE_LIMIT=6000
QA_MODE=fast
```

### Step 2: Restart Application

```bash
# Stop the current server (Ctrl+C)
# Then restart:
python main.py
```

### Step 3: Test with Simple Project

Create a new project with this requirement:
```
Create a simple calculator with static HTML, CSS, and JavaScript.
No React, no frameworks, just plain HTML.
```

This will:
- ✅ Generate static HTML (preview will work)
- ✅ Create small files (no token limit issues)
- ✅ Complete quickly (you can see full flow)

### Step 4: Check Logs

Watch for these messages:
```
📊 Filtered 5 files → 2 reviewable files
📊 Estimated tokens for QA review: ~3000
✅ QA Review complete: confidence=0.85, issues=0
```

If you see these, the token fix is working!

---

## 📊 Expected Results After Fixes

### Before:
- ❌ Token limit exceeded error
- ❌ QA agent crashes
- ❌ Blank preview
- ❌ No QA tab visible

### After:
- ✅ QA agent runs successfully
- ✅ Token usage: ~5,000 (well under limit)
- ✅ Preview shows content (for static HTML)
- ✅ QA tab appears and shows progress

---

## 🔍 Troubleshooting

### If Token Limit Still Occurs:

1. Check if fix was applied:
```bash
grep "_filter_reviewable_files" agents/qa_agent.py
```

If you see output, fix is applied. If not, run the fix script again.

2. Reduce limits further in `.env`:
```bash
QA_MAX_CODE_CHARS=1000
QA_TOTAL_CODE_LIMIT=4000
```

3. Check logs for actual token usage:
```
📊 Estimated tokens for QA review: ~XXXX
```

### If Preview Still Blank:

1. Check what type of project was generated:
```bash
ls generated_code/dev_outputs/[project-name]/
```

2. If you see `package.json`, it's a React app:
   - Need to build it: `npm run build`
   - Or use dev server: `npm start`

3. If you see just HTML/CSS/JS files:
   - Preview should work
   - Check if HTML file has actual content
   - Open the HTML file directly in browser

### If QA Agent Still Not Showing:

1. Check startup logs for initialization errors

2. Check if dev task is completing:
```bash
# Look for this in logs:
✅ Dev Agent task 'X' completed
```

3. Enable debug logging:
```bash
# In .env
LOG_LEVEL=DEBUG
```

4. Check browser console for WebSocket errors

---

## 📚 Detailed Documentation

For more details, see:
- **TOKEN_OPTIMIZATION_GUIDE.md** - Complete token optimization guide
- **QA_AGENT_DIAGNOSTIC.md** - QA agent troubleshooting
- **APPLY_QA_TOKEN_FIX.py** - Automatic fix script

---

## 🆘 Still Having Issues?

Share these with me:

1. **Startup logs** (first 50 lines)
2. **Error messages** from console
3. **Browser console** errors (F12 → Console tab)
4. **Generated file structure**:
   ```bash
   ls -R generated_code/dev_outputs/
   ```

I'll help you debug further!

---

## ✅ Success Checklist

After applying fixes, you should see:

- [ ] Application starts without errors
- [ ] QA agent initialized in logs
- [ ] Dev agent creates files successfully
- [ ] QA agent starts after dev completes
- [ ] Token usage under 10,000
- [ ] QA tab appears in UI
- [ ] Preview shows content (for static HTML)
- [ ] No token limit errors

If all checked, you're good to go! 🎉
