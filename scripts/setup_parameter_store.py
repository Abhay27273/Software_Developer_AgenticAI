#!/usr/bin/env python3
"""
Script to initialize AWS Systems Manager Parameter Store with required secrets.
Run this script once during initial AWS setup.

Usage:
    python scripts/setup_parameter_store.py --environment prod
"""

import argparse
import boto3
import sys
from getpass import getpass


def create_parameter(ssm_client, name, value, description, parameter_type='SecureString'):
    """Create or update a parameter in Parameter Store."""
    try:
        ssm_client.put_parameter(
            Name=name,
            Value=value,
            Description=description,
            Type=parameter_type,
            Overwrite=True,
            Tier='Standard'
        )
        print(f"✓ Created/Updated parameter: {name}")
        return True
    except Exception as e:
        print(f"✗ Failed to create parameter {name}: {str(e)}")
        return False


def verify_parameters(ssm_client, parameter_names):
    """Verify that all parameters were created successfully."""
    print("\n🔍 Verifying parameters...\n")
    
    all_verified = True
    for name in parameter_names:
        try:
            response = ssm_client.get_parameter(Name=name, WithDecryption=False)
            param_type = response['Parameter']['Type']
            print(f"✓ {name} ({param_type})")
        except ssm_client.exceptions.ParameterNotFound:
            print(f"✗ {name} - NOT FOUND")
            all_verified = False
        except Exception as e:
            print(f"✗ {name} - ERROR: {str(e)}")
            all_verified = False
    
    return all_verified


def main():
    parser = argparse.ArgumentParser(description='Initialize AWS Parameter Store for AgenticAI')
    parser.add_argument('--environment', '-e', default='prod', 
                       choices=['dev', 'staging', 'prod'],
                       help='Deployment environment')
    parser.add_argument('--region', '-r', default='us-east-1',
                       help='AWS region')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify existing parameters without creating new ones')
    args = parser.parse_args()

    print(f"\n🚀 Setting up Parameter Store for environment: {args.environment}")
    print(f"   Region: {args.region}\n")

    # Initialize AWS SSM client
    try:
        ssm = boto3.client('ssm', region_name=args.region)
        # Test connection
        ssm.describe_parameters(MaxResults=1)
        print("✓ Connected to AWS Systems Manager\n")
    except Exception as e:
        print(f"✗ Failed to connect to AWS: {str(e)}")
        print("  Make sure you have configured AWS credentials (aws configure)")
        sys.exit(1)

    prefix = f"/agenticai/{args.environment}"
    
    # If verify-only mode, just check existing parameters
    if args.verify_only:
        parameter_names = [
            f'{prefix}/gemini-api-key',
            f'{prefix}/jwt-secret',
            f'{prefix}/github-token'
        ]
        all_verified = verify_parameters(ssm, parameter_names)
        if all_verified:
            print("\n✓ All parameters verified successfully")
            sys.exit(0)
        else:
            print("\n✗ Some parameters are missing or inaccessible")
            sys.exit(1)

    # Collect secrets from user
    print("Please provide the following secrets:")
    print("(Press Enter to skip optional parameters)\n")

    secrets = {}

    # Required parameters
    print("Required Parameters:")
    secrets['gemini_api_key'] = getpass("1. Gemini API Key: ")
    if not secrets['gemini_api_key']:
        print("✗ Gemini API Key is required!")
        sys.exit(1)

    # Optional parameters
    print("\nOptional Parameters:")
    secrets['github_token'] = getpass("2. GitHub Token (for repo operations): ")
    secrets['jwt_secret'] = getpass("3. JWT Secret (for authentication): ")
    
    # Generate JWT secret if not provided
    if not secrets['jwt_secret']:
        import secrets as py_secrets
        secrets['jwt_secret'] = py_secrets.token_urlsafe(32)
        print("   Generated random JWT secret")

    # Create parameters
    print("\n📝 Creating parameters in Parameter Store...\n")
    
    success_count = 0
    
    parameters = [
        {
            'name': f'{prefix}/gemini-api-key',
            'value': secrets['gemini_api_key'],
            'description': 'Google Gemini API key for LLM operations'
        },
        {
            'name': f'{prefix}/jwt-secret',
            'value': secrets['jwt_secret'],
            'description': 'JWT secret for authentication tokens'
        }
    ]
    
    # Add optional parameters if provided
    if secrets['github_token']:
        parameters.append({
            'name': f'{prefix}/github-token',
            'value': secrets['github_token'],
            'description': 'GitHub personal access token for repository operations'
        })

    for param in parameters:
        if create_parameter(ssm, param['name'], param['value'], param['description']):
            success_count += 1

    # Summary
    print(f"\n{'='*60}")
    if success_count == len(parameters):
        print(f"✓ Successfully created all {success_count} parameters")
    else:
        print(f"⚠ Created {success_count}/{len(parameters)} parameters")
        print(f"  {len(parameters) - success_count} parameter(s) failed")
    print(f"{'='*60}\n")

    print("Parameter names created:")
    for param in parameters:
        print(f"  - {param['name']}")
    
    # Verify parameters were created
    parameter_names = [p['name'] for p in parameters]
    verify_parameters(ssm, parameter_names)

    print("\n💡 Next steps:")
    print("  1. Verify parameters in AWS Console:")
    print(f"     https://console.aws.amazon.com/systems-manager/parameters?region={args.region}")
    print("  2. Deploy the SAM template:")
    print("     sam build && sam deploy --guided")
    print("  3. Lambda functions will automatically load these parameters")
    print("  4. Update parameters anytime with:")
    print("     aws ssm put-parameter --name <name> --value <value> --overwrite")
    print("\n📚 Documentation:")
    print("  - See docs/AWS_PARAMETER_STORE_SETUP.md for detailed usage")
    print("  - See lambda/shared/README.md for Lambda integration examples")
    print()


if __name__ == '__main__':
    main()
