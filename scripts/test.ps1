# AI Teleprompter — Test Runner Script

Write-Host "Running AI Teleprompter tests..." -ForegroundColor Cyan

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$failed = $false

# Python tests
Write-Host ""
Write-Host "=== Python Backend Tests ===" -ForegroundColor Yellow
Set-Location (Join-Path $projectRoot "backend")
$pythonPath = Join-Path $projectRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    $pythonPath = "python"
}
& $pythonPath -m pytest tests/ -v --tb=short
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python tests FAILED" -ForegroundColor Red
    $failed = $true
} else {
    Write-Host "Python tests PASSED" -ForegroundColor Green
}

# Frontend type check
Write-Host ""
Write-Host "=== Frontend Type Check ===" -ForegroundColor Yellow
Set-Location $projectRoot
npm run typecheck
if ($LASTEXITCODE -ne 0) {
    Write-Host "TypeScript type check FAILED" -ForegroundColor Red
    $failed = $true
} else {
    Write-Host "TypeScript type check PASSED" -ForegroundColor Green
}

Write-Host ""
if ($failed) {
    Write-Host "Some tests FAILED." -ForegroundColor Red
    exit 1
} else {
    Write-Host "All tests PASSED." -ForegroundColor Green
}
