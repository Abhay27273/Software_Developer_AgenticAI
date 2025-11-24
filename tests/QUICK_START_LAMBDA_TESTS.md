# Quick Start: Lambda Integration Tests

## 1. Install Dependencies

```bash
pip install moto[dynamodb,s3,sqs,ssm] boto3 pytest
```

Or install all project dependencies:

```bash
pip install -r requirements.txt
```

## 2. Run Tests

### Run all Lambda tests:
```bash
pytest tests/test_lambda_api_handler.py tests/test_lambda_agent_workers.py -v
```

### Run API Handler tests only:
```bash
pytest tests/test_lambda_api_handler.py -v
```

### Run Agent Worker tests only:
```bash
pytest tests/test_lambda_agent_workers.py -v
```

## 3. Expected Output

```
tests/test_lambda_api_handler.py::test_create_project_success PASSED
tests/test_lambda_api_handler.py::test_create_project_invalid_type PASSED
tests/test_lambda_api_handler.py::test_get_project_success PASSED
...
tests/test_lambda_agent_workers.py::test_pm_agent_process_planning_task PASSED
tests/test_lambda_agent_workers.py::test_dev_agent_code_generation PASSED
tests/test_lambda_agent_workers.py::test_qa_agent_test_code PASSED
...

======================== 35 passed in 5.23s ========================
```

## 4. What Gets Tested

✅ **API Handler Lambda**
- Project CRUD operations
- Modification requests
- Template management
- Error handling

✅ **PM Agent Worker**
- Planning task processing
- LLM integration
- Plan storage

✅ **Dev Agent Worker**
- Code generation
- Code modification
- File management

✅ **QA Agent Worker**
- Code testing
- Syntax checking
- Quality analysis

✅ **Ops Agent Worker**
- Deployment preparation
- Project type detection
- Configuration generation

## 5. No AWS Account Needed

These tests use **moto** to mock AWS services. No real AWS account or credentials required!

## 6. Troubleshooting

**Problem**: `ModuleNotFoundError: No module named 'moto'`
**Solution**: `pip install moto[dynamodb,s3,sqs,ssm]`

**Problem**: `ModuleNotFoundError: No module named 'boto3'`
**Solution**: `pip install boto3`

**Problem**: `ModuleNotFoundError: No module named 'pytest'`
**Solution**: `pip install pytest`

## 7. Next Steps

After tests pass:
1. Deploy Lambda functions to AWS using SAM
2. Run end-to-end tests against live environment
3. Set up CI/CD pipeline with these tests

## 8. More Information

See `tests/README_LAMBDA_TESTS.md` for detailed documentation.
