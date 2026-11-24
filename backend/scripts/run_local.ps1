# Start the backend for local testing: a throw-away SQLite database, development sign-in, local attachment folder.
# Usage (from the backend folder):  powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1
$here = Split-Path -Parent $PSScriptRoot
Set-Location $here
$env:ENVIRONMENT = "development"
$env:AUTH_PROVIDER = "dev"
$env:DATABASE_URL = "sqlite:///$($here -replace '\','/')/local_dev.db"
$env:ATTACHMENT_LOCAL_DIR = "$here\local_attachments"
python scripts\dev_local.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
