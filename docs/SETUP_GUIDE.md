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
> - **NOT Required for:** Running the frontend UI, executing the automated test suite (uses isolated in-memory test session), browsing API Swagger documentation, and evaluating workflow states in dev mode.
> - **REQUIRED for:** Running Alembic database migrations (`alembic upgrade head`), saving real persistent item master records, posting transactions, and querying persistent stock ledger entries.

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

## 3. Starting the Application

Open **two separate PowerShell terminal windows**:

### Terminal 1: Start FastAPI Backend
```powershell
cd "C:\VSPL_MM\Material managment system"
.\scripts\run-backend.ps1
```
*Direct execution:*
```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
* **API URL:** `http://127.0.0.1:8000`
* **Swagger Docs:** `http://127.0.0.1:8000/docs`
* **Departments API:** `http://127.0.0.1:8000/api/v1/departments`
* **UOMs API:** `http://127.0.0.1:8000/api/v1/uoms`
* **Items API:** `http://127.0.0.1:8000/api/v1/items`
* **Vendors API:** `http://127.0.0.1:8000/api/v1/vendors`
* **Item Requests API:** `http://127.0.0.1:8000/api/v1/item-requests`

### Terminal 2: Start React Frontend
```powershell
cd "C:\VSPL_MM\Material managment system"
.\scripts\run-frontend.ps1
```
*Direct execution:*
```powershell
cd frontend
npm run dev
```
* **Frontend Web App:** `http://localhost:5173`

---

## 4. Running Automated Tests & Verification

### Run Automated Quality Gate (Backend Pytest Suite + Frontend Build):
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

## 5. Database Migrations & Seeding (Requires PostgreSQL)

When your local PostgreSQL instance is running and the database `vspl_material_management` has been created:

```powershell
# 1. Run migrations to head
.\scripts\run-migrations.ps1

# Or manually inside backend:
cd "C:\VSPL_MM\Material managment system\backend"
.\.venv\Scripts\alembic.exe upgrade head

# 2. Seed the 8 departments and standard UOMs into PostgreSQL:
.\.venv\Scripts\python.exe -c "from app.db.session import SessionLocal; from app.db.seed import seed_reference_data; db = SessionLocal(); print(seed_reference_data(db)); db.close()"
```

---

## 6. Common Errors & Troubleshooting

### Issue 1: PowerShell Script Execution Policy Restriction
* **Symptom:** `File ... cannot be loaded because running scripts is disabled on this system.`
* **Solution:** Run PowerShell as Administrator and enable script execution for CurrentUser:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

### Issue 2: PostgreSQL Service Not Found
* **Symptom:** `psql` or PostgreSQL service is not installed on this workstation.
* **Solution:** Download and install PostgreSQL 15+ or 16+ from [postgresql.org](https://www.postgresql.org/download/windows/). Create database `vspl_material_management` and update `backend\.env`. The test suite and frontend run safely even before PostgreSQL is installed.

### Issue 3: Port 8000 or 5173 Occupied
* **Solution:**
  ```powershell
  Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
  Stop-Process -Id <PID> -Force
  ```

## Authentication note (Security Hardening Sprint 1)

The API no longer trusts `X-User-*` headers. By default (`AUTH_PROVIDER=none`) every protected route returns HTTP 401. For local development set `ENVIRONMENT=development` and `AUTH_PROVIDER=dev` in `backend\.env` (both are in `.env.example`); the UI then signs in through the loopback-only dev endpoint. Production authentication is pending IT approval - see `docs/security/AUTHENTICATION_INTEGRATION.md`.
