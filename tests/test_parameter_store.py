"""
Unit tests for Parameter Store utility.

These tests use moto to mock AWS SSM service.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from moto import mock_aws
import boto3


# Mock the parameter_store module
@pytest.fixture
def mock_ssm_client():
    """Create a mocked SSM client."""
    with mock_aws():
        client = boto3.client('ssm', region_name='us-east-1')
        
        # Create test parameters
        client.put_parameter(
            Name='/agenticai/prod/gemini-api-key',
            Value='test-gemini-key-123',
            Type='SecureString',
            Description='Test Gemini API key'
        )
        client.put_parameter(
            Name='/agenticai/prod/jwt-secret',
            Value='test-jwt-secret-456',
            Type='SecureString',
            Description='Test JWT secret'
        )
        client.put_parameter(
            Name='/agenticai/prod/github-token',
            Value='test-github-token-789',
            Type='SecureString',
            Description='Test GitHub token'
        )
        
        yield client


@mock_aws
def test_get_parameter_success():
    """Test successful parameter retrieval."""
    # Setup
    client = boto3.client('ssm', region_name='us-east-1')
    client.put_parameter(
        Name='/test/param',
        Value='test-value',
        Type='SecureString'
    )
    
    # Import after mocking
    from lambda.shared.parameter_store import get_parameter, clear_cache
    clear_cache()
    
    # Test
    with patch('lambda.shared.parameter_store.ssm_client', client):
        value = get_parameter('/test/param')
        assert value == 'test-value'


@mock_aws
def test_get_parameter_not_found():
    """Test parameter not found error."""
    client = boto3.client('ssm', region_name='us-east-1')
    
    from lambda.shared.parameter_store import get_parameter, clear_cache
    clear_cache()
    
    with patch('lambda.shared.parameter_store.ssm_client', client):
        with pytest.raises(ValueError, match="Parameter not found"):
            get_parameter('/nonexistent/param')


@mock_aws
def test_get_parameter_caching():
    """Test that parameters are cached."""
    client = boto3.client('ssm', region_name='us-east-1')
    client.put_parameter(
        Name='/test/cached',
        Value='cached-value',
        Type='String'
    )
    
    from lambda.shared.parameter_store import get_parameter, clear_cache
    clear_cache()
    
    with patch('lambda.shared.parameter_store.ssm_client', client) as mock_client:
        # First call
        value1 = get_parameter('/test/cached')
        
        # Second call should use cache
        value2 = get_parameter('/test/cached')
        
        assert value1 == value2 == 'cached-value'
        # Should only call SSM once due to caching
        assert mock_client.get_parameter.call_count == 1


@mock_aws
def test_get_all_parameters():
    """Test retrieving all parameters for an environment."""
    client = boto3.client('ssm', region_name='us-east-1')
    
    # Create multiple parameters
    client.put_parameter(Name='/agenticai/dev/param1', Value='value1', Type='String')
    client.put_parameter(Name='/agenticai/dev/param2', Value='value2', Type='String')
    client.put_parameter(Name='/agenticai/prod/param3', Value='value3', Type='String')
    
    from lambda.shared.parameter_store import get_all_parameters, clear_cache
    clear_cache()
    
    with patch('lambda.shared.parameter_store.ssm_client', client):
        params = get_all_parameters('dev')
        
        assert 'param1' in params
        assert 'param2' in params
        assert 'param3' not in params  # Different environment
        assert params['param1'] == 'value1'
        assert params['param2'] == 'value2'


@mock_aws
def test_load_secrets_success():
    """Test loading all required secrets."""
    client = boto3.client('ssm', region_name='us-east-1')
    
    # Create required parameters
    client.put_parameter(
        Name='/agenticai/prod/gemini-api-key',
        Value='gemini-key',
        Type='SecureString'
    )
    client.put_parameter(
        Name='/agenticai/prod/jwt-secret',
        Value='jwt-secret',
        Type='SecureString'
    )
    client.put_parameter(
        Name='/agenticai/prod/github-token',
        Value='github-token',
        Type='SecureString'
    )
    
    from lambda.shared.parameter_store import load_secrets, clear_cache
    clear_cache()
    
    with patch('lambda.shared.parameter_store.ssm_client', client):
        with patch.dict(os.environ, {'ENVIRONMENT': 'prod'}):
            secrets = load_secrets()
            
            assert secrets['gemini_api_key'] == 'gemini-key'
            assert secrets['jwt_secret'] == 'jwt-secret'
            assert secrets['github_token'] == 'github-token'


@mock_aws
def test_load_secrets_missing_required():
    """Test error when required secrets are missing."""
    client = boto3.client('ssm', region_name='us-east-1')
    
    # Only create one required parameter
    client.put_parameter(
        Name='/agenticai/prod/gemini-api-key',
        Value='gemini-key',
        Type='SecureString'
    )
    
    from lambda.shared.parameter_store import load_secrets, clear_cache
    clear_cache()
    
    with patch('lambda.shared.parameter_store.ssm_client', client):
        with patch.dict(os.environ, {'ENVIRONMENT': 'prod'}):
            with pytest.raises(Exception, match="Failed to load required secrets"):
                load_secrets()


@mock_aws
def test_load_secrets_optional_missing():
    """Test that optional secrets can be missing."""
    client = boto3.client('ssm', region_name='us-east-1')
    
    # Create only required parameters
    client.put_parameter(
        Name='/agenticai/prod/gemini-api-key',
        Value='gemini-key',
        Type='SecureString'
    )
    client.put_parameter(
        Name='/agenticai/prod/jwt-secret',
        Value='jwt-secret',
        Type='SecureString'
    )
    # Don't create github-token (optional)
    
    from lambda.shared.parameter_store import load_secrets, clear_cache
    clear_cache()
    
    with patch('lambda.shared.parameter_store.ssm_client', client):
        with patch.dict(os.environ, {'ENVIRONMENT': 'prod'}):
            secrets = load_secrets()
            
            assert secrets['gemini_api_key'] == 'gemini-key'
            assert secrets['jwt_secret'] == 'jwt-secret'
            assert secrets['github_token'] is None


@mock_aws
def test_clear_cache():
    """Test cache clearing functionality."""
    client = boto3.client('ssm', region_name='us-east-1')
    client.put_parameter(Name='/test/param', Value='value1', Type='String')
    
    from lambda.shared.parameter_store import get_parameter, clear_cache
    clear_cache()
    
    with patch('lambda.shared.parameter_store.ssm_client', client):
        # Get parameter
        value1 = get_parameter('/test/param')
        assert value1 == 'value1'
        
        # Update parameter
        client.put_parameter(Name='/test/param', Value='value2', Type='String', Overwrite=True)
        
        # Should still get cached value
        value2 = get_parameter('/test/param')
        assert value2 == 'value1'
        
        # Clear cache
        clear_cache()
        
        # Should get new value
        value3 = get_parameter('/test/param')
        assert value3 == 'value2'


def test_environment_variable_default():
    """Test that ENVIRONMENT defaults to 'prod'."""
    from lambda.shared.parameter_store import load_secrets, clear_cache
    clear_cache()
    
    with patch('lambda.shared.parameter_store.get_parameter') as mock_get:
        mock_get.side_effect = [
            'gemini-key',  # gemini-api-key
            'jwt-secret',  # jwt-secret
            Exception()    # github-token (optional, fails)
        ]
        
        with patch.dict(os.environ, {}, clear=True):
            secrets = load_secrets()
            
            # Should use 'prod' as default
            mock_get.assert_any_call('/agenticai/prod/gemini-api-key')
            mock_get.assert_any_call('/agenticai/prod/jwt-secret')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
