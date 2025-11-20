# CodeModifier with LangGraph

## Overview

The CodeModifier is a sophisticated code modification system built using **LangGraph**, a framework for building stateful, multi-step agent workflows. It enables safe, intelligent modification of existing code through natural language requests.

## Architecture

### LangGraph Workflow

The CodeModifier implements a stateful workflow with the following states:

```
┌─────────┐
│  PARSE  │ ──> Parse existing code structure
└────┬────┘
     │
     v
┌─────────┐
│  PLAN   │ ──> Generate modification plan using LLM
└────┬────┘
     │
     v
┌──────────────┐
│ VALIDATE_PLAN│ ──> Validate plan for safety
└────┬─────────┘
     │
     ├──> [Safe] ──> APPLY
     │
     └──> [Unsafe] ──> ROLLBACK
     
┌─────────┐
│  APPLY  │ ──> Apply modifications to code
└────┬────┘
     │
     v
┌───────────────┐
│ VALIDATE_CODE │ ──> Validate modified code syntax
└────┬──────────┘
     │
     ├──> [Valid] ──> GENERATE_DIFF
     │
     └──> [Invalid] ──> ROLLBACK

┌───────────────┐
│ GENERATE_DIFF │ ──> Create before/after diff
└────┬──────────┘
     │
     v
┌──────────┐
│ COMPLETE │ ──> Success!
└──────────┘

┌──────────┐
│ ROLLBACK │ ──> Restore original code
└──────────┘
```

### Key Components

#### 1. **WorkflowState**
TypedDict that maintains state throughout the workflow:
- Input: modification request, file path, original content
- Intermediate: parsed AST, code structure, modification plan
- Output: modified content, diff, validation results

#### 2. **ModificationPlan**
Structured plan for code changes:
- List of changes (type, target, action, new code)
- Rationale for modifications
- Risk level assessment
- Affected functions/classes
- New dependencies

#### 3. **ModificationResult**
Result of modification operation:
- Success status
- Modified files
- Diff showing changes
- Validation errors
- Rollback availability
- Metadata

## Features

### 1. **Intelligent Code Parsing**

The system parses code to understand its structure:

**Python:**
- Uses AST (Abstract Syntax Tree) for precise parsing
- Extracts functions, classes, imports
- Identifies code structure and dependencies

**JavaScript/TypeScript:**
- Uses LLM-based parsing for structure understanding
- Identifies components, functions, exports

### 2. **Safe Modification Planning**

Before making changes, the system:
- Analyzes the modification request
- Identifies affected code sections
- Assesses risk level (low/medium/high)
- Creates a detailed modification plan
- Validates the plan for safety

### 3. **Syntax Validation**

After modifications:
- Validates Python syntax using AST
- Checks for common errors
- Ensures code is executable
- Verifies significant changes were made

### 4. **Diff Generation**

Provides clear visibility into changes:
- Unified diff format
- Shows additions and deletions
- Line-by-line comparison
- Easy to review before committing

### 5. **Automatic Rollback**

If anything goes wrong:
- Automatically restores original code
- Preserves backup files
- Reports validation errors
- Maintains code integrity

## Usage

### Basic Usage

```python
from utils.code_modifier import modify_code_file

# Simple modification
result = await modify_code_file(
    file_path="calculator.py",
    original_content=original_code,
    modification_request="Add input validation to all methods"
)

if result.success:
    print("Modified code:", result.modified_files["calculator.py"])
    print("Diff:", result.diff)
else:
    print("Errors:", result.validation_errors)
```

### Advanced Usage with CodeModifier Class

```python
from utils.code_modifier import CodeModifier

# Create modifier instance
modifier = CodeModifier(model="gemini-2.5-pro")

# Modify code with full control
result = await modifier.modify_code(
    file_path="src/main.py",
    original_content=code,
    modification_request="Refactor to use async/await"
)

# Access detailed results
print(f"Success: {result.success}")
print(f"Rollback available: {result.rollback_available}")
print(f"Metadata: {result.metadata}")
```

### Integration with Dev Agent

```python
from agents.dev_agent import DevAgent

dev_agent = DevAgent()

# Modify code in a project
result = await dev_agent.modify_code(
    project_id="my_project",
    file_path="src/api/routes.py",
    modification_request="Add authentication middleware"
)

# Dev Agent handles:
# - File location resolution
# - Backup creation
# - WebSocket notifications
# - Error handling
```

## Modification Request Examples

### 1. Add New Functionality

```python
modification_request = """
Add a new method called 'calculate_average' that:
1. Takes a list of numbers as input
2. Returns the average
3. Handles empty lists by returning 0
4. Includes proper error handling
"""
```

### 2. Refactor Existing Code

```python
modification_request = """
Refactor the authentication logic to:
1. Extract validation into a separate helper method
2. Use dependency injection for the database
3. Add type hints to all methods
4. Improve error messages
"""
```

### 3. Add Error Handling

```python
modification_request = """
Add comprehensive error handling:
1. Wrap database operations in try-except blocks
2. Add custom exception classes
3. Log errors with proper context
4. Return meaningful error responses
"""
```

### 4. Optimize Performance

```python
modification_request = """
Optimize the data processing pipeline:
1. Add caching for frequently accessed data
2. Use batch processing for database queries
3. Implement connection pooling
4. Add async/await for I/O operations
"""
```

## LangGraph Workflow Details

### State Transitions

The workflow uses conditional edges to determine the next state:

```python
def _should_proceed_with_modification(state: WorkflowState) -> str:
    """Decide whether to proceed or rollback."""
    if state.get("should_rollback"):
        return "rollback"
    
    plan_validation = state.get("plan_validation", {})
    if not plan_validation.get("is_safe", False):
        return "rollback"
    
    return "apply"

def _is_code_valid(state: WorkflowState) -> str:
    """Check if modified code is valid."""
    if state.get("syntax_valid", False):
        return "generate_diff"
    return "rollback"
```

### Node Functions

Each node in the workflow is an async function that:
1. Receives the current state
2. Performs its operation
3. Updates the state
4. Returns the modified state

Example:

```python
async def _parse_code(self, state: WorkflowState) -> WorkflowState:
    """Parse existing code to understand its structure."""
    try:
        # Parse code based on language
        language = self._detect_language(state["file_path"])
        
        if language == "python":
            parsed_ast, code_structure = self._parse_python_code(
                state["original_content"]
            )
        else:
            code_structure = await self._parse_with_llm(
                state["original_content"], 
                language
            )
        
        # Update state
        state["code_structure"] = code_structure
        state["current_state"] = ModificationState.PLAN.value
        
    except Exception as e:
        state["should_rollback"] = True
        state["error_message"] = str(e)
    
    return state
```

## Error Handling

### Validation Errors

The system catches and reports various errors:

1. **Syntax Errors**: Invalid Python/JS syntax
2. **Plan Validation Errors**: Unsafe modification plans
3. **LLM Errors**: API failures or invalid responses
4. **File Errors**: Missing files or permission issues

### Rollback Mechanism

When errors occur:
1. Original content is preserved
2. Backup files are maintained
3. Error details are logged
4. User is notified via WebSocket

## Performance Considerations

### LLM Calls

The workflow makes 2-3 LLM calls:
1. **Planning**: Generate modification plan (~2-5 seconds)
2. **Application**: Apply modifications (~3-10 seconds)
3. **Parsing** (optional): For non-Python languages (~1-3 seconds)

### Optimization Tips

1. **Use appropriate models**: 
   - `gemini-2.5-pro` for complex modifications
   - `gemini-1.5-flash` for simple changes

2. **Batch modifications**: 
   - Combine related changes in one request
   - Reduces LLM calls and improves consistency

3. **Cache code structure**:
   - Parse once, modify multiple times
   - Reuse parsed AST when possible

## Testing

### Unit Tests

```bash
pytest tests/test_code_modifier.py -v
```

Tests cover:
- Code parsing (Python, JS, TS)
- Modification planning
- Plan validation
- Code application
- Syntax validation
- Diff generation
- Error handling

### Integration Tests

```bash
pytest tests/test_dev_agent_code_modification.py -v
```

Tests cover:
- Dev Agent integration
- File handling
- Backup creation
- WebSocket notifications
- Multi-file scenarios

### Demo Script

```bash
python examples/code_modification_demo.py
```

Demonstrates:
- Basic modifications
- Adding new methods
- Refactoring code
- Error handling
- Complex multi-step changes

## Best Practices

### 1. Clear Modification Requests

✅ **Good:**
```
Add input validation to the calculate_sum function:
1. Check if both parameters are numbers
2. Raise TypeError if not
3. Include descriptive error messages
```

❌ **Bad:**
```
Make it better
```

### 2. Incremental Changes

✅ **Good:** Make one logical change at a time
❌ **Bad:** Request multiple unrelated changes together

### 3. Review Diffs

Always review the generated diff before committing:
```python
if result.success:
    print("Review changes:")
    print(result.diff)
    
    # Confirm before saving
    if input("Apply changes? (y/n): ").lower() == 'y':
        save_file(result.modified_files)
```

### 4. Maintain Backups

The system creates backups automatically:
```python
# Backup is created at: {file_path}.backup
# Restore if needed:
shutil.copy(f"{file_path}.backup", file_path)
```

## Troubleshooting

### Issue: Modification fails with syntax error

**Solution:** 
- Check if original code has syntax errors
- Simplify the modification request
- Try with a different LLM model

### Issue: Plan validation fails

**Solution:**
- Request is too vague or complex
- Break into smaller modifications
- Provide more specific instructions

### Issue: LLM timeout

**Solution:**
- File is too large (>2000 lines)
- Split into smaller files
- Increase timeout in LLM setup

### Issue: Changes not as expected

**Solution:**
- Review the modification plan in logs
- Provide more detailed instructions
- Include examples in the request

## Future Enhancements

### Planned Features

1. **Multi-file modifications**: Modify multiple related files atomically
2. **Test generation**: Automatically generate tests for modified code
3. **Conflict resolution**: Handle concurrent modifications
4. **Version control integration**: Automatic git commits with diffs
5. **Rollback history**: Maintain history of modifications
6. **Interactive mode**: Ask clarifying questions before modifying

### Experimental Features

1. **AI-powered code review**: Suggest improvements before applying
2. **Performance profiling**: Measure impact of modifications
3. **Security scanning**: Check for vulnerabilities in modified code
4. **Documentation updates**: Auto-update docs when code changes

## Contributing

To contribute to the CodeModifier:

1. **Add new language support**: Implement parser for new languages
2. **Improve validation**: Add more validation checks
3. **Enhance error messages**: Make errors more actionable
4. **Add examples**: Create more demo scenarios
5. **Write tests**: Increase test coverage

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Python AST Module](https://docs.python.org/3/library/ast.html)
- [Unified Diff Format](https://www.gnu.org/software/diffutils/manual/html_node/Detailed-Unified.html)

## License

This implementation is part of the Software Developer Agentic AI system.

---

**Last Updated:** November 2024  
**Version:** 1.0.0  
**Status:** Production Ready ✅
