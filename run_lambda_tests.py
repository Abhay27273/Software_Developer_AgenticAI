"""
Simple test runner for Lambda integration tests.

This script runs the Lambda integration tests without requiring full pytest installation.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all Lambda modules can be imported."""
    print("Testing Lambda module imports...")
    
    # Set AWS region for boto3
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    
    try:
        import importlib
        app = importlib.import_module('lambda.api_handler.app')
        print("✓ API Handler imported successfully")
    except Exception as e:
        print(f"✗ API Handler import failed: {e}")
        return False
    
    try:
        import importlib
        pm_worker = importlib.import_module('lambda.pm_agent.worker')
        print("✓ PM Agent Worker imported successfully")
    except Exception as e:
        print(f"✗ PM Agent Worker import failed: {e}")
        return False
    
    try:
        import importlib
        dev_worker = importlib.import_module('lambda.dev_agent.worker')
        print("✓ Dev Agent Worker imported successfully")
    except Exception as e:
        print(f"✗ Dev Agent Worker import failed: {e}")
        return False
    
    try:
        import importlib
        qa_worker = importlib.import_module('lambda.qa_agent.worker')
        print("✓ QA Agent Worker imported successfully")
    except Exception as e:
        print(f"✗ QA Agent Worker import failed: {e}")
        return False
    
    try:
        import importlib
        ops_worker = importlib.import_module('lambda.ops_agent.worker')
        print("✓ Ops Agent Worker imported successfully")
    except Exception as e:
        print(f"✗ Ops Agent Worker import failed: {e}")
        return False
    
    return True


def test_basic_functionality():
    """Test basic Lambda handler functionality."""
    print("\nTesting basic Lambda handler functionality...")
    
    try:
        import importlib
        app_module = importlib.import_module('lambda.api_handler.app')
        create_response = app_module.create_response
        health_check = app_module.health_check
        
        # Test response creation
        response = create_response(200, {'test': 'data'})
        assert response['statusCode'] == 200
        assert 'body' in response
        print("✓ Response creation works")
        
        # Test health check
        health_response = health_check()
        assert health_response['statusCode'] == 200
        print("✓ Health check works")
        
        return True
    except Exception as e:
        print(f"✗ Basic functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Lambda Integration Tests - Quick Verification")
    print("=" * 60)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    # Test basic functionality
    if not test_basic_functionality():
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All quick tests passed!")
        print("\nTo run full integration tests with moto mocking:")
        print("  pip install moto[dynamodb,s3,sqs,ssm] boto3")
        print("  pytest tests/test_lambda_api_handler.py -v")
        print("  pytest tests/test_lambda_agent_workers.py -v")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
