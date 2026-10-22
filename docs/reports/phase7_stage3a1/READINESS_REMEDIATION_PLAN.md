# VSPL Material Management & Costing System — Readiness Remediation Plan

**Document ID:** `DOC-P7-S3A1-REMEDIATION-PLAN`  
**System:** VSPL Material Management & Costing System  
**Date:** 2026-10-17  
**Governance Scope:** Master Strategic Roadmap & Remediation Architecture to Achieve 100% Migration Readiness  
**Execution Status:** **READ-ONLY PLANNING DOCUMENT — ZERO MUTATING OPERATIONS EXECUTED**  

---

## 1. Executive Summary & Context

Vijay Spheroidals Pvt. Ltd. (VSPL) has completed **Phase 7 Stage 3A: Controlled Migration Pre-Flight**. The pre-flight audit established that while the core application codebase is robust (Master Git commit `dd85bcc`, 68/68 automated regression tests passing, clean frontend build), **live data migration into PostgreSQL remains strictly blocked**.

### 1.1 The Current Readiness Scorecard
- **Acceptance Gates:** **1 of 13 Satisfied** (Gate G11: Source Workbook Cryptographic Hashes verified intact; Gates G1–G10 and G12–G13 remain blocked).
- **Executive Decisions:** **0 of 8 Approved** (DEC-001 through DEC-008 remain in `PENDING_REVIEW` status).
- **Core Database Engine:** Host port `5432` is occupied by an external project container (`backend-db-1`), requiring an isolated non-production deployment on port `5439`.
- **Primary Operational Hazard:** An **82-day operational void** (22-Jul-2026 to 12-Oct-2026) and **7 negative raw material balances** (-500 kg scrap, -300 kg gatings, etc.) resulting from the interim spreadsheet subtracting furnace charges directly from zero opening balances.

### 1.2 Objective of Stage 3A.1
This **Readiness Remediation Plan** provides the definitive, sequenced, risk-managed roadmap to systematically eliminate every blocker, satisfy all 13 Acceptance Gates, and transition VSPL from a blocked pre-flight state to fully certified migration readiness.

---

## 2. Governance Framework & Accountable Roles

Closing migration readiness gaps requires cross-functional coordination between executive management, plant operations, metallurgy, commercial procurement, and software engineering.

### 2.1 RACI Governance Matrix

| Role | Title | Primary Accountabilities in Remediation | Assigned Gates / Decisions |
| :--- | :--- | :--- | :--- |
| **MD** | Managing Director | Final executive sign-off; authorization of Cutoff Scenario A; resource allocation | G1, G2, DEC-002 |
| **PH** | Plant Head | Manufacturing operational policy; physical stocktake authorization; cutoff execution | G2, G5, G7, DEC-002, DEC-005 |
| **FH** | Finance Head | Commercial invoice rate verification; inventory valuation sign-off; Rule C1 compliance | G1, G3, DEC-001 |
| **SM** | Stores Manager | Physical issue slip audits; item master additions; stocktake count management | G4, G6, G7, DEC-003, DEC-004 |
| **FM** | Foundry Metallurgist | Optical emission spectrometry scrap testing; furnace charge data retrieval | G5, G9, DEC-003, DEC-007 |
| **IT** | IT / Systems Head | Legacy archive formal retirement; host infrastructure and backup preservation | G10, DEC-008 |
| **SA** | Systems Architect | Idempotent import design; manifest generator logic; backup rehearsal SOP | G8, G13, DEC-006 |
| **DBA** | Lead Database Engineer | Isolated PostgreSQL container provisioning on port 5439; Alembic migrations | G12 |
| **QA** | Lead QA Auditor | Cryptographic digest verification; gate audit certification; compliance sign-off | G11, G13 |

---

## 3. Phased Remediation Roadmap (Phases A through G)

To ensure zero operational disruption and maintain an unbroken audit trail, remediation must proceed through seven strictly sequenced phases:

```
┌────────────────────────────────────────────────────────────────────────┐
│               SEVEN-PHASE READINESS REMEDIATION ROADMAP                 │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE A: EXECUTIVE GOVERNANCE & COMMERCIAL RATE RESOLUTION             │
│ • Resolve DEC-001 (Commercial Invoice Rates)                           │
│ • Resolve DEC-002 (Scenario A Cutoff Policy Mandate)                   │
│ • Satisfy Gates G1, G2, G3                                             │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE B: MASTER DATA, METALLURGY & TRANSACTION NORMALIZATION           │
│ • Resolve DEC-003 (Item Additions & Spectrometer Scrap Grade)          │
│ • Resolve DEC-004 (Physical Issue Slip Date Verification)              │
│ • Satisfy Gates G4, G5, G6                                             │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE C: PHYSICAL STOCKTAKE EXECUTION & OPENING BALANCE CERTIFICATION   │
│ • Execute double-blind physical count per PHYSICAL_STOCKTAKE_PROTOCOL   │
│ • Resolve DEC-005 (7 Negative Stock Balances & 11,793 kg Omitted Scrap)│
│ • Populate Sheet D of VSPL_Physical_Stocktake_Register.xlsx            │
│ • Satisfy Gate G7                                                      │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE D: MANIFEST CLEANSING & LEGACY RETIREMENT                        │
│ • Resolve DEC-006 (Purge Row 2 Template Dummy Rows)                    │
│ • Resolve DEC-007 (Furnace Charge Staging Quarantine)                  │
│ • Resolve DEC-008 (Formal IT Retirement of Store Inventory.xlsx)       │
│ • Satisfy Gates G8, G9, G10                                            │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE E: ISOLATED POSTGRESQL NON-PRODUCTION PROVISIONING               │
│ • Deploy isolated PostgreSQL 16 container on dedicated port 5439       │
│ • Apply Alembic schema migrations (001-005) -> 36 tables, 114 indexes  │
│ • Execute regression test suite against live PostgreSQL engine         │
│ • Satisfy Gate G12                                                     │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE F: PRE-MIGRATION BACKUP & RESTORE REHEARSAL                      │
│ • Capture atomic pg_dump (-Fc) pre-migration baseline                  │
│ • Execute automated rehearsal restore into vspl_mm_restore_test        │
│ • Audit 36 tables, indexes, and schema invariants                      │
│ • Satisfy Gate G13                                                     │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE G: FINAL ACCEPTANCE GATE AUDIT & AUTHORIZATION SIGN-OFF          │
│ • Re-verify all 5 source workbook cryptographic digests (Gate G11)     │
│ • Verify 13 of 13 Acceptance Gates Certified                           │
│ • Submit Final Stage 3 Live Migration Request for Executive Sign-Off   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Comprehensive Blocker Resolution Strategies

### 4.1 DEC-001: Commercial Invoice Rates (Gates G1, G3)
- **Root Cause:** Historical GRN rows 2–5 lack rate columns; Item Master Col K is empty across all 391 items. Rule C1 weighted-average calculations collapse to zero without incoming purchase rates.
- **Remediation Action:**
  1. Finance Head retrieves physical supplier tax invoices for GRN receipts (Emery paper, Generator set, Tool post, CRCA scrap).
  2. Finance team extracts ex-GST base unit rates and enters them into a certified `commercial_rates_staging.csv`.
  3. Finance Head signs rate certification form attached to `MANAGEMENT_SIGNOFF_TEMPLATE.md`.
- **Exit Criteria:** Certified commercial purchase rates recorded for 100% of GRN line items.

### 4.2 DEC-002: Scenario A Adoption & 82-Day Void Policy (Gates G1, G2)
- **Root Cause:** 82 calendar days elapsed between July 22 (source data cutoff) and October 12 (costing start date).
- **Remediation Action:**
  1. Submit executive policy memorandum formally recommending **Scenario A (Historical Audit Archive & Certified Physical Cutoff)**.
  2. Managing Director and Plant Head sign executive mandate establishing that July data serves strictly as a historical audit archive, while October 12 physical counts establish the opening balance for live operations.
- **Exit Criteria:** Signed executive mandate adopting Scenario A on file.

### 4.3 DEC-003: Unmapped GRN Items & Ambiguous Scrap Grade (Gates G4, G5)
- **Root Cause:** Items `3306PMKT-Generator` and `Tool Post` are not in the Item Master; `crca scrap` matches both `RM-SC-007` (0.15–0.25% Mn) and `RM-SC-008` (0.35–0.50% Mn).
- **Remediation Action:**
  1. Stores Manager submits Phase 2 Item Request forms for `MNT-CN-001` (Generator Set) and `MCS-CN-002` (Tool Post).
  2. Foundry Quality Lab retrieves scrap supplier delivery dockets and conducts an optical emission spectrometry test on a retained melt sample to certify manganese content.
  3. Chief Metallurgist issues signed Spectrometry Test Certificate mapping the 15,200 kg scrap to either `RM-SC-007` or `RM-SC-008`.
- **Exit Criteria:** Canonical codes created in master data; scrap chemistry certified in writing.

### 4.4 DEC-004: Issue Date Typo Authorization (Gate G6)
- **Root Cause:** Rows 537–548 in `VSPL_Material_Entry.xlsx` contain year `20236` (e.g. `7-16-20236`).
- **Remediation Action:**
  1. Stores Manager locates hardcopy paper store slips 327, 910, 325, 1149, 326, 2725, and 1148 in the warehouse archive.
  2. Stores Manager verifies the physical date written on the dockets is `16-07-2026`.
  3. Stores Manager and Lead QA Auditor execute a Date Normalization Certificate authorizing automated ETL mapping to `2026-07-16`.
- **Exit Criteria:** Signed physical docket verification certificate archived.

### 4.5 DEC-005: Seven Negative Stock Balances & 11,793 kg Omitted Scrap (Gate G7)
- **Root Cause:** Interim spreadsheet subtracted furnace heat `H-260714-01` charges directly from zero opening stock, causing negative balances (-500 kg scrap, -300 kg gatings, etc.) and omitting 11,793 kg of actual store scrap issues.
- **Remediation Action:**
  1. Conduct double-blind physical stocktake per [`PHYSICAL_STOCKTAKE_PROTOCOL.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stocktake_preparation/PHYSICAL_STOCKTAKE_PROTOCOL.md) as of 12-Oct-2026.
  2. Populate Sheet D of `VSPL_Physical_Stocktake_Register.xlsx` with certified count figures.
  3. Plant Head and Independent Inventory Auditor certify opening balances, bypassing historical negative balances.
- **Exit Criteria:** Fully signed `VSPL_Physical_Stocktake_Register.xlsx` with zero uninvestigated variances.

### 4.6 DEC-006: Template Dummy Row Purge (Gate G8)
- **Root Cause:** Row 2 of each sheet in `VSPL_Material_Entry.xlsx` is a template sample entry per workbook Read Me.
- **Remediation Action:**
  1. Update `scripts/phase7_stage2_manifest_generator.py` to add explicit exclusion filter `row_number != 2`.
  2. Re-generate proposed operational manifest and confirm total candidate count adjusts cleanly from 616 to 613 rows.
- **Exit Criteria:** Verified operational manifest free of template development artifacts.

### 4.7 DEC-007: Furnace Charge Mass-Balance Deficit (Gate G9)
- **Root Cause:** 18 heats on 22-Jul-2026 have zero recorded charge lines in `VSPL_Foundry_Heat_Log.xlsx`.
- **Remediation Action:**
  1. Foundry Supervisor retrieves physical paper melt log sheets from the furnace control deck.
  2. If physical logs are available, charge details are transcribed into staging; if unavailable, configure staging loader to place all 18 heats into a `QUARANTINED_STAGING` state.
  3. Prohibit any furnace records from posting to live production tables until charges balance.
- **Exit Criteria:** Written charge reconciliation report or certified quarantine order from Foundry Head.

### 4.8 DEC-008: Legacy Archive Formal Retirement (Gate G10)
- **Root Cause:** `Store Inventory.xlsx` contains 113 future-dated receipt records (`2026-11-07`) with supplier marked 'Physical stock'.
- **Remediation Action:**
  1. IT Head and Lead Auditor sign formal retirement memorandum declaring `Store Inventory.xlsx` an obsolete legacy backup.
  2. Update migration runner configuration to exclude `Store Inventory.xlsx` entirely from the active ETL ingestion pipeline.
- **Exit Criteria:** Signed archive retirement memorandum; ETL configuration permanently decoupled from legacy workbook.

---

## 5. Technical Environment & Testing Strategy (Port 5439)

To ensure zero collision with existing host containers (e.g. `backend-db-1` on port 5432):
1. **Isolated Port:** Bind PostgreSQL strictly to `127.0.0.1:5439`.
2. **Schema Realization:** Execute Alembic revisions 001 through 005 to instantiate:
   - 36 public tables.
   - 114 indexes (including composite unique index `uq_source_doc_line_posting`).
   - Revision head `005_cost_history`.
3. **PostgreSQL Test Suite Execution:** Run all 68 pytest regression tests against the PostgreSQL instance to certify that all dialect-specific queries, UUID types, and constraints execute flawlessly.

---

## 6. Pre-Migration Backup & Restore Rehearsal SOP

To satisfy Gate G13:
1. **Atomic Baseline Dump:** Capture pre-migration snapshot via `pg_dump -Fc -Z 6` to `backups/vspl_mm_baseline_{TIMESTAMP}.dump`.
2. **Cryptographic Fingerprint:** Compute SHA-256 digest and persist to sidecar `.sha256` file.
3. **Automated Rehearsal Restoration:** Restore snapshot into temporary scratch database `vspl_mm_restore_test`.
4. **Programmatic Verification:** Assert table count == 36, index count >= 114, Alembic revision == `005_cost_history`.
5. **Teardown & Sign-off:** Drop scratch database and issue certified `RESTORE_REHEARSAL_CERTIFICATE.md`.

---

## 7. Migration Idempotency & Invariants

All future ingestion scripts must comply with the architecture established in `IMPORT_IDEMPOTENCY_REVIEW.md`:
1. **Immutable Source Keys:** Every row identified by `{WORKBOOK}_{SHEET}_{ROW:04d}_{LINE:02d}`.
2. **Three-Tier Duplicate Prevention:** Staging query pre-filter, domain service idempotency check, and database unique constraint `uq_source_doc_line_posting`.
3. **Mandatory Domain Routing:** All transactions routed through `grn_service`, `issue_service`, `waste_service`, and `heat_service`. Direct SQL `INSERT` statements are strictly prohibited.
4. **Document Savepoint Boundaries:** Failures roll back cleanly at the document level without corrupting ledger state.

---

## 8. Mandatory Stop Condition & Safety Attestation

### Operational Attestation:
- **Scope Compliance:** This document and its accompanying deliverables (`ACCEPTANCE_GATE_ACTION_MATRIX.csv`, `DECISION_EVIDENCE_CHECKLIST.csv`, `POSTGRESQL_NONPROD_SETUP_PLAN.md`, `BACKUP_RESTORE_VERIFICATION_PLAN.md`, `IMPORT_IDEMPOTENCY_REVIEW.md`) represent a **strictly read-only planning and remediation architecture**.
- **No Mutating Operations:** Zero application database records have been inserted, updated, or deleted; zero stock ledger entries have been posted; zero Docker containers have been launched; zero Alembic migrations have been applied; and zero source workbooks have been modified.
- **Final Stop Condition:** Phase 7 Stage 3 live migration remains **STRICTLY UNAUTHORIZED** until all 13 Acceptance Gates are certified in writing by the designated authorities.
