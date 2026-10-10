# ==============================================================================
# VSPL Material Management & Costing System — Automated Test Runner (PowerShell)
# ==============================================================================

$BackendDir = Join-Path $PSScriptRoot "..\backend"
$FrontendDir = Join-Path $PSScriptRoot "..\frontend"
$VenvPytest = Join-Path $BackendDir ".venv\Scripts\pytest.exe"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "VSPL System Quality Gate: Automated Test Suite Execution" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Run Backend Pytest Suite
Write-Host "`n[1/2] Running Backend Pytest Tests..." -ForegroundColor Yellow
if (-not (Test-Path $VenvPytest)) {
    Write-Error "Pytest not found. Run .\scripts\setup-env.ps1 first."
    exit 1
}

Push-Location $BackendDir
try {
    & $VenvPytest tests -v
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Backend tests failed!"
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

# 2. Run Frontend Build & Typecheck
Write-Host "`n[2/2] Running Frontend Type Check & Production Build..." -ForegroundColor Yellow
Push-Location $FrontendDir
try {
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Frontend build verification failed!"
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

Write-Host "`nAll Quality Gates Passed (Backend tests & Frontend build verified)!" -ForegroundColor Green
