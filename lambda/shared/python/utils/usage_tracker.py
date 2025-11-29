"""
Usage tracking utility for monitoring AWS resource consumption.

This module provides functions to track and report usage metrics to CloudWatch,
helping monitor free tier limits and optimize costs.
"""

import boto3
import os
from datetime import datetime
from typing import Dict, Optional
from .logger import get_logger

logger = get_logger(__name__)

# Initialize CloudWatch client
cloudwatch = boto3.client('cloudwatch')

# Namespace for custom metrics
NAMESPACE = 'AgenticAI/Usage'


def track_lambda_invocation(function_name: str, duration_ms: float, memory_used_mb: float):
    """
    Track Lambda function invocation metrics.
    
    Args:
        function_name: Name of the Lambda function
        duration_ms: Execution duration in milliseconds
        memory_used_mb: Memory used in megabytes
    """
    try:
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    'MetricName': 'LambdaInvocations',
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': function_name},
                        {'Name': 'Service', 'Value': 'Lambda'}
                    ]
                },
                {
                    'MetricName': 'LambdaDuration',
                    'Value': duration_ms,
                    'Unit': 'Milliseconds',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': function_name},
                        {'Name': 'Service', 'Value': 'Lambda'}
                    ]
                },
                {
                    'MetricName': 'LambdaMemoryUsed',
                    'Value': memory_used_mb,
                    'Unit': 'Megabytes',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': function_name},
                        {'Name': 'Service', 'Value': 'Lambda'}
                    ]
                }
            ]
        )
        logger.debug(f"Tracked Lambda invocation for {function_name}")
    except Exception as e:
        logger.error(f"Failed to track Lambda invocation: {str(e)}")


def track_dynamodb_operation(operation_type: str, table_name: str, item_count: int = 1):
    """
    Track DynamoDB operation metrics.
    
    Args:
        operation_type: Type of operation (read, write, query, scan)
        table_name: Name of the DynamoDB table
        item_count: Number of items processed
    """
    try:
        metric_name = f'DynamoDB{operation_type.capitalize()}Operations'
        
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Value': item_count,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {'Name': 'TableName', 'Value': table_name},
                        {'Name': 'OperationType', 'Value': operation_type},
                        {'Name': 'Service', 'Value': 'DynamoDB'}
                    ]
                }
            ]
        )
        logger.debug(f"Tracked DynamoDB {operation_type} operation on {table_name}")
    except Exception as e:
        logger.error(f"Failed to track DynamoDB operation: {str(e)}")


def track_s3_operation(operation_type: str, bucket_name: str, object_size_bytes: Optional[int] = None):
    """
    Track S3 operation metrics.
    
    Args:
        operation_type: Type of operation (get, put, delete, list)
        bucket_name: Name of the S3 bucket
        object_size_bytes: Size of object in bytes (for put operations)
    """
    try:
        metric_data = [
            {
                'MetricName': f'S3{operation_type.capitalize()}Operations',
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.utcnow(),
                'Dimensions': [
                    {'Name': 'BucketName', 'Value': bucket_name},
                    {'Name': 'OperationType', 'Value': operation_type},
                    {'Name': 'Service', 'Value': 'S3'}
                ]
            }
        ]
        
        # Track object size for PUT operations
        if operation_type == 'put' and object_size_bytes is not None:
            metric_data.append({
                'MetricName': 'S3StorageBytes',
                'Value': object_size_bytes,
                'Unit': 'Bytes',
                'Timestamp': datetime.utcnow(),
                'Dimensions': [
                    {'Name': 'BucketName', 'Value': bucket_name},
                    {'Name': 'Service', 'Value': 'S3'}
                ]
            })
        
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=metric_data
        )
        logger.debug(f"Tracked S3 {operation_type} operation on {bucket_name}")
    except Exception as e:
        logger.error(f"Failed to track S3 operation: {str(e)}")


def track_sqs_operation(operation_type: str, queue_name: str, message_count: int = 1):
    """
    Track SQS operation metrics.
    
    Args:
        operation_type: Type of operation (send, receive, delete)
        queue_name: Name of the SQS queue
        message_count: Number of messages processed
    """
    try:
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    'MetricName': f'SQS{operation_type.capitalize()}Operations',
                    'Value': message_count,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {'Name': 'QueueName', 'Value': queue_name},
                        {'Name': 'OperationType', 'Value': operation_type},
                        {'Name': 'Service', 'Value': 'SQS'}
                    ]
                }
            ]
        )
        logger.debug(f"Tracked SQS {operation_type} operation on {queue_name}")
    except Exception as e:
        logger.error(f"Failed to track SQS operation: {str(e)}")


def track_api_gateway_request(endpoint: str, method: str, status_code: int, duration_ms: float):
    """
    Track API Gateway request metrics.
    
    Args:
        endpoint: API endpoint path
        method: HTTP method
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
    """
    try:
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    'MetricName': 'APIGatewayRequests',
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {'Name': 'Endpoint', 'Value': endpoint},
                        {'Name': 'Method', 'Value': method},
                        {'Name': 'StatusCode', 'Value': str(status_code)},
                        {'Name': 'Service', 'Value': 'APIGateway'}
                    ]
                },
                {
                    'MetricName': 'APIGatewayLatency',
                    'Value': duration_ms,
                    'Unit': 'Milliseconds',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {'Name': 'Endpoint', 'Value': endpoint},
                        {'Name': 'Method', 'Value': method},
                        {'Name': 'Service', 'Value': 'APIGateway'}
                    ]
                }
            ]
        )
        logger.debug(f"Tracked API Gateway request: {method} {endpoint}")
    except Exception as e:
        logger.error(f"Failed to track API Gateway request: {str(e)}")


def get_free_tier_usage_percentage(service: str, metric_name: str, limit: float) -> float:
    """
    Calculate the percentage of free tier usage for a specific metric.
    
    Args:
        service: AWS service name (Lambda, DynamoDB, S3, etc.)
        metric_name: Name of the metric to check
        limit: Free tier limit for the metric
        
    Returns:
        Percentage of free tier used (0-100)
    """
    try:
        # Get metric statistics for the current month
        from datetime import datetime, timedelta
        
        end_time = datetime.utcnow()
        start_time = end_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        response = cloudwatch.get_metric_statistics(
            Namespace=NAMESPACE,
            MetricName=metric_name,
            Dimensions=[{'Name': 'Service', 'Value': service}],
            StartTime=start_time,
            EndTime=end_time,
            Period=86400,  # 1 day
            Statistics=['Sum']
        )
        
        # Calculate total usage
        total_usage = sum(point['Sum'] for point in response['Datapoints'])
        
        # Calculate percentage
        percentage = (total_usage / limit) * 100 if limit > 0 else 0
        
        logger.info(f"{service} {metric_name}: {percentage:.2f}% of free tier used")
        return percentage
        
    except Exception as e:
        logger.error(f"Failed to get free tier usage: {str(e)}")
        return 0.0


def check_free_tier_limits() -> Dict[str, float]:
    """
    Check usage against free tier limits for all services.
    
    Returns:
        Dictionary mapping service metrics to usage percentages
    """
    limits = {
        'Lambda': {
            'LambdaInvocations': 1_000_000,  # 1M requests/month
            'LambdaComputeSeconds': 400_000   # 400K GB-seconds/month
        },
        'DynamoDB': {
            'DynamoDBReadOperations': 25 * 30 * 24 * 3600,  # 25 RCU for 30 days
            'DynamoDBWriteOperations': 25 * 30 * 24 * 3600  # 25 WCU for 30 days
        },
        'S3': {
            'S3GetOperations': 20_000,  # 20K GET requests/month
            'S3PutOperations': 2_000    # 2K PUT requests/month
        },
        'SQS': {
            'SQSSendOperations': 1_000_000  # 1M requests/month
        },
        'APIGateway': {
            'APIGatewayRequests': 1_000_000  # 1M requests/month
        }
    }
    
    usage = {}
    
    for service, metrics in limits.items():
        for metric_name, limit in metrics.items():
            percentage = get_free_tier_usage_percentage(service, metric_name, limit)
            usage[f"{service}.{metric_name}"] = percentage
            
            # Log warning if approaching limit
            if percentage > 80:
                logger.warning(f"⚠️  {service} {metric_name} at {percentage:.2f}% of free tier limit!")
    
    return usage


def create_usage_dashboard():
    """
    Create a CloudWatch dashboard for monitoring usage metrics.
    """
    try:
        dashboard_body = {
            "widgets": [
                {
                    "type": "metric",
                    "properties": {
                        "metrics": [
                            [NAMESPACE, "LambdaInvocations", {"stat": "Sum"}]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": os.getenv('AWS_REGION', 'us-east-1'),
                        "title": "Lambda Invocations"
                    }
                },
                {
                    "type": "metric",
                    "properties": {
                        "metrics": [
                            [NAMESPACE, "DynamoDBReadOperations", {"stat": "Sum"}],
                            [NAMESPACE, "DynamoDBWriteOperations", {"stat": "Sum"}]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": os.getenv('AWS_REGION', 'us-east-1'),
                        "title": "DynamoDB Operations"
                    }
                },
                {
                    "type": "metric",
                    "properties": {
                        "metrics": [
                            [NAMESPACE, "S3GetOperations", {"stat": "Sum"}],
                            [NAMESPACE, "S3PutOperations", {"stat": "Sum"}]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": os.getenv('AWS_REGION', 'us-east-1'),
                        "title": "S3 Operations"
                    }
                },
                {
                    "type": "metric",
                    "properties": {
                        "metrics": [
                            [NAMESPACE, "APIGatewayRequests", {"stat": "Sum"}]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": os.getenv('AWS_REGION', 'us-east-1'),
                        "title": "API Gateway Requests"
                    }
                }
            ]
        }
        
        cloudwatch.put_dashboard(
            DashboardName='AgenticAI-Usage-Monitoring',
            DashboardBody=str(dashboard_body)
        )
        
        logger.info("Created CloudWatch usage monitoring dashboard")
        
    except Exception as e:
        logger.error(f"Failed to create usage dashboard: {str(e)}")
