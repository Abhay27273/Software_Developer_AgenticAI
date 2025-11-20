# Model Configuration

## Overview
This document describes the LLM model configuration across all agents in the Software Developer Agentic AI system.

## Current Configuration

### Agent-Specific Models

| Agent | Model | Reason |
|-------|-------|--------|
| **Dev Agent** | `gemini-2.5-pro` | Higher quality code generation and fixes |
| **PM Agent** | `gemini-2.5-flash` | Fast planning and coordination |
| **QA Agent** | `gemini-2.5-flash` | Quick test analysis and reviews |
| **Ops Agent** | `gemini-2.5-flash` | Efficient deployment tasks |

### Rate Limits (Free Tier)

| Model | RPM Limit | Use Case |
|-------|-----------|----------|
| `gemini-2.5-pro` | 2 RPM | Dev Agent only (high quality needed) |
| `gemini-2.5-flash` | 15 RPM | All other agents (speed prioritized) |

## Configuration Files

### 1. `.env` (Environment Variables)
```properties
# Model Configuration
MODEL=gemini-2.5-flash          # Default model for most agents
DEV_MODEL=gemini-2.5-pro        # Specific model for dev agent
```

### 2. `config.py` (Python Constants)
```python
DEFAULT_MODEL_NAME = "gemini-2.5-flash"      # PM, QA, Ops agents
PLANNER_MODEL_NAME = "gemini-2.5-flash"      # Planning tasks
DEV_MODEL_NAME = "gemini-2.5-pro"            # Dev Agent only
```

### 3. `agents/dev_agent.py` (Dev Agent)
```python
# Model configuration - use gemini-2.5-pro for dev agent (higher quality code)
DEV_MODEL = os.getenv("DEV_MODEL", "gemini-2.5-pro")

# Used in two places:
# 1. Code generation (line ~574)
# 2. Code fixes (line ~1268)
```

## Rate Limiting Strategy

### Current Settings (`utils/llm_setup.py`)
- **Max Concurrent Requests:** 1 (reduced from 2 to avoid overload)
- **Min Request Interval:** 5.0 seconds (increased from 1.0s)
- **Max Retries:** 3 attempts
- **Backoff Strategy:** Exponential with 3x multiplier for 503 errors

### Retry Logic
```
Attempt 1: Immediate
Attempt 2: 3s delay (1s * 2^1 * 3 for 503 errors)
Attempt 3: 6s delay (1s * 2^2 * 3 for 503 errors)
```

## Why This Configuration?

### Dev Agent Uses Pro Model
1. **Code Quality:** Generates more robust, production-ready code
2. **Complex Logic:** Better at understanding dependencies and edge cases
3. **Fixes:** More accurate when debugging and fixing issues
4. **Acceptable Trade-off:** Slower but fewer iterations needed

### Other Agents Use Flash Model
1. **Speed:** PM, QA, and Ops agents need quick responses
2. **Volume:** These agents handle more frequent, smaller tasks
3. **Rate Limits:** Flash has 15 RPM vs Pro's 2 RPM (7.5x more capacity)
4. **Sufficient Quality:** Planning, testing, and deployment don't need Pro-level reasoning

## Troubleshooting

### "503 The model is overloaded" Errors

**Root Cause:** Gemini API is rejecting requests due to high server load

**Solutions:**
1. ✅ **Already Applied:** Reduced concurrency to 1, increased interval to 5s
2. ✅ **Already Applied:** Enhanced 503 error handling with 3x backoff
3. ✅ **Already Applied:** Using Flash for most agents (better availability)
4. ⚠️ **If Issues Persist:** Consider upgrading to paid tier for higher quotas

### Switching Models

**To change Dev Agent to Flash (faster, lower quality):**
```bash
# In .env file
DEV_MODEL=gemini-2.5-flash
```

**To use Pro for all agents (slower, higher quality):**
```bash
# In .env file
MODEL=gemini-2.5-pro
DEV_MODEL=gemini-2.5-pro
```

**To use experimental model (even faster):**
```bash
# In .env file
MODEL=gemini-2.0-flash-exp
DEV_MODEL=gemini-2.0-flash-exp
```

## Monitoring

### Check Model Usage in Logs
```bash
# Look for these log entries:
INFO:utils.llm_setup:📦 Loading model gemini-2.5-pro with temp=0.3
INFO:utils.llm_setup:🚦 Rate limiting: Max 1 concurrent request, 5.0s interval
```

### Verify Configuration
```python
# In Python console:
import os
from config import DEFAULT_MODEL_NAME, DEV_MODEL_NAME

print(f"Default Model: {DEFAULT_MODEL_NAME}")
print(f"Dev Model: {DEV_MODEL_NAME}")
print(f"Env Dev Model: {os.getenv('DEV_MODEL', 'not set')}")
```

## Performance Impact

### Expected Behavior
- **Dev Tasks:** 30-60s per task (using Pro model)
- **QA Fast Mode:** 30-60s (using Flash model)
- **Planning:** 10-20s (using Flash model)
- **Deployment:** 5-10s (using Flash model)

### If Tasks Are Too Slow
1. Switch Dev Agent to Flash model (loses some quality)
2. Increase worker pool sizes (more parallelism)
3. Enable result caching (avoid redundant LLM calls)

### If Tasks Are Failing with 503 Errors
1. Further increase request interval (5s → 10s)
2. Reduce max concurrent requests (already at 1)
3. Add longer backoff delays
4. Switch to paid tier for better SLA

## Future Improvements

1. **Dynamic Model Selection:** Choose model based on task complexity
2. **Fallback Chain:** Pro → Flash → Exp on failures
3. **Local Model Support:** Add support for local LLMs (Ollama, LMStudio)
4. **Cost Tracking:** Monitor API usage and optimize based on budget
5. **A/B Testing:** Compare Pro vs Flash output quality metrics
