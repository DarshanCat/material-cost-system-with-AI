# VSPL Material Management & Costing System — Implementation Roadmap

This roadmap defines the engineering execution strategy across eight controlled phases for Vijay Spheroidals Pvt. Ltd. (VSPL).

---

## Roadmap Overview

```mermaid
flowchart TD
    P1[Phase 1: Foundation & Shell] --> P2[Phase 2: Master Data & Approvals]
    P2 --> P3[Phase 3: Material Entry & Validation]
    P3 --> P4[Phase 4: Append-Only Inventory Ledger]
    P4 --> P5[Phase 5: Heat Log & Issue Reconciliation]
    P5 --> P6[Phase 6: Costing & Valuation Engine]
    P6 --> P7[Phase 7: Excel Migration & Historical Reconciliation]
    P7 --> P8[Phase 8: Parallel Run, LAN Hardening & Deployment]
    
    style P1 fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    style P2 fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    style P3 fill:#fef3c7,stroke:#d97706,stroke-width:2px
```

---

## Detailed Phase Status

### Phase 1: Architectural Foundation & Development Shell
* **Status:** **COMPLETE**
* **Summary:** FastAPI backend, SQLAlchemy 2.x declarative base, Alembic migrations, React ERP shell, pytest suite, Vite build verification, and system documentation.

---

### Phase 2: Master Data & Approval Workflows
* **Status:** **COMPLETE (Current Deliverable)**
* **Summary:**
  - Material Item Master schema (`material_items`) supporting ~741 items scope.
  - Item code convention: `DEPT-CATEGORY-SERIAL` (e.g. `FDY-RM-016`).
  - Department Master (`departments`) seeded idempotently with 8 plant units.
  - Controlled UOM Master (`uoms`) with explicit quantity decimal precision (KG=4, NOS=0, LTR=3).
  - Vendor Master (`vendors`) with normalized search deduplication and optional 15-character GSTIN validation.
  - Complete Requisition State Machine (`item_requests` & `item_request_audit_logs`) enforcing `DRAFT` $\rightarrow$ `SUBMITTED` $\rightarrow$ `APPROVED` / `REJECTED` / `CANCELLED`.
  - Separation of duties: Strict self-approval prevention and mandatory rejection reason.
  - Full REST API endpoints and interactive React ERP interface with modals, search, and pagination.
  - 20 automated unit and integration tests passing.

---

### Phase 3: Material Entry & Inward/Outward Validation
* **Status:** **COMPLETE (Current Deliverable)**
* **Deliverables:**
  - Goods Receipt Note (GRN) logging with mandatory unit rate excluding GST for raw materials and separated tax rates.
  - Sourcing for external vendors, internal VSPL movements, and segregation yard returns.
  - Departmental Material Issue Slips with furnace heat allocation tracking (`H-102603-3721`).
  - Scrap and waste disposition logging across foundry categories (borings, gatings, returns, rejected castings).
  - Duplicate detection engine with hard document constraints and soft invoice audit flags.
  - Decimal precision and suspect entry heuristic engine.
  - Atomic All-or-Nothing Excel Import Engine with preview and zero partial commits on errors.
  - 29 automated Pytest tests passing and full frontend ERP views operational.

---

### Phase 4: Append-Only Live Inventory Ledger
* **Status:** **UPCOMING (Next Step)**
* **Deliverables:**
  - Immutable stock ledger table design (`stock_ledger_entries`).
  - Enforced business rule: Zero stock depletion without an authorized Issue transaction.
  - Strict prohibition of `UPDATE` and `DELETE` operations on transaction history.
  - Opening balance ledger entries as of the baseline cutoff.
  - Physical stock audit reconciliation workflow generating signed `ADJUSTMENT` journal entries.
  - Real-time stock balance queries by department and warehouse location.

---

### Phase 5: Heat Log & Requisition Reconciliation
* **Status:** **QUEUED**
* **Deliverables:**
  - Induction furnace Heat Log entry (Heat number, date, shift, furnace ID, metallurgist).
  - Detailed charge mix logging (Pig iron, Steel scrap, Returns, FeSi, FeMn, Inoculants, Mg treatment).
  - Finished parts cast and good vs rejected casting counts.
  - **Issue-to-Heat Reconciliation Module:** Compares raw materials issued to Foundry against logged furnace charges.
  - Variance reporting: Identifies melting loss, spillages, and unreported material usage without fabricating stock adjustments.

---

### Phase 6: Costing Engine & Valuation
* **Status:** **QUEUED**
* **Deliverables:**
  - Formal implementation of the Weighted-Average Costing engine.
  - Strict costing start date enforcement: **12 October 2026**.
  - Arbitrary-precision financial calculations using `Decimal/Numeric`.
  - Heat Cost calculation: Total metal charge cost divided by liquid metal tapped / good casting weight.
  - Unit Part Cost calculation for automotive and engineering castings.
  - Dedicated automated test harness with extensive parameterized test fixtures for costing algorithms.

---

### Phase 7: Excel Migration & Historical Reconciliation
* **Status:** **QUEUED**
* **Deliverables:**
  - High-integrity data migration pipeline for approximately **12,280 historical records**.
  - Comprehensive pre-import validation: column headers, type checking, duplicate detection.
  - Traceable staging tables and import discrepancy logs.
  - Historical reconciliation report comparing legacy spreadsheet totals with newly migrated ledger balances.

---

### Phase 8: Parallel Run, Security Hardening & Plant LAN Deployment
* **Status:** **QUEUED**
* **Deliverables:**
  - Production authentication system (JWT / OAuth2 / LDAP).
  - Production security hardening and plant LAN deployment.
  - Parallel run with existing Excel processes for validation and user sign-off.
