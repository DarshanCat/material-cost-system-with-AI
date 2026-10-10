# ==============================================================================
# VSPL Material Management & Costing System — Start Backend Server (PowerShell)
# ==============================================================================
# Starts FastAPI using Uvicorn on http://127.0.0.1:8000
# ==============================================================================

$BackendDir = Join-Path $PSScriptRoot "..\backend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual environment python not found at $VenvPython. Run .\scripts\setup-env.ps1 first."
    exit 1
}

Write-Host "Starting VSPL Material Management FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Cyan
Write-Host "Swagger Documentation: http://127.0.0.1:8000/docs" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray

Push-Location $BackendDir
try {
    & $VenvPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
} finally {
    Pop-Location
}
