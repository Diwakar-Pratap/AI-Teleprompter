# AI Teleprompter — Windows Setup Script
# Run this once to set up the development environment.

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  AI Teleprompter - Development Setup" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"

# Check Node.js
Write-Host "Checking Node.js..." -ForegroundColor Yellow
$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Node.js not found. Install from https://nodejs.org/" -ForegroundColor Red
    exit 1
}
Write-Host "Node.js: $nodeVersion" -ForegroundColor Green

# Check npm
$npmVersion = npm --version 2>&1
Write-Host "npm: $npmVersion" -ForegroundColor Green

# Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not found. Install Python 3.11+ from https://python.org/" -ForegroundColor Red
    exit 1
}
Write-Host "Python: $pythonVersion" -ForegroundColor Green

# Set project root
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Write-Host "Project root: $projectRoot" -ForegroundColor Gray

# Install npm dependencies
Write-Host ""
Write-Host "Installing npm dependencies..." -ForegroundColor Yellow
Set-Location $projectRoot
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: npm install failed" -ForegroundColor Red
    exit 1
}
Write-Host "npm dependencies installed." -ForegroundColor Green

# Create Python virtual environment
Write-Host ""
Write-Host "Setting up Python virtual environment..." -ForegroundColor Yellow
$venvPath = Join-Path $projectRoot "backend\.venv"
if (-not (Test-Path $venvPath)) {
    python -m venv $venvPath
    Write-Host "Virtual environment created at: $venvPath" -ForegroundColor Green
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor Gray
}

# Install Python dependencies
Write-Host ""
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
$pipPath = Join-Path $venvPath "Scripts\pip.exe"
& $pipPath install -r (Join-Path $projectRoot "backend\requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install failed" -ForegroundColor Red
    exit 1
}
Write-Host "Python dependencies installed." -ForegroundColor Green

# Copy .env.example if .env doesn't exist
$envFile = Join-Path $projectRoot ".env"
$envExample = Join-Path $projectRoot ".env.example"
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host ""
    Write-Host "Created .env from .env.example" -ForegroundColor Green
    Write-Host "Edit .env to add your API keys before running." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  To start development:" -ForegroundColor White
Write-Host "    .\scripts\dev.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  To run tests:" -ForegroundColor White
Write-Host "    .\scripts\test.ps1" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Cyan
