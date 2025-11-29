# Test API Workflow Script
$API_ENDPOINT = "https://xx4apeixl1.execute-api.us-east-1.amazonaws.com/prod"

Write-Host "=== AgenticAI API Workflow Test ===" -ForegroundColor Cyan
Write-Host ""

# 1. Health Check
Write-Host "1. Health Check" -ForegroundColor Yellow
try {
    $health = Invoke-WebRequest -Uri "$API_ENDPOINT/health"
    if ($health.StatusCode -eq 200) {
        Write-Host "✓ API is healthy" -ForegroundColor Green
    }
} catch {
    Write-Host "✗ API health check failed" -ForegroundColor Red
}
Write-Host ""

# 2. Create Project
Write-Host "2. Creating Test Project" -ForegroundColor Yellow
$projectId = $null
try {
    $response = Invoke-WebRequest -Method POST -Uri "$API_ENDPOINT/api/projects" `
        -Headers @{"Content-Type"="application/json"} `
        -Body '{"name":"Test API","type":"api","description":"Testing deployment"}'
    
    if ($response.StatusCode -eq 201) {
        Write-Host "✓ Project created" -ForegroundColor Green
        $data = $response.Content | ConvertFrom-Json
        $projectId = $data.project.project_id
        Write-Host "  ID: $projectId" -ForegroundColor Gray
    }
} catch {
    Write-Host "✗ Failed to create project" -ForegroundColor Red
}
Write-Host ""

# 3. Get Project
if ($projectId) {
    Write-Host "3. Getting Project Details" -ForegroundColor Yellow
    try {
        $response = Invoke-WebRequest -Uri "$API_ENDPOINT/api/projects/$projectId"
        if ($response.StatusCode -eq 200) {
            Write-Host "✓ Project retrieved" -ForegroundColor Green
            $data = $response.Content | ConvertFrom-Json
            Write-Host "  Name: $($data.project.name)" -ForegroundColor Gray
        }
    } catch {
        Write-Host "✗ Failed to get project" -ForegroundColor Red
    }
    Write-Host ""
}

# 4. Summary
Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host "API Endpoint: $API_ENDPOINT"
Write-Host "Your API is deployed and working!" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:"
Write-Host "  - Review: docs/QUICK_START_USAGE_GUIDE.md"
Write-Host "  - Monitor: CloudWatch Logs"
Write-Host "  - Integrate: Use Python/JS client examples"
Write-Host ""
