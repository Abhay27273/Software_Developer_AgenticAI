# Create CloudWatch Dashboard using AWS CLI
# This script creates the AgenticAI-Production dashboard

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CloudWatch Dashboard Creation (AWS CLI)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$region = "us-east-1"
$dashboardName = "AgenticAI-Production"

# Save dashboard JSON to temp file
$tempFile = [System.IO.Path]::GetTempFileName()

$dashboardBody = @'
{
  "widgets": [
    {
      "type": "metric",
      "x": 0,
      "y": 0,
      "width": 8,
      "height": 6,
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum", "label": "Lambda Invocations"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "Lambda Invocations",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Count"
          }
        }
      }
    },
    {
      "type": "metric",
      "x": 8,
      "y": 0,
      "width": 8,
      "height": 6,
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Errors", {"stat": "Sum", "label": "Lambda Errors", "color": "#d62728"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "Lambda Errors",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Count"
          }
        }
      }
    },
    {
      "type": "metric",
      "x": 16,
      "y": 0,
      "width": 8,
      "height": 6,
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Duration", {"stat": "p50", "label": "Lambda p50"}],
          ["...", {"stat": "p95", "label": "Lambda p95"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "Lambda Duration (p50, p95)",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Milliseconds"
          }
        }
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 6,
      "width": 12,
      "height": 6,
      "properties": {
        "metrics": [
          ["AWS/ApiGateway", "Count", {"stat": "Sum", "label": "Total Requests"}],
          [".", "4XXError", {"stat": "Sum", "label": "4XX Errors", "color": "#ff7f0e"}],
          [".", "5XXError", {"stat": "Sum", "label": "5XX Errors", "color": "#d62728"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "API Gateway Requests & Errors",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Count"
          }
        }
      }
    },
    {
      "type": "metric",
      "x": 12,
      "y": 6,
      "width": 12,
      "height": 6,
      "properties": {
        "metrics": [
          ["AWS/ApiGateway", "Latency", {"stat": "p50", "label": "p50 Latency"}],
          ["...", {"stat": "p95", "label": "p95 Latency"}],
          ["...", {"stat": "p99", "label": "p99 Latency"}],
          [".", "IntegrationLatency", {"stat": "Average", "label": "Integration Latency"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "API Gateway Latency",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Milliseconds"
          }
        }
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 12,
      "width": 12,
      "height": 6,
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Duration", {"stat": "Maximum", "label": "Max Duration"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "Lambda Cold Start Metrics (Max Duration)",
        "period": 60,
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
    },
    {
      "type": "metric",
      "x": 12,
      "y": 12,
      "width": 12,
      "height": 6,
      "properties": {
        "metrics": [
          ["AWS/ApiGateway", "Latency", {"stat": "p50", "label": "p50 (median)", "color": "#1f77b4"}],
          ["...", {"stat": "p95", "label": "p95", "color": "#ff7f0e"}],
          ["...", {"stat": "p99", "label": "p99", "color": "#d62728"}],
          [".", "IntegrationLatency", {"stat": "p95", "label": "Integration p95", "color": "#9467bd"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "API Response Time Percentiles (p50, p95, p99)",
        "period": 60,
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
    },
    {
      "type": "metric",
      "x": 0,
      "y": 18,
      "width": 12,
      "height": 6,
      "properties": {
        "metrics": [
          ["AWS/DynamoDB", "ConsumedReadCapacityUnits", {"stat": "Sum", "label": "Read Capacity"}],
          [".", "ConsumedWriteCapacityUnits", {"stat": "Sum", "label": "Write Capacity"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "DynamoDB Capacity Usage",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Units"
          }
        }
      }
    },
    {
      "type": "metric",
      "x": 12,
      "y": 18,
      "width": 12,
      "height": 6,
      "properties": {
        "metrics": [
          ["AWS/DynamoDB", "ReadThrottleEvents", {"stat": "Sum", "label": "Read Throttles", "color": "#d62728"}],
          [".", "WriteThrottleEvents", {"stat": "Sum", "label": "Write Throttles", "color": "#ff7f0e"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "DynamoDB Throttles",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Count"
          }
        }
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 24,
      "width": 12,
      "height": 6,
      "properties": {
        "metrics": [
          ["AWS/SQS", "ApproximateNumberOfMessagesVisible", {"stat": "Average", "label": "Messages in Queue"}],
          [".", "ApproximateAgeOfOldestMessage", {"stat": "Maximum", "label": "Oldest Message Age (s)", "yAxis": "right"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
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
    },
    {
      "type": "metric",
      "x": 12,
      "y": 24,
      "width": 12,
      "height": 6,
      "properties": {
        "metrics": [
          ["AWS/Lambda", "ConcurrentExecutions", {"stat": "Maximum", "label": "Concurrent Executions"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "Lambda Concurrent Executions",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Count"
          }
        }
      }
    }
  ]
}
'@

Write-Host "Creating dashboard: $dashboardName" -ForegroundColor Yellow
Write-Host "Region: $region" -ForegroundColor Yellow
Write-Host ""

# Write dashboard body to temp file
$dashboardBody | Out-File -FilePath $tempFile -Encoding utf8

# Create the dashboard
aws cloudwatch put-dashboard --dashboard-name $dashboardName --dashboard-body file://$tempFile --region $region

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ Dashboard created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "View dashboard at:" -ForegroundColor Cyan
    Write-Host "https://$region.console.aws.amazon.com/cloudwatch/home?region=$region#dashboards:name=$dashboardName" -ForegroundColor Cyan
    Write-Host ""
    
    # Verify dashboard
    Write-Host "Verifying dashboard..." -ForegroundColor Yellow
    $dashboard = aws cloudwatch get-dashboard --dashboard-name $dashboardName --region $region | ConvertFrom-Json
    
    if ($dashboard) {
        $body = $dashboard.DashboardBody | ConvertFrom-Json
        $widgetCount = $body.widgets.Count
        Write-Host "✓ Dashboard verified: $widgetCount widgets" -ForegroundColor Green
        Write-Host ""
    }
    
    # Clean up temp file
    Remove-Item $tempFile -ErrorAction SilentlyContinue
    
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Dashboard Setup Complete" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
} else {
    Write-Host "✗ Failed to create dashboard" -ForegroundColor Red
    Remove-Item $tempFile -ErrorAction SilentlyContinue
    exit 1
}
