# VSPL Material Management & Costing System — Windows Setup & Run Guide

This guide provides step-by-step instructions for setting up and running the VSPL Material Management & Costing System in a Windows environment using **PowerShell**.

---

## 1. Prerequisites Checklist

| Component | Minimum Version | Windows Verification Command | Required For |
| :--- | :--- | :--- | :--- |
| **Python** | 3.11+ | `python --version` | Backend API & Tests |
| **Node.js** | 18+ (LTS) | `node --version` | Frontend Build & Dev Server |
| **npm** | 9+ | `npm --version` | Frontend Dependencies |
| **PostgreSQL** | 15+ or 16+ | `Get-Service *postgres*` | Database Migrations & Persistence |
| **Git** | 2.30+ | `git --version` | Version Control |

> **IMPORTANT: When is PostgreSQL Required?**
> - **NOT Required for:** Initial project initialization, running the frontend UI, executing backend unit tests (tests use mocked connections), and browsing API Swagger documentation.
> - **REQUIRED for:** Running Alembic database migrations (`alembic upgrade head`), saving real item master records, posting transactions, and querying persistent stock ledger entries.

---

## 2. Automated One-Step Setup (Recommended)

Run the automated setup script from the root workspace directory:

```powershell
# Open PowerShell in the project root: c:\VSPL_MM\Material managment system
.\scripts\setup-env.ps1
```

This script:
1. Creates `backend\.venv` if not present.
2. Installs all backend packages from `backend\requirements.txt`.
3. Creates `backend\.env` from `backend\.env.example`.
4. Installs all frontend packages via `npm install`.

---

## 3. Manual Step-by-Step PowerShell Instructions

If you prefer executing steps manually, follow these commands:

### Step 3.1: Python Virtual Environment & Backend Dependencies
```powershell
# 1. Navigate to project root
cd "C:\VSPL_MM\Material managment system"

# 2. Create Python virtual environment
python -m venv backend\.venv

# 3. Upgrade pip in the virtual environment
.\backend\.venv\Scripts\python.exe -m pip install --upgrade pip

# 4. Install backend dependencies
.\backend\.venv\Scripts\pip.exe install -r backend\requirements.txt
```

### Step 3.2: Configure Environment Variables
```powershell
# Copy the safe template to .env
Copy-Item backend\.env.example backend\.env

# Open and edit with your local development PostgreSQL credentials
notepad backend\.env
```

Review and update the following values in `backend\.env` if necessary:
```ini
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_local_password
POSTGRES_DB=vspl_material_management
```

### Step 3.3: Frontend Dependencies
```powershell
cd "C:\VSPL_MM\Material managment system\frontend"
npm install
cd ..
```

---

## 4. Starting the Application

Open **two separate PowerShell terminal windows**:

### Terminal 1: Start FastAPI Backend
```powershell
cd "C:\VSPL_MM\Material managment system"
.\scripts\run-backend.ps1
```
*Manual alternative:*
```powershell
cd "C:\VSPL_MM\Material managment system\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
* **API URL:** `http://127.0.0.1:8000`
* **Swagger Docs:** `http://127.0.0.1:8000/docs`
* **Health Check:** `http://127.0.0.1:8000/api/v1/health`

### Terminal 2: Start React Frontend
```powershell
cd "C:\VSPL_MM\Material managment system"
.\scripts\run-frontend.ps1
```
*Manual alternative:*
```powershell
cd "C:\VSPL_MM\Material managment system\frontend"
npm run dev
```
* **Frontend Web App:** `http://localhost:5173`

---

## 5. Running Automated Tests & Verification

### Run Automated Quality Gate (Backend Tests + Frontend Build):
```powershell
cd "C:\VSPL_MM\Material managment system"
.\scripts\run-tests.ps1
```

### Run Backend Tests Independently:
```powershell
cd "C:\VSPL_MM\Material managment system"
.\backend\.venv\Scripts\pytest.exe backend\tests -v
```

### Run Frontend Build Independently:
```powershell
cd "C:\VSPL_MM\Material managment system\frontend"
npm run build
```

---

## 6. Database Migrations (Requires PostgreSQL)

When your local PostgreSQL instance is running and the database `vspl_material_management` has been created:

```powershell
# Using the automated migration runner:
.\scripts\run-migrations.ps1

# Or manually via Alembic inside backend:
cd "C:\VSPL_MM\Material managment system\backend"
.\.venv\Scripts\alembic.exe upgrade head
```

---

## 7. Common Errors & Troubleshooting

### Issue 1: PowerShell Script Execution Policy Restriction
* **Symptom:** `File ... cannot be loaded because running scripts is disabled on this system.`
* **Solution:** Run PowerShell as Administrator and enable script execution for CurrentUser:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

### Issue 2: `psql` or PostgreSQL Service Not Found
* **Symptom:** PostgreSQL is not installed or the Windows service is stopped.
* **Solution:**
  1. Verify if PostgreSQL service is installed:
     ```powershell
     Get-Service *postgres*
     ```
  2. If installed but stopped, start it:
     ```powershell
     Start-Service postgresql-x64-16
     ```
  3. If not installed, download PostgreSQL from [postgresql.org](https://www.postgresql.org/download/windows/) and run the installer. The FastAPI application will run in degraded mode with mock-safe health checks until PostgreSQL is installed.

### Issue 3: Port 8000 or 5173 Already in Use
* **Symptom:** `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`
* **Solution:** Find the occupying process and terminate it:
  ```powershell
  Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
  Stop-Process -Id <PID> -Force
  ```
