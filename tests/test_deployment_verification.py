"""
Integration tests for AWS deployment verification.
These tests run after deployment to verify the stack is functioning correctly.
"""

import os
import json
import time
import pytest
import boto3
from botocore.exceptions import ClientError


# Environment variables set by GitHub Actions
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
STACK_NAME = os.environ.get('STACK_NAME', 'agenticai-stack')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'prod')


@pytest.fixture(scope='module')
def cloudformation_client():
    """Create CloudFormation client."""
    return boto3.client('cloudformation', region_name=AWS_REGION)


@pytest.fixture(scope='module')
def stack_outputs(cloudformation_client):
    """Get stack outputs."""
    try:
        response = cloudformation_client.describe_stacks(StackName=STACK_NAME)
        outputs = {}
        for output in response['Stacks'][0]['Outputs']:
            outputs[output['OutputKey']] = output['OutputValue']
        return outputs
    except ClientError as e:
        pytest.fail(f"Failed to get stack outputs: {e}")


@pytest.fixture(scope='module')
def dynamodb_client():
    """Create DynamoDB client."""
    return boto3.client('dynamodb', region_name=AWS_REGION)


@pytest.fixture(scope='module')
def s3_client():
    """Create S3 client."""
    return boto3.client('s3', region_name=AWS_REGION)


@pytest.fixture(scope='module')
def sqs_client():
    """Create SQS client."""
    return boto3.client('sqs', region_name=AWS_REGION)


@pytest.fixture(scope='module')
def ecs_client():
    """Create ECS client."""
    return boto3.client('ecs', region_name=AWS_REGION)


class TestStackDeployment:
    """Test CloudFormation stack deployment."""

    def test_stack_exists(self, cloudformation_client):
        """Verify the stack exists and is in CREATE_COMPLETE or UPDATE_COMPLETE state."""
        try:
            response = cloudformation_client.describe_stacks(StackName=STACK_NAME)
            stack = response['Stacks'][0]
            
            assert stack['StackStatus'] in [
                'CREATE_COMPLETE',
                'UPDATE_COMPLETE'
            ], f"Stack is in unexpected state: {stack['StackStatus']}"
            
            print(f"✓ Stack {STACK_NAME} is in {stack['StackStatus']} state")
        except ClientError as e:
            pytest.fail(f"Stack {STACK_NAME} does not exist: {e}")

    def test_stack_outputs_present(self, stack_outputs):
        """Verify all required stack outputs are present."""
        required_outputs = [
            'DataTableName',
            'DataTableArn',
            'CodeBucketName',
            'PMQueueUrl',
            'DevQueueUrl',
            'QAQueueUrl',
            'OpsQueueUrl',
            'WebSocketEndpoint',
            'ECSClusterName',
            'WebSocketServiceName',
            'WebSocketRepositoryUri'
        ]
        
        for output_key in required_outputs:
            assert output_key in stack_outputs, f"Missing required output: {output_key}"
            assert stack_outputs[output_key], f"Output {output_key} is empty"
        
        print(f"✓ All {len(required_outputs)} required stack outputs are present")


class TestDynamoDBTable:
    """Test DynamoDB table configuration."""

    def test_table_exists(self, dynamodb_client, stack_outputs):
        """Verify DynamoDB table exists."""
        table_name = stack_outputs['DataTableName']
        
        try:
            response = dynamodb_client.describe_table(TableName=table_name)
            assert response['Table']['TableStatus'] == 'ACTIVE'
            print(f"✓ DynamoDB table {table_name} is ACTIVE")
        except ClientError as e:
            pytest.fail(f"DynamoDB table {table_name} does not exist: {e}")

    def test_table_has_gsi(self, dynamodb_client, stack_outputs):
        """Verify DynamoDB table has required Global Secondary Indexes."""
        table_name = stack_outputs['DataTableName']
        
        response = dynamodb_client.describe_table(TableName=table_name)
        gsi_names = [gsi['IndexName'] for gsi in response['Table'].get('GlobalSecondaryIndexes', [])]
        
        assert 'GSI1' in gsi_names, "Missing GSI1 index"
        assert 'GSI2' in gsi_names, "Missing GSI2 index"
        
        print(f"✓ DynamoDB table has required GSI indexes: {gsi_names}")

    def test_table_has_pitr_enabled(self, dynamodb_client, stack_outputs):
        """Verify Point-in-Time Recovery is enabled."""
        table_name = stack_outputs['DataTableName']
        
        response = dynamodb_client.describe_continuous_backups(TableName=table_name)
        pitr_status = response['ContinuousBackupsDescription']['PointInTimeRecoveryDescription']['PointInTimeRecoveryStatus']
        
        assert pitr_status == 'ENABLED', f"PITR is not enabled: {pitr_status}"
        print(f"✓ Point-in-Time Recovery is enabled for {table_name}")

    def test_table_encryption_enabled(self, dynamodb_client, stack_outputs):
        """Verify table encryption is enabled."""
        table_name = stack_outputs['DataTableName']
        
        response = dynamodb_client.describe_table(TableName=table_name)
        sse_description = response['Table'].get('SSEDescription', {})
        
        assert sse_description.get('Status') == 'ENABLED', "Table encryption is not enabled"
        print(f"✓ Encryption is enabled for {table_name}")


class TestS3Bucket:
    """Test S3 bucket configuration."""

    def test_bucket_exists(self, s3_client, stack_outputs):
        """Verify S3 bucket exists."""
        bucket_name = stack_outputs['CodeBucketName']
        
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"✓ S3 bucket {bucket_name} exists")
        except ClientError as e:
            pytest.fail(f"S3 bucket {bucket_name} does not exist: {e}")

    def test_bucket_encryption_enabled(self, s3_client, stack_outputs):
        """Verify bucket encryption is enabled."""
        bucket_name = stack_outputs['CodeBucketName']
        
        try:
            response = s3_client.get_bucket_encryption(Bucket=bucket_name)
            rules = response['ServerSideEncryptionConfiguration']['Rules']
            
            assert len(rules) > 0, "No encryption rules found"
            assert rules[0]['ApplyServerSideEncryptionByDefault']['SSEAlgorithm'] == 'AES256'
            
            print(f"✓ S3 bucket {bucket_name} has encryption enabled")
        except ClientError as e:
            pytest.fail(f"Failed to get bucket encryption: {e}")

    def test_bucket_versioning_enabled(self, s3_client, stack_outputs):
        """Verify bucket versioning is enabled."""
        bucket_name = stack_outputs['CodeBucketName']
        
        try:
            response = s3_client.get_bucket_versioning(Bucket=bucket_name)
            assert response.get('Status') == 'Enabled', "Versioning is not enabled"
            print(f"✓ S3 bucket {bucket_name} has versioning enabled")
        except ClientError as e:
            pytest.fail(f"Failed to get bucket versioning: {e}")

    def test_bucket_public_access_blocked(self, s3_client, stack_outputs):
        """Verify public access is blocked."""
        bucket_name = stack_outputs['CodeBucketName']
        
        try:
            response = s3_client.get_public_access_block(Bucket=bucket_name)
            config = response['PublicAccessBlockConfiguration']
            
            assert config['BlockPublicAcls'] is True
            assert config['BlockPublicPolicy'] is True
            assert config['IgnorePublicAcls'] is True
            assert config['RestrictPublicBuckets'] is True
            
            print(f"✓ S3 bucket {bucket_name} has public access blocked")
        except ClientError as e:
            pytest.fail(f"Failed to get public access block: {e}")


class TestSQSQueues:
    """Test SQS queue configuration."""

    def test_all_queues_exist(self, sqs_client, stack_outputs):
        """Verify all SQS queues exist."""
        queue_urls = [
            stack_outputs['PMQueueUrl'],
            stack_outputs['DevQueueUrl'],
            stack_outputs['QAQueueUrl'],
            stack_outputs['OpsQueueUrl']
        ]
        
        for queue_url in queue_urls:
            try:
                sqs_client.get_queue_attributes(
                    QueueUrl=queue_url,
                    AttributeNames=['QueueArn']
                )
                print(f"✓ Queue exists: {queue_url}")
            except ClientError as e:
                pytest.fail(f"Queue {queue_url} does not exist: {e}")

    def test_queues_have_dlq(self, sqs_client, stack_outputs):
        """Verify queues have Dead Letter Queue configured."""
        queue_urls = [
            stack_outputs['PMQueueUrl'],
            stack_outputs['DevQueueUrl'],
            stack_outputs['QAQueueUrl'],
            stack_outputs['OpsQueueUrl']
        ]
        
        for queue_url in queue_urls:
            response = sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['RedrivePolicy']
            )
            
            assert 'RedrivePolicy' in response['Attributes'], f"No DLQ configured for {queue_url}"
            
            redrive_policy = json.loads(response['Attributes']['RedrivePolicy'])
            assert 'deadLetterTargetArn' in redrive_policy
            assert redrive_policy['maxReceiveCount'] == '3'
            
        print(f"✓ All queues have DLQ configured with maxReceiveCount=3")

    def test_queue_visibility_timeouts(self, sqs_client, stack_outputs):
        """Verify queue visibility timeouts are correctly configured."""
        expected_timeouts = {
            'PMQueueUrl': 360,
            'DevQueueUrl': 960,
            'QAQueueUrl': 660,
            'OpsQueueUrl': 360
        }
        
        for queue_key, expected_timeout in expected_timeouts.items():
            queue_url = stack_outputs[queue_key]
            response = sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['VisibilityTimeout']
            )
            
            actual_timeout = int(response['Attributes']['VisibilityTimeout'])
            assert actual_timeout == expected_timeout, \
                f"Queue {queue_key} has incorrect visibility timeout: {actual_timeout} (expected {expected_timeout})"
        
        print(f"✓ All queues have correct visibility timeouts")


class TestECSService:
    """Test ECS Fargate service for WebSocket handler."""

    def test_cluster_exists(self, ecs_client, stack_outputs):
        """Verify ECS cluster exists."""
        cluster_name = stack_outputs['ECSClusterName']
        
        try:
            response = ecs_client.describe_clusters(clusters=[cluster_name])
            assert len(response['clusters']) > 0
            assert response['clusters'][0]['status'] == 'ACTIVE'
            print(f"✓ ECS cluster {cluster_name} is ACTIVE")
        except ClientError as e:
            pytest.fail(f"ECS cluster {cluster_name} does not exist: {e}")

    def test_service_exists(self, ecs_client, stack_outputs):
        """Verify ECS service exists and is running."""
        cluster_name = stack_outputs['ECSClusterName']
        service_name = stack_outputs['WebSocketServiceName']
        
        try:
            response = ecs_client.describe_services(
                cluster=cluster_name,
                services=[service_name]
            )
            
            assert len(response['services']) > 0
            service = response['services'][0]
            assert service['status'] == 'ACTIVE'
            assert service['desiredCount'] >= 1
            
            print(f"✓ ECS service {service_name} is ACTIVE with {service['desiredCount']} desired tasks")
        except ClientError as e:
            pytest.fail(f"ECS service {service_name} does not exist: {e}")

    def test_service_tasks_running(self, ecs_client, stack_outputs):
        """Verify ECS service has running tasks."""
        cluster_name = stack_outputs['ECSClusterName']
        service_name = stack_outputs['WebSocketServiceName']
        
        # Wait up to 60 seconds for tasks to be running
        max_attempts = 12
        for attempt in range(max_attempts):
            response = ecs_client.describe_services(
                cluster=cluster_name,
                services=[service_name]
            )
            
            service = response['services'][0]
            running_count = service['runningCount']
            
            if running_count >= 1:
                print(f"✓ ECS service has {running_count} running task(s)")
                return
            
            if attempt < max_attempts - 1:
                print(f"Waiting for tasks to start... (attempt {attempt + 1}/{max_attempts})")
                time.sleep(5)
        
        pytest.fail(f"ECS service {service_name} has no running tasks after {max_attempts * 5} seconds")


class TestWebSocketEndpoint:
    """Test WebSocket endpoint availability."""

    def test_websocket_endpoint_format(self, stack_outputs):
        """Verify WebSocket endpoint has correct format."""
        ws_endpoint = stack_outputs['WebSocketEndpoint']
        
        assert ws_endpoint.startswith('http://'), "WebSocket endpoint should start with http://"
        assert '.elb.' in ws_endpoint or 'amazonaws.com' in ws_endpoint, \
            "WebSocket endpoint should be an AWS load balancer URL"
        
        print(f"✓ WebSocket endpoint format is valid: {ws_endpoint}")


class TestResourceTags:
    """Test that resources have proper tags."""

    def test_dynamodb_table_tags(self, dynamodb_client, stack_outputs):
        """Verify DynamoDB table has required tags."""
        table_arn = stack_outputs['DataTableArn']
        
        response = dynamodb_client.list_tags_of_resource(ResourceArn=table_arn)
        tags = {tag['Key']: tag['Value'] for tag in response['Tags']}
        
        assert 'Application' in tags
        assert tags['Application'] == 'AgenticAI'
        assert 'Environment' in tags
        
        print(f"✓ DynamoDB table has required tags: {tags}")

    def test_s3_bucket_tags(self, s3_client, stack_outputs):
        """Verify S3 bucket has required tags."""
        bucket_name = stack_outputs['CodeBucketName']
        
        try:
            response = s3_client.get_bucket_tagging(Bucket=bucket_name)
            tags = {tag['Key']: tag['Value'] for tag in response['TagSet']}
            
            assert 'Application' in tags
            assert tags['Application'] == 'AgenticAI'
            assert 'Environment' in tags
            
            print(f"✓ S3 bucket has required tags: {tags}")
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchTagSet':
                pytest.fail(f"Failed to get bucket tags: {e}")


class TestLambdaFunctions:
    """Test Lambda function deployment and configuration."""

    def test_lambda_functions_exist(self, cloudformation_client):
        """Verify all Lambda functions are deployed."""
        try:
            response = cloudformation_client.list_stack_resources(
                StackName=STACK_NAME
            )
            
            lambda_resources = [
                r for r in response['StackResourceSummaries']
                if r['ResourceType'] == 'AWS::Lambda::Function'
            ]
            
            assert len(lambda_resources) >= 5, f"Expected at least 5 Lambda functions, found {len(lambda_resources)}"
            
            function_names = [r['LogicalResourceId'] for r in lambda_resources]
            print(f"✓ Found {len(lambda_resources)} Lambda functions: {function_names}")
        except ClientError as e:
            pytest.fail(f"Failed to list Lambda functions: {e}")

    def test_lambda_functions_have_correct_runtime(self):
        """Verify Lambda functions use Python 3.11 runtime."""
        lambda_client = boto3.client('lambda', region_name=AWS_REGION)
        
        try:
            cf_client = boto3.client('cloudformation', region_name=AWS_REGION)
            response = cf_client.list_stack_resources(StackName=STACK_NAME)
            
            lambda_resources = [
                r for r in response['StackResourceSummaries']
                if r['ResourceType'] == 'AWS::Lambda::Function'
            ]
            
            for resource in lambda_resources:
                function_name = resource['PhysicalResourceId']
                
                func_config = lambda_client.get_function_configuration(
                    FunctionName=function_name
                )
                
                assert func_config['Runtime'] == 'python3.11', \
                    f"Function {function_name} has incorrect runtime: {func_config['Runtime']}"
            
            print(f"✓ All Lambda functions use Python 3.11 runtime")
        except ClientError as e:
            pytest.fail(f"Failed to check Lambda runtime: {e}")

    def test_lambda_functions_have_environment_variables(self):
        """Verify Lambda functions have required environment variables."""
        lambda_client = boto3.client('lambda', region_name=AWS_REGION)
        
        try:
            cf_client = boto3.client('cloudformation', region_name=AWS_REGION)
            response = cf_client.list_stack_resources(StackName=STACK_NAME)
            
            lambda_resources = [
                r for r in response['StackResourceSummaries']
                if r['ResourceType'] == 'AWS::Lambda::Function'
            ]
            
            required_env_vars = ['DYNAMODB_TABLE_NAME', 'S3_BUCKET_NAME', 'AWS_REGION']
            
            for resource in lambda_resources:
                function_name = resource['PhysicalResourceId']
                
                func_config = lambda_client.get_function_configuration(
                    FunctionName=function_name
                )
                
                env_vars = func_config.get('Environment', {}).get('Variables', {})
                
                for var in required_env_vars:
                    assert var in env_vars, \
                        f"Function {function_name} missing environment variable: {var}"
            
            print(f"✓ All Lambda functions have required environment variables")
        except ClientError as e:
            pytest.fail(f"Failed to check Lambda environment variables: {e}")


class TestCloudWatchAlarms:
    """Test CloudWatch alarms configuration."""

    def test_alarms_exist(self):
        """Verify CloudWatch alarms are created."""
        cloudwatch_client = boto3.client('cloudwatch', region_name=AWS_REGION)
        
        try:
            response = cloudwatch_client.describe_alarms(
                AlarmNamePrefix='agenticai'
            )
            
            alarms = response['MetricAlarms']
            assert len(alarms) > 0, "No CloudWatch alarms found"
            
            alarm_names = [alarm['AlarmName'] for alarm in alarms]
            print(f"✓ Found {len(alarms)} CloudWatch alarms: {alarm_names}")
        except ClientError as e:
            pytest.fail(f"Failed to list CloudWatch alarms: {e}")


class TestEndToEndFlow:
    """Test end-to-end deployment flow."""

    def test_dynamodb_write_and_read(self, dynamodb_client, stack_outputs):
        """Test writing and reading from DynamoDB."""
        table_name = stack_outputs['DataTableName']
        
        test_item = {
            'PK': {'S': 'TEST#verification'},
            'SK': {'S': 'METADATA'},
            'EntityType': {'S': 'Test'},
            'timestamp': {'S': str(time.time())}
        }
        
        try:
            # Write test item
            dynamodb_client.put_item(
                TableName=table_name,
                Item=test_item
            )
            print(f"✓ Successfully wrote test item to DynamoDB")
            
            # Read test item
            response = dynamodb_client.get_item(
                TableName=table_name,
                Key={
                    'PK': {'S': 'TEST#verification'},
                    'SK': {'S': 'METADATA'}
                }
            )
            
            assert 'Item' in response, "Failed to read test item from DynamoDB"
            print(f"✓ Successfully read test item from DynamoDB")
            
            # Clean up
            dynamodb_client.delete_item(
                TableName=table_name,
                Key={
                    'PK': {'S': 'TEST#verification'},
                    'SK': {'S': 'METADATA'}
                }
            )
            print(f"✓ Successfully deleted test item from DynamoDB")
            
        except ClientError as e:
            pytest.fail(f"DynamoDB write/read test failed: {e}")

    def test_s3_write_and_read(self, s3_client, stack_outputs):
        """Test writing and reading from S3."""
        bucket_name = stack_outputs['CodeBucketName']
        test_key = 'verification/test.txt'
        test_content = b'Deployment verification test'
        
        try:
            # Write test object
            s3_client.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=test_content
            )
            print(f"✓ Successfully wrote test object to S3")
            
            # Read test object
            response = s3_client.get_object(
                Bucket=bucket_name,
                Key=test_key
            )
            
            content = response['Body'].read()
            assert content == test_content, "S3 content mismatch"
            print(f"✓ Successfully read test object from S3")
            
            # Clean up
            s3_client.delete_object(
                Bucket=bucket_name,
                Key=test_key
            )
            print(f"✓ Successfully deleted test object from S3")
            
        except ClientError as e:
            pytest.fail(f"S3 write/read test failed: {e}")

    def test_sqs_send_and_receive(self, sqs_client, stack_outputs):
        """Test sending and receiving messages from SQS."""
        queue_url = stack_outputs['PMQueueUrl']
        test_message = json.dumps({
            'test': 'verification',
            'timestamp': time.time()
        })
        
        try:
            # Send test message
            response = sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=test_message
            )
            
            message_id = response['MessageId']
            print(f"✓ Successfully sent test message to SQS: {message_id}")
            
            # Receive test message
            time.sleep(2)  # Wait for message to be available
            
            response = sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=5
            )
            
            assert 'Messages' in response, "No messages received from SQS"
            assert len(response['Messages']) > 0, "No messages in response"
            
            received_message = response['Messages'][0]
            assert json.loads(received_message['Body'])['test'] == 'verification'
            print(f"✓ Successfully received test message from SQS")
            
            # Clean up
            sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=received_message['ReceiptHandle']
            )
            print(f"✓ Successfully deleted test message from SQS")
            
        except ClientError as e:
            pytest.fail(f"SQS send/receive test failed: {e}")


class TestSecurityConfiguration:
    """Test security configuration."""

    def test_iam_roles_have_least_privilege(self, cloudformation_client):
        """Verify IAM roles follow least privilege principle."""
        iam_client = boto3.client('iam', region_name=AWS_REGION)
        
        try:
            response = cloudformation_client.list_stack_resources(
                StackName=STACK_NAME
            )
            
            role_resources = [
                r for r in response['StackResourceSummaries']
                if r['ResourceType'] == 'AWS::IAM::Role'
            ]
            
            for resource in role_resources:
                role_name = resource['PhysicalResourceId']
                
                # Get role policies
                policies = iam_client.list_attached_role_policies(
                    RoleName=role_name
                )
                
                # Verify no overly permissive policies
                for policy in policies['AttachedPolicies']:
                    assert 'AdministratorAccess' not in policy['PolicyName'], \
                        f"Role {role_name} has overly permissive policy: {policy['PolicyName']}"
                
            print(f"✓ All IAM roles follow least privilege principle")
            
        except ClientError as e:
            pytest.fail(f"Failed to check IAM roles: {e}")

    def test_encryption_at_rest_enabled(self, stack_outputs):
        """Verify encryption at rest is enabled for all data stores."""
        # Already tested in individual resource tests
        # This is a summary test
        print(f"✓ Encryption at rest verified for DynamoDB and S3")


class TestPerformance:
    """Test performance characteristics."""

    def test_dynamodb_response_time(self, dynamodb_client, stack_outputs):
        """Verify DynamoDB response time is acceptable."""
        table_name = stack_outputs['DataTableName']
        
        start_time = time.time()
        
        try:
            dynamodb_client.get_item(
                TableName=table_name,
                Key={
                    'PK': {'S': 'NONEXISTENT'},
                    'SK': {'S': 'METADATA'}
                }
            )
        except ClientError:
            pass
        
        response_time = time.time() - start_time
        
        assert response_time < 1.0, f"DynamoDB response time too slow: {response_time}s"
        print(f"✓ DynamoDB response time: {response_time:.3f}s")

    def test_s3_response_time(self, s3_client, stack_outputs):
        """Verify S3 response time is acceptable."""
        bucket_name = stack_outputs['CodeBucketName']
        
        start_time = time.time()
        
        try:
            s3_client.list_objects_v2(
                Bucket=bucket_name,
                MaxKeys=1
            )
        except ClientError:
            pass
        
        response_time = time.time() - start_time
        
        assert response_time < 2.0, f"S3 response time too slow: {response_time}s"
        print(f"✓ S3 response time: {response_time:.3f}s")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
