#!/usr/bin/env python3
"""
CloudWatch Dashboard Test Script

Tests that the CloudWatch dashboard displays metrics correctly by:
1. Verifying dashboard exists
2. Checking all required widgets are present
3. Validating metric configurations
4. Testing metric data retrieval
"""

import boto3
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any


class CloudWatchDashboardTester:
    """Test CloudWatch dashboard configuration and metrics"""
    
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.dashboard_name = 'AgenticAI-Production'
        self.test_results = []
    
    def _add_result(self, test_name: str, passed: bool, message: str):
        """Add a test result"""
        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'message': message
        })
        
        status = "✓" if passed else "✗"
        print(f"  {status} {test_name}: {message}")
    
    def test_dashboard_exists(self) -> bool:
        """Test that the dashboard exists"""
        print("\n1. Testing dashboard existence...")
        
        try:
            response = self.cloudwatch.get_dashboard(
                DashboardName=self.dashboard_name
            )
            
            self._add_result(
                "Dashboard Exists",
                True,
                f"Dashboard '{self.dashboard_name}' found"
            )
            return True
            
        except self.cloudwatch.exceptions.ResourceNotFound:
            self._add_result(
                "Dashboard Exists",
                False,
                f"Dashboard '{self.dashboard_name}' not found"
            )
            return False
        except Exception as e:
            self._add_result(
                "Dashboard Exists",
                False,
                f"Error checking dashboard: {e}"
            )
            return False
    
    def test_widget_count(self) -> bool:
        """Test that all required widgets are present"""
        print("\n2. Testing widget count...")
        
        try:
            response = self.cloudwatch.get_dashboard(
                DashboardName=self.dashboard_name
            )
            
            dashboard_body = json.loads(response['DashboardBody'])
            widgets = dashboard_body.get('widgets', [])
            widget_count = len(widgets)
            
            expected_count = 9
            passed = widget_count == expected_count
            
            self._add_result(
                "Widget Count",
                passed,
                f"Found {widget_count} widgets (expected {expected_count})"
            )
            
            return passed
            
        except Exception as e:
            self._add_result(
                "Widget Count",
                False,
                f"Error checking widgets: {e}"
            )
            return False
    
    def test_required_metrics(self) -> bool:
        """Test that all required metrics are configured"""
        print("\n3. Testing required metrics...")
        
        required_metrics = {
            'Lambda Invocations': ['AWS/Lambda', 'Invocations'],
            'Lambda Errors': ['AWS/Lambda', 'Errors'],
            'Lambda Duration': ['AWS/Lambda', 'Duration'],
            'API Gateway Requests': ['AWS/ApiGateway', 'Count'],
            'API Gateway Errors': ['AWS/ApiGateway', '4XXError', '5XXError'],
            'API Gateway Latency': ['AWS/ApiGateway', 'Latency'],
            'DynamoDB Capacity': ['AWS/DynamoDB', 'ConsumedReadCapacityUnits', 'ConsumedWriteCapacityUnits'],
            'DynamoDB Throttles': ['AWS/DynamoDB', 'ReadThrottleEvents', 'WriteThrottleEvents'],
            'SQS Queue': ['AWS/SQS', 'ApproximateNumberOfMessagesVisible']
        }
        
        try:
            response = self.cloudwatch.get_dashboard(
                DashboardName=self.dashboard_name
            )
            
            dashboard_body = json.loads(response['DashboardBody'])
            widgets = dashboard_body.get('widgets', [])
            
            # Extract all metrics from all widgets
            all_metrics = []
            for widget in widgets:
                if widget.get('type') == 'metric':
                    metrics = widget.get('properties', {}).get('metrics', [])
                    for metric in metrics:
                        if isinstance(metric, list) and len(metric) >= 2:
                            all_metrics.append((metric[0], metric[1]))
            
            # Check each required metric
            all_passed = True
            for metric_name, metric_parts in required_metrics.items():
                namespace = metric_parts[0]
                metric_names = metric_parts[1:]
                
                found = False
                for ns, mn in all_metrics:
                    if ns == namespace and mn in metric_names:
                        found = True
                        break
                
                if found:
                    self._add_result(
                        f"Metric: {metric_name}",
                        True,
                        "Configured correctly"
                    )
                else:
                    self._add_result(
                        f"Metric: {metric_name}",
                        False,
                        "Not found in dashboard"
                    )
                    all_passed = False
            
            return all_passed
            
        except Exception as e:
            self._add_result(
                "Required Metrics",
                False,
                f"Error checking metrics: {e}"
            )
            return False
    
    def test_metric_data_retrieval(self) -> bool:
        """Test that metrics can retrieve data"""
        print("\n4. Testing metric data retrieval...")
        
        # Test a few key metrics to ensure data can be retrieved
        test_metrics = [
            {
                'name': 'Lambda Invocations',
                'namespace': 'AWS/Lambda',
                'metric_name': 'Invocations',
                'stat': 'Sum'
            },
            {
                'name': 'API Gateway Requests',
                'namespace': 'AWS/ApiGateway',
                'metric_name': 'Count',
                'stat': 'Sum'
            }
        ]
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        
        all_passed = True
        
        for metric in test_metrics:
            try:
                response = self.cloudwatch.get_metric_statistics(
                    Namespace=metric['namespace'],
                    MetricName=metric['metric_name'],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=[metric['stat']]
                )
                
                datapoints = response.get('Datapoints', [])
                
                self._add_result(
                    f"Data Retrieval: {metric['name']}",
                    True,
                    f"Retrieved {len(datapoints)} datapoints"
                )
                
            except Exception as e:
                self._add_result(
                    f"Data Retrieval: {metric['name']}",
                    False,
                    f"Error: {e}"
                )
                all_passed = False
        
        return all_passed
    
    def test_widget_configuration(self) -> bool:
        """Test widget configuration details"""
        print("\n5. Testing widget configuration...")
        
        try:
            response = self.cloudwatch.get_dashboard(
                DashboardName=self.dashboard_name
            )
            
            dashboard_body = json.loads(response['DashboardBody'])
            widgets = dashboard_body.get('widgets', [])
            
            all_passed = True
            
            # Check that widgets have proper period (5 minutes = 300 seconds)
            for i, widget in enumerate(widgets):
                if widget.get('type') == 'metric':
                    period = widget.get('properties', {}).get('period', 0)
                    
                    if period == 300:
                        self._add_result(
                            f"Widget {i+1} Period",
                            True,
                            "5-minute granularity configured"
                        )
                    else:
                        self._add_result(
                            f"Widget {i+1} Period",
                            False,
                            f"Period is {period}s (expected 300s)"
                        )
                        all_passed = False
            
            return all_passed
            
        except Exception as e:
            self._add_result(
                "Widget Configuration",
                False,
                f"Error checking configuration: {e}"
            )
            return False
    
    def test_dashboard_layout(self) -> bool:
        """Test dashboard layout and positioning"""
        print("\n6. Testing dashboard layout...")
        
        try:
            response = self.cloudwatch.get_dashboard(
                DashboardName=self.dashboard_name
            )
            
            dashboard_body = json.loads(response['DashboardBody'])
            widgets = dashboard_body.get('widgets', [])
            
            # Check that widgets have position information
            positioned_widgets = 0
            for widget in widgets:
                if 'x' in widget and 'y' in widget and 'width' in widget and 'height' in widget:
                    positioned_widgets += 1
            
            passed = positioned_widgets == len(widgets)
            
            self._add_result(
                "Widget Positioning",
                passed,
                f"{positioned_widgets}/{len(widgets)} widgets have position data"
            )
            
            return passed
            
        except Exception as e:
            self._add_result(
                "Dashboard Layout",
                False,
                f"Error checking layout: {e}"
            )
            return False
    
    def run_all_tests(self) -> bool:
        """Run all tests and return overall result"""
        print("=" * 60)
        print("CloudWatch Dashboard Test Suite")
        print("=" * 60)
        
        # Run all tests
        tests = [
            self.test_dashboard_exists,
            self.test_widget_count,
            self.test_required_metrics,
            self.test_metric_data_retrieval,
            self.test_widget_configuration,
            self.test_dashboard_layout
        ]
        
        for test in tests:
            test()
        
        # Print summary
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        
        passed_count = sum(1 for r in self.test_results if r['passed'])
        total_count = len(self.test_results)
        
        print(f"\nTotal Tests: {total_count}")
        print(f"Passed: {passed_count}")
        print(f"Failed: {total_count - passed_count}")
        
        if passed_count == total_count:
            print("\n✓ All tests passed!")
            return True
        else:
            print(f"\n✗ {total_count - passed_count} test(s) failed")
            return False
    
    def print_dashboard_url(self):
        """Print the dashboard URL"""
        print(f"\nDashboard URL:")
        print(f"https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={self.dashboard_name}")


def main():
    """Main execution function"""
    region = sys.argv[1] if len(sys.argv) > 1 else 'us-east-1'
    
    tester = CloudWatchDashboardTester(region=region)
    success = tester.run_all_tests()
    
    tester.print_dashboard_url()
    
    if not success:
        sys.exit(1)
    
    print()


if __name__ == '__main__':
    main()
