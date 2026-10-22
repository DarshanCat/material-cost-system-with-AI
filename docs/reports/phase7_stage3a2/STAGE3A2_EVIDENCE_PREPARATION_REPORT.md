# VSPL Material Management & Costing System — Stage 3A.2 Evidence Preparation Report

**Document ID:** `DOC-P7-S3A2-MASTER-REPORT`  
**System:** VSPL Material Management & Costing System  
**Date:** 2026-10-17  
**Governance Scope:** Master Synthesis & Departmental Evidence Package for Migration Blocker Remediation  
**Execution Status:** **READ-ONLY PLANNING & DOCUMENTATION PHASE — STAGE 3B STRICTLY UNAUTHORIZED**  

---

## 1. Executive Summary

This report completes **Phase 7 Stage 3A.2: Remediation Evidence Preparation** for Vijay Spheroidals Pvt. Ltd. (VSPL). Building directly upon the Stage 3A Pre-Flight Assessment and the Stage 3A.1 Readiness Remediation Plan, this package translates the outstanding migration blockers into actionable, departmental evidence requirements.

### 1.1 Executive Scorecard & System Status
- **Repository Branch:** `master`
- **Git Commit HEAD:** `dd85bcc64e1da9268075077159ccd2abf6a94f0b` (Verified intact)
- **Automated Regression Suite:** **68 of 68 tests passing** in 5.62s (Isolated in-memory SQLite `StaticPool`)
- **Acceptance Gate Status:** **1 of 13 Gates Satisfied** (Gate `G11`: Cryptographic Hashes 100% verified; Gates `G1`–`G10` and `G12`–`G13` remain **BLOCKED**)
- **Executive Decision Status:** **0 of 8 Decisions Approved** (`DEC-001` through `DEC-008` remain strictly `PENDING_REVIEW`)
- **PostgreSQL Database Status:** Target database **NOT PROVISIONED**. Host port `5432` is actively claimed by OMS container `backend-db-1`; dedicated non-production port `5439` is verified unallocated.
- **Governing Prohibition:** **Stage 3 Live Historical Migration remains STRICTLY UNAUTHORIZED.**

---

## 2. Baseline Verification & Evidence Hash Integrity

In compliance with mandatory safety rules, all underlying data assets, frozen archives, and software baselines were cryptographically and programmatically verified prior to generating this package:

### 2.1 Cryptographic Hash Verification Table
Every source workbook and the Stage 2.1 frozen archive match their recorded cryptographic baselines to the exact byte:

| Data Asset | Physical File Location | Baseline SHA-256 Digest | Verified Digest | Match Status |
| :--- | :--- | :--- | :--- | :--- |
| **ITEM_MASTER** | `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Item_Master.xlsx` | `6005441b7b022cc8b6e4e65b2d2563ca4462e2448eb3c66d5fdf40552c6e8ccd` | `6005441b7b022cc8b6e4e65b2d2563ca4462e2448eb3c66d5fdf40552c6e8ccd` | **VERIFIED (100%)** |
| **MATERIAL_ENTRY** | `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Material_Entry.xlsx` | `97c6448db72fa65bdc09ec0956c9dbb7d645de7a854cf5c20d072b3df8376cb4` | `97c6448db72fa65bdc09ec0956c9dbb7d645de7a854cf5c20d072b3df8376cb4` | **VERIFIED (100%)** |
| **HEAT_LOG** | `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Foundry_Heat_Log.xlsx` | `356e8c536a3c3cb853869804d65dd2381df7e7ec3731e798b7b26be2345f881d` | `356e8c536a3c3cb853869804d65dd2381df7e7ec3731e798b7b26be2345f881d` | **VERIFIED (100%)** |
| **MASTER_LEDGER** | `C:\VSPL_MM\VSPL_MM_Data\ledger\VSPL_Master_Ledger.xlsx` | `7cb034054d5b4c4e471558b6e1c52b4c0ec7dc786d9b9a555aed42193d984600` | `7cb034054d5b4c4e471558b6e1c52b4c0ec7dc786d9b9a555aed42193d984600` | **VERIFIED (100%)** |
| **STORE_INVENTORY**| `C:\VSPL_MM\_legacy_archive\Store Inventory.xlsx` | `40194dcf05ea29efb42f61aae7c25787a6f0ad482bca4b2bdfa777c7a6874b6d` | `40194dcf05ea29efb42f61aae7c25787a6f0ad482bca4b2bdfa777c7a6874b6d` | **VERIFIED (100%)** |
| **FREEZE_ARCHIVE** | `C:\VSPL_MM\VSPL_Phase7_Stage2_1_Evidence_Freeze_20261013.zip` | `033684d8b26dc65e9c67b569e48991b07c0d0909c2cc37717b5d3485d922c5c5` | `033684d8b26dc65e9c67b569e48991b07c0d0909c2cc37717b5d3485d922c5c5` | **VERIFIED (100%)** |

### 2.2 Automated Regression Suite Baseline
- **Execution Command:** `backend\.venv\Scripts\python.exe -m pytest backend/tests`
- **Results:** 68 passed, 3 deprecation warnings in **5.62 seconds**.
- **Dialect Invariant:** All tests execute against an in-memory SQLite database utilizing `StaticPool`. Passing SQLite tests does **not** prove PostgreSQL 16 dialect readiness or concurrency safety.

---

## 3. Cross-Document Reconciliation & Unresolved Findings

A systematic audit across `docs/reports/phase7_stage2_1/`, `docs/reports/phase7_stage3_preflight/`, and `docs/reports/phase7_stage3a1/` confirms complete mathematical consistency across reported figures:

1. **Candidate Transaction Population (616 Rows):**
   - Sourced from `VSPL_Material_Entry.xlsx`:
     - '3. Receipt GRN': 4 rows (rows 2–5)
     - '4. Issue': 600 rows (rows 2–601)
     - '5. Scrap': 12 rows (rows 2–13)
   - Reconciled dual classification lenses:
     - **Technical Lens:** 545 VALID_NEW_CANDIDATE, 31 MANUAL_REVIEW, 37 INVALID_SOURCE, 3 UNMAPPED (Total = 616).
     - **Operational Lens:** 515 ELIGIBLE, 66 PENDING_REVIEW, 35 BLOCKED (Total = 616).
2. **The 82-Day Operational Void:**
   - Digital logging in source workbooks ceases abruptly on **22-Jul-2026**.
   - System costing start date is **12-Oct-2026**.
   - 82 calendar days of foundry melt operations and store issues have zero electronic trace.
3. **The 7 Negative Balances & 11,793 kg Omitted Scrap Issues:**
   - `VSPL_Master_Ledger.xlsx` subtracted furnace charges for heat `H-260714-01` directly from zero opening stock, yielding negative balances for 7 raw materials (-500 kg to -2 kg).
   - Simultaneously, 11,793 kg of scrap issues recorded on store issue slips were completely omitted from the interim ledger sheet.
   - **Reconciliation Verdict:** Confirms that carrying unverified July balances forward without a certified physical stocktake will corrupt live inventory and financial moving average costs.

---

## 4. The Stage 3A.2 Deliverables Package

To provide departmental ownership and granular tracking, seven dedicated deliverables have been generated in [`docs/reports/phase7_stage3a2/`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a2/):

| Deliverable Artifact | Primary Target Audience | Core Content & Governance Value |
| :--- | :--- | :--- |
| [`STAGE3A2_EVIDENCE_PREPARATION_REPORT.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a2/STAGE3A2_EVIDENCE_PREPARATION_REPORT.md) | Executive Management & Auditors | Master synthesis, baseline verification, cross-document reconciliation, safety declarations. |
| [`DECISION_EVIDENCE_REGISTER.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a2/DECISION_EVIDENCE_REGISTER.csv) | Project Management & Leads | Exhaustive register for `DEC-001`–`DEC-008` documenting verified facts, source coordinates, required evidence, owners, criteria, impacts, and blocking conditions. |
| [`DEPARTMENT_EVIDENCE_CHECKLISTS.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a2/DEPARTMENT_EVIDENCE_CHECKLISTS.md) | Department Heads & Supervisors | Concrete, field-level evidence checklists for Purchase/Finance, Stores, Foundry/Quality, Master-Data Owner, Management, and IT. |
| [`G1_G13_EVIDENCE_TRACKER.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a2/G1_G13_EVIDENCE_TRACKER.csv) | Lead QA Auditor & Leads | Exhaustive tracker for Gates `G1`–`G13` detailing current status, evidence present, missing evidence, verification procedures, and pass criteria. |
| [`POSTGRESQL_VERIFICATION_CHECKLIST.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a2/POSTGRESQL_VERIFICATION_CHECKLIST.md) | Lead DBA & Systems Architect | Technical pre-provisioning verification checklist detailing port 5439, loopback isolation, volume allocation, Alembic checks, and test requirements without provisioning. |
| [`MIGRATION_CONTROL_VERIFICATION_MATRIX.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a2/MIGRATION_CONTROL_VERIFICATION_MATRIX.csv) | Software Engineers & Auditors | Verification matrix analyzing 12 migration controls, classifying each as `VERIFIED_IN_CODE`, `VERIFIED_IN_TESTS`, `PLANNED_IN_DESIGN`, or `DOCUMENTATION_ONLY`. |
| [`OPEN_BLOCKERS_AND_DEPENDENCIES.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a2/OPEN_BLOCKERS_AND_DEPENDENCIES.md) | Technical Project Manager | Comprehensive dependency mapping, Mermaid flowchart, critical path analysis, risk escalation triggers, and safe sequential next actions. |

---

## 5. Departmental Distribution & Action Plan

Each operational department must execute its specific evidence collection tasks without modifying application databases:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   DEPARTMENTAL EVIDENCE DISTRIBUTION                   │
├────────────────────────────────────────────────────────────────────────┤
│ 1. PURCHASE / FINANCE (DEC-001 -> Gate G3)                             │
│    • Retrieve vendor tax invoices for GRN rows 2-5.                    │
│    • Extract ex-GST unit rates and certify commercial rate schedule.   │
├────────────────────────────────────────────────────────────────────────┤
│ 2. STORES (DEC-003, DEC-004, DEC-005, DEC-006 -> Gates G4, G6, G7, G8) │
│    • Audit physical issue slips 327-1148; certify date 2026-07-16.     │
│    • Execute double-blind physical stocktake per SOP-P7 (12-Oct cut).   │
│    • Submit Item Creation Requests for MNT-CN-001 and MCS-CN-002.      │
├────────────────────────────────────────────────────────────────────────┤
│ 3. FOUNDRY / QUALITY (DEC-003, DEC-007 -> Gates G5, G9)                │
│    • Conduct spectrometer test on CRCA scrap (classify 007 vs 008).    │
│    • Retrieve paper melt deck heat logs for 22-Jul (or sign quarantine)│
├────────────────────────────────────────────────────────────────────────┤
│ 4. MASTER DATA OWNER (DEC-003, DEC-006 -> Gates G4, G8)                │
│    • Approve canonical codes MNT-CN-001 and MCS-CN-002 in master.      │
│    • Filter sample dummy row 2 from manifest generation scripts.       │
├────────────────────────────────────────────────────────────────────────┤
│ 5. EXECUTIVE MANAGEMENT (DEC-001..008 -> Gates G1, G2)                 │
│    • Sign executive policy mandate adopting Scenario A Cutoff.         │
│    • Execute MANAGEMENT_SIGNOFF_TEMPLATE.md across all 8 decisions.    │
├────────────────────────────────────────────────────────────────────────┤
│ 6. IT & DATABASE OPERATIONS (DEC-008 -> Gates G10, G12, G13)           │
│    • Sign formal retirement memorandum for Store Inventory.xlsx.       │
│    • Verify port 5439 availability and Docker compose non-prod spec.   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Migration Control Verification Summary

The architectural assessment in `MIGRATION_CONTROL_VERIFICATION_MATRIX.csv` provides a rigorous breakdown of existing application capabilities versus future tooling:

- **Controls Fully Verified in Code & Tests (7 Controls):**
  1. Relational unique constraint `uq_source_doc_line_posting` on `stock_ledger_entries` (`MC-02`).
  2. Domain service duplicate check in [`ledger_service.py`](file:///C:/VSPL_MM/Material%20managment%20system/backend/app/services/ledger_service.py) (`MC-03`).
  3. Mandatory domain service dispatch path (`MC-04`).
  4. Negative stock balance prevention via HTTP 409 Conflict (`MC-05`).
  5. Uninitialized balance recognition (`MC-06`).
  6. Phase 5 Rule H1 isolation of furnace charges from inventory ledger (`MC-07`).
  7. Phase 6 Rule C1 moving weighted-average recalculation (`MC-08`).
  8. Compensating reversal immutability (`MC-09`).
- **Controls Planned in Architectural Design (4 Controls):**
  1. Canonical source coordinate key generation (`MC-01`).
  2. Document-level nested transaction savepoint boundaries (`MC-10`).
  3. Checkpoint resumption from `migration_batch_logs` (`MC-11`).
- **Controls Existing as Documentation Only (1 Control):**
  1. Per-document error quarantine to `migration_exceptions.csv` (`MC-12`).

---

## 7. PostgreSQL Non-Production Environment Review

Pre-flight inspection confirms that **Port `5432` remains actively claimed by `backend-db-1`** (the Order Management System container in `C:\VSPL`). 
- **Target Non-Production Port:** Port **`5439`** is verified completely free of listening sockets.
- **Specification:** [`POSTGRESQL_NONPROD_SETUP_PLAN.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a1/POSTGRESQL_NONPROD_SETUP_PLAN.md) provides the complete Compose definition (`postgres:16-alpine`), loopback binding (`127.0.0.1:5439`), dedicated named volume (`vspl_mm_pg16_nonprod_data`), and application role isolation (`vspl_app`).
- **Safety Status:** **NO CONTAINERS WERE STARTED.** Deployment remains paused until executive clearance is granted.

---

## 8. Safety Affirmation & Recommended Next Action

### Mandatory Safety Confirmation:
- **Zero Database Writes:** No SQL inserts, updates, deletes, or ledger postings occurred.
- **Zero Infrastructure Changes:** No Docker commands, Windows services, or network adapters were modified.
- **Zero Schema Migrations:** No Alembic commands were executed against any database.
- **Zero Source Modifications:** All five source workbooks remain unedited, with SHA-256 hashes matching baseline digests 100%.

### Recommended Next Safe Action:
1. Distribute [`DEPARTMENT_EVIDENCE_CHECKLISTS.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a2/DEPARTMENT_EVIDENCE_CHECKLISTS.md) to respective department heads.
2. Convene executive briefing with Managing Director and Plant Head to execute **Scenario A Cutoff Policy Mandate (DEC-002)**.
3. Initiate physical stocktake preparation per [`PHYSICAL_STOCKTAKE_PROTOCOL.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stocktake_preparation/PHYSICAL_STOCKTAKE_PROTOCOL.md) as the primary critical-path milestone.

**Stage 3A.2 is complete. Stage 3B remains unauthorized.**
