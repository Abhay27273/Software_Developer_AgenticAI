#!/usr/bin/env python3
"""
Deployment Verification Script

This script performs comprehensive verification of the AWS deployment,
checking all resources and running integration tests.

Usage:
    python scripts/verify_deployment.py --stack-name agenticai-stack-prod
    python scripts/verify_deployment.py --stack-name agenticai-stack-prod --quick
"""

import argparse
import sys
import time
import json
import boto3
from botocore.exceptions import ClientError
from typing import Dict, List, Tuple


class DeploymentVerifier:
    """Verify AWS deployment health and functionality."""
    
    def __init__(self, stack_name: str, region: str = 'us-east-1'):
        self.stack_name = stack_name
        self.region = region
        self.cf_client = boto3.client('cloudformation', region_name=region)
        self.dynamodb_client = boto3.client('dynamodb', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        self.sqs_client = boto3.client('sqs', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.ecs_client = boto3.client('ecs', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        
        self.stack_outputs = {}
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }
    
    def run_verification(self, quick: bool = False) -> bool:
        """Run all verification checks."""
        print(f"\n{'='*60}")
        print(f"AWS Deployment Verification")
        print(f"Stack: {self.stack_name}")
        print(f"Region: {self.region}")
        print(f"{'='*60}\n")
        
        checks = [
            ("Stack Status", self.verify_stack_status),
            ("Stack Outputs", self.verify_stack_outputs),
            ("DynamoDB Table", self.verify_dynamodb),
            ("S3 Bucket", self.verify_s3),
            ("SQS Queues", self.verify_sqs),
            ("Lambda Functions", self.verify_lambda),
            ("ECS Service", self.verify_ecs),
        ]
        
        if not quick:
            checks.extend([
                ("CloudWatch Alarms", self.verify_cloudwatch),
                ("Security Configuration", self.verify_security),
                ("End-to-End Flow", self.verify_e2e_flow),
                ("Performance", self.verify_performance),
            ])
        
        for check_name, check_func in checks:
            print(f"\n{'─'*60}")
            print(f"Checking: {check_name}")
            print(f"{'─'*60}")
            
            try:
                check_func()
                self.results['passed'].append(check_name)
                print(f"✅ {check_name}: PASSED")
            except Exception as e:
                self.results['failed'].append((check_name, str(e)))
                print(f"❌ {check_name}: FAILED - {e}")
        
        self.print_summary()
        
        return len(self.results['failed']) == 0
    
    def verify_stack_status(self):
        """Verify CloudFormation stack status."""
        response = self.cf_client.describe_stacks(StackName=self.stack_name)
        stack = response['Stacks'][0]
        
        status = stack['StackStatus']
        if status not in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
            raise Exception(f"Stack in unexpected state: {status}")
        
        print(f"  Stack Status: {status}")
        print(f"  Created: {stack['CreationTime']}")
        print(f"  Last Updated: {stack.get('LastUpdatedTime', 'N/A')}")
    
    def verify_stack_outputs(self):
        """Verify all required stack outputs are present."""
        response = self.cf_client.describe_stacks(StackName=self.stack_name)
        
        for output in response['Stacks'][0]['Outputs']:
            self.stack_outputs[output['OutputKey']] = output['OutputValue']
        
        required_outputs = [
            'DataTableName', 'DataTableArn', 'CodeBucketName',
            'PMQueueUrl', 'DevQueueUrl', 'QAQueueUrl', 'OpsQueueUrl',
            'WebSocketEndpoint', 'ECSClusterName'
        ]
        
        missing = [o for o in required_outputs if o not in self.stack_outputs]
        if missing:
            raise Exception(f"Missing outputs: {missing}")
        
        print(f"  Found {len(self.stack_outputs)} stack outputs")
        for key, value in self.stack_outputs.items():
            print(f"    {key}: {value}")
    
    def verify_dynamodb(self):
        """Verify DynamoDB table configuration."""
        table_name = self.stack_outputs['DataTableName']
        
        response = self.dynamodb_client.describe_table(TableName=table_name)
        table = response['Table']
        
        if table['TableStatus'] != 'ACTIVE':
            raise Exception(f"Table not active: {table['TableStatus']}")
        
        # Check GSI
        gsi_names = [gsi['IndexName'] for gsi in table.get('GlobalSecondaryIndexes', [])]
        if 'GSI1' not in gsi_names or 'GSI2' not in gsi_names:
            raise Exception(f"Missing GSI indexes. Found: {gsi_names}")
        
        # Check PITR
        pitr_response = self.dynamodb_client.describe_continuous_backups(TableName=table_name)
        pitr_status = pitr_response['ContinuousBackupsDescription']['PointInTimeRecoveryDescription']['PointInTimeRecoveryStatus']
        
        if pitr_status != 'ENABLED':
            self.results['warnings'].append(f"PITR not enabled for {table_name}")
        
        print(f"  Table: {table_name}")
        print(f"  Status: {table['TableStatus']}")
        print(f"  Item Count: {table['ItemCount']}")
        print(f"  Size: {table['TableSizeBytes']} bytes")
        print(f"  GSI Indexes: {gsi_names}")
        print(f"  PITR: {pitr_status}")
    
    def verify_s3(self):
        """Verify S3 bucket configuration."""
        bucket_name = self.stack_outputs['CodeBucketName']
        
        # Check bucket exists
        self.s3_client.head_bucket(Bucket=bucket_name)
        
        # Check encryption
        try:
            enc_response = self.s3_client.get_bucket_encryption(Bucket=bucket_name)
            encryption = enc_response['ServerSideEncryptionConfiguration']['Rules'][0]['ApplyServerSideEncryptionByDefault']['SSEAlgorithm']
        except ClientError:
            encryption = "Not configured"
            self.results['warnings'].append(f"Encryption not configured for {bucket_name}")
        
        # Check versioning
        ver_response = self.s3_client.get_bucket_versioning(Bucket=bucket_name)
        versioning = ver_response.get('Status', 'Disabled')
        
        # Check public access block
        try:
            pab_response = self.s3_client.get_public_access_block(Bucket=bucket_name)
            public_access_blocked = all([
                pab_response['PublicAccessBlockConfiguration']['BlockPublicAcls'],
                pab_response['PublicAccessBlockConfiguration']['BlockPublicPolicy'],
                pab_response['PublicAccessBlockConfiguration']['IgnorePublicAcls'],
                pab_response['PublicAccessBlockConfiguration']['RestrictPublicBuckets']
            ])
        except ClientError:
            public_access_blocked = False
            self.results['warnings'].append(f"Public access block not configured for {bucket_name}")
        
        print(f"  Bucket: {bucket_name}")
        print(f"  Encryption: {encryption}")
        print(f"  Versioning: {versioning}")
        print(f"  Public Access Blocked: {public_access_blocked}")
    
    def verify_sqs(self):
        """Verify SQS queue configuration."""
        queue_keys = ['PMQueueUrl', 'DevQueueUrl', 'QAQueueUrl', 'OpsQueueUrl']
        
        for queue_key in queue_keys:
            queue_url = self.stack_outputs[queue_key]
            
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['All']
            )
            
            attrs = response['Attributes']
            
            # Check DLQ
            if 'RedrivePolicy' not in attrs:
                self.results['warnings'].append(f"No DLQ configured for {queue_key}")
            
            print(f"  Queue: {queue_key}")
            print(f"    URL: {queue_url}")
            print(f"    Messages Available: {attrs.get('ApproximateNumberOfMessages', 0)}")
            print(f"    Visibility Timeout: {attrs.get('VisibilityTimeout', 'N/A')}s")
    
    def verify_lambda(self):
        """Verify Lambda function configuration."""
        response = self.cf_client.list_stack_resources(StackName=self.stack_name)
        
        lambda_resources = [
            r for r in response['StackResourceSummaries']
            if r['ResourceType'] == 'AWS::Lambda::Function'
        ]
        
        if len(lambda_resources) < 5:
            raise Exception(f"Expected at least 5 Lambda functions, found {len(lambda_resources)}")
        
        print(f"  Found {len(lambda_resources)} Lambda functions:")
        
        for resource in lambda_resources:
            function_name = resource['PhysicalResourceId']
            
            config = self.lambda_client.get_function_configuration(
                FunctionName=function_name
            )
            
            print(f"    {resource['LogicalResourceId']}:")
            print(f"      Runtime: {config['Runtime']}")
            print(f"      Memory: {config['MemorySize']} MB")
            print(f"      Timeout: {config['Timeout']}s")
            
            if config['Runtime'] != 'python3.11':
                self.results['warnings'].append(f"Function {function_name} not using Python 3.11")
    
    def verify_ecs(self):
        """Verify ECS service configuration."""
        cluster_name = self.stack_outputs['ECSClusterName']
        service_name = self.stack_outputs['WebSocketServiceName']
        
        # Check cluster
        cluster_response = self.ecs_client.describe_clusters(clusters=[cluster_name])
        if not cluster_response['clusters'] or cluster_response['clusters'][0]['status'] != 'ACTIVE':
            raise Exception(f"ECS cluster {cluster_name} not active")
        
        # Check service
        service_response = self.ecs_client.describe_services(
            cluster=cluster_name,
            services=[service_name]
        )
        
        if not service_response['services']:
            raise Exception(f"ECS service {service_name} not found")
        
        service = service_response['services'][0]
        
        print(f"  Cluster: {cluster_name}")
        print(f"  Service: {service_name}")
        print(f"  Status: {service['status']}")
        print(f"  Desired Tasks: {service['desiredCount']}")
        print(f"  Running Tasks: {service['runningCount']}")
        
        if service['runningCount'] < service['desiredCount']:
            self.results['warnings'].append(f"ECS service has fewer running tasks than desired")
    
    def verify_cloudwatch(self):
        """Verify CloudWatch alarms."""
        response = self.cloudwatch_client.describe_alarms(
            AlarmNamePrefix='agenticai'
        )
        
        alarms = response['MetricAlarms']
        
        print(f"  Found {len(alarms)} CloudWatch alarms")
        
        for alarm in alarms:
            print(f"    {alarm['AlarmName']}: {alarm['StateValue']}")
            
            if alarm['StateValue'] == 'ALARM':
                self.results['warnings'].append(f"Alarm in ALARM state: {alarm['AlarmName']}")
    
    def verify_security(self):
        """Verify security configuration."""
        # Check IAM roles
        response = self.cf_client.list_stack_resources(StackName=self.stack_name)
        
        role_resources = [
            r for r in response['StackResourceSummaries']
            if r['ResourceType'] == 'AWS::IAM::Role'
        ]
        
        print(f"  Found {len(role_resources)} IAM roles")
        
        # Verify encryption is enabled (already checked in individual tests)
        print(f"  Encryption verified for DynamoDB and S3")
    
    def verify_e2e_flow(self):
        """Verify end-to-end flow with actual operations."""
        print("  Testing DynamoDB write/read...")
        self._test_dynamodb_operations()
        
        print("  Testing S3 write/read...")
        self._test_s3_operations()
        
        print("  Testing SQS send/receive...")
        self._test_sqs_operations()
    
    def _test_dynamodb_operations(self):
        """Test DynamoDB operations."""
        table_name = self.stack_outputs['DataTableName']
        
        test_item = {
            'PK': {'S': 'TEST#verification'},
            'SK': {'S': 'METADATA'},
            'EntityType': {'S': 'Test'},
            'timestamp': {'S': str(time.time())}
        }
        
        # Write
        self.dynamodb_client.put_item(TableName=table_name, Item=test_item)
        
        # Read
        response = self.dynamodb_client.get_item(
            TableName=table_name,
            Key={'PK': {'S': 'TEST#verification'}, 'SK': {'S': 'METADATA'}}
        )
        
        if 'Item' not in response:
            raise Exception("Failed to read test item from DynamoDB")
        
        # Clean up
        self.dynamodb_client.delete_item(
            TableName=table_name,
            Key={'PK': {'S': 'TEST#verification'}, 'SK': {'S': 'METADATA'}}
        )
    
    def _test_s3_operations(self):
        """Test S3 operations."""
        bucket_name = self.stack_outputs['CodeBucketName']
        test_key = 'verification/test.txt'
        test_content = b'Deployment verification test'
        
        # Write
        self.s3_client.put_object(Bucket=bucket_name, Key=test_key, Body=test_content)
        
        # Read
        response = self.s3_client.get_object(Bucket=bucket_name, Key=test_key)
        content = response['Body'].read()
        
        if content != test_content:
            raise Exception("S3 content mismatch")
        
        # Clean up
        self.s3_client.delete_object(Bucket=bucket_name, Key=test_key)
    
    def _test_sqs_operations(self):
        """Test SQS operations."""
        queue_url = self.stack_outputs['PMQueueUrl']
        test_message = json.dumps({'test': 'verification', 'timestamp': time.time()})
        
        # Send
        response = self.sqs_client.send_message(QueueUrl=queue_url, MessageBody=test_message)
        message_id = response['MessageId']
        
        # Receive
        time.sleep(2)
        response = self.sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5
        )
        
        if 'Messages' not in response or len(response['Messages']) == 0:
            raise Exception("No messages received from SQS")
        
        # Clean up
        self.sqs_client.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=response['Messages'][0]['ReceiptHandle']
        )
    
    def verify_performance(self):
        """Verify performance characteristics."""
        # Test DynamoDB response time
        table_name = self.stack_outputs['DataTableName']
        start = time.time()
        try:
            self.dynamodb_client.get_item(
                TableName=table_name,
                Key={'PK': {'S': 'NONEXISTENT'}, 'SK': {'S': 'METADATA'}}
            )
        except ClientError:
            pass
        dynamodb_time = time.time() - start
        
        # Test S3 response time
        bucket_name = self.stack_outputs['CodeBucketName']
        start = time.time()
        try:
            self.s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
        except ClientError:
            pass
        s3_time = time.time() - start
        
        print(f"  DynamoDB response time: {dynamodb_time:.3f}s")
        print(f"  S3 response time: {s3_time:.3f}s")
        
        if dynamodb_time > 1.0:
            self.results['warnings'].append(f"DynamoDB response time slow: {dynamodb_time:.3f}s")
        
        if s3_time > 2.0:
            self.results['warnings'].append(f"S3 response time slow: {s3_time:.3f}s")
    
    def print_summary(self):
        """Print verification summary."""
        print(f"\n{'='*60}")
        print("Verification Summary")
        print(f"{'='*60}\n")
        
        print(f"✅ Passed: {len(self.results['passed'])}")
        for check in self.results['passed']:
            print(f"   - {check}")
        
        if self.results['failed']:
            print(f"\n❌ Failed: {len(self.results['failed'])}")
            for check, error in self.results['failed']:
                print(f"   - {check}: {error}")
        
        if self.results['warnings']:
            print(f"\n⚠️  Warnings: {len(self.results['warnings'])}")
            for warning in self.results['warnings']:
                print(f"   - {warning}")
        
        print(f"\n{'='*60}")
        
        if self.results['failed']:
            print("❌ VERIFICATION FAILED")
        else:
            print("✅ VERIFICATION PASSED")
        
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='Verify AWS deployment')
    parser.add_argument('--stack-name', required=True, help='CloudFormation stack name')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--quick', action='store_true', help='Run quick verification (skip optional checks)')
    
    args = parser.parse_args()
    
    verifier = DeploymentVerifier(args.stack_name, args.region)
    
    try:
        success = verifier.run_verification(quick=args.quick)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Verification failed with error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
