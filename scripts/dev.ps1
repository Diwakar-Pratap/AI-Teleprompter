# AI Teleprompter — Development Run Script
# Starts backend and Electron frontend in development mode.

Write-Host "Starting AI Teleprompter in development mode..." -ForegroundColor Cyan

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $projectRoot

# Start Python backend in background
Write-Host "Starting Python backend..." -ForegroundColor Yellow
$pythonPath = Join-Path $projectRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    $pythonPath = "python"
    Write-Host "Using system Python (venv not found)" -ForegroundColor Gray
}

$backendJob = Start-Job -ScriptBlock {
    param($python, $script)
    & $python $script --host 127.0.0.1 --port 8765 --log-level info
} -ArgumentList $pythonPath, (Join-Path $projectRoot "backend\main.py")

Write-Host "Backend starting (PID: $($backendJob.Id))..." -ForegroundColor Gray

# Give backend time to start
Start-Sleep -Seconds 3

# Start Electron + React
Write-Host "Starting Electron frontend..." -ForegroundColor Yellow
npm run dev

# Cleanup on exit
Write-Host "Stopping backend..." -ForegroundColor Yellow
Stop-Job $backendJob
Remove-Job $backendJob
