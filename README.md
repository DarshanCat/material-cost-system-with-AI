# VSPL Material Management & Costing System

Enterprise Material Management & Costing System engineered for **Vijay Spheroidals Pvt. Ltd. (VSPL)** — an SG (Spheroidal Graphite) iron foundry.

The system manages inventory across **741 material items**, provides an immutable append-only stock ledger, reconciles induction furnace heat logs against material issues, and calculates weighted-average metal and part costs with a baseline cutoff of **12 October 2026**.

---

## Current Status: Phase 4 Active (Append-Only Live Inventory Ledger)

- **Phase 1: Foundation & Application Shell** — Complete
- **Phase 2: Master Data & Approval Workflows** — Complete
- **Phase 3: Material Entry & Transaction Validation** — Complete
- **Phase 4: Append-Only Live Inventory Ledger** — Complete
  - Append-Only Stock Ledger (`stock_ledger_entries`) with absolute immutability (zero `UPDATE` / `DELETE` endpoints).
  - Derived Balance Calculation Engine (`SUM(quantity_delta)`) with point-in-time historical reconstruction.
  - 4 Distinct Stock States: `UNINITIALIZED`, `IN_STOCK`, `OUT_OF_STOCK`, `NEGATIVE_STOCK`.
  - Transactional posting coordinated directly with document approvals (GRN $\rightarrow$ Inward Receipt, Issue $\rightarrow$ Outward Issue, Waste $\rightarrow$ Scrap Outward/Recovery).
  - Database-enforced idempotency via `UNIQUE(source_document_type, source_line_id)` preventing duplicate postings.
  - Traceable compensating `REVERSAL` journal entries linked via `reversal_of_entry_id`.
  - Configurable negative stock prevention (`settings.ALLOW_NEGATIVE_STOCK = False` default) and uninitialized stock protection.
  - Baseline Opening Balance import engine for **12 October 2026** cutoff with preview validation and atomic commit.
  - Physical Stock Audit Module (`physical_audit_headers`, `physical_audit_lines`) calculating system cutoff balances, recording physical counts, and posting signed variance adjustments.
  - Interactive industrial ERP frontend views: Live Inventory Dashboard, Opening Balance View, Physical Audit Reconciliation.
  - 35 automated Pytest tests passing with zero regressions.

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
│   │   │       │   ├── item_requests.py
│   │   │       │   ├── grn.py
│   │   │       │   ├── issues.py
│   │   │       │   ├── waste.py
│   │   │       │   ├── excel_import.py
│   │   │       │   ├── ledger.py
│   │   │       │   ├── opening_balances.py
│   │   │       │   └── physical_audits.py
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
│   │   │   ├── item_request.py
│   │   │   ├── grn.py
│   │   │   ├── issue.py
│   │   │   ├── waste.py
│   │   │   ├── ledger.py
│   │   │   └── physical_audit.py
│   │   ├── schemas/
│   │   │   ├── department.py
│   │   │   ├── uom.py
│   │   │   ├── item.py
│   │   │   ├── vendor.py
│   │   │   ├── item_request.py
│   │   │   ├── grn.py
│   │   │   ├── issue.py
│   │   │   ├── waste.py
│   │   │   ├── excel_import.py
│   │   │   ├── ledger.py
│   │   │   ├── opening_balance.py
│   │   │   └── physical_audit.py
│   │   ├── services/
│   │   │   ├── validators.py        # GSTIN & vendor normalization
│   │   │   ├── item_request_service.py # Workflow state machine
│   │   │   ├── grn_service.py
│   │   │   ├── issue_service.py
│   │   │   ├── waste_service.py
│   │   │   ├── excel_import_service.py
│   │   │   ├── ledger_service.py    # Append-only journal & derived balances
│   │   │   ├── opening_balance_service.py
│   │   │   └── physical_audit_service.py
│   │   └── main.py
│   ├── migrations/
│   │   ├── versions/
│   │   │   ├── 001_phase2_master_data.py
│   │   │   ├── 002_phase3_material_entry.py
│   │   │   └── 003_phase4_stock_ledger.py
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── tests/
│   │   ├── conftest.py              # Test database session & role fixtures
│   │   ├── test_config.py
│   │   ├── test_health.py
│   │   ├── test_master_data.py
│   │   ├── test_vendors.py
│   │   ├── test_item_requests_workflow.py
│   │   ├── test_grn.py
│   │   ├── test_issues.py
│   │   ├── test_waste.py
│   │   ├── test_excel_import.py
│   │   ├── test_ledger_posting.py
│   │   ├── test_ledger_issues.py
│   │   ├── test_opening_balances.py
│   │   └── test_physical_audits.py
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
│   │   │   ├── GRNManagementView.tsx
│   │   │   ├── MaterialIssueView.tsx
│   │   │   ├── WasteDispositionView.tsx
│   │   │   ├── ExcelImportView.tsx
│   │   │   ├── LiveInventoryDashboard.tsx
│   │   │   ├── OpeningBalanceView.tsx
│   │   │   ├── PhysicalAuditView.tsx
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
