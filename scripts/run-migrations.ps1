# ==============================================================================
# VSPL Material Management & Costing System — Database Migration Runner
# ==============================================================================
# IMPORTANT:
#   - This script runs Alembic migrations against the configured PostgreSQL database.
#   - It requires a running PostgreSQL instance on the host / port specified in backend\.env.
#   - DO NOT run migrations against production without authorized migration change control.
# ==============================================================================

$BackendDir = Join-Path $PSScriptRoot "..\backend"
$AlembicExe = Join-Path $BackendDir ".venv\Scripts\alembic.exe"

if (-not (Test-Path $AlembicExe)) {
    Write-Error "Alembic not found in backend\.venv. Run .\scripts\setup-env.ps1 first."
    exit 1
}

Write-Host "Checking Alembic configuration and running pending migrations..." -ForegroundColor Cyan

Push-Location $BackendDir
try {
    & $AlembicExe upgrade head
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Database migrations successfully applied to head!" -ForegroundColor Green
    } else {
        Write-Host "`n[NOTICE] Migration command exited with error code $LASTEXITCODE." -ForegroundColor Yellow
        Write-Host "Please ensure local PostgreSQL service is running and credentials in backend\.env are valid." -ForegroundColor Yellow
        Write-Host "Check that database 'vspl_material_management' exists (e.g. created via 'createdb vspl_material_management')." -ForegroundColor Gray
    }
} finally {
    Pop-Location
}
