#!/usr/bin/env python3
"""
Cost Monitoring and Resource Limit Management Script

This script monitors AWS resource usage against free tier limits and
provides recommendations for adjusting resource limits to stay within budget.
"""

import boto3
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Initialize AWS clients
cloudwatch = boto3.client('cloudwatch')
lambda_client = boto3.client('lambda')
apigateway = boto3.client('apigateway')
budgets = boto3.client('budgets')

# Free tier limits
FREE_TIER_LIMITS = {
    'Lambda': {
        'Invocations': 1_000_000,  # per month
        'ComputeSeconds': 400_000   # GB-seconds per month
    },
    'DynamoDB': {
        'ReadOperations': 25 * 30 * 24 * 3600,  # 25 RCU for 30 days
        'WriteOperations': 25 * 30 * 24 * 3600  # 25 WCU for 30 days
    },
    'S3': {
        'GetOperations': 20_000,
        'PutOperations': 2_000
    },
    'SQS': {
        'SendOperations': 1_000_000
    },
    'APIGateway': {
        'Requests': 1_000_000
    }
}

# Warning thresholds
WARNING_THRESHOLD = 0.80  # 80%
CRITICAL_THRESHOLD = 0.95  # 95%


def get_metric_statistics(namespace: str, metric_name: str, dimensions: List[Dict], 
                          start_time: datetime, end_time: datetime) -> float:
    """
    Get metric statistics from CloudWatch.
    
    Args:
        namespace: CloudWatch namespace
        metric_name: Name of the metric
        dimensions: Metric dimensions
        start_time: Start time for the query
        end_time: End time for the query
        
    Returns:
        Total sum of the metric values
    """
    try:
        response = cloudwatch.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=86400,  # 1 day
            Statistics=['Sum']
        )
        
        total = sum(point['Sum'] for point in response['Datapoints'])
        return total
        
    except Exception as e:
        print(f"Error getting metric statistics: {str(e)}")
        return 0.0


def check_lambda_usage() -> Dict[str, Tuple[float, float, str]]:
    """
    Check Lambda usage against free tier limits.
    
    Returns:
        Dictionary with usage data: {metric: (current, limit, status)}
    """
    print("\n=== Lambda Usage ===")
    
    # Get current month's data
    end_time = datetime.utcnow()
    start_time = end_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Check invocations
    invocations = get_metric_statistics(
        'AgenticAI/Usage',
        'LambdaInvocations',
        [{'Name': 'Service', 'Value': 'Lambda'}],
        start_time,
        end_time
    )
    
    invocation_limit = FREE_TIER_LIMITS['Lambda']['Invocations']
    invocation_pct = (invocations / invocation_limit) * 100
    
    status = 'OK'
    if invocation_pct >= CRITICAL_THRESHOLD * 100:
        status = 'CRITICAL'
    elif invocation_pct >= WARNING_THRESHOLD * 100:
        status = 'WARNING'
    
    print(f"Invocations: {invocations:,.0f} / {invocation_limit:,.0f} ({invocation_pct:.1f}%) - {status}")
    
    return {
        'Invocations': (invocations, invocation_limit, status)
    }


def check_dynamodb_usage() -> Dict[str, Tuple[float, float, str]]:
    """
    Check DynamoDB usage against free tier limits.
    
    Returns:
        Dictionary with usage data: {metric: (current, limit, status)}
    """
    print("\n=== DynamoDB Usage ===")
    
    end_time = datetime.utcnow()
    start_time = end_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    results = {}
    
    for operation in ['Read', 'Write']:
        metric_name = f'DynamoDB{operation}Operations'
        usage = get_metric_statistics(
            'AgenticAI/Usage',
            metric_name,
            [{'Name': 'Service', 'Value': 'DynamoDB'}],
            start_time,
            end_time
        )
        
        limit = FREE_TIER_LIMITS['DynamoDB'][f'{operation}Operations']
        pct = (usage / limit) * 100
        
        status = 'OK'
        if pct >= CRITICAL_THRESHOLD * 100:
            status = 'CRITICAL'
        elif pct >= WARNING_THRESHOLD * 100:
            status = 'WARNING'
        
        print(f"{operation} Operations: {usage:,.0f} / {limit:,.0f} ({pct:.1f}%) - {status}")
        results[f'{operation}Operations'] = (usage, limit, status)
    
    return results


def check_s3_usage() -> Dict[str, Tuple[float, float, str]]:
    """
    Check S3 usage against free tier limits.
    
    Returns:
        Dictionary with usage data: {metric: (current, limit, status)}
    """
    print("\n=== S3 Usage ===")
    
    end_time = datetime.utcnow()
    start_time = end_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    results = {}
    
    for operation in ['Get', 'Put']:
        metric_name = f'S3{operation}Operations'
        usage = get_metric_statistics(
            'AgenticAI/Usage',
            metric_name,
            [{'Name': 'Service', 'Value': 'S3'}],
            start_time,
            end_time
        )
        
        limit = FREE_TIER_LIMITS['S3'][f'{operation}Operations']
        pct = (usage / limit) * 100
        
        status = 'OK'
        if pct >= CRITICAL_THRESHOLD * 100:
            status = 'CRITICAL'
        elif pct >= WARNING_THRESHOLD * 100:
            status = 'WARNING'
        
        print(f"{operation} Operations: {usage:,.0f} / {limit:,.0f} ({pct:.1f}%) - {status}")
        results[f'{operation}Operations'] = (usage, limit, status)
    
    return results


def check_api_gateway_usage() -> Dict[str, Tuple[float, float, str]]:
    """
    Check API Gateway usage against free tier limits.
    
    Returns:
        Dictionary with usage data: {metric: (current, limit, status)}
    """
    print("\n=== API Gateway Usage ===")
    
    end_time = datetime.utcnow()
    start_time = end_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    requests = get_metric_statistics(
        'AgenticAI/Usage',
        'APIGatewayRequests',
        [{'Name': 'Service', 'Value': 'APIGateway'}],
        start_time,
        end_time
    )
    
    limit = FREE_TIER_LIMITS['APIGateway']['Requests']
    pct = (requests / limit) * 100
    
    status = 'OK'
    if pct >= CRITICAL_THRESHOLD * 100:
        status = 'CRITICAL'
    elif pct >= WARNING_THRESHOLD * 100:
        status = 'WARNING'
    
    print(f"Requests: {requests:,.0f} / {limit:,.0f} ({pct:.1f}%) - {status}")
    
    return {
        'Requests': (requests, limit, status)
    }


def get_budget_status(account_id: str, budget_name: str) -> Dict:
    """
    Get current budget status.
    
    Args:
        account_id: AWS account ID
        budget_name: Name of the budget
        
    Returns:
        Dictionary with budget information
    """
    try:
        response = budgets.describe_budget(
            AccountId=account_id,
            BudgetName=budget_name
        )
        
        budget = response['Budget']
        limit = float(budget['BudgetLimit']['Amount'])
        
        # Get actual spend
        calculated_spend = budget.get('CalculatedSpend', {})
        actual = float(calculated_spend.get('ActualSpend', {}).get('Amount', 0))
        forecasted = float(calculated_spend.get('ForecastedSpend', {}).get('Amount', 0))
        
        pct = (actual / limit) * 100 if limit > 0 else 0
        
        print(f"\n=== Budget Status ===")
        print(f"Budget Limit: ${limit:.2f}")
        print(f"Actual Spend: ${actual:.2f} ({pct:.1f}%)")
        print(f"Forecasted Spend: ${forecasted:.2f}")
        
        return {
            'limit': limit,
            'actual': actual,
            'forecasted': forecasted,
            'percentage': pct
        }
        
    except Exception as e:
        print(f"\nError getting budget status: {str(e)}")
        return {}


def get_lambda_concurrency_limits(environment: str) -> Dict[str, int]:
    """
    Get current Lambda reserved concurrency limits.
    
    Args:
        environment: Deployment environment (dev, staging, prod)
        
    Returns:
        Dictionary mapping function names to concurrency limits
    """
    print("\n=== Lambda Concurrency Limits ===")
    
    function_names = [
        f'agenticai-pm-agent-{environment}',
        f'agenticai-dev-agent-{environment}',
        f'agenticai-qa-agent-{environment}',
        f'agenticai-ops-agent-{environment}'
    ]
    
    limits = {}
    total = 0
    
    for function_name in function_names:
        try:
            response = lambda_client.get_function_concurrency(
                FunctionName=function_name
            )
            concurrency = response.get('ReservedConcurrentExecutions', 'Unreserved')
            limits[function_name] = concurrency
            if isinstance(concurrency, int):
                total += concurrency
            print(f"{function_name}: {concurrency}")
        except lambda_client.exceptions.ResourceNotFoundException:
            print(f"{function_name}: Not found")
        except Exception as e:
            print(f"{function_name}: Error - {str(e)}")
    
    print(f"\nTotal Reserved Concurrency: {total}")
    print(f"Recommended Limit: 10 (to stay within free tier)")
    
    return limits


def generate_recommendations(usage_data: Dict) -> List[str]:
    """
    Generate recommendations based on usage data.
    
    Args:
        usage_data: Dictionary with usage statistics
        
    Returns:
        List of recommendation strings
    """
    recommendations = []
    
    print("\n=== Recommendations ===")
    
    # Check for critical usage
    critical_services = []
    warning_services = []
    
    for service, metrics in usage_data.items():
        for metric, (current, limit, status) in metrics.items():
            if status == 'CRITICAL':
                critical_services.append(f"{service}.{metric}")
            elif status == 'WARNING':
                warning_services.append(f"{service}.{metric}")
    
    if critical_services:
        recommendations.append(
            f"⚠️  CRITICAL: The following services are at >95% of free tier limits: {', '.join(critical_services)}"
        )
        recommendations.append(
            "   Action: Consider reducing Lambda concurrency, implementing caching, or upgrading to paid tier"
        )
    
    if warning_services:
        recommendations.append(
            f"⚠️  WARNING: The following services are at >80% of free tier limits: {', '.join(warning_services)}"
        )
        recommendations.append(
            "   Action: Monitor closely and prepare to optimize or scale"
        )
    
    if not critical_services and not warning_services:
        recommendations.append("✅ All services are within acceptable usage limits")
    
    # General recommendations
    recommendations.extend([
        "",
        "General Optimization Tips:",
        "1. Enable API Gateway caching to reduce Lambda invocations",
        "2. Implement client-side caching for frequently accessed data",
        "3. Use DynamoDB batch operations to reduce request count",
        "4. Compress S3 objects to reduce storage and transfer costs",
        "5. Set up CloudWatch alarms for proactive monitoring"
    ])
    
    for rec in recommendations:
        print(rec)
    
    return recommendations


def main():
    """Main execution function."""
    print("=" * 60)
    print("AgenticAI Cost Monitoring Report")
    print(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)
    
    # Get environment from command line or use default
    environment = sys.argv[1] if len(sys.argv) > 1 else 'prod'
    account_id = boto3.client('sts').get_caller_identity()['Account']
    
    # Collect usage data
    usage_data = {
        'Lambda': check_lambda_usage(),
        'DynamoDB': check_dynamodb_usage(),
        'S3': check_s3_usage(),
        'APIGateway': check_api_gateway_usage()
    }
    
    # Check budget
    budget_name = f'agenticai-monthly-budget-{environment}'
    get_budget_status(account_id, budget_name)
    
    # Check Lambda concurrency limits
    get_lambda_concurrency_limits(environment)
    
    # Generate recommendations
    generate_recommendations(usage_data)
    
    print("\n" + "=" * 60)
    print("End of Report")
    print("=" * 60)


if __name__ == '__main__':
    main()
