# VSPL Material Management & Costing System — Phase 7 Stage 3A Pre-Flight Report

**Document ID:** `DOC-P7-S3A-PREFLIGHT-MASTER`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd., Peenya Industrial Area, Bangalore  
**Audit Date:** 2026-10-17  
**Git Branch & HEAD:** `master` at [`dd85bcc`](file:///C:/VSPL_MM/Material%20managment%20system/backend/app/models/costing.py)  
**Test Suite Verification:** **68/68 Tests Passing (4.65s)** in isolated in-memory SQLite  
**Frontend Build Verification:** **TypeScript / Vite build passed** (1928 modules, 487ms)  
**Frozen Evidence Archive:** `C:\VSPL_MM\VSPL_Phase7_Stage2_1_Evidence_Freeze_20261013.zip`  
**Archive SHA-256 Digest:** `033684d8b26dc65e9c67b569e48991b07c0d0909c2cc37717b5d3485d922c5c5` (Verified)  
**Governance Scope:** Read-Only Migration Pre-Flight Assessment  
**Overall Readiness Verdict:** **BLOCKED (0% LIVE READINESS) — STAGE 3B STRICTLY UNAUTHORIZED**  

---

## 1. Executive Summary & Mandatory Compliance Statement

This master report synthesizes the read-only pre-flight assessment conducted under **Phase 7 Stage 3A** for the VSPL Material Management & Costing System.

### Mandatory Compliance Confirmation:
- **Zero Database Writes:** No connection to a production or development PostgreSQL database was established; zero database writes, table updates, or schema mutations were executed.
- **Zero Stock Postings:** Zero inventory movements, opening balances, or stock adjustments were posted to the stock ledger.
- **Source Immutability:** All five primary historical Excel workbooks remain unaltered with bit-for-bit verified cryptographic checksums.
- **Isolation Preserved:** The core ERP codebase, migrations, and test suite remain intact at commit `dd85bcc`.
- **Phase Boundary:** This assessment concludes Stage 3A. **Phase 7 Stage 3B live import remains strictly unauthorized.**

---

## 2. Cryptographic Source Integrity & Archive Verification

The integrity of all historical source files was verified against the immutable Stage 2.1 baseline:

```
+------------------+-----------------------------------------------------------+---------+------------------------------------------------------------------+----------+
| Source File Code | Absolute Physical File Path                               | Size    | Verified SHA-256 Digest                                          | Baseline |
+------------------+-----------------------------------------------------------+---------+------------------------------------------------------------------+----------+
| FREEZE_ARCHIVE   | C:\VSPL_MM\VSPL_Phase7_Stage2_1_Evidence_Freeze_20261013.zip| 418,912 | 033684d8b26dc65e9c67b569e48991b07c0d0909c2cc37717b5d3485d922c5c5| MATCH    |
| ITEM_MASTER      | C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Item_Master.xlsx      | 43,026  | 6005441b7b022cc8b6e4e65b2d2563ca4462e2448eb3c66d5fdf40552c6e8ccd| MATCH    |
| MATERIAL_ENTRY   | C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Material_Entry.xlsx   | 153,553 | 97c6448db72fa65bdc09ec0956c9dbb7d645de7a854cf5c20d072b3df8376cb4| MATCH    |
| HEAT_LOG         | C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Foundry_Heat_Log.xlsx | 246,077 | 356e8c536a3c3cb853869804d65dd2381df7e7ec3731e798b7b26be2345f881d| MATCH    |
| MASTER_LEDGER    | C:\VSPL_MM\VSPL_MM_Data\ledger\VSPL_Master_Ledger.xlsx    | 29,043  | 7cb034054d5b4c4e471558b6e1c52b4c0ec7dc786d9b9a555aed42193d984600| MATCH    |
| STORE_INVENTORY  | C:\VSPL_MM\_legacy_archive\Store Inventory.xlsx           | 126,293 | 40194dcf05ea29efb42f61aae7c25787a6f0ad482bca4b2bdfa777c7a6874b6d| MATCH    |
+------------------+-----------------------------------------------------------+---------+------------------------------------------------------------------+----------+
```

---

## 3. Migration Decision Status (DEC-001 through DEC-008)

All eight decisions remain **`PENDING_REVIEW`**; zero decisions have been approved:

| Decision ID | Scope & Title | Current Status | Blocking Impact | Accountable Authority |
| :--- | :--- | :--- | :--- | :--- |
| **DEC-001** | Missing Historical GRN Commercial Rates | `PENDING_REVIEW` | **BLOCKS COSTING & GRN INGESTION** (0 of 4 rates available) | Finance Head / Purchase Head |
| **DEC-002** | 12-Oct-2026 Cutoff Policy & 82-Day Void | `PENDING_REVIEW` | **BLOCKS ALL LIVE MIGRATION** (Scenario A vs B vs C) | Managing Director / Plant Head |
| **DEC-003** | Unmapped Items & Scrap Chemistry | `PENDING_REVIEW` | **BLOCKS GRN ROWS 3-5** (MNT-CN-001, MCS-CN-002, scrap grade) | Plant Head / Metallurgist |
| **DEC-004** | Issue Date Typo (`7-16-20236`) | `PENDING_REVIEW` | **BLOCKS ROWS 537-548** (Requires physical slip audit) | Stores Manager / QA Lead |
| **DEC-005** | Seven Negative Stock Balances | `PENDING_REVIEW` | **BLOCKS RAW MATERIAL POSTING** (Requires physical count) | Plant Head / Inventory Auditor |
| **DEC-006** | Template Dummy Rows (Row 2) | `PENDING_REVIEW` | **BLOCKS MANIFEST IMPORT** (Sample row purge authorization) | Stores Manager / Systems Arch |
| **DEC-007** | Furnace Charge Mass Deficit | `PENDING_REVIEW` | **BLOCKS RECONCILIATION & COSTING** (18 heats with 0 charge)| Foundry Head / Metallurgist |
| **DEC-008** | Legacy Archive Future Dates (`2026-11-07`) | `PENDING_REVIEW` | **BLOCKS LEGACY IMPORT** (Formally retire archive) | IT Head / Inventory Auditor |

*Full analysis in [`DECISION_BLOCKER_MATRIX.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3_preflight/DECISION_BLOCKER_MATRIX.csv).*

---

## 4. PostgreSQL Readiness Evaluation

- **Status:** **UNVERIFIED / UNAVAILABLE.**
- **Port 5432 Conflict:** Port 5432 is occupied by an active Docker container (`backend-db-1`) belonging to another VSPL project. Connections from this application fail with authentication errors.
- **Dedicated Database Missing:** No database named `vspl_material_management` exists on the workstation.
- **SQLite vs PostgreSQL:** While 68/68 unit tests pass in SQLite, PostgreSQL-specific concurrency, sequence behavior, locking, and connection pool behavior have **not** been tested.
- **Verification Plan:** An isolated non-production PostgreSQL 16 container must be provisioned on a dedicated port (e.g. `5439`) to run pre-flight tests before any live migration is attempted.
*Full analysis in [`POSTGRESQL_READINESS_REPORT.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3_preflight/POSTGRESQL_READINESS_REPORT.md).*

---

## 5. Migration Chain Static Code Audit

- **Files Inspected:** 5 migration revisions (`001` through `005`) in `backend/migrations/versions/`.
- **Topology:** **100% linear and consistent.** Single root (`001_phase2_master_data`), zero missing parents, zero branches, zero duplicate revision IDs.
- **Schema Scale:** Creates **36 tables** with **114 indexes**.
- **Append-Only Protection:** Unique composite index on `stock_ledger_entries (source_document_type, source_document_id, source_line_id)` guarantees absolute ledger idempotency against double-posting.
- **Reversibility:** Every migration file implements a clean, symmetric `downgrade()` function dropping tables in reverse foreign-key order.
*Full analysis in [`ALEMBIC_CHAIN_AUDIT.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3_preflight/ALEMBIC_CHAIN_AUDIT.md).*

---

## 6. Historical Manifest Integrity & Completeness

- **Operational Scale:** Exactly **616 operational transaction rows** staged across GRN (4), Issue (561), Waste (6), Heat Log (19), Charge Details (10), and Parts Produced (16).
- **Determinism:** Verified; manifest generation script executes deterministically with zero row shifts.
- **Dataset Boundary:** The 616 manifest rows represent only the staged subset from July 2026; they do not represent the entire historical dataset, which includes 3,675 non-empty rows across discovered workbooks and an 82-day operational void.
- **Duplicate Descriptions:** 15 item descriptions appear multiple times across 33 canonical codes, requiring strict code-based matching during data entry.
*Full analysis in [`MANIFEST_INTEGRITY_REPORT.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3_preflight/MANIFEST_INTEGRITY_REPORT.md).*

---

## 7. Opening Stock & Cutoff Policy Standards

- **The 82-Day Void:** Digital records cease on 22-Jul-2026; costing start date is 12-Oct-2026.
- **Policy Comparison:**
  - **Scenario A (Technically Recommended):** July data preserved as read-only historical archive. Live ledger initialized as of 12-Oct-2026 via certified physical stocktake.
  - **Scenario B:** Full paper reconstruction across 82 days (extreme audit risk due to missing paper slips).
  - **Scenario C (Rejected):** Assume July balances equal October opening stock (catastrophic negative stock crashes and zero-rate costing corruption).
- **Segregated Standards:** Physical quantities require primary measurement (weighbridge tickets, scale records, count tags); valuations require commercial purchase invoices (ex-GST base rates).
*Full analysis in [`OPENING_STOCK_EVIDENCE_REQUIREMENTS.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3_preflight/OPENING_STOCK_EVIDENCE_REQUIREMENTS.md).*

---

## 8. Controlled Import Architecture & Backup Protocols

- **Import Design Blueprint:** Specifies an idempotent, service-routed migration pipeline utilizing composite source keys (`ME_ISS_0537_01`), pre-import duplicate scanning, atomic document transactions, and resume-from-checkpoint capability. Zero raw SQL table bypasses permitted.
- **Backup & Recovery SOP:** Mandates binary `pg_dump -Fc` pre-migration snapshots, SHA-256 digest logging, mandatory restore rehearsals in scratch databases (`vspl_mm_restore_test`), and explicit hard rollback criteria (duplicate errors, negative stock triggers, moving average collapse).
*Full analyses in [`CONTROLLED_IMPORT_DESIGN.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3_preflight/CONTROLLED_IMPORT_DESIGN.md) and [`BACKUP_AND_RECOVERY_PLAN.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3_preflight/BACKUP_AND_RECOVERY_PLAN.md).*

---

## 9. Final Dry-Run Acceptance Gate Status

The 13-point acceptance gate is currently **LOCKED (BLOCKED)**:
- **Satisfied Gates:** **1 of 13** (G11 Cryptographic Hashes verified).
- **Blocked Gates:** **12 of 13** (G1–G10 pending management decisions, physical stocktake, and invoice audits; G12–G13 pending PostgreSQL non-production provisioning and backup rehearsal).
- **Readiness Score:** **0% LIVE MIGRATION READINESS.**
*Full analysis in [`FINAL_DRY_RUN_ACCEPTANCE_GATE.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3_preflight/FINAL_DRY_RUN_ACCEPTANCE_GATE.md).*

---

## 10. Summary of Deliverables Produced in Stage 3A

All 9 deliverables specified in the handover mandate have been generated and archived in [`docs/reports/phase7_stage3_preflight/`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3_preflight/):

```
docs/reports/phase7_stage3_preflight/
├── STAGE3_PREFLIGHT_REPORT.md                # This master pre-flight report
├── DECISION_BLOCKER_MATRIX.csv               # 8-decision matrix with status, impact & blockers
├── POSTGRESQL_READINESS_REPORT.md            # Workstation PG inspection & non-prod test plan
├── ALEMBIC_CHAIN_AUDIT.md                    # Static review of revisions 001-005 (36 tables)
├── MANIFEST_INTEGRITY_REPORT.md              # 616-row manifest determinism & completeness
├── OPENING_STOCK_EVIDENCE_REQUIREMENTS.md    # Scenarios A/B/C & quantity vs valuation evidence
├── CONTROLLED_IMPORT_DESIGN.md               # Idempotent technical import design blueprint
├── BACKUP_AND_RECOVERY_PLAN.md               # SOP for pg_dump, restore rehearsals & rollback
└── FINAL_DRY_RUN_ACCEPTANCE_GATE.md          # 13-point mandatory acceptance checklist
```

---

## 11. Final Compliance Statement & Stop Condition

> [!CAUTION]
> **Mandatory Stop Condition Enforced:**  
> The read-only pre-flight assessment (Phase 7 Stage 3A) is complete.  
> **Phase 7 Stage 3B (live historical migration, database writes, and ledger postings) remains strictly unauthorized.**  
> I am standing by for your explicit instructions and formal management sign-off on DEC-001 through DEC-008 before any write-enabled stage is initiated.
