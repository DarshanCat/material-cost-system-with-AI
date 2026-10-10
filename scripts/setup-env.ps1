# ==============================================================================
# VSPL Material Management & Costing System — Environment Setup Script (PowerShell)
# ==============================================================================
# Prerequisites:
#   - Python 3.11+ installed and on PATH
#   - Node.js (v18+) and npm installed and on PATH
#   - PostgreSQL installed and running locally for database operations
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "VSPL Material Management System - Environment Initializer" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Backend Virtual Environment Setup
$BackendDir = Join-Path $PSScriptRoot "..\backend"
$VenvPath = Join-Path $BackendDir ".venv"

if (-not (Test-Path $VenvPath)) {
    Write-Host "[1/5] Creating Python virtual environment in backend\.venv..." -ForegroundColor Yellow
    python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment."
        exit $LASTEXITCODE
    }
} else {
    Write-Host "[1/5] Python virtual environment already exists at $VenvPath." -ForegroundColor Green
}

# 2. Install Backend Dependencies
Write-Host "[2/5] Installing/verifying backend dependencies..." -ForegroundColor Yellow
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$PipExe = Join-Path $VenvPath "Scripts\pip.exe"
$ReqFile = Join-Path $BackendDir "requirements.txt"

& $PipExe install -r $ReqFile
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install Python requirements."
    exit $LASTEXITCODE
}

# 3. Environment Variable Configuration
$EnvExample = Join-Path $BackendDir ".env.example"
$EnvFile = Join-Path $BackendDir ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Host "[3/5] Initializing backend\.env from template..." -ForegroundColor Yellow
    Copy-Item $EnvExample $EnvFile
    Write-Host "Created backend\.env. Please update with your local PostgreSQL password if needed." -ForegroundColor Green
} else {
    Write-Host "[3/5] backend\.env already configured." -ForegroundColor Green
}

# 4. Frontend Dependencies Setup
$FrontendDir = Join-Path $PSScriptRoot "..\frontend"
Write-Host "[4/5] Installing frontend npm packages..." -ForegroundColor Yellow
Push-Location $FrontendDir
try {
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install npm dependencies."
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

Write-Host "[5/5] Setup completed successfully!" -ForegroundColor Green
Write-Host "To start backend: .\scripts\run-backend.ps1" -ForegroundColor Cyan
Write-Host "To start frontend: .\scripts\run-frontend.ps1" -ForegroundColor Cyan
Write-Host "To run test suites: .\scripts\run-tests.ps1" -ForegroundColor Cyan
