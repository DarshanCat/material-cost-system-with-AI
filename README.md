# VSPL Material Management & Costing System

Enterprise Material Management & Costing System engineered for **Vijay Spheroidals Pvt. Ltd. (VSPL)** — an SG (Spheroidal Graphite) iron foundry.

The system manages inventory across **741 material items**, provides an immutable append-only stock ledger, reconciles induction furnace heat logs against material issues, and calculates weighted-average metal and part costs with a baseline cutoff of **12 October 2026**.

---

## Current Status: Phase 5 Active (Induction Furnace Heat Log & Issue Reconciliation)

- **Phase 1: Foundation & Application Shell** — Complete
- **Phase 2: Master Data & Approval Workflows** — Complete
- **Phase 3: Material Entry & Transaction Validation** — Complete
- **Phase 4: Append-Only Live Inventory Ledger** — Complete
- **Phase 5: Induction Furnace Heat Log & Issue Reconciliation** — Complete
  - Induction Furnace Heat Logs (`heat_headers`, `heat_charge_lines`, `heat_parts_produced`) capturing heat number, furnace ID, shift, charged materials, and parts produced.
  - Heat reference normalization: bidirectional matching between `102603-3721` and `H-102603-3721`.
  - Material Alias Master (`material_aliases`, `material_alias_audit_logs`) mapping raw descriptions (e.g. `CRC Scrap-Low High MN`) to canonical items without mutating source records.
  - Deterministic 3-Pass Reconciliation Engine (`reconciliation_runs`, `reconciliation_results`):
    - **Pass 1:** Exact heat reference matching with line-by-line item comparison.
    - **Pass 2:** Same-day batch aggregation for remaining unallocated lines without double-counting.
    - **Pass 3:** Advisory fuzzy candidate suggestions (`reconciliation_candidate_matches`) requiring explicit supervisor confirmation.
  - Tolerance Precedence Rule: $\text{Limit} = \max(0.50\text{ kg}, 0.02 \times \text{Issued Quantity})$.
  - Signed Variance Convention: $\text{Variance} = \text{Issued Quantity} - \text{Charged Quantity}$.
  - Exception Management Queue (`reconciliation_exceptions`) with assignment and resolution workflows.
  - Multi-sheet/flattened Heat Log Excel Import Engine with dry-run preview and atomic rollback on validation errors.
  - **NON-NEGOTIABLE ISOLATION:** Strictly zero stock ledger movements or balance adjustments caused by heat logs or reconciliation runs.
  - Interactive industrial ERP frontend views: Furnace Heat Log Manager, Material Aliases, Reconciliation Dashboard, and Heat Excel Import.
  - 46 automated Pytest tests passing with zero regressions.

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
│   │   │       │   ├── physical_audits.py
│   │   │       │   ├── heats.py
│   │   │       │   ├── material_aliases.py
│   │   │       │   ├── reconciliation.py
│   │   │       │   └── heat_import.py
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
│   │   │   ├── physical_audit.py
│   │   │   ├── heat.py
│   │   │   ├── material_alias.py
│   │   │   └── reconciliation.py
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
│   │   │   ├── physical_audit.py
│   │   │   ├── heat.py
│   │   │   ├── material_alias.py
│   │   │   └── reconciliation.py
│   │   ├── services/
│   │   │   ├── validators.py        # GSTIN, vendor & heat normalizations
│   │   │   ├── item_request_service.py # Workflow state machine
│   │   │   ├── grn_service.py
│   │   │   ├── issue_service.py
│   │   │   ├── waste_service.py
│   │   │   ├── excel_import_service.py
│   │   │   ├── ledger_service.py    # Append-only journal & derived balances
│   │   │   ├── opening_balance_service.py
│   │   │   ├── physical_audit_service.py
│   │   │   ├── material_alias_service.py
│   │   │   ├── heat_service.py
│   │   │   ├── reconciliation_service.py # 3-pass reconciliation engine
│   │   │   └── heat_import_service.py
│   │   └── main.py
│   ├── migrations/
│   │   ├── versions/
│   │   │   ├── 001_phase2_master_data.py
│   │   │   ├── 002_phase3_material_entry.py
│   │   │   ├── 003_phase4_stock_ledger.py
│   │   │   └── 004_phase5_heat_reconciliation.py
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
│   │   ├── test_physical_audits.py
│   │   ├── test_heats.py
│   │   ├── test_material_aliases.py
│   │   ├── test_reconciliation.py
│   │   ├── test_reconciliation_isolation.py
│   │   └── test_heat_import.py
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
│   │   │   ├── HeatLogManagementView.tsx
│   │   │   ├── MaterialAliasView.tsx
│   │   │   ├── ReconciliationDashboard.tsx
│   │   │   ├── HeatExcelImportView.tsx
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
