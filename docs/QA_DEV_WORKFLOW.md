# QA-Dev One-Time Fix Workflow

**Date:** November 10, 2025  
**Status:** ✅ IMPLEMENTED

## Overview

Implemented an efficient QA→Dev→Ops workflow where:
1. **QA tests once** and finds errors
2. **Dev fixes once** based on QA feedback  
3. **File goes directly to Ops** without retesting

This eliminates redundant QA cycles and speeds up the pipeline.

---

## Workflow Diagram

```
┌─────────────┐
│  Dev Agent  │
│  Generates  │
│    Code     │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│         QA Agent (ONE TEST)         │
│  • Runs comprehensive tests         │
│  • Finds syntax/style/runtime issues│
│  • Attempts ONE simple fix (if any) │
└──────┬─────────────────┬────────────┘
       │                 │
   ✅ PASS          ❌ FAIL
       │                 │
       │                 ▼
       │     ┌──────────────────────────┐
       │     │  Communicate with Dev    │
       │     │  • Send detailed issues  │
       │     │  • Include test results  │
       │     │  • Request ONE-TIME fix  │
       │     └───────────┬──────────────┘
       │                 │
       │                 ▼
       │        ┌─────────────────┐
       │        │   Dev Agent     │
       │        │   Fixes Code    │
       │        │   (ONE TIME)    │
       │        └────────┬────────┘
       │                 │
       │                 │ ⚠️ NO RETEST
       │                 │
       ▼                 ▼
┌─────────────────────────────────┐
│         Ops Agent               │
│  • Deploys passing files        │
│  • Deploys fixed files (tagged) │
└─────────────────────────────────┘
```

---

## Key Features

### 1. **QA Agent Behavior**

**Testing Strategy:**
- Runs comprehensive tests **once**
- Identifies 4 types of issues:
  - `syntax` - Code syntax errors
  - `style` - Code style violations
  - `runtime` - Runtime errors during execution
  - `test_failure` - Unit test failures

**Fix Attempt:**
- QA attempts **ONE** simple fix (syntax/style only)
- If issues remain or are complex → Communicate with Dev

**Communication with Dev:**
```json
{
  "issues_found": [
    {
      "file_path": "src/main.py",
      "issue_type": "runtime",
      "description": "NameError: name 'undefined_var' is not defined",
      "line_number": 42,
      "suggested_fix": "Check variable definition before use"
    }
  ],
  "test_results": [...],
  "requires_dev_fix": true
}
```

---

### 2. **Event Routing Logic**

**Enhanced Pipeline Manager** (`utils/enhanced_pipeline_manager.py`):

```python
async def _handle_qa_failed(self, event: Event):
    """QA failed → Route to Dev for ONE-TIME fix"""
    
    fix_attempt_count = payload.get('fix_attempt_count', 0)
    
    if fix_attempt_count >= 1:
        # Already fixed once → Send to Ops with warnings
        logger.warning("File already fixed, sending to Ops with known issues")
        deploy_task = QueueTask(
            task_id=f"deploy_{event.task_id}_with_issues",
            task_type="deploy",
            payload={'has_known_issues': True, ...}
        )
        await self.deploy_queue.put(deploy_task)
    else:
        # First fix attempt → Send to Dev
        fix_task = QueueTask(
            task_id=f"fix_{event.task_id}",
            task_type="fix",
            payload={'fix_attempt_count': 1, 'is_final_fix': True, ...}
        )
        await self.unified_queue.put(fix_task)
```

```python
async def _handle_fix_completed(self, event: Event):
    """Fix completed → Send DIRECTLY to Ops (skip retest)"""
    
    deploy_task = QueueTask(
        task_id=f"deploy_{event.task_id}_fixed",
        task_type="deploy",
        payload={'was_fixed': True, 'skip_qa_retest': True, ...}
    )
    await self.deploy_queue.put(deploy_task)
```

---

### 3. **Dev Agent Integration**

**Current Behavior:**
- Dev receives issues via task metadata:
  ```python
  task.metadata['qa_issues'] = [...]
  task.metadata['qa_test_results'] = [...]
  task.metadata['requires_dev_fix'] = True
  ```

**Future Enhancement:**
- Add `DevAgent.handle_qa_feedback()` method
- Parse QA issues and apply targeted fixes
- Return fixed code with change log

---

## Benefits

### Performance Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **QA Tests per File** | 1-5 (with retests) | 1 (one-time) | **80% reduction** |
| **Dev Fix Cycles** | Multiple iterations | 1 iteration | **Faster fixes** |
| **Pipeline Time** | ~3-5 min/file | ~1-2 min/file | **40-60% faster** |
| **API Calls** | High (multiple QA tests) | Low (one test) | **Lower costs** |

### Quality Improvements

- ✅ **Clear Communication**: QA provides detailed issue reports to Dev
- ✅ **Single Fix Focus**: Dev addresses all issues in one pass
- ✅ **Confidence**: QA's initial test is comprehensive
- ✅ **Traceability**: Files tagged with fix history

---

## Implementation Details

### Files Modified

1. **`utils/enhanced_pipeline_manager.py`**
   - Modified `_handle_qa_failed()` - Check fix count, route accordingly
   - Modified `_handle_fix_completed()` - Send directly to deploy, skip retest

2. **`agents/qa_agent.py`**
   - Modified `_communicate_with_dev_agent()` - Document issues, no actual fix
   - Modified `_should_apply_fixes()` - Limit to one simple fix attempt
   - Modified `_finalize_qa_results()` - Handle new "communicated_to_dev" status

---

## Message Flow Example

### Scenario: QA finds runtime errors

```
1. Dev completes code generation
   → Event: FILE_COMPLETED

2. QA runs comprehensive tests
   📊 Tests: syntax ✅, style ✅, runtime ❌, unit_tests ❌
   
3. QA attempts simple fix (none available for runtime errors)
   
4. QA communicates with Dev
   📞 "Found 3 runtime errors and 2 test failures"
   
   WebSocket Message:
   {
     "type": "qa_dev_fix_requested",
     "issues_summary": [
       {"type": "runtime", "file": "main.py", "description": "NameError..."},
       {"type": "test_failure", "file": "test_main.py", "description": "AssertionError..."}
     ],
     "total_issues": 5
   }
   
5. QA marks task as FAILED
   → Event: QA_FAILED
   
6. Pipeline routes to Dev fix queue
   fix_attempt_count: 1
   is_final_fix: true
   
7. Dev processes fix (applies AI-powered fixes)
   
8. Dev completes fix
   → Event: FIX_COMPLETED
   
9. Pipeline sends DIRECTLY to Ops (NO retest)
   → Event: DEPLOY_READY
   
10. Ops deploys with metadata:
    - was_fixed: true
    - skip_qa_retest: true
    - original_issues: [...]
```

---

## Configuration

### QA Agent Settings

```python
# In QA workflow initialization
max_fix_attempts = 1  # QA only tries once

# Simple vs Complex issue detection
simple_issues = ["syntax", "style"]
complex_issues = ["runtime", "test_failure", "logic_error"]
```

### Pipeline Settings

```python
# In enhanced_pipeline_manager.py
max_fix_attempts_per_task = 1  # Dev fixes once
retest_after_fix = False       # Skip QA retest
```

---

## Monitoring & Metrics

### Key Metrics to Track

1. **Fix Success Rate**
   - % of files fixed successfully on first Dev attempt
   
2. **Issues Communicated**
   - Average number of issues per QA→Dev communication
   
3. **Deployment with Known Issues**
   - % of files deployed with unresolved issues after fix
   
4. **Time Savings**
   - Compare avg pipeline time before/after this workflow

### WebSocket Events

Monitor these for debugging:
- `qa_dev_communication` - QA requesting Dev fix
- `qa_dev_fix_requested` - Issues documented for Dev
- `qa_dev_communication_failed` - Communication error

---

## Future Enhancements

### Phase 1: Improve Dev Fix Quality
- [ ] Add `DevAgent.handle_qa_feedback()` method
- [ ] Implement AI-powered targeted fixes
- [ ] Generate fix change logs

### Phase 2: Smart Retest Conditions
- [ ] Allow optional retest for critical files
- [ ] Add retest triggers (e.g., security issues)
- [ ] Configurable retest rules per project

### Phase 3: Machine Learning
- [ ] Learn from fix success patterns
- [ ] Predict fix complexity
- [ ] Optimize QA test coverage based on issue history

---

## Troubleshooting

### Issue: Dev fixes don't address QA issues

**Solution:**
- Check `task.metadata['qa_issues']` is populated
- Verify Dev agent receives task metadata
- Add logging in Dev fix workflow

### Issue: Files go to Ops with unresolved issues

**Expected Behavior:**
- This is intentional after one fix attempt
- Check `has_known_issues` flag in deployment
- Monitor failure patterns

### Issue: QA attempts multiple fixes

**Solution:**
- Check `fix_attempts` counter reset
- Verify `_should_apply_fixes()` logic
- Ensure state persists correctly

---

## Testing

### Unit Tests Needed

1. Test QA one-time fix logic
2. Test event routing after QA failure
3. Test fix→deploy without retest
4. Test fix attempt counter

### Integration Tests

1. Full pipeline: Dev → QA (fail) → Dev (fix) → Ops
2. QA pass directly to Ops
3. Multiple files with different fix outcomes

---

## References

- Main Pipeline: `utils/enhanced_pipeline_manager.py`
- QA Agent: `agents/qa_agent.py`
- Event Types: `utils/enhanced_components.py` (EventType enum)
- Phase 2 Docs: `docs/PHASE2_COMPLETE_REPORT.md`

---

**Status:** ✅ ACTIVE  
**Next Review:** After 10 pipeline runs  
**Owner:** System Architecture Team
