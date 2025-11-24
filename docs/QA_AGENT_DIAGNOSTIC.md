# QA Agent Not Starting - Diagnostic Guide

## Current Situation

Based on your logs, the Dev Agent is creating files successfully, but the QA Agent is not starting. Let me help you diagnose and fix this issue.

## How the System Works

### Sequential Flow (Phase 1 - Default)
```
PM Agent → Dev Agent → QA Agent → Ops Agent
```

1. **PM Agent** creates tasks from requirements
2. **Dev Agent** executes each dev_agent task and creates files
3. **QA Agent** automatically runs AFTER each dev task completes
4. **Ops Agent** runs after ALL dev+QA tasks complete

### Key Code Flow in main.py

```python
# Line ~1220: After dev task completes
async def execute_dev_task_sequential(task: Task, websocket: WebSocket):
    updated_task = await execute_dev_task_with_streaming(task, websocket)
    
    # THIS IS WHERE QA SHOULD START
    if updated_task.status == TaskStatus.COMPLETED:
        await execute_qa_after_dev(updated_task, websocket)
```

## Why QA Might Not Be Starting

### Possible Causes:

1. **Dev Task Not Completing Successfully**
   - If dev task status is not `COMPLETED`, QA won't trigger
   - Check if dev task is failing or getting stuck

2. **WebSocket Connection Issues**
   - QA messages might not be reaching the frontend
   - Check browser console for WebSocket errors

3. **QA Agent Initialization Failed**
   - Check startup logs for QA agent initialization errors
   - Look for: `✅ Core agents initialized: • QA Agent: qa_agent`

4. **Exception in QA Execution**
   - QA might be starting but failing silently
   - Check logs for QA-related errors

## Diagnostic Steps

### Step 1: Check Startup Logs

Look for this in your console when the app starts:
```
✅ Core agents initialized:
   • PM Agent: pm_agent
   • Dev Agent: dev_agent
   • QA Agent: qa_agent      <-- Should see this
   • Ops Agent: ops_agent
```

### Step 2: Check Dev Task Completion

In your WebSocket messages, look for:
```json
{
  "type": "task_status_update",
  "agent_id": "dev",
  "status": "completed"     <-- Must be "completed"
}
```

### Step 3: Check for QA Initiation Message

After dev completes, you should see:
```json
{
  "type": "dev_task_complete_init_qa",
  "message": "Development completed. Initiating QA..."
}
```

### Step 4: Check Browser Console

Open browser DevTools (F12) and look for:
- WebSocket connection status
- Any JavaScript errors
- QA-related messages

## Quick Fixes

### Fix 1: Enable Detailed Logging

Add this to your `.env` file:
```bash
LOG_LEVEL=DEBUG
```

Restart the application and check logs for detailed QA execution info.

### Fix 2: Check QA Configuration

Verify your `.env` has QA settings:
```bash
QA_MODE=fast
FAST_QA_TIMEOUT=60
QA_CONFIDENCE_PASS=0.8
```

### Fix 3: Manual QA Test

Test if QA agent works independently:

```python
# Create a test script: test_qa_manual.py
import asyncio
from agents.qa_agent import QAAgent
from models.task import Task, TaskStatus
from parse.websocket_manager import WebSocketManager

async def test_qa():
    ws_manager = WebSocketManager()
    qa_agent = QAAgent(websocket_manager=ws_manager)
    
    test_task = Task(
        id="test-1",
        title="Test QA",
        description="Manual QA test",
        agent_type="dev_agent",
        status=TaskStatus.COMPLETED,
        metadata={"output_directory": "generated_code/dev_outputs"}
    )
    
    result = await qa_agent.execute_task(test_task)
    print(f"QA Result: {result.status}")

asyncio.run(test_qa())
```

Run it:
```bash
python test_qa_manual.py
```

### Fix 4: Check File Paths

QA agent looks for files in the dev output directory. Verify:

1. Dev agent is saving files to the correct location
2. The `metadata["output_directory"]` is set correctly
3. Files actually exist in that directory

```python
# Check in your code
print(f"Dev output dir: {task.metadata.get('output_directory')}")
print(f"Files created: {list(Path(output_dir).rglob('*.py'))}")
```

## Common Issues and Solutions

### Issue 1: "No files found for QA"

**Solution:** Dev agent didn't save files or path is wrong
```python
# In dev_agent.py, ensure files are saved:
output_dir = DEV_OUTPUT_DIR / f"task_{task.id}"
output_dir.mkdir(parents=True, exist_ok=True)
# ... save files ...
task.metadata["output_directory"] = str(output_dir.relative_to(BASE_DIR))
```

### Issue 2: QA starts but hangs

**Solution:** Timeout issue, adjust QA config
```bash
# In .env
FAST_QA_TIMEOUT=120  # Increase timeout
```

### Issue 3: QA fails immediately

**Solution:** Check if required tools are installed
```bash
pip install pytest pylint black mypy
```

## Monitoring QA Execution

### Add Debug Logging

In `main.py`, add logging before QA execution:

```python
async def execute_qa_after_dev(dev_task: Task, websocket: WebSocket):
    logger.info(f"🔍 QA TRIGGER: Dev task {dev_task.id} completed")
    logger.info(f"   Status: {dev_task.status}")
    logger.info(f"   Output dir: {dev_task.metadata.get('output_directory')}")
    
    # Check if files exist
    output_dir = Path(dev_task.metadata.get('output_directory', ''))
    if output_dir.exists():
        files = list(output_dir.rglob('*'))
        logger.info(f"   Files found: {len(files)}")
    else:
        logger.warning(f"   ⚠️ Output directory doesn't exist!")
    
    # ... rest of QA execution
```

## Next Steps

1. **Run the diagnostic steps above**
2. **Check your logs** for the specific error messages
3. **Share the logs** with me if you need more help

Look for these specific log patterns:
- `🔍 QA TRIGGER:` - QA is being called
- `🧪 QA Agent executing task:` - QA agent started
- `✅ QA Agent task` - QA completed
- `❌` or `ERROR` - Something failed

## Expected Normal Flow

When everything works correctly, you should see:

```
1. 🔨 Dev Agent executing task: 'Create API endpoints'
2. ✅ Dev Agent task 'Create API endpoints' completed
3. 🔍 Development completed. Initiating QA...
4. 🧪 QA Agent executing task: 'Create API endpoints'
5. 📝 Testing file: api/routes.py
6. ✅ All tests passed for api/routes.py
7. ✅ QA Agent task completed
```

If you're not seeing step 3-7, that's where the problem is.

## Contact Points

Share with me:
1. Your startup logs (first 50 lines)
2. The last dev task completion message
3. Any error messages in the console
4. Browser console errors (if any)

This will help me pinpoint the exact issue!
