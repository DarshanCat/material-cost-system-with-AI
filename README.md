# VSPL Material Management & Costing System

Enterprise Material Management & Costing System engineered for **Vijay Spheroidals Pvt. Ltd. (VSPL)** — an SG (Spheroidal Graphite) iron foundry.

The system manages inventory across **741 material items**, provides an immutable append-only stock ledger, reconciles induction furnace heat logs against material issues, and calculates weighted-average metal and part costs with a baseline cutoff of **12 October 2026**.

---

## Technology Stack

- **Backend:** Python 3.11+ (tested on Python 3.14), FastAPI, SQLAlchemy 2.x, Alembic, psycopg 3, Pydantic v2, Pytest
- **Frontend:** React 19, TypeScript, Vite, Lucide Icons
- **Database:** PostgreSQL (with `DECIMAL`/`NUMERIC` precision for financial calculations)
- **Deployment Target:** Industrial Plant Local Area Network (LAN)

---

## Directory Structure

```
VSPL-Material-Management-Costing/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   └── health.py
│   │   │       └── api.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── security.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   └── session.py
│   │   ├── models/
│   │   ├── schemas/
│   │   │   └── health.py
│   │   ├── services/
│   │   ├── repositories/
│   │   └── main.py
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_config.py
│   │   └── test_health.py
│   ├── requirements.txt
│   ├── .env.example
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DashboardView.tsx
│   │   │   ├── DiagnosticsView.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── ModulePlaceholder.tsx
│   │   │   └── Sidebar.tsx
│   │   ├── App.css
│   │   ├── App.tsx
│   │   ├── index.css
│   │   ├── main.tsx
│   │   └── types.ts
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATABASE_DESIGN.md
│   ├── BUSINESS_RULES.md
│   ├── IMPLEMENTATION_ROADMAP.md
│   └── SETUP_GUIDE.md
├── scripts/
│   ├── setup-env.ps1
│   ├── run-backend.ps1
│   ├── run-frontend.ps1
│   ├── run-tests.ps1
│   └── run-migrations.ps1
├── .gitignore
└── README.md
```

---

## Quick Start (Windows PowerShell)

### 1. Prerequisites
- **Python 3.11+** installed (`python --version`)
- **Node.js v18+ & npm** installed (`node --version`, `npm --version`)
- **PostgreSQL 15+** installed and running (required for real migrations and database persistence)

### 2. Environment Initialization
Run the automated environment setup script:
```powershell
.\scripts\setup-env.ps1
```

### 3. Start Backend Server
```powershell
.\scripts\run-backend.ps1
```
- API Base: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Swagger OpenAPI Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

### 4. Start Frontend Application
In a second PowerShell terminal:
```powershell
.\scripts\run-frontend.ps1
```
- Web Application: [http://localhost:5173](http://localhost:5173)

---

## Testing & Quality Assurance

To execute all automated quality gates (backend pytest suite + frontend TypeScript typecheck and Vite build):
```powershell
.\scripts\run-tests.ps1
```

### Run Backend Tests Independently:
```powershell
.\backend\.venv\Scripts\pytest.exe backend\tests -v
```

### Run Frontend Build Independently:
```powershell
cd frontend
npm run build
```

---

## Database Migrations

When your local PostgreSQL instance is running:
```powershell
.\scripts\run-migrations.ps1
```

> **Note:** The application starts and functions in offline-safe mode even if PostgreSQL is not currently active, reporting degraded database health without crashing.

---

## Project Documentation

Detailed technical documentation is available in the `docs/` directory:
- [ARCHITECTURE.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/ARCHITECTURE.md) — System boundaries, layered architecture, RBAC, and audit principles.
- [DATABASE_DESIGN.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/DATABASE_DESIGN.md) — Relational schema design, entity definitions, and Decimal precision rules.
- [BUSINESS_RULES.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/BUSINESS_RULES.md) — Strict accounting invariants, cutoff dates, and unresolved costing decisions.
- [IMPLEMENTATION_ROADMAP.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/IMPLEMENTATION_ROADMAP.md) — 8-Phase engineering delivery roadmap.
- [SETUP_GUIDE.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/SETUP_GUIDE.md) — Complete Windows setup guide and troubleshooting.
