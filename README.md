# VSPL Material Management & Costing System

Enterprise Material Management & Costing System engineered for **Vijay Spheroidals Pvt. Ltd. (VSPL)** — an SG (Spheroidal Graphite) iron foundry.

The system manages inventory across **741 material items**, provides an immutable append-only stock ledger, reconciles induction furnace heat logs against material issues, and calculates weighted-average metal and part costs with a baseline cutoff of **12 October 2026**.

---

## Current Status: Phase 3 Active (Material Entry & Transaction Validation)

- **Phase 1: Foundation & Application Shell** — Complete
- **Phase 2: Master Data & Approval Workflows** — Complete
- **Phase 3: Material Entry & Transaction Validation** — Complete
  - Goods Receipt Notes (`grn_headers`, `grn_line_items`) for External Vendors, Internal VSPL, and Segregation Yard.
  - Pre-GST rate enforcement for raw materials with tax separation.
  - Material Issue Slips (`material_issue_headers`, `material_issue_line_items`) with heat number standardization (`H-102603-3721`).
  - Scrap & Waste Disposition (`waste_disposition_headers`, `waste_disposition_line_items`) with recovery / outward classification.
  - Duplicate detection engine preventing duplicate document numbers and double invoice processing.
  - Decimal precision and suspect entry heuristic validation.
  - Atomic All-or-Nothing Excel Import Engine (`/api/v1/excel-import`) with preview and zero partial commits.
  - 29 automated Pytest tests passing.

---

## Technology Stack

- **Backend:** Python 3.11+ (tested on Python 3.14), FastAPI, SQLAlchemy 2.x, Alembic, psycopg 3, Pydantic v2, Pytest
- **Frontend:** React 19, TypeScript, Vite, Lucide Icons
- **Database:** PostgreSQL (with `DECIMAL`/`NUMERIC` precision for financial and quantity calculations)
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
│   │   │       │   ├── health.py
│   │   │       │   ├── departments.py
│   │   │       │   ├── uoms.py
│   │   │       │   ├── items.py
│   │   │       │   ├── vendors.py
│   │   │       │   └── item_requests.py
│   │   │       └── api.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── security.py          # RBAC matrix, DevUserContext, permissions
│   │   ├── db/
│   │   │   ├── base.py              # DeclarativeBase, TimestampMixin
│   │   │   ├── session.py           # Engine & SessionLocal
│   │   │   └── seed.py              # Idempotent reference data seeding
│   │   ├── models/
│   │   │   ├── department.py
│   │   │   ├── uom.py
│   │   │   ├── item.py
│   │   │   ├── vendor.py
│   │   │   └── item_request.py
│   │   ├── schemas/
│   │   │   ├── department.py
│   │   │   ├── uom.py
│   │   │   ├── item.py
│   │   │   ├── vendor.py
│   │   │   ├── item_request.py
│   │   │   └── health.py
│   │   ├── services/
│   │   │   ├── validators.py        # GSTIN & vendor normalization
│   │   │   └── item_request_service.py # Workflow state machine
│   │   └── main.py
│   ├── migrations/
│   │   ├── versions/
│   │   │   └── 001_phase2_master_data.py # Master data & workflow tables
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── tests/
│   │   ├── conftest.py              # Test database session & role fixtures
│   │   ├── test_config.py
│   │   ├── test_health.py
│   │   ├── test_master_data.py      # Master data & code generation tests
│   │   ├── test_vendors.py          # Vendor deduplication & GSTIN tests
│   │   └── test_item_requests_workflow.py # Approval workflow & state tests
│   ├── requirements.txt
│   ├── .env.example
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DashboardView.tsx
│   │   │   ├── MaterialMasterView.tsx
│   │   │   ├── VendorMasterView.tsx
│   │   │   ├── ItemRequestsView.tsx
│   │   │   ├── ReferenceDataView.tsx
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
│   ├── ARCHITECTURE.md              # System boundaries, RBAC matrix, auditability
│   ├── DATABASE_DESIGN.md           # Entity specifications, ER diagram, precision rules
│   ├── BUSINESS_RULES.md            # Master data & non-negotiable accounting rules
│   ├── IMPLEMENTATION_ROADMAP.md    # 8-Phase engineering delivery roadmap
│   └── SETUP_GUIDE.md               # PowerShell commands & troubleshooting
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
- **Python 3.11+** (`python --version`)
- **Node.js v18+ & npm** (`node --version`, `npm --version`)
- **PostgreSQL 15+** (Required for real database persistence and migrations)

### 2. Environment Initialization
Run the automated setup script:
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

To execute all automated quality gates (20 backend unit & integration tests + frontend TypeScript typecheck and Vite production build):
```powershell
.\scripts\run-tests.ps1
```

---

## Project Documentation

Detailed technical documentation is available in the `docs/` directory:
- [ARCHITECTURE.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/ARCHITECTURE.md)
- [DATABASE_DESIGN.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/DATABASE_DESIGN.md)
- [BUSINESS_RULES.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/BUSINESS_RULES.md)
- [IMPLEMENTATION_ROADMAP.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/IMPLEMENTATION_ROADMAP.md)
- [SETUP_GUIDE.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/SETUP_GUIDE.md)
