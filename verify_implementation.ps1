# Phase 1-3 Implementation Verification Script

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "🔍 Verifying Phase 1-3 Implementation" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

$allGood = $true

# Check 1: main.py exists and has required functions
Write-Host "📝 Checking main.py implementation..." -ForegroundColor Yellow
if (Test-Path "main.py") {
    $mainContent = Get-Content "main.py" -Raw
    
    $checks = @{
        "execute_qa_task function" = "async def execute_qa_task"
        "check_and_trigger_ops function" = "async def check_and_trigger_ops"
        "trigger-ops endpoint" = '@app.post\("/api/trigger-ops"\)'
        "deployment-status endpoint" = '@app.get\("/api/deployment-status"\)'
        "qa_started notification" = '"type": "qa_started"'
        "qa_complete notification" = '"type": "qa_complete"'
    }
    
    foreach ($check in $checks.GetEnumerator()) {
        if ($mainContent -match $check.Value) {
            Write-Host "  ✅ $($check.Key)" -ForegroundColor Green
        } else {
            Write-Host "  ❌ $($check.Key) - MISSING" -ForegroundColor Red
            $allGood = $false
        }
    }
} else {
    Write-Host "  ❌ main.py not found!" -ForegroundColor Red
    $allGood = $false
}
Write-Host ""

# Check 2: E2E test files exist
Write-Host "🧪 Checking E2E test files..." -ForegroundColor Yellow
$testFiles = @(
    "tests/test_e2e_simple_project.py",
    "tests/test_e2e_multi_file.py",
    "tests/test_e2e_parallel.py"
)

foreach ($file in $testFiles) {
    if (Test-Path $file) {
        Write-Host "  ✅ $file" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $file - MISSING" -ForegroundColor Red
        $allGood = $false
    }
}
Write-Host ""

# Check 3: Test runner script exists
Write-Host "⚙️  Checking test runner..." -ForegroundColor Yellow
if (Test-Path "run_e2e_tests.ps1") {
    Write-Host "  ✅ run_e2e_tests.ps1" -ForegroundColor Green
} else {
    Write-Host "  ❌ run_e2e_tests.ps1 - MISSING" -ForegroundColor Red
    $allGood = $false
}
Write-Host ""

# Check 4: Documentation
Write-Host "📚 Checking documentation..." -ForegroundColor Yellow
if (Test-Path "docs/PHASE1_3_IMPLEMENTATION.md") {
    Write-Host "  ✅ PHASE1_3_IMPLEMENTATION.md" -ForegroundColor Green
} else {
    Write-Host "  ❌ PHASE1_3_IMPLEMENTATION.md - MISSING" -ForegroundColor Red
    $allGood = $false
}
Write-Host ""

# Check 5: Required Python packages
Write-Host "📦 Checking Python dependencies..." -ForegroundColor Yellow
$requiredPackages = @("pytest", "pytest-asyncio", "fastapi", "uvicorn")
foreach ($package in $requiredPackages) {
    $installed = python -m pip show $package 2>$null
    if ($installed) {
        Write-Host "  ✅ $package" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  $package - NOT INSTALLED (run: pip install $package)" -ForegroundColor Yellow
    }
}
Write-Host ""

# Final summary
Write-Host "===========================================================" -ForegroundColor Cyan
if ($allGood) {
    Write-Host "✅ ALL CHECKS PASSED!" -ForegroundColor Green
    Write-Host ""
    Write-Host "🎉 Phase 1-3 Implementation Complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Yellow
    Write-Host "  1. Run E2E tests:    .\run_e2e_tests.ps1" -ForegroundColor White
    Write-Host "  2. Start server:     python main.py" -ForegroundColor White
    Write-Host "  3. Test Ops trigger: curl -X POST http://localhost:7860/api/trigger-ops" -ForegroundColor White
} else {
    Write-Host "⚠️  SOME CHECKS FAILED" -ForegroundColor Red
    Write-Host "Please review the output above and fix missing components." -ForegroundColor Yellow
}
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""
