#!/usr/bin/env python3
"""
Test script for the alerting system.
This script triggers test errors to verify that CloudWatch alarms fire correctly
and SNS notifications are sent.
"""

import boto3
import json
import time
import sys
from datetime import datetime

# Initialize AWS clients
cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
sns = boto3.client('sns', region_name='us-east-1')
lambda_client = boto3.client('lambda', region_name='us-east-1')
logs = boto3.client('logs', region_name='us-east-1')

ENVIRONMENT = 'prod'


def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_status(text, status="info"):
    """Print a status message"""
    colors = {
        "info": "\033[94m",  # Blue
        "success": "\033[92m",  # Green
        "warning": "\033[93m",  # Yellow
        "error": "\033[91m",  # Red
        "reset": "\033[0m"
    }
    
    symbols = {
        "info": "ℹ",
        "success": "✓",
        "warning": "⚠",
        "error": "✗"
    }
    
    color = colors.get(status, colors["info"])
    symbol = symbols.get(status, "•")
    print(f"{color}{symbol} {text}{colors['reset']}")


def check_sns_subscription():
    """Check if SNS topic subscription is confirmed"""
    print_header("Checking SNS Subscription")
    
    try:
        # Get SNS topic ARN
        response = cloudwatch.describe_alarms(
            AlarmNamePrefix=f'agenticai-lambda-error-rate-{ENVIRONMENT}'
        )
        
        if not response['MetricAlarms']:
            print_status("No alarms found. Please deploy the alerting infrastructure first.", "error")
            return False
        
        alarm = response['MetricAlarms'][0]
        if not alarm.get('AlarmActions'):
            print_status("No alarm actions configured", "error")
            return False
        
        topic_arn = alarm['AlarmActions'][0]
        print_status(f"SNS Topic ARN: {topic_arn}", "info")
        
        # Check subscriptions
        subscriptions = sns.list_subscriptions_by_topic(TopicArn=topic_arn)
        
        confirmed = False
        for sub in subscriptions['Subscriptions']:
            status = sub['SubscriptionArn']
            if status != 'PendingConfirmation':
                print_status(f"Subscription confirmed: {sub['Endpoint']}", "success")
                confirmed = True
            else:
                print_status(f"Subscription pending: {sub['Endpoint']}", "warning")
        
        if not confirmed:
            print_status("Please confirm your email subscription before testing", "warning")
            return False
        
        return True
    
    except Exception as e:
        print_status(f"Error checking subscription: {str(e)}", "error")
        return False


def check_alarm_status(alarm_name):
    """Check the current status of an alarm"""
    try:
        response = cloudwatch.describe_alarms(AlarmNames=[alarm_name])
        if response['MetricAlarms']:
            alarm = response['MetricAlarms'][0]
            state = alarm['StateValue']
            reason = alarm.get('StateReason', 'N/A')
            return state, reason
        return None, None
    except Exception as e:
        print_status(f"Error checking alarm: {str(e)}", "error")
        return None, None


def list_all_alarms():
    """List all configured alarms"""
    print_header("Configured Alarms")
    
    try:
        response = cloudwatch.describe_alarms(
            AlarmNamePrefix=f'agenticai-'
        )
        
        if not response['MetricAlarms']:
            print_status("No alarms found", "warning")
            return
        
        for alarm in response['MetricAlarms']:
            state = alarm['StateValue']
            status_type = "success" if state == "OK" else "warning" if state == "INSUFFICIENT_DATA" else "error"
            print_status(f"{alarm['AlarmName']}: {state}", status_type)
            print(f"  Description: {alarm.get('AlarmDescription', 'N/A')}")
            print(f"  Metric: {alarm['MetricName']}")
            print(f"  Threshold: {alarm['Threshold']}")
            print()
    
    except Exception as e:
        print_status(f"Error listing alarms: {str(e)}", "error")


def trigger_test_alarm():
    """Trigger a test alarm by setting alarm state manually"""
    print_header("Triggering Test Alarm")
    
    alarm_name = f'agenticai-lambda-error-rate-{ENVIRONMENT}'
    
    print_status(f"Setting alarm state to ALARM for: {alarm_name}", "info")
    print_status("This will send a test notification to your email", "warning")
    
    try:
        cloudwatch.set_alarm_state(
            AlarmName=alarm_name,
            StateValue='ALARM',
            StateReason='Manual test triggered by test_alerting.py script',
            StateReasonData=json.dumps({
                'test': True,
                'timestamp': datetime.now().isoformat(),
                'message': 'This is a test alert. No actual errors occurred.'
            })
        )
        
        print_status("Test alarm triggered successfully!", "success")
        print_status("Check your email for the alert notification", "info")
        print()
        
        # Wait a moment and check the alarm state
        time.sleep(2)
        state, reason = check_alarm_status(alarm_name)
        if state:
            print_status(f"Current alarm state: {state}", "info")
            print(f"  Reason: {reason}")
        
        # Reset alarm to OK
        print()
        print_status("Resetting alarm to OK state...", "info")
        cloudwatch.set_alarm_state(
            AlarmName=alarm_name,
            StateValue='OK',
            StateReason='Test completed, resetting to OK'
        )
        print_status("Alarm reset to OK", "success")
        
        return True
    
    except Exception as e:
        print_status(f"Error triggering test alarm: {str(e)}", "error")
        return False


def verify_alarm_configuration():
    """Verify that all required alarms are configured correctly"""
    print_header("Verifying Alarm Configuration")
    
    required_alarms = [
        f'agenticai-lambda-error-rate-{ENVIRONMENT}',
        f'agenticai-api-handler-consecutive-failures-{ENVIRONMENT}',
        f'agenticai-pm-agent-consecutive-failures-{ENVIRONMENT}',
        f'agenticai-dev-agent-consecutive-failures-{ENVIRONMENT}',
        f'agenticai-qa-agent-consecutive-failures-{ENVIRONMENT}',
        f'agenticai-ops-agent-consecutive-failures-{ENVIRONMENT}',
        f'agenticai-api-gateway-5xx-errors-{ENVIRONMENT}'
    ]
    
    all_configured = True
    
    for alarm_name in required_alarms:
        try:
            response = cloudwatch.describe_alarms(AlarmNames=[alarm_name])
            if response['MetricAlarms']:
                alarm = response['MetricAlarms'][0]
                has_actions = len(alarm.get('AlarmActions', [])) > 0
                if has_actions:
                    print_status(f"{alarm_name}: Configured ✓", "success")
                else:
                    print_status(f"{alarm_name}: Missing alarm actions", "warning")
                    all_configured = False
            else:
                print_status(f"{alarm_name}: Not found", "error")
                all_configured = False
        except Exception as e:
            print_status(f"{alarm_name}: Error - {str(e)}", "error")
            all_configured = False
    
    print()
    if all_configured:
        print_status("All alarms are properly configured!", "success")
    else:
        print_status("Some alarms are missing or misconfigured", "warning")
    
    return all_configured


def main():
    """Main test function"""
    print_header("AgenticAI Alerting System Test")
    
    # Step 1: Verify alarm configuration
    if not verify_alarm_configuration():
        print_status("Please deploy the alerting infrastructure first", "error")
        sys.exit(1)
    
    # Step 2: Check SNS subscription
    if not check_sns_subscription():
        print_status("Please confirm your SNS subscription before continuing", "warning")
        response = input("\nDo you want to continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)
    
    # Step 3: List all alarms
    list_all_alarms()
    
    # Step 4: Ask user if they want to trigger a test alarm
    print()
    response = input("Do you want to trigger a test alarm? This will send an email notification. (y/n): ")
    if response.lower() == 'y':
        trigger_test_alarm()
    
    print_header("Test Complete")
    print_status("Alerting system verification complete!", "success")
    print()
    print("Next steps:")
    print("  1. Verify you received the test email notification")
    print("  2. Check the CloudWatch console to see alarm history")
    print("  3. Monitor your application for real alerts")
    print()


if __name__ == '__main__':
    main()
