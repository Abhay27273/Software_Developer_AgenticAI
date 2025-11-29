$API = "https://xx4apeixl1.execute-api.us-east-1.amazonaws.com/prod"

Write-Host "Testing API..." -ForegroundColor Green

# Health Check
Write-Host "`n1. Health Check"
curl "$API/health"

# Create Project
Write-Host "`n2. Create Project"
curl -Method POST "$API/api/projects" -Headers @{"Content-Type"="application/json"} -Body '{"name":"Demo API","type":"api","description":"Test"}'

Write-Host "`nDone! Your API is working." -ForegroundColor Green
