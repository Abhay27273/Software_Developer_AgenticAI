# Lambda Import Fix

## Problem

The test files were using direct imports like:
```python
from lambda.api_handler.app import lambda_handler
```

This caused a `SyntaxError` because `lambda` is a reserved keyword in Python.

## Solution

Changed all imports to use `importlib.import_module()`:

```python
import importlib

# Helper function
def import_lambda_module(module_path):
    """Import a lambda module using importlib to avoid keyword conflict."""
    return importlib.import_module(module_path)

# Usage in tests
lambda_handler = import_lambda_module('lambda.api_handler.app').lambda_handler
```

## Files Fixed

1. **tests/test_lambda_api_handler.py**
   - Added `import_lambda_module()` helper function
   - Replaced all 17 direct imports with `import_lambda_module()` calls

2. **tests/test_lambda_agent_workers.py**
   - Added `import_lambda_module()` helper function
   - Replaced all 13 direct imports with `import_lambda_module()` calls

## Verification

Tests now compile without syntax errors:
```bash
python -m py_compile tests/test_lambda_api_handler.py tests/test_lambda_agent_workers.py
# Exit Code: 0 ✓
```

## Running Tests

Now you can run the tests successfully:

```bash
# Install dependencies first
pip install moto[dynamodb,s3,sqs,ssm] boto3 pytest

# Run tests
pytest tests/test_lambda_api_handler.py tests/test_lambda_agent_workers.py -v
```

## Why This Works

- `importlib.import_module()` takes a string argument, so `'lambda'` is just a string, not the keyword
- The function dynamically imports the module at runtime
- This is a standard Python pattern for importing modules with problematic names

## Alternative Solutions Considered

1. **Rename lambda directory** - Would break AWS SAM deployment structure
2. **Use `__import__()`** - Less readable and not recommended
3. **Relative imports** - Doesn't work for test files outside the lambda package

The `importlib` solution is the cleanest and most maintainable approach.


## Moto Import Update

### Problem
Newer versions of moto (5.x+) changed the import syntax. The old syntax:
```python
from moto import mock_dynamodb, mock_s3, mock_sqs, mock_ssm
```

No longer works and causes:
```
ImportError: cannot import name 'mock_dynamodb' from 'moto'
```

### Solution
Use the unified `mock_aws` decorator:
```python
from moto import mock_aws

@pytest.fixture
def mock_dynamodb_table(aws_credentials):
    with mock_aws():
        # Create DynamoDB resources
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        # ...
```

### Files Updated
- `tests/test_lambda_api_handler.py` - Updated all moto decorators
- `tests/test_lambda_agent_workers.py` - Updated all moto decorators  
- `tests/test_parameter_store.py` - Updated all moto decorators

The `mock_aws()` context manager mocks all AWS services at once, which is simpler and works with moto 5.x+.
