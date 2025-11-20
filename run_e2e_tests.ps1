# E2E Test Runner for Phase 1-3 Testing
# Run this script to execute all end-to-end workflow tests

$separator = '==========================================================='
$divider = '-----------------------------------------------------------'

Write-Host $separator -ForegroundColor Cyan
Write-Host 'Running End-to-End Workflow Tests (Phase 1-3)' -ForegroundColor Cyan
Write-Host $separator -ForegroundColor Cyan
Write-Host ""

$totalTests = 0
$passedTests = 0
$failedTests = 0

# Test 1: Simple FastAPI Project
Write-Host 'Test 1: Simple FastAPI Project' -ForegroundColor Yellow
Write-Host $divider -ForegroundColor Gray
$test1 = python -m pytest tests/test_e2e_simple_project.py::test_simple_fastapi_workflow -v -s
if ($LASTEXITCODE -eq 0) {
    $passedTests++
    Write-Host 'PASSED' -ForegroundColor Green
} else {
    $failedTests++
    Write-Host 'FAILED' -ForegroundColor Red
}
$totalTests++
Write-Host ""

# Test 2: Error Recovery
Write-Host 'Test 2: Error Recovery Workflow' -ForegroundColor Yellow
Write-Host $divider -ForegroundColor Gray
$test2 = python -m pytest tests/test_e2e_simple_project.py::test_error_recovery_workflow -v -s
if ($LASTEXITCODE -eq 0) {
    $passedTests++
    Write-Host 'PASSED' -ForegroundColor Green
} else {
    $failedTests++
    Write-Host 'FAILED' -ForegroundColor Red
}
$totalTests++
Write-Host ""

# Test 3: Multi-File Todo API
Write-Host 'Test 3: Multi-File Todo API Project' -ForegroundColor Yellow
Write-Host $divider -ForegroundColor Gray
$test3 = python -m pytest tests/test_e2e_multi_file.py::test_todo_api_workflow -v -s
if ($LASTEXITCODE -eq 0) {
    $passedTests++
    Write-Host 'PASSED' -ForegroundColor Green
} else {
    $failedTests++
    Write-Host 'FAILED' -ForegroundColor Red
}
$totalTests++
Write-Host ""

# Test 4: Parallel Execution
Write-Host 'Test 4: Parallel Execution Performance' -ForegroundColor Yellow
Write-Host $divider -ForegroundColor Gray
$test4 = python -m pytest tests/test_e2e_parallel.py::test_parallel_execution_performance -v -s
if ($LASTEXITCODE -eq 0) {
    $passedTests++
    Write-Host 'PASSED' -ForegroundColor Green
} else {
    $failedTests++
    Write-Host 'FAILED' -ForegroundColor Red
}
$totalTests++
Write-Host ""

# Summary
Write-Host $separator -ForegroundColor Cyan
Write-Host 'TEST SUMMARY' -ForegroundColor Cyan
Write-Host $separator -ForegroundColor Cyan
Write-Host ("Total Tests:  {0}" -f $totalTests) -ForegroundColor White
Write-Host ("Passed:       {0}" -f $passedTests) -ForegroundColor Green
Write-Host ("Failed:       {0}" -f $failedTests) -ForegroundColor Red
Write-Host $separator -ForegroundColor Cyan

if ($failedTests -eq 0) {
    Write-Host 'ALL TESTS PASSED!' -ForegroundColor Green
    Write-Host 'Phase 1-3 Implementation Complete!' -ForegroundColor Green
} else {
    Write-Host 'Some tests failed. Please review the output above.' -ForegroundColor Yellow
}

Write-Host $separator -ForegroundColor Cyan
Write-Host ""
