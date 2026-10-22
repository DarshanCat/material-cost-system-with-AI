# VSPL Material Management & Costing System — Stage 3A.6 Executive Readiness Review

**Document ID:** `DOC-P7-S3A6-EXECUTIVE-REVIEW`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd., Peenya Industrial Area, Bangalore  
**Repository Baseline:** `master` — `dd85bcc64e1da9268075077159ccd2abf6a94f0b`  
**Target Executive Audience:** Managing Director, Plant Head, Finance Head, Lead Internal Auditor  
**Audit Scope:** Evidence Reconciliation, Data-Integrity Deep Dive & Executive Readiness Review  
**Execution Authority:** **READ-ONLY AUDIT REPORT — ZERO OPERATIONAL MUTATIONS — STAGE 3B STRICTLY UNAUTHORIZED**  

---

## 1. Executive Summary & Verification Baseline

This report constitutes the comprehensive **Phase 7 Stage 3A.6: Evidence Reconciliation and Executive Readiness Review** for Vijay Spheroidals Pvt. Ltd. (VSPL). It performs an exhaustive, evidence-backed audit across all preceding Phase 7 deliverables (Stages 1 through 3A.5), reconciling repository baselines, open decisions (`DEC-001` through `DEC-008`), acceptance gates (`G1` through `G13`), code-level rate validations, and relational database infrastructure readiness.

### 1.1 Executive Readiness Scorecard
- **Repository Branch:** `master`
- **Git Commit HEAD:** `dd85bcc64e1da9268075077159ccd2abf6a94f0b` (Verified 100% intact)
- **Working Tree State:** Clean; zero uncommitted modifications to application code, migrations, or workbooks.
- **Automated Regression Suite:** **68 of 68 tests passing** in 5.62 seconds (Executed in isolated, in-memory SQLite `StaticPool`).
- **Acceptance Gate Readiness:** **1 of 13 Gates Satisfied** (Gate `G11` is Verified; Gates `G1`–`G10` and `G12`–`G13` remain **BLOCKED**).
- **Executive Decision Status:** **0 of 8 Decisions Approved** (`DEC-001` through `DEC-008` remain strictly `PENDING_REVIEW`).
- **Target PostgreSQL Database:** **NOT PROVISIONED**. Host port `5432` is actively occupied by OMS container `backend-db-1`; dedicated non-production port `5439` is verified unallocated.
- **Governing Invariant:** **Stage 3 Live Historical Migration (Stage 3B) remains STRICTLY UNAUTHORIZED.**

---

## 2. Workstream 1: Repository & Evidence Baseline Verification

In compliance with read-only audit procedures, the cryptographic digests of all five primary Excel workbooks and the frozen evidence archive were re-verified against recorded fingerprints:

### 2.1 Cryptographic Hash Verification Table
| Evidentiary Asset | Physical Location on Disk | Recorded SHA-256 Fingerprint | Verified SHA-256 Digest | Match Status |
| :--- | :--- | :--- | :--- | :--- |
| **ITEM_MASTER** | `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Item_Master.xlsx` | `6005441b7b022cc8b6e4e65b2d2563ca4462e2448eb3c66d5fdf40552c6e8ccd` | `6005441b7b022cc8b6e4e65b2d2563ca4462e2448eb3c66d5fdf40552c6e8ccd` | **VERIFIED (100%)** |
| **MATERIAL_ENTRY** | `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Material_Entry.xlsx` | `97c6448db72fa65bdc09ec0956c9dbb7d645de7a854cf5c20d072b3df8376cb4` | `97c6448db72fa65bdc09ec0956c9dbb7d645de7a854cf5c20d072b3df8376cb4` | **VERIFIED (100%)** |
| **HEAT_LOG** | `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Foundry_Heat_Log.xlsx` | `356e8c536a3c3cb853869804d65dd2381df7e7ec3731e798b7b26be2345f881d` | `356e8c536a3c3cb853869804d65dd2381df7e7ec3731e798b7b26be2345f881d` | **VERIFIED (100%)** |
| **MASTER_LEDGER** | `C:\VSPL_MM\VSPL_MM_Data\ledger\VSPL_Master_Ledger.xlsx` | `7cb034054d5b4c4e471558b6e1c52b4c0ec7dc786d9b9a555aed42193d984600` | `7cb034054d5b4c4e471558b6e1c52b4c0ec7dc786d9b9a555aed42193d984600` | **VERIFIED (100%)** |
| **STORE_INVENTORY**| `C:\VSPL_MM\_legacy_archive\Store Inventory.xlsx` | `40194dcf05ea29efb42f61aae7c25787a6f0ad482bca4b2bdfa777c7a6874b6d` | `40194dcf05ea29efb42f61aae7c25787a6f0ad482bca4b2bdfa777c7a6874b6d` | **VERIFIED (100%)** |
| **FREEZE_ARCHIVE** | `C:\VSPL_MM\VSPL_Phase7_Stage2_1_Evidence_Freeze_20261013.zip` | `033684d8b26dc65e9c67b569e48991b07c0d0909c2cc37717b5d3485d922c5c5` | `033684d8b26dc65e9c67b569e48991b07c0d0909c2cc37717b5d3485d922c5c5` | **VERIFIED (100%)** |

### 2.2 Reconciling Claims vs Physical Artifacts
A systematic audit across all prior reports confirms:
1. **No Artifact Discrepancies:** All referenced reports in `docs/reports/phase7_stage2_1/`, `phase7_stage3_preflight/`, `phase7_stage3a1/`, `phase7_stage3a2/`, `phase7_stage3a3/`, and `phase7_stage3a4/` physically exist and maintain complete numerical alignment.
2. **Strict Fact vs Hypothesis Distinction:** 
   - **Directly Verified Facts:** Source file hashes; cell coordinates; lack of rates in GRN rows 2–5; empty Column K in Item Master; year 20236 in cells A537:A548; 7 negative balances; 18 uncharged heats; unallocated port 5439.
   - **Report-Derived Claims:** Operational manifest candidate population (616 rows); 82-day void duration.
   - **Unresolved Hypotheses:** Proposed mapping of year 20236 to 2026 (requires physical slip audit); classification of CRCA scrap as `RM-SC-007` vs `008` (requires laboratory OES spectrometry).

---

## 3. Workstream 2: Reconciling Decisions DEC-001 through DEC-008

Every decision has been re-evaluated against the actual evidence present in the repository. As detailed in [`DECISION_RECONCILIATION_MATRIX.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a6/DECISION_RECONCILIATION_MATRIX.csv), **all eight decisions remain strictly `PENDING_REVIEW`**:

| Decision ID | Decision Title | Status | Evidence Present on Disk | Evidence Still Missing | Accountable Authority |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DEC-001** | Missing GRN Commercial Rates | `PENDING_REVIEW` | GRN rows 2–5 quantities; Item Master Col K audited | Original vendor tax invoices with ex-GST rates | Finance Head / Purchase Head |
| **DEC-002** | 82-Day Void & Cutoff Policy | `PENDING_REVIEW` | Executive brief & blank decision template compiled | Signed Executive Policy Memorandum (Scenario A) | Managing Director / Plant Head |
| **DEC-003** | Unmapped Items & Scrap Grade | `PENDING_REVIEW` | Items identified; scrap grade ambiguity noted | OES lab test certificate; Phase 2 item additions | Plant Head / Foundry Metallurgist |
| **DEC-004** | Issue Date Typo (Year 20236) | `PENDING_REVIEW` | Date discrepancy report across rows 537–548 | Hardcopy store slips 327–1148; signed certificate | Stores Manager / Lead QA Auditor |
| **DEC-005** | 7 Negative Balances & Omitted Scrap | `PENDING_REVIEW` | Negative balances verified; stocktake SOP prepared | Certified physical stocktake tally sheets (Sheet D) | Plant Head / Lead Inventory Auditor |
| **DEC-006** | Template Dummy Rows Purged | `PENDING_REVIEW` | Read Me cell A14 noted; Emery Paper impact audited | Committed script update filtering row 2 from manifest | Systems Architect / Lead QA Auditor |
| **DEC-007** | 18 Uncharged Furnace Heats | `PENDING_REVIEW` | 18 heats identified with Total Charge = 0 kg | Physical paper melt deck sheets OR quarantine order | Foundry Head / Chief Metallurgist |
| **DEC-008** | Legacy Archive Future Dates | `PENDING_REVIEW` | 113 future-dated rows in Store Inventory analyzed | Signed IT retirement memo; ETL exclusion config | IT Head / Lead Auditor |

---

## 4. Workstream 3: Reconciling Acceptance Gates G1–G13

As documented in [`GATE_RECONCILIATION_MATRIX.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a6/GATE_RECONCILIATION_MATRIX.csv), **only Gate G11 is Satisfied**; the remaining 12 gates remain **BLOCKED**:

```
+----+------------------------------------+----------------+---------------------------------------------------------------+
| #  | Acceptance Gate Area               | Current Status | Primary Blocker / Reason for Blocked State                    |
+----+------------------------------------+----------------+---------------------------------------------------------------+
| G1 | Executive Decision Sign-Off        | BLOCKED        | Awaiting physical signatures on DEC-001 through DEC-008       |
| G2 | Cutoff Policy Authorization        | BLOCKED        | Awaiting executive policy memorandum adopting Scenario A      |
| G3 | Commercial Purchase Rates          | BLOCKED        | Awaiting certified vendor tax invoice schedule                |
| G4 | Item Master Additions              | BLOCKED        | Awaiting approval of MNT-CN-001 and MCS-CN-002                |
| G5 | Scrap Metallurgy Certification     | BLOCKED        | Awaiting lab OES test certificate for 15,200 kg scrap         |
| G6 | Issue Date Typo Authorization      | BLOCKED        | Awaiting physical store slips audit for date 2026-07-16       |
| G7 | Certified Physical Stocktake       | BLOCKED        | Awaiting physical stocktake execution as of 12-Oct cutoff     |
| G8 | Template Dummy Rows Purged         | BLOCKED        | Awaiting script update filtering row 2 from manifest          |
| G9 | Furnace Heat Log Quarantine        | BLOCKED        | Awaiting melt deck sheets or signed quarantine order          |
| G10| Legacy Archive Formally Retired    | BLOCKED        | Awaiting formal IT policy retirement memo                     |
| G11| Source Hashes Re-Verified          | VERIFIED       | 100% SHA-256 match across all workbooks and freeze archive    |
| G12| PostgreSQL Non-Prod Verification   | BLOCKED        | Container unprovisioned; Alembic unapplied on PostgreSQL      |
| G13| Backup Rehearsal Certified         | BLOCKED        | Blocked downstream of Gate G12 provisioning                   |
+----+------------------------------------+----------------+---------------------------------------------------------------+
```

---

## 5. Workstream 4: Investigation of Critical Data-Integrity Concerns

A deep audit of source workbooks, application code, and test suites was conducted across the eight primary data-integrity issues (detailed in [`DATA_INTEGRITY_FINDINGS_REGISTER.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a6/DATA_INTEGRITY_FINDINGS_REGISTER.csv)):

### 5.1 Code-Level Rate Handling Analysis
The codebase was inspected to determine whether zero or missing rates are treated as valid, missing data, or exceptions:
1. **Validation at GRN Entry:**
   - In `backend/app/services/decimal_validator.py` (lines 111–115):
     ```python
     if source_type == "EXTERNAL_VENDOR":
         if item_category and "RAW" in item_category.upper():
             if rate_ex_gst is None or rate_ex_gst <= Decimal("0"):
                 errors.append("External vendor receipt for Raw Material requires rate per UOM (excluding GST) > 0.")
     ```
   - In `backend/app/services/grn_service.py` (lines 102–109): Any external raw material receipt missing a rate raises `HTTP_422_UNPROCESSABLE_ENTITY`.
   - **Test Evidence:** `backend/tests/test_grn.py::test_grn_external_vendor_mandatory_rate_rule` explicitly tests and asserts that external GRNs with `rate_ex_gst: None` fail with status 422.
2. **Valuation & Weighted-Average Recalculation:**
   - In `backend/app/services/costing_service.py` (lines 191–197):
     ```python
     # Missing rate on receipt
     has_missing_receipt_rate = True
     running_qty += delta
     step_status = "MISSING_RECEIPT_RATE"
     notes = "External GRN receipt missing rate_ex_gst; cannot blend into weighted average"
     ```
   - In `costing_service.py` (lines 271–272): If `has_missing_receipt_rate` is true, the overall valuation status is flagged as `ValuationStatus.INSUFFICIENT_COST_DATA`.
   - In `costing_service.py` (lines 284–290): `get_item_rate_as_of_date()` returns `None` for unvalued items, triggering `InsufficientMeltDataError` in heat costing and finished part cost rollups.
   - **Conclusion:** The application **strictly treats missing or zero rates as costing exceptions**, not valid values. Ingesting historical GRNs without commercial rates will cause financial costing to fail immediately.

### 5.2 Summary of the Remaining Data-Integrity Findings
- **Item Master Col K:** Confirmed empty across all 391 items in `VSPL_Item_Master.xlsx`. Opening valuation requires an approved valuation schedule.
- **Year 20236 Typo:** Confirmed in cells `A537:A548` of `VSPL_Material_Entry.xlsx`. Must be normalized to `2026-07-16` upon physical slip inspection.
- **Ambiguous 15,200 kg Scrap:** Confirmed in row 5 of GRN sheet. Requires laboratory OES spectrometry to classify manganese content.
- **Seven Negative Balances:** Confirmed in `VSPL_Master_Ledger.xlsx` (-500 kg to -2 kg). Deducting furnace charges from zero opening stock breaks non-negative invariants.
- **18 Uncharged Heats:** Confirmed in `VSPL_Foundry_Heat_Log.xlsx` (22-Jul heats 2–20). Total charge = 0 kg while tapping 504–524 kg of liquid metal.
- **Sample Dummy Rows:** Confirmed in row 2 across sheets per Read Me cell A14.
- **The 82-Day Operational Void:** Confirmed from 23-Jul-2026 to 11-Oct-2026. Proves that authoritative opening inventory can only be established via certified physical stocktake.

---

## 6. Workstream 5: PostgreSQL Non-Production Environment Review

Pre-flight technical audit confirms:
- **Port 5432:** Occupied by container `backend-db-1` belonging to `C:\VSPL` (OMS project).
- **Port 5439:** Confirmed unallocated on loopback interface `127.0.0.1`.
- **Infrastructure State:** Planned specification only. Zero Docker containers running; zero tables created in PostgreSQL.
- **Dialect Invariant:** 68/68 passing tests in in-memory SQLite does **not** certify PostgreSQL readiness. Full dialect testing on port 5439 remains blocked downstream of Gate G1.

---

## 7. Deliverables Package Summary

All six required deliverables have been generated in [`docs/reports/phase7_stage3a6/`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a6/):

| Deliverable Artifact | Type | Core Value |
| :--- | :--- | :--- |
| [`STAGE3A6_EXECUTIVE_READINESS_REVIEW.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a6/STAGE3A6_EXECUTIVE_READINESS_REVIEW.md) | Markdown | **Master Synthesis Report**: Evidentiary reconciliation, code-level rate analysis, data-integrity findings, safety declarations. |
| [`DECISION_RECONCILIATION_MATRIX.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a6/DECISION_RECONCILIATION_MATRIX.csv) | CSV (9 rows, 11 cols) | **Decisions DEC-001..008 Matrix**: Reconciles available vs missing evidence, accountable roles, dependencies, and pass criteria. |
| [`GATE_RECONCILIATION_MATRIX.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a6/GATE_RECONCILIATION_MATRIX.csv) | CSV (14 rows, 9 cols) | **Gates G1–G13 Matrix**: Original definitions, current statuses, evidence references, verification methods, and pass criteria. |
| [`DATA_INTEGRITY_FINDINGS_REGISTER.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a6/DATA_INTEGRITY_FINDINGS_REGISTER.csv) | CSV (9 rows, 9 cols) | **Data Integrity Deep Dive**: Concrete evidence for the 8 data-integrity concerns, code handling, and test references. |
| [`POSTGRESQL_READINESS_STATUS.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a6/POSTGRESQL_READINESS_STATUS.md) | Markdown | **Database Infrastructure Status**: Distinguishes planned configuration from host reality; details port 5439 and dialect invariants. |
| [`NEXT_ACTIONS_AND_DEPENDENCIES.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a6/NEXT_ACTIONS_AND_DEPENDENCIES.md) | Markdown | **Critical Path & Next Steps**: Mermaid dependency graph, critical path bottlenecks, and exact prerequisites for Stage 3B. |

---

## 8. Safety Attestation & The Next Three Safe Actions

### Mandatory Safety Confirmation:
- **Zero Database Operations:** No database records were inserted, modified, or deleted. Zero stock ledger postings or opening balances were created.
- **Zero Infrastructure Changes:** No Docker containers were started, stopped, or altered. Host port 5432 and external services remain untouched.
- **Zero Source Modifications:** All five source workbooks and the freeze ZIP archive remain unedited, with SHA-256 fingerprints 100% intact.
- **Prohibition Enforced:** **Stage 3A.6 is complete. Stage 3B live migration remains strictly unauthorized until all 13 Acceptance Gates are certified in writing.**

### The Next Three Safe Actions:
1. **Executive Cutoff Briefing (DEC-002):** The **Managing Director** and **Plant Head** convene to deliberate on the six executive questions in [`DEC002_EXECUTIVE_DECISION_BRIEF.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a4/DEC002_EXECUTIVE_DECISION_BRIEF.md) and execute the formal Decision Record Template to unblock **Gate G2**.
2. **Commercial & Physical Docket Audit:**
   - Finance pulls original vendor tax invoices for GRN rows 2–5 to unblock **DEC-001 (Gate G3)**.
   - Stores inspects physical paper issue slips 327–1148 to unblock **DEC-004 (Gate G6)**.
   - Foundry Quality Lab tests scrap sample on OES spectrometer to unblock **DEC-003 (Gate G5)**.
3. **Physical Stocktake Site Preparation:** Stores and Foundry leadership initiate pre-count site preparations (two-part tag printing, weighbridge/scale calibrations, scrap bay boundary marking) per [`PHYSICAL_STOCKTAKE_PROTOCOL.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stocktake_preparation/PHYSICAL_STOCKTAKE_PROTOCOL.md).
