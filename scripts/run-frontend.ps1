# ==============================================================================
# VSPL Material Management & Costing System — Start Frontend Server (PowerShell)
# ==============================================================================
# Starts Vite React development server on http://localhost:5173
# ==============================================================================

$FrontendDir = Join-Path $PSScriptRoot "..\frontend"

Write-Host "Starting VSPL Frontend ERP Application on http://localhost:5173..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray

Push-Location $FrontendDir
try {
    npm run dev
} finally {
    Pop-Location
}
