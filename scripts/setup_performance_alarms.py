#!/usr/bin/env python3
"""
Performance Alarms Setup Script

Creates CloudWatch alarms for performance monitoring:
- Lambda duration > 10 seconds
- API Gateway latency > 3 seconds for 5 minutes

Requirements: 4.1, 4.2
"""

import boto3
import json
import sys
from typing import Dict, List, Optional


class PerformanceAlarmsSetup:
    """Setup performance monitoring alarms for AgenticAI"""
    
    def __init__(self, region: str = 'us-east-1', stack_name: str = 'agenticai-stack', environment: str = 'prod'):
        self.region = region
        self.stack_name = stack_name
        self.environment = environment
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.cloudformation = boto3.client('cloudformation', region_name=region)
        self.sns = boto3.client('sns', region_name=region)
        
        # Get resource names from CloudFormation stack
        self.resources = self._get_stack_resources()
        self.sns_topic_arn = self._get_sns_topic_arn()
    
    def _get_stack_resources(self) -> Dict[str, str]:
        """Get resource names from CloudFormation stack"""
        resources = {}
        
        try:
            response = self.cloudformation.describe_stack_resources(
                StackName=self.stack_name
            )
            
            for resource in response['StackResources']:
                resource_type = resource['ResourceType']
                physical_id = resource['PhysicalResourceId']
                logical_id = resource['LogicalId']
                
                if resource_type == 'AWS::Lambda::Function':
                    resources[logical_id] = physical_id
                elif resource_type == 'AWS::ApiGateway::RestApi':
                    resources['ApiGateway'] = physical_id
                elif resource_type == 'AWS::ApiGateway::Stage':
                    resources['ApiStage'] = physical_id
            
            print(f"✓ Found {len(resources)} resources in stack")
            return resources
            
        except Exception as e:
            print(f"⚠ Warning: Could not get stack resources: {e}")
            print("Using default resource names...")
            return {
                'ApiHandlerFunction': 'agenticai-stack-ApiHandlerFunction',
                'PMAgentFunction': 'agenticai-stack-PMAgentFunction',
                'DevAgentFunction': 'agenticai-stack-DevAgentFunction',
                'QAAgentFunction': 'agenticai-stack-QAAgentFunction',
                'OpsAgentFunction': 'agenticai-stack-OpsAgentFunction',
                'ApiGateway': 'agenticai-api',
                'ApiStage': 'Prod'
            }
    
    def _get_sns_topic_arn(self) -> Optional[str]:
        """Get SNS topic ARN for alerts"""
        try:
            # Try to find existing SNS topic
            response = self.sns.list_topics()
            for topic in response['Topics']:
                if 'agenticai-alerts' in topic['TopicArn']:
                    print(f"✓ Found SNS topic: {topic['TopicArn']}")
                    return topic['TopicArn']
            
            print("⚠ Warning: SNS topic 'agenticai-alerts' not found")
            print("  Alarms will be created without notifications")
            return None
            
        except Exception as e:
            print(f"⚠ Warning: Could not get SNS topic: {e}")
            return None
    
    def create_lambda_duration_alarms(self) -> bool:
        """Create alarms for Lambda duration > 10 seconds"""
        print("\nCreating Lambda duration alarms...")
        
        lambda_functions = [
            (name, physical_id) for name, physical_id in self.resources.items() 
            if 'Function' in name
        ]
        
        success_count = 0
        
        for logical_name, function_name in lambda_functions:
            alarm_name = f'agenticai-{logical_name.lower()}-duration-{self.environment}'
            
            try:
                alarm_config = {
                    'AlarmName': alarm_name,
                    'AlarmDescription': f'Alert when {logical_name} duration exceeds 10 seconds',
                    'MetricName': 'Duration',
                    'Namespace': 'AWS/Lambda',
                    'Statistic': 'Average',
                    'Period': 60,  # 1 minute
                    'EvaluationPeriods': 1,
                    'Threshold': 10000.0,  # 10 seconds in milliseconds
                    'ComparisonOperator': 'GreaterThanThreshold',
                    'Dimensions': [
                        {
                            'Name': 'FunctionName',
                            'Value': function_name
                        }
                    ],
                    'TreatMissingData': 'notBreaching'
                }
                
                # Add SNS notification if topic exists
                if self.sns_topic_arn:
                    alarm_config['AlarmActions'] = [self.sns_topic_arn]
                
                self.cloudwatch.put_metric_alarm(**alarm_config)
                print(f"  ✓ Created alarm: {alarm_name}")
                success_count += 1
                
            except Exception as e:
                print(f"  ✗ Error creating alarm {alarm_name}: {e}")
        
        print(f"\n✓ Created {success_count}/{len(lambda_functions)} Lambda duration alarms")
        return success_count == len(lambda_functions)
    
    def create_api_gateway_latency_alarm(self) -> bool:
        """Create alarm for API Gateway latency > 3 seconds for 5 minutes"""
        print("\nCreating API Gateway latency alarm...")
        
        alarm_name = f'agenticai-api-gateway-latency-{self.environment}'
        api_name = self.resources.get('ApiGateway', 'agenticai-api')
        stage_name = self.resources.get('ApiStage', 'Prod')
        
        try:
            alarm_config = {
                'AlarmName': alarm_name,
                'AlarmDescription': 'Alert when API Gateway latency exceeds 3 seconds for 5 minutes',
                'MetricName': 'Latency',
                'Namespace': 'AWS/ApiGateway',
                'Statistic': 'Average',
                'Period': 60,  # 1 minute
                'EvaluationPeriods': 5,  # 5 consecutive minutes
                'Threshold': 3000.0,  # 3 seconds in milliseconds
                'ComparisonOperator': 'GreaterThanThreshold',
                'Dimensions': [
                    {
                        'Name': 'ApiName',
                        'Value': api_name
                    }
                ],
                'TreatMissingData': 'notBreaching'
            }
            
            # Add SNS notification if topic exists
            if self.sns_topic_arn:
                alarm_config['AlarmActions'] = [self.sns_topic_arn]
            
            self.cloudwatch.put_metric_alarm(**alarm_config)
            print(f"  ✓ Created alarm: {alarm_name}")
            return True
            
        except Exception as e:
            print(f"  ✗ Error creating alarm {alarm_name}: {e}")
            return False
    
    def verify_alarms(self) -> bool:
        """Verify all performance alarms were created"""
        print("\nVerifying performance alarms...")
        
        # Expected alarms
        lambda_functions = [
            name for name in self.resources.keys() 
            if 'Function' in name
        ]
        
        expected_alarms = [
            f'agenticai-{name.lower()}-duration-{self.environment}'
            for name in lambda_functions
        ]
        expected_alarms.append(f'agenticai-api-gateway-latency-{self.environment}')
        
        all_found = True
        
        for alarm_name in expected_alarms:
            try:
                response = self.cloudwatch.describe_alarms(
                    AlarmNames=[alarm_name]
                )
                
                if response['MetricAlarms']:
                    alarm = response['MetricAlarms'][0]
                    state = alarm['StateValue']
                    print(f"  ✓ {alarm_name}: {state}")
                else:
                    print(f"  ✗ {alarm_name}: Not found")
                    all_found = False
                    
            except Exception as e:
                print(f"  ✗ {alarm_name}: Error - {e}")
                all_found = False
        
        return all_found
    
    def list_performance_alarms(self) -> None:
        """List all performance alarms with details"""
        print("\nPerformance Alarms Summary:")
        print("-" * 60)
        
        try:
            response = self.cloudwatch.describe_alarms(
                AlarmNamePrefix=f'agenticai-'
            )
            
            performance_alarms = [
                alarm for alarm in response['MetricAlarms']
                if 'duration' in alarm['AlarmName'].lower() or 'latency' in alarm['AlarmName'].lower()
            ]
            
            if not performance_alarms:
                print("  No performance alarms found")
                return
            
            for alarm in performance_alarms:
                print(f"\nAlarm: {alarm['AlarmName']}")
                print(f"  State: {alarm['StateValue']}")
                print(f"  Metric: {alarm['MetricName']}")
                print(f"  Threshold: {alarm['Threshold']} ms")
                print(f"  Period: {alarm['Period']} seconds")
                print(f"  Evaluation Periods: {alarm['EvaluationPeriods']}")
                
                if alarm.get('AlarmActions'):
                    print(f"  Notifications: Enabled")
                else:
                    print(f"  Notifications: None")
        
        except Exception as e:
            print(f"  Error listing alarms: {e}")


def main():
    """Main execution function"""
    print("=" * 60)
    print("Performance Alarms Setup for AgenticAI")
    print("=" * 60)
    
    # Parse command line arguments
    region = sys.argv[1] if len(sys.argv) > 1 else 'us-east-1'
    stack_name = sys.argv[2] if len(sys.argv) > 2 else 'agenticai-stack'
    environment = sys.argv[3] if len(sys.argv) > 3 else 'prod'
    
    print(f"\nConfiguration:")
    print(f"  Region: {region}")
    print(f"  Stack Name: {stack_name}")
    print(f"  Environment: {environment}")
    print()
    
    # Create alarms setup instance
    setup = PerformanceAlarmsSetup(region=region, stack_name=stack_name, environment=environment)
    
    # Create Lambda duration alarms
    lambda_success = setup.create_lambda_duration_alarms()
    
    # Create API Gateway latency alarm
    api_success = setup.create_api_gateway_latency_alarm()
    
    # Verify all alarms
    print()
    verified = setup.verify_alarms()
    
    # List all performance alarms
    setup.list_performance_alarms()
    
    # Summary
    print("\n" + "=" * 60)
    if lambda_success and api_success and verified:
        print("✓ Performance Alarms Setup Complete")
        print("=" * 60)
        print("\nAll performance alarms created successfully!")
    else:
        print("⚠ Performance Alarms Setup Completed with Warnings")
        print("=" * 60)
        print("\nSome alarms may not have been created successfully.")
    
    print("\nNext Steps:")
    print("1. View alarms in CloudWatch console")
    print("2. Test alarms by triggering performance issues")
    print("3. Proceed to Task 3.2: Add performance metrics to dashboard")
    print()


if __name__ == '__main__':
    main()
