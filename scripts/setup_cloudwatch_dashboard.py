#!/usr/bin/env python3
"""
CloudWatch Dashboard Setup Script

Creates a comprehensive CloudWatch dashboard for monitoring the AgenticAI system.
Includes metrics for Lambda functions, API Gateway, DynamoDB, and SQS.
"""

import boto3
import json
import sys
from typing import Dict, List, Any


class CloudWatchDashboardSetup:
    """Setup CloudWatch monitoring dashboard for AgenticAI"""
    
    def __init__(self, region: str = 'us-east-1', stack_name: str = 'agenticai-stack'):
        self.region = region
        self.stack_name = stack_name
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.cloudformation = boto3.client('cloudformation', region_name=region)
        
        # Get resource names from CloudFormation stack
        self.resources = self._get_stack_resources()
    
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
                elif resource_type == 'AWS::DynamoDB::Table':
                    resources['DynamoDBTable'] = physical_id
                elif resource_type == 'AWS::SQS::Queue':
                    resources[logical_id] = physical_id
            
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
                'DynamoDBTable': 'agenticai-data',
                'TaskQueue': 'agenticai-task-queue'
            }
    
    def _create_lambda_metrics_widget(self) -> Dict[str, Any]:
        """Create Lambda function metrics widget"""
        lambda_functions = [
            name for name in self.resources.keys() 
            if 'Function' in name
        ]
        
        metrics = []
        
        # Invocations
        for func_name in lambda_functions:
            metrics.append([
                "AWS/Lambda", "Invocations",
                {"stat": "Sum", "label": f"{func_name} Invocations"}
            ])
        
        return {
            "type": "metric",
            "properties": {
                "metrics": metrics,
                "view": "timeSeries",
                "stacked": False,
                "region": self.region,
                "title": "Lambda Invocations",
                "period": 300,
                "yAxis": {
                    "left": {
                        "label": "Count"
                    }
                }
            }
        }
    
    def _create_lambda_errors_widget(self) -> Dict[str, Any]:
        """Create Lambda errors widget"""
        lambda_functions = [
            name for name in self.resources.keys() 
            if 'Function' in name
        ]
        
        metrics = []
        
        for func_name in lambda_functions:
            metrics.append([
                "AWS/Lambda", "Errors",
                {"stat": "Sum", "label": f"{func_name} Errors", "color": "#d62728"}
            ])
        
        return {
            "type": "metric",
            "properties": {
                "metrics": metrics,
                "view": "timeSeries",
                "stacked": False,
                "region": self.region,
                "title": "Lambda Errors",
                "period": 300,
                "yAxis": {
                    "left": {
                        "label": "Count"
                    }
                }
            }
        }
    
    def _create_lambda_duration_widget(self) -> Dict[str, Any]:
        """Create Lambda duration widget"""
        lambda_functions = [
            name for name in self.resources.keys() 
            if 'Function' in name
        ]
        
        metrics = []
        
        for func_name in lambda_functions:
            # p50, p95, p99 percentiles
            metrics.append([
                "AWS/Lambda", "Duration",
                {"stat": "p50", "label": f"{func_name} p50"}
            ])
            metrics.append([
                "...",
                {"stat": "p95", "label": f"{func_name} p95"}
            ])
        
        return {
            "type": "metric",
            "properties": {
                "metrics": metrics,
                "view": "timeSeries",
                "stacked": False,
                "region": self.region,
                "title": "Lambda Duration (p50, p95)",
                "period": 300,
                "yAxis": {
                    "left": {
                        "label": "Milliseconds"
                    }
                }
            }
        }
    
    def _create_api_gateway_requests_widget(self) -> Dict[str, Any]:
        """Create API Gateway requests widget"""
        api_id = self.resources.get('ApiGateway', 'unknown')
        
        return {
            "type": "metric",
            "properties": {
                "metrics": [
                    ["AWS/ApiGateway", "Count", {"stat": "Sum", "label": "Total Requests"}],
                    [".", "4XXError", {"stat": "Sum", "label": "4XX Errors", "color": "#ff7f0e"}],
                    [".", "5XXError", {"stat": "Sum", "label": "5XX Errors", "color": "#d62728"}]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": self.region,
                "title": "API Gateway Requests & Errors",
                "period": 300,
                "yAxis": {
                    "left": {
                        "label": "Count"
                    }
                }
            }
        }
    
    def _create_api_gateway_latency_widget(self) -> Dict[str, Any]:
        """Create API Gateway latency widget"""
        return {
            "type": "metric",
            "properties": {
                "metrics": [
                    ["AWS/ApiGateway", "Latency", {"stat": "p50", "label": "p50 Latency"}],
                    ["...", {"stat": "p95", "label": "p95 Latency"}],
                    ["...", {"stat": "p99", "label": "p99 Latency"}],
                    [".", "IntegrationLatency", {"stat": "Average", "label": "Integration Latency"}]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": self.region,
                "title": "API Gateway Latency",
                "period": 300,
                "yAxis": {
                    "left": {
                        "label": "Milliseconds"
                    }
                }
            }
        }
    
    def _create_dynamodb_capacity_widget(self) -> Dict[str, Any]:
        """Create DynamoDB capacity widget"""
        table_name = self.resources.get('DynamoDBTable', 'agenticai-data')
        
        return {
            "type": "metric",
            "properties": {
                "metrics": [
                    ["AWS/DynamoDB", "ConsumedReadCapacityUnits", 
                     {"stat": "Sum", "label": "Read Capacity"}],
                    [".", "ConsumedWriteCapacityUnits", 
                     {"stat": "Sum", "label": "Write Capacity"}]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": self.region,
                "title": "DynamoDB Capacity Usage",
                "period": 300,
                "yAxis": {
                    "left": {
                        "label": "Units"
                    }
                }
            }
        }
    
    def _create_dynamodb_throttles_widget(self) -> Dict[str, Any]:
        """Create DynamoDB throttles widget"""
        return {
            "type": "metric",
            "properties": {
                "metrics": [
                    ["AWS/DynamoDB", "ReadThrottleEvents", 
                     {"stat": "Sum", "label": "Read Throttles", "color": "#d62728"}],
                    [".", "WriteThrottleEvents", 
                     {"stat": "Sum", "label": "Write Throttles", "color": "#ff7f0e"}]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": self.region,
                "title": "DynamoDB Throttles",
                "period": 300,
                "yAxis": {
                    "left": {
                        "label": "Count"
                    }
                }
            }
        }
    
    def _create_sqs_queue_depth_widget(self) -> Dict[str, Any]:
        """Create SQS queue depth widget"""
        queue_name = self.resources.get('TaskQueue', 'agenticai-task-queue')
        
        return {
            "type": "metric",
            "properties": {
                "metrics": [
                    ["AWS/SQS", "ApproximateNumberOfMessagesVisible",
                     {"stat": "Average", "label": "Messages in Queue"}],
                    [".", "ApproximateAgeOfOldestMessage",
                     {"stat": "Maximum", "label": "Oldest Message Age (s)", "yAxis": "right"}]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": self.region,
                "title": "SQS Queue Metrics",
                "period": 300,
                "yAxis": {
                    "left": {
                        "label": "Message Count"
                    },
                    "right": {
                        "label": "Age (seconds)"
                    }
                }
            }
        }
    
    def _create_lambda_concurrent_executions_widget(self) -> Dict[str, Any]:
        """Create Lambda concurrent executions widget"""
        lambda_functions = [
            name for name in self.resources.keys() 
            if 'Function' in name
        ]
        
        metrics = []
        
        for func_name in lambda_functions:
            metrics.append([
                "AWS/Lambda", "ConcurrentExecutions",
                {"stat": "Maximum", "label": f"{func_name}"}
            ])
        
        return {
            "type": "metric",
            "properties": {
                "metrics": metrics,
                "view": "timeSeries",
                "stacked": False,
                "region": self.region,
                "title": "Lambda Concurrent Executions",
                "period": 300,
                "yAxis": {
                    "left": {
                        "label": "Count"
                    }
                }
            }
        }
    
    def _create_lambda_cold_start_widget(self) -> Dict[str, Any]:
        """Create Lambda cold start metrics widget with 1-minute granularity"""
        lambda_functions = [
            name for name in self.resources.keys() 
            if 'Function' in name
        ]
        
        metrics = []
        
        # Cold starts are indicated by initialization duration
        for func_name in lambda_functions:
            physical_name = self.resources[func_name]
            metrics.append([
                "AWS/Lambda", "Duration",
                {"FunctionName": physical_name},
                {"stat": "Maximum", "label": f"{func_name} Max Duration"}
            ])
        
        return {
            "type": "metric",
            "properties": {
                "metrics": metrics,
                "view": "timeSeries",
                "stacked": False,
                "region": self.region,
                "title": "Lambda Cold Start Metrics (Max Duration)",
                "period": 60,  # 1-minute granularity
                "yAxis": {
                    "left": {
                        "label": "Milliseconds"
                    }
                },
                "annotations": {
                    "horizontal": [
                        {
                            "label": "10s threshold",
                            "value": 10000,
                            "fill": "above",
                            "color": "#d62728"
                        }
                    ]
                }
            }
        }
    
    def _create_api_response_time_percentiles_widget(self) -> Dict[str, Any]:
        """Create API response time percentiles widget with 1-minute granularity"""
        return {
            "type": "metric",
            "properties": {
                "metrics": [
                    ["AWS/ApiGateway", "Latency", {"stat": "p50", "label": "p50 (median)", "color": "#1f77b4"}],
                    ["...", {"stat": "p95", "label": "p95", "color": "#ff7f0e"}],
                    ["...", {"stat": "p99", "label": "p99", "color": "#d62728"}],
                    [".", "IntegrationLatency", {"stat": "p95", "label": "Integration p95", "color": "#9467bd"}]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": self.region,
                "title": "API Response Time Percentiles (p50, p95, p99)",
                "period": 60,  # 1-minute granularity
                "yAxis": {
                    "left": {
                        "label": "Milliseconds"
                    }
                },
                "annotations": {
                    "horizontal": [
                        {
                            "label": "3s threshold",
                            "value": 3000,
                            "fill": "above",
                            "color": "#d62728"
                        }
                    ]
                }
            }
        }
    
    def create_dashboard(self) -> bool:
        """Create the CloudWatch dashboard"""
        dashboard_name = 'AgenticAI-Production'
        
        # Build dashboard body with all widgets
        dashboard_body = {
            "widgets": [
                # Row 1: Lambda Metrics (3 widgets)
                {**self._create_lambda_metrics_widget(), "x": 0, "y": 0, "width": 8, "height": 6},
                {**self._create_lambda_errors_widget(), "x": 8, "y": 0, "width": 8, "height": 6},
                {**self._create_lambda_duration_widget(), "x": 16, "y": 0, "width": 8, "height": 6},
                
                # Row 2: API Gateway Metrics (2 widgets)
                {**self._create_api_gateway_requests_widget(), "x": 0, "y": 6, "width": 12, "height": 6},
                {**self._create_api_gateway_latency_widget(), "x": 12, "y": 6, "width": 12, "height": 6},
                
                # Row 3: Performance Metrics (2 widgets) - NEW
                {**self._create_lambda_cold_start_widget(), "x": 0, "y": 12, "width": 12, "height": 6},
                {**self._create_api_response_time_percentiles_widget(), "x": 12, "y": 12, "width": 12, "height": 6},
                
                # Row 4: DynamoDB Metrics (2 widgets)
                {**self._create_dynamodb_capacity_widget(), "x": 0, "y": 18, "width": 12, "height": 6},
                {**self._create_dynamodb_throttles_widget(), "x": 12, "y": 18, "width": 12, "height": 6},
                
                # Row 5: SQS and Lambda Concurrency (2 widgets)
                {**self._create_sqs_queue_depth_widget(), "x": 0, "y": 24, "width": 12, "height": 6},
                {**self._create_lambda_concurrent_executions_widget(), "x": 12, "y": 24, "width": 12, "height": 6}
            ]
        }
        
        try:
            self.cloudwatch.put_dashboard(
                DashboardName=dashboard_name,
                DashboardBody=json.dumps(dashboard_body)
            )
            
            print(f"\n✓ Successfully created CloudWatch dashboard: {dashboard_name}")
            print(f"  View at: https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={dashboard_name}")
            return True
            
        except Exception as e:
            print(f"\n✗ Error creating dashboard: {e}")
            return False
    
    def verify_dashboard(self) -> bool:
        """Verify the dashboard was created successfully"""
        dashboard_name = 'AgenticAI-Production'
        
        try:
            response = self.cloudwatch.get_dashboard(
                DashboardName=dashboard_name
            )
            
            dashboard_body = json.loads(response['DashboardBody'])
            widget_count = len(dashboard_body.get('widgets', []))
            
            print(f"\n✓ Dashboard verification successful")
            print(f"  Dashboard name: {dashboard_name}")
            print(f"  Widget count: {widget_count}")
            print(f"  Expected widgets: 11")
            
            if widget_count == 11:
                print(f"  Status: ✓ All widgets present")
                return True
            else:
                print(f"  Status: ⚠ Widget count mismatch (expected 11, got {widget_count})")
                return False
                
        except Exception as e:
            print(f"\n✗ Dashboard verification failed: {e}")
            return False


def main():
    """Main execution function"""
    print("=" * 60)
    print("CloudWatch Dashboard Setup for AgenticAI")
    print("=" * 60)
    
    # Parse command line arguments
    region = sys.argv[1] if len(sys.argv) > 1 else 'us-east-1'
    stack_name = sys.argv[2] if len(sys.argv) > 2 else 'agenticai-stack'
    
    print(f"\nConfiguration:")
    print(f"  Region: {region}")
    print(f"  Stack Name: {stack_name}")
    print()
    
    # Create dashboard setup instance
    setup = CloudWatchDashboardSetup(region=region, stack_name=stack_name)
    
    # Create the dashboard
    print("Creating CloudWatch dashboard...")
    success = setup.create_dashboard()
    
    if not success:
        print("\n✗ Dashboard creation failed")
        sys.exit(1)
    
    # Verify the dashboard
    print("\nVerifying dashboard...")
    verified = setup.verify_dashboard()
    
    if not verified:
        print("\n⚠ Dashboard verification had issues")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✓ CloudWatch Dashboard Setup Complete")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. View the dashboard in AWS Console")
    print("2. Verify metrics are displaying correctly")
    print("3. Customize widget layouts if needed")
    print("4. Proceed to Task 2: Implement error alerting system")
    print()


if __name__ == '__main__':
    main()
