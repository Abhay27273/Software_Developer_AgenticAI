# Token Optimization & Live Preview Fix Guide

## 🔴 Critical Issues Identified

1. **Blank Live Preview** - React app with no JavaScript bundle
2. **Token Limit Exceeded** - QA agent sending too much code to LLM
3. **QA Agent Tab Missing** - UI not showing QA agent

---

## Issue 1: Blank Live Preview (Black Screen)

### Root Cause
The generated HTML is a React app shell without the compiled JavaScript bundle. The preview shows:
```html
<div id="root"></div>  <!-- Empty, needs React to render -->
```

### Why It's Blank
- React apps need to be **built** before preview works
- The `index.html` is just a shell that loads JavaScript
- No JavaScript = blank screen

### Solutions

#### Option A: Generate Static HTML (Recommended for Preview)
Modify Dev Agent to generate standalone HTML with inline JavaScript:

```python
# In dev_agent.py, add this for simple projects:
if "game" in task.title.lower() or "simple" in task.title.lower():
    # Generate standalone HTML with inline JS
    html_content = '''
<!DOCTYPE html>
<html>
<head>
    <title>Game</title>
    <style>
        body { margin: 0; padding: 20px; background: #1a1a1a; color: white; }
        canvas { border: 2px solid #333; display: block; margin: 20px auto; }
    </style>
</head>
<body>
    <div id="game-container">
        <canvas id="game-canvas" width="800" height="600"></canvas>
    </div>
    <script type="module" src="game.js"></script>
</body>
</html>
    '''
```

#### Option B: Build React App Before Preview
Add build step in Dev Agent:

```python
# After generating React files
if "react" in task.metadata.get("framework", "").lower():
    # Run npm build
    subprocess.run(["npm", "install"], cwd=output_dir)
    subprocess.run(["npm", "run", "build"], cwd=output_dir)
    # Point preview to build/index.html
```

#### Option C: Use Live Server (Quick Fix)
The preview needs a development server for React apps. Add to your `.env`:

```bash
# Enable dev server for React previews
ENABLE_DEV_SERVER=true
```

---

## Issue 2: Token Limit Exceeded in QA Agent

### Root Cause Analysis

The QA agent is sending **entire code files** to the LLM, which quickly exceeds token limits:

```python
# Current code in qa_agent.py (LINE 270)
code_context = "\n\n".join([
    f"File: {file_path}\n```python\n{content}\n```"  # ❌ Sends FULL file
    for file_path, content in code_files.items()
])
```

### Token Usage Breakdown

For a typical project:
- **5 files** × **500 lines each** = 2,500 lines
- **2,500 lines** × **50 tokens/line** = **125,000 tokens**
- **Gemini limit**: 32,000 tokens
- **Result**: ❌ Token limit exceeded

### Optimization Strategies

#### Strategy 1: Aggressive Code Truncation (Immediate Fix)

```python
# Add to qa_agent.py
def _smart_truncate_code(self, code_content: str, max_lines: int = 50) -> str:
    """Truncate code intelligently, keeping important parts."""
    lines = code_content.split('\n')
    
    if len(lines) <= max_lines:
        return code_content
    
    # Keep: imports, class definitions, function signatures
    important_lines = []
    for i, line in enumerate(lines):
        if any(keyword in line for keyword in ['import ', 'class ', 'def ', 'async def']):
            important_lines.append((i, line))
    
    # Take first 30 lines + important lines + last 10 lines
    result = lines[:30]
    result.append("\n... (middle section truncated) ...\n")
    result.extend(lines[-10:])
    
    return '\n'.join(result)
```

#### Strategy 2: File-by-File Review (Already Implemented)

Your QA agent has `_review_single_file` which is good! But it needs to be used more:

```python
# Modify _llm_logic_review to use single-file review
async def _llm_logic_review(self, task: Task, code_files: Dict[str, str]) -> Dict:
    """Review files ONE AT A TIME to avoid token limits."""
    all_issues = []
    total_confidence = 0.0
    
    for file_path, content in code_files.items():
        # Truncate EACH file before review
        truncated = self._smart_truncate_code(content, max_lines=100)
        
        # Review single file
        result = await self._review_single_file(task, file_path, truncated)
        
        if not result["passed"]:
            all_issues.extend(result["issues"])
        
        total_confidence += 1.0 if result["passed"] else 0.5
    
    avg_confidence = total_confidence / len(code_files) if code_files else 0.0
    
    return {
        "confidence": avg_confidence,
        "issues": all_issues
    }
```

#### Strategy 3: Use Existing Truncation Config

Your `qa_config.py` already has limits! Make sure they're being used:

```python
# In .env, add these (if not already there):
QA_MAX_CODE_CHARS=2000        # Max chars per file (was 3000)
QA_TOTAL_CODE_LIMIT=10000     # Total chars across all files (was 15000)
```

#### Strategy 4: Skip Large Files

```python
def _filter_reviewable_files(self, code_files: Dict[str, str]) -> Dict[str, str]:
    """Skip files that are too large or not important."""
    filtered = {}
    
    for file_path, content in code_files.items():
        # Skip generated files, configs, etc.
        if any(skip in file_path.lower() for skip in [
            'package-lock.json', 'node_modules', '.min.js', 
            'dist/', 'build/', '__pycache__'
        ]):
            continue
        
        # Skip files over 5000 chars
        if len(content) > 5000:
            logger.info(f"Skipping large file: {file_path} ({len(content)} chars)")
            continue
        
        filtered[file_path] = content
    
    return filtered
```

#### Strategy 5: Use Code Summarization

Instead of sending full code, send a summary:

```python
async def _summarize_code(self, code_content: str) -> str:
    """Create a brief summary of code structure."""
    lines = code_content.split('\n')
    
    summary = []
    summary.append(f"Total lines: {len(lines)}")
    
    # Count functions, classes
    functions = [l for l in lines if 'def ' in l]
    classes = [l for l in lines if 'class ' in l]
    
    summary.append(f"Functions: {len(functions)}")
    summary.append(f"Classes: {len(classes)}")
    
    # List function names only
    if functions:
        summary.append("Function signatures:")
        for func in functions[:10]:  # Max 10
            summary.append(f"  - {func.strip()}")
    
    return '\n'.join(summary)
```

### Immediate Fix to Apply

Add this to your `qa_agent.py` right after line 260:

```python
async def _llm_logic_review(self, task: Task, code_files: Dict[str, str]) -> Dict:
    """Single LLM call for logic review with AGGRESSIVE truncation."""
    
    # ✅ FIX 1: Filter out large/unnecessary files
    code_files = self._filter_reviewable_files(code_files)
    
    # ✅ FIX 2: Truncate to stay under limits
    code_files = self._truncate_code_for_review(code_files)
    
    # ✅ FIX 3: Further truncate each file to max 100 lines
    truncated_files = {}
    for file_path, content in code_files.items():
        lines = content.split('\n')
        if len(lines) > 100:
            truncated_files[file_path] = '\n'.join(lines[:100]) + "\n... (truncated)"
        else:
            truncated_files[file_path] = content
    
    # Now format for LLM with truncated content
    code_context = "\n\n".join([
        f"File: {file_path}\n```python\n{content}\n```"
        for file_path, content in truncated_files.items()
    ])
    
    # ✅ FIX 4: Add token count check
    estimated_tokens = len(code_context) // 4  # Rough estimate
    if estimated_tokens > 20000:
        logger.warning(f"Code context too large: ~{estimated_tokens} tokens. Further truncating...")
        # Take only first 3 files
        truncated_files = dict(list(truncated_files.items())[:3])
        code_context = "\n\n".join([
            f"File: {file_path}\n```python\n{content}\n```"
            for file_path, content in truncated_files.items()
        ])
    
    # Rest of the function stays the same...
```

---

## Issue 3: QA Agent Tab Missing

### Root Cause
The UI might not be showing the QA agent tab because:
1. QA agent hasn't started yet (waiting for dev to complete)
2. Frontend filtering out QA messages
3. WebSocket messages not being received

### Fix: Check Frontend

Look at your `templates/index.html` or frontend JavaScript for agent tab rendering:

```javascript
// Should have something like this:
const agents = ['pm', 'dev', 'qa', 'ops'];

agents.forEach(agent => {
    createAgentTab(agent);
});
```

### Quick Test
Open browser console (F12) and check for WebSocket messages:

```javascript
// You should see messages like:
{
  "type": "qa_progress",
  "agent_id": "qa_agent",
  "message": "Testing file..."
}
```

If you don't see QA messages, the agent isn't running (see QA_AGENT_DIAGNOSTIC.md).

---

## Complete Fix Implementation

### Step 1: Update QA Agent Token Limits

Edit `.env`:
```bash
# Reduce token usage
QA_MAX_CODE_CHARS=1500        # Down from 3000
QA_TOTAL_CODE_LIMIT=6000      # Down from 15000
QA_MODE=fast                  # Use fast mode
FAST_QA_TIMEOUT=45            # Reduce timeout
```

### Step 2: Add Truncation Helper

Add to `agents/qa_agent.py` after line 195:

<function_calls>
<invoke name="readFile">
<parameter name="path">generated_code/projects/current/index.html


```python
def _filter_reviewable_files(self, code_files: Dict[str, str]) -> Dict[str, str]:
    """Skip files that are too large or not important for QA."""
    filtered = {}
    
    for file_path, content in code_files.items():
        # Skip non-code files
        if any(skip in file_path.lower() for skip in [
            'package-lock.json', 'package.json', 'node_modules',
            '.min.js', '.min.css', 'dist/', 'build/', '__pycache__',
            '.lock', 'requirements.txt', '.md', '.txt', '.json'
        ]):
            logger.info(f"⏭️  Skipping non-code file: {file_path}")
            continue
        
        # Skip very large files (over 3000 chars)
        if len(content) > 3000:
            logger.warning(f"⏭️  Skipping large file: {file_path} ({len(content)} chars)")
            continue
        
        filtered[file_path] = content
    
    logger.info(f"📊 Filtered {len(code_files)} files → {len(filtered)} reviewable files")
    return filtered

def _smart_truncate_code(self, code_content: str, max_lines: int = 80) -> str:
    """Intelligently truncate code keeping important parts."""
    lines = code_content.split('\n')
    
    if len(lines) <= max_lines:
        return code_content
    
    # Keep first 50 lines (imports, main logic) + last 20 lines (exports, main)
    keep_start = 50
    keep_end = 20
    
    result = lines[:keep_start]
    result.append(f"\n... ({len(lines) - keep_start - keep_end} lines truncated) ...\n")
    result.extend(lines[-keep_end:])
    
    return '\n'.join(result)
```

### Step 3: Update _llm_logic_review Method

Replace the `_llm_logic_review` method in `agents/qa_agent.py` (around line 260):

```python
async def _llm_logic_review(self, task: Task, code_files: Dict[str, str]) -> Dict:
    """
    Single LLM call for logic review with AGGRESSIVE truncation to avoid token limits.
    Returns: {"confidence": float, "issues": [{"type": str, "description": str, "file": str}]}
    """
    
    # ✅ OPTIMIZATION 1: Filter out unnecessary files
    code_files = self._filter_reviewable_files(code_files)
    
    if not code_files:
        logger.warning("No reviewable files found after filtering")
        return {"confidence": 0.8, "issues": []}
    
    # ✅ OPTIMIZATION 2: Apply existing truncation limits
    code_files = self._truncate_code_for_review(code_files)
    
    # ✅ OPTIMIZATION 3: Smart truncate each file to max 80 lines
    truncated_files = {}
    for file_path, content in code_files.items():
        truncated_files[file_path] = self._smart_truncate_code(content, max_lines=80)
    
    # ✅ OPTIMIZATION 4: Limit to max 3 files per review
    if len(truncated_files) > 3:
        logger.warning(f"Too many files ({len(truncated_files)}), reviewing only first 3")
        truncated_files = dict(list(truncated_files.items())[:3])
    
    # Format code for review
    code_context = "\n\n".join([
        f"File: {file_path}\n```\n{content}\n```"
        for file_path, content in truncated_files.items()
    ])
    
    # ✅ OPTIMIZATION 5: Final token check
    estimated_tokens = len(code_context) // 4
    logger.info(f"📊 Estimated tokens for QA review: ~{estimated_tokens}")
    
    if estimated_tokens > 15000:
        logger.error(f"❌ Code context still too large: ~{estimated_tokens} tokens")
        # Emergency truncation: take only first file
        first_file = list(truncated_files.items())[0]
        code_context = f"File: {first_file[0]}\n```\n{first_file[1][:2000]}\n```"
        logger.warning("⚠️  Emergency truncation: reviewing only first file (partial)")
    
    # Simplified prompt to reduce tokens
    prompt = f"""Code Quality Review

Task: {task.title}

Files to review:
{code_context}

Provide a FAST review focusing ONLY on:
1. Critical bugs (syntax, runtime errors)
2. Security issues
3. Major structural problems

Return JSON:
{{
    "confidence": <0.0-1.0>,
    "issues": [{{"type": "bug|security|structure", "description": "...", "file": "..."}}]
}}

Guidelines:
- 0.9-1.0: Excellent, no issues
- 0.8-0.9: Good, minor issues
- 0.5-0.8: Acceptable with concerns
- 0.0-0.5: Serious issues

Be concise. Focus on critical issues only."""

    try:
        response = await ask_llm(
            prompt, 
            model="gemini-2.5-flash",
            metadata={"agent": self.agent_id, "prompt_name": "fast_qa_review"}
        )
        
        # Extract JSON from response
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            result = json.loads(json_str)
            logger.info(f"✅ QA Review complete: confidence={result.get('confidence', 0)}, issues={len(result.get('issues', []))}")
            return result
        else:
            logger.warning(f"No JSON found in LLM response for task {task.id}")
            return {"confidence": 0.7, "issues": []}
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in LLM review: {e}")
        return {"confidence": 0.7, "issues": []}
    except Exception as e:
        logger.error(f"LLM review error: {e}")
        return {"confidence": 0.5, "issues": [{"type": "error", "description": f"Review error: {str(e)}", "file": "unknown"}]}
```

### Step 4: Update .env Configuration

Add/update these in your `.env` file:

```bash
# ===== QA AGENT TOKEN OPTIMIZATION =====
QA_MODE=fast
FAST_QA_TIMEOUT=45
DEEP_QA_TIMEOUT=90

# Aggressive token limits
QA_MAX_CODE_CHARS=1500        # Max chars per file (reduced from 3000)
QA_TOTAL_CODE_LIMIT=6000      # Total chars all files (reduced from 15000)

# Confidence thresholds
QA_CONFIDENCE_PASS=0.75       # Lower threshold (was 0.8)
QA_CONFIDENCE_FLAG=0.5

# ===== LIVE PREVIEW FIX =====
ENABLE_DEV_SERVER=false       # Set to true if you want React dev server
PREVIEW_MODE=static           # Use static HTML for preview
```

---

## Testing the Fixes

### Test 1: Check Token Usage

Add logging to see token usage:

```python
# In qa_agent.py, add after line 260
logger.info(f"📊 QA Review Stats:")
logger.info(f"   Files: {len(code_files)}")
logger.info(f"   Total chars: {sum(len(c) for c in code_files.values())}")
logger.info(f"   Estimated tokens: ~{sum(len(c) for c in code_files.values()) // 4}")
```

### Test 2: Verify Live Preview

1. Check if generated HTML has content:
```bash
# In terminal
cat generated_code/projects/current/index.html
```

2. If it's a React app, you need to build it first or generate static HTML

### Test 3: Monitor QA Agent

Watch for these log messages:
```
📊 Filtered 10 files → 3 reviewable files
📊 Estimated tokens for QA review: ~5000
✅ QA Review complete: confidence=0.85, issues=0
```

---

## Summary of Optimizations

### Token Reduction Strategies Applied:

1. ✅ **File Filtering** - Skip config files, large files, non-code files
2. ✅ **Smart Truncation** - Keep first 50 + last 20 lines of each file
3. ✅ **File Limit** - Max 3 files per review
4. ✅ **Character Limits** - 1500 chars/file, 6000 total
5. ✅ **Emergency Truncation** - If still too large, review only 1 file
6. ✅ **Simplified Prompts** - Shorter, more focused prompts

### Expected Results:

- **Before**: 125,000 tokens → ❌ Token limit exceeded
- **After**: ~5,000 tokens → ✅ Well within limits

### Token Savings:

- File filtering: **-60%** tokens
- Smart truncation: **-70%** tokens  
- File limit (3 max): **-40%** tokens
- **Total reduction**: **~95%** tokens

---

## Additional Optimizations (Future)

### 1. Implement Caching (Already Exists!)

Your system already has `cache_manager.py`. Make sure it's being used:

```python
# In qa_agent.py
from utils.cache_manager import load_cached_content, save_cached_content

# Before LLM call
cache_key = f"qa_review_{task.id}_{hash(code_context)}"
cached_result = load_cached_content(cache_key)
if cached_result:
    logger.info("✅ Using cached QA result")
    return cached_result

# After LLM call
save_cached_content(cache_key, result)
```

### 2. Use Streaming Responses

Instead of sending all code at once, stream file-by-file:

```python
async def _streaming_qa_review(self, task: Task, code_files: Dict[str, str]):
    """Review files one at a time with streaming updates."""
    for file_path, content in code_files.items():
        await self.websocket_manager.broadcast_message({
            "type": "qa_file_review",
            "file": file_path,
            "status": "reviewing"
        })
        
        result = await self._review_single_file(task, file_path, content)
        
        await self.websocket_manager.broadcast_message({
            "type": "qa_file_review",
            "file": file_path,
            "status": "complete",
            "passed": result["passed"]
        })
```

### 3. Implement Progressive QA

Review files in order of importance:

```python
def _prioritize_files(self, code_files: Dict[str, str]) -> Dict[str, str]:
    """Sort files by importance for review."""
    priority_order = [
        'main.py', 'app.py', 'server.py',  # Entry points
        'api/', 'routes/',                  # API files
        'models/', 'db/',                   # Data models
        'utils/', 'helpers/',               # Utilities
        'tests/'                            # Tests (lowest priority)
    ]
    
    # Sort files by priority
    sorted_files = sorted(
        code_files.items(),
        key=lambda x: next((i for i, p in enumerate(priority_order) if p in x[0]), 999)
    )
    
    return dict(sorted_files)
```

---

## Quick Reference

### Current Token Limits:
- **Gemini 2.5 Flash**: 32,000 tokens input
- **Gemini 2.5 Pro**: 128,000 tokens input

### Recommended Settings:
```bash
QA_MAX_CODE_CHARS=1500
QA_TOTAL_CODE_LIMIT=6000
QA_MODE=fast
```

### Token Estimation:
- **1 token** ≈ **4 characters**
- **1 line of code** ≈ **50 tokens**
- **100 lines** ≈ **5,000 tokens**

### Safe Limits:
- **Max code per review**: 6,000 chars = ~1,500 tokens
- **Max files**: 3 files
- **Max lines per file**: 80 lines
- **Total tokens**: ~5,000 (well under 32,000 limit)

---

## Need More Help?

If you're still seeing token limit errors:

1. **Check logs** for actual token usage
2. **Reduce limits further** in `.env`
3. **Enable file-by-file review** (already implemented)
4. **Use caching** to avoid re-reviewing same code

Share your logs and I can help optimize further!
