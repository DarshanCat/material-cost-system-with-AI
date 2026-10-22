# VSPL Material Management & Costing System — Phase 7 Stage 2.1 Audit Report

**Document ID:** `DOC-P7-S2-1-AUDIT-REPORT`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd. (SG Iron Foundry & Machine Shop, Peenya, Bangalore)  
**Lead Auditor:** Senior Software Architect, Manufacturing ERP Consultant, Inventory Control Specialist, Cost Accountant, and QA Lead  
**Audit Date:** 2026-10-13  
**Status:** **STAGE 2.1 COMPLETE — STAGE 3 MIGRATION STRICTLY UNAUTHORIZED & BLOCKED**  

---

## 1. Executive Summary

This audit report delivers the findings of **Phase 7 Stage 2.1: Migration Audit Reconciliation** for the VSPL Material Management & Costing System.

The audit was executed under **strict read-only safety constraints**:
- **Zero database writes:** No records were imported into PostgreSQL or SQLite.
- **Zero ledger mutations:** The append-only inventory ledger was not modified or adjusted.
- **Zero source file alterations:** All five original Excel workbooks were treated as immutable evidence.
- **Zero artificial approvals:** All technical decisions remain pending formal management sign-off.
- **Zero fabricated data:** No missing commercial rates, dates, quantities, or item codes were invented.

### Primary Audit Verdict:
**Live historical data migration is 0% ready and remains BLOCKED.**  
All 616 operational manifest rows and secondary legacy records are subject to unresolved business policy dependencies, missing commercial purchase rates, corrupt legacy references, or physical stocktake requirements.

---

## 2. Source Workbooks Inventory & Fingerprint Integrity

The audit inspected all five source workbooks and verified their SHA256 checksums, sizes, and timestamps against historical inventory logs.

| Workbook ID | Description | File Path | Size (Bytes) | SHA256 Fingerprint | Verification Status |
|---|---|---|---|---|---|
| `ITEM_MASTER` | Canonical Item Master (391 items) | `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Item_Master.xlsx` | 43,026 | `6005441b7b022cc8b6e4e65b2d2563ca4462e2448eb3c66d5fdf40552c6e8ccd` | **VERIFIED MATCH** |
| `MATERIAL_ENTRY` | Operational Data Entry (GRN, Issue, Waste) | `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Material_Entry.xlsx` | 153,553 | `97c6448db72fa65bdc09ec0956c9dbb7d645de7a854cf5c20d072b3df8376cb4` | **VERIFIED MATCH** |
| `HEAT_LOG` | Induction Furnace Log & Charge Details | `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Foundry_Heat_Log.xlsx` | 246,077 | `356e8c536a3c3cb853869804d65dd2381df7e7ec3731e798b7b26be2345f881d` | **VERIFIED MATCH** |
| `MASTER_LEDGER` | Interim Physical Material Ledger | `C:\VSPL_MM\VSPL_MM_Data\ledger\VSPL_Master_Ledger.xlsx` | 29,043 | `7cb034054d5b4c4e471558b6e1c52b4c0ec7dc786d9b9a555aed42193d984600` | **VERIFIED MATCH** |
| `STORE_INVENTORY`| Legacy Raw Spreadsheets (July 2026 Archive) | `C:\VSPL_MM\_legacy_archive\Store Inventory.xlsx` | 126,293 | `40194dcf05ea29efb42f61aae7c25787a6f0ad482bca4b2bdfa777c7a6874b6d` | **VERIFIED MATCH** |

*Generated Artifact:* [source_fingerprint_verification.csv](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/source_fingerprint_verification.csv)

### Disclosure of Errata in Prior Stage 1 and Stage 2 Reports:
1. **Source Hash Truncation in Stage 1:** The Stage 1 narrative report recorded truncated hashes (`fa1fefcb...` and `57ba78b8...`) for `ITEM_MASTER` and `MATERIAL_ENTRY`. Full-file SHA256 hashing confirms that the files match `source_workbooks_inventory.csv` exactly and have not been modified since July 2026.
2. **Dataset Scale Clarification:** Previous handover documentation loosely referenced "12,280 transactions". The actual electronic universe comprises **3,675 non-empty rows** across all five workbooks, of which **616 rows** form the operational manifest.
3. **Stage 1 Unsupported Costing Readiness:** Stage 1 reported costing readiness figures (0 / 113 / 4 / 25 / 249) that were not output by any script; these figures are officially withdrawn as unsupported.

---

## 3. Reconciliation of Stage 2 Inconsistencies

### 3.1 Primary Classification vs Readiness Status Reconciliation
The handover noted that Stage 2 reported:
- **Primary Classification:** 545 `VALID_NEW_CANDIDATE`, 31 `MANUAL_REVIEW`, 37 `INVALID_SOURCE`, 3 `UNMAPPED` (Sum = 616).
- **Readiness Classification:** 515 `ELIGIBLE`, 66 `PENDING_REVIEW`, 35 `BLOCKED` (Sum = 616).

The audit established that these two classifications evaluate different dimensions of data governance:
- **Primary Classification** evaluates schema and syntactic conformance of individual row fields.
- **Readiness Status** evaluates operational eligibility for posting to the live append-only inventory ledger, incorporating blocking external dependencies.

#### Dimensional Cross-Tabulation Matrix:

| Primary Classification | ELIGIBLE | PENDING_REVIEW | BLOCKED | Row Total |
|---|---|---|---|---|
| **VALID_NEW_CANDIDATE** | **515** | **30** | 0 | **545** |
| **MANUAL_REVIEW** | 0 | **31** | 0 | **31** |
| **INVALID_SOURCE** | 0 | **2** | **35** | **37** |
| **UNMAPPED** | 0 | **3** | 0 | **3** |
| **Column Total** | **515** | **66** | **35** | **616** |

#### Resolution of Specific Discrepancies:
1. **Reconciliation of 545 Candidates vs 515 Eligible (Difference = 30):**
   - Exactly 30 rows are syntactically valid candidates but held in `PENDING_REVIEW` due to policy/technical blockers:
     - **1 GRN Row** (`MAN-GRN-0002`, Emery Paper, Row 2): Blocked by DEC-001 (missing commercial rate).
     - **19 Heat Log Rows** (`MAN-HEAT-0002` to `0020`): Blocked by DEC-002 (cutoff) and DEC-007 (negative melt loss mass balance anomaly).
     - **10 Charge Details Rows** (`MAN-CHG-0002` to `0011`): Blocked by DEC-002 and DEC-005 (negative stock / unlogged heats).
   - $545 - 30 = 515\text{ ELIGIBLE}$.
2. **Reconciliation of 37 Invalid vs 35 Blocked (Difference = 2):**
   - 35 rows are permanently blocked due to zero or null quantities (34 zero-quantity Issue rows + 1 null-quantity Waste row).
   - 2 GRN rows (`MAN-GRN-0004` Tool Post and `MAN-GRN-0005` crca scrap) possess multiple fatal defects (missing date, missing GRN number, missing rate, unmapped code). The Stage 2 generator marked them `INVALID_SOURCE` in primary classification, but routed them to `PENDING_REVIEW` under DEC-001/DEC-003 to enable purchase order research.
   - $37 - 2 = 35\text{ BLOCKED}$.
3. **Reconciliation of 3 Unmapped Rows:**
   - Comprises 1 GRN row (`MAN-GRN-0003`, 3306PMKT-Generator) and 2 Issue rows (`MAN-ISS-0537` and `MAN-ISS-0538`, cable and plug). All 3 map to `PENDING_REVIEW` under DEC-003 and DEC-004.
4. **Stage 2 Generator Bug Disclosures:**
   - *Precedence Bug:* Issue rows 537 and 538 possess both the year typo and an unmapped item code. In Stage 2, the unmapped check ran after the typo check, overwriting primary classification from `MANUAL_REVIEW` to `UNMAPPED` while preserving the `DEC-004` reference.
   - *GRN Override:* GRN rows 4 and 5 possess missing dates and unmapped codes. In Stage 2, the missing date check overwrote the class to `INVALID_SOURCE` whereas Stage 1 kept them `UNMAPPED`.

*Generated Artifact:* [classification_crosswalk.csv](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/classification_crosswalk.csv)

---

## 4. Specific Factual Investigations

### 4.1 Suspected Date Typo Investigation (DEC-004)
- **Source Location:** Workbook `VSPL_Material_Entry.xlsx`, Worksheet `4. Issue`, Column A (`Date`).
- **Exact Physical Range:** Exactly **12 physical rows (rows 537 to 548)** contain the literal text string `7-16-20236`.
- **Prior Reporting Errors:** Stage 1 cited "rows 535-544 (10 rows)"; Stage 2 generator held 10 rows as `MANUAL_REVIEW` and 2 as `UNMAPPED`. Both prior reports misstated the physical range.
- **Source Verification:**
  - Rows 535 and 536 are dated `2026-07-15`.
  - Rows 537 to 548 contain Issue Slips 327 (rows 537-538), 910 (row 539), 325 (rows 540-542), 1149 (row 543), 326 (row 544), 2725 (rows 545-546), and 1148 (rows 547-548).
  - Row 549 is dated `2026-07-15` (Slips 328, 329).
- **Audit Verdict:** Chronological slip sequence strongly indicates `2026-07-16`. However, in compliance with safety constraints, the date has **NOT been automatically normalized**. It remains flagged as `PENDING_REVIEW` awaiting Stores Manager written sign-off.

*Generated Artifact:* [date_discrepancy_report.csv](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/date_discrepancy_report.csv)

### 4.2 Missing Commercial GRN Rates (DEC-001)
- **Source Location:** Workbook `VSPL_Material_Entry.xlsx`, Worksheet `3. Receipt GRN`, rows 2 to 5.
- **Verified Facts:**
  - The worksheet contains **NO unit rate or price column** by design. Readme explicitly confirms: *"Phase 1: quantities only (no prices)"*.
  - Canonical `Item Master` contains **0 populated rates across all 391 items** (`Rate (INR)` column is 100% empty).
  - Legacy `Store Inventory.xlsx` contains **0 populated rates** across all sheets.
- **Audit Verdict:** Commercial rates cannot be derived, inferred from market prices, or generated from future transactions. Physical vendor invoices must be audited before weighted-average costing can run.

### 4.3 Unmapped GRN Items & Ambiguous Scrap Mapping (DEC-003)
- **Source Location:** Workbook `VSPL_Material_Entry.xlsx`, Worksheet `3. Receipt GRN`, rows 3, 4, 5.
- **Detailed Findings:**
  1. **Row 3 (`3306PMKT-Generator`, Qty 1):** Exact description exists in `2. New Items` row 5 proposing `MNT-CN-001` (Maintenance, Set). Plausible, but requires Phase 2 Master Data approval.
  2. **Row 4 (`Tool Post`, Qty 4):** Exact description exists in `2. New Items` row 6 proposing `MCS-CN-002` (Machine Shop, Nos). Plausible, but requires Phase 2 Master Data approval.
  3. **Row 5 (`crca scrap`, Qty 15,200 kg):** Stage 2 tentatively proposed `FDY-RM-008` (CRC Scrap-Low MN). The audit reveals this is **chemically AMBIGUOUS**:
     - Item Master has both `FDY-RM-007` (CRC Scrap-Low High MN) and `FDY-RM-008` (CRC Scrap-Low MN).
     - Heat Log Read Me equates CRCA to general "steel scrap".
     - Without PO 140726-02 chemical analysis, auto-mapping to 008 is an unverified assumption. Status downgraded to **AMBIGUOUS**.

*Generated Artifact:* [grn_mapping_pricing_exceptions.csv](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/grn_mapping_pricing_exceptions.csv)

### 4.4 Reconciliation of Seven Negative Closing Stock Balances (DEC-005)
- **Source Location:** Workbook `VSPL_Master_Ledger.xlsx`, Worksheet `Ledger`.
- **Affected Items:** `FDY-RM-008` (-500 kg), `FDY-RM-011` (-300 kg), `FDY-RM-014` (-2 kg), `FDY-RM-016` (-15 kg), `FDY-RM-017` (-3 kg), `FDY-RM-019` (-150 kg), `FDY-RM-020` (-5 kg).
- **Root Cause Established:**
  - These seven negative balances **identically equal the furnace charges** of heat `H-260714-01` in worksheet `Charge Details` (500, 300, 150, 5, 3, 15, 2 kg).
  - The interim master ledger erroneously deducted furnace charges as store issues, violating **Phase 5 Rule H1**.
  - In addition, store issues in worksheet `4. Issue` total **11,793 kg for 008**, **278.509 kg for 017**, and **50.218 kg for 020**, which were completely omitted from the interim ledger.
  - Zero opening stock was established for these items. Legacy archive holds unposted physical stock for Inoculant 15 (92.5 kg), Magnesium (550 kg), Manganese (20 kg), and Silicon (26 kg), but 0 for Scrap, Gatings, and Pig Iron.
- **Audit Verdict:** Reconstructing inventory balances without an approved opening physical stocktake is impossible. All seven items are BLOCKED pending physical audit.

*Generated Artifact:* [negative_stock_reconciliation.csv](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/negative_stock_reconciliation.csv)

### 4.5 Sample Template Rows in Material Entry Sheets (DEC-006)
- **Source Location:** `VSPL_Material_Entry.xlsx`, Readme Sheet line 8.
- **Documented Rule:** *"Row 2 of each sheet is a sample entry — overwrite it or delete it before real use"*.
- **Findings:**
  - Row 2 of GRN (Emery Paper 25 kg), Issue (Emery Paper 220 kg, Slip 132607), and Waste (Emery Paper 5 kg, Note WD-0001) are documented sample rows.
  - GRN Row 2 contains document collisions with legacy records: GRN 2599 & Invoice 096 belong to 'Cement empty' 1000 from s.srinivas, while PO 110726-02 belongs to MM Tools 'Grinding Wheel 7 Inch' 25.
  - Interim Master Ledger incorporated Received 25 and Waste 5 from these dummy rows.
- **Audit Verdict:** Raised as candidate decision **DEC-006** to exclude row 2 from operational migration.

### 4.6 Induction Furnace Heat Log Mass Balance Contradictions (DEC-007)
- **Source Location:** Workbook `VSPL_Foundry_Heat_Log.xlsx`.
- **Findings:**
  - 18 of 19 logged heats report Total Charge = 0 kg yet report Metal Tapped = 504 to 524 kg, generating negative melt loss (-100% to -125%).
  - `Charge Details` holds only 10 rows: 7 belong to unlogged heat `H-260714-01`, 1 to `L-260722-02`, 1 to `H-200125-05`, and only 1 to logged heat `072613-2092` (4 kg charged vs 507 kg tapped).
  - `Parts Produced` row 2 reports 2016 kg of cast parts against 507 kg tapped metal.
- **Audit Verdict:** Production data is severely incomplete. Furnace records cannot reconcile against store issues or establish heat costing. Raised as **DEC-007**.

### 4.7 Legacy Spreadsheet Corruption and Future Dates (DEC-008)
- **Source Location:** Workbook `Store Inventory.xlsx`.
- **Findings:**
  - Worksheet `Old data` contains corrupt code mappings: `Frm08` is assigned to 58 rows of 'Silicon' (Item Master Frm08 is CRC Scrap); 'Crc' rows are mapped to `FRM01` (Bial).
  - Worksheet `Material Receipt` contains 113 physical stock rows dated `2026-11-07` (future date relative to July 2026 transactions, likely mm/dd transposition of 11-Jul-2026).
- **Audit Verdict:** Legacy sheets must not be auto-mapped or ingested into the live ledger. Raised as **DEC-008**.

---

## 5. Costing Cutoff Policy Scenarios (12-Oct-2026)

The system is configured with `COSTING_START_DATE = 2026-10-12`. Historical transactions span **08-Jul-2026 to 22-Jul-2026**, creating an **82-day undocumented gap**. Management must choose between three scenarios:

1. **Scenario A: Historical Audit Archive (Recommended)**
   - July transactions stored in read-only archive tables; live append-only ledger begins 12-Oct-2026 using audited physical stocktake as Opening Balance.
   - *Advantage:* Zero risk of ledger corruption or negative stock; clean weighted-average costing.
2. **Scenario B: Reconstructed Opening Position as of 12-Oct-2026**
   - Attempt to reconstruct stock through August and September.
   - *Limitation:* **EXTREME RISK.** Zero electronic records exist for August and September 2026.
3. **Scenario C: Two-Phase Transition (Staged Movement Import)**
   - July transactions simulated in a sandbox ledger; difference against October stocktake absorbed via manual adjustment journals.
   - *Limitation:* Requires extensive auditing and may distort consumption costing.

*Detailed Analysis:* [READINESS_SUMMARY.md](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/READINESS_SUMMARY.md)

---

## 6. Decision Register Governance Updates

The decision register has been versioned to Version 2. Existing decision IDs and audit histories are preserved.

| Decision ID | Summary Title | Status | Primary Update in Version 2 |
|---|---|---|---|
| **DEC-001** | Missing Commercial GRN Rates | **PENDING_REVIEW** | Verified 0/391 rates in Item Master and legacy archive. |
| **DEC-002** | July vs 12-Oct-2026 Costing Cutoff | **PENDING_REVIEW** | Documented exact 82-day data void and 3 cutoff scenarios. |
| **DEC-003** | Unmapped GRN Items | **PENDING_REVIEW** | Downgraded `crca scrap` to AMBIGUOUS between 007 and 008. |
| **DEC-004** | Issue Date Typo (`7-16-20236`) | **PENDING_REVIEW** | Corrected physical scope to exactly 12 rows (537–548). |
| **DEC-005** | Seven Negative Stock Balances | **PENDING_REVIEW** | Mathematical proof of heat charge correlation & unposted store issues. |
| **DEC-006** | Template Dummy Rows (Row 2) | **PENDING_REVIEW** | *New:* Documented sample rows and legacy document collision. |
| **DEC-007** | Furnace Heat Mass Balance Deficit | **PENDING_REVIEW** | *New:* Identified 18 heats with 0 kg charge & negative melt loss. |
| **DEC-008** | Legacy Code Corruption & Future Dates | **PENDING_REVIEW** | *New:* Identified corrupt code mapping and 2026-11-07 dates. |

*Generated Artifacts:*
- [migration_decision_register_v2.csv](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/migration_decision_register_v2.csv)
- [MIGRATION_DECISION_REGISTER_v2.md](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/MIGRATION_DECISION_REGISTER_v2.md)

---

## 7. Verification, Tests, and Repeatability

### 7.1 Determinism & Byte-Repeatability Test
The Stage 2.1 audit engine (`scripts/phase7_stage2_1_audit.py`) was executed multiple times. Output file checksums were compared:
- `source_fingerprint_verification.csv`: `d8227860280c...` (MATCH: True)
- `classification_crosswalk.csv`: `0772a7d55bed...` (MATCH: True)
- `date_discrepancy_report.csv`: `9d8d8d7e81a1...` (MATCH: True)
- `grn_mapping_pricing_exceptions.csv`: `653af57c5c64...` (MATCH: True)
- `negative_stock_reconciliation.csv`: `159849c15a93...` (MATCH: True)
- `stage2_1_metrics.json`: `34374828d8b3...` (MATCH: True)
- **Result:** **100% Deterministic and Byte-Reproducible.**

### 7.2 Backend Test Suite Execution
- **Command:** `backend\.venv\Scripts\pytest.exe backend\tests -v`
- **Result:** **68 passed, 3 warnings in 5.32s.**
- **Scope:** Master data, GRN, issues, waste, opening balances, ledger posting, inventory valuation, weighted-average costing, heat logging, part costing, reconciliation.

### 7.3 Frontend Production Build
- **Command:** `npm run build` (in `frontend/`)
- **Result:** **Built in 504ms. Zero TypeScript or JSX compilation errors.**

---

## 8. Source & Database Integrity Affirmation

1. **Source Excel Files:** Immutable. Zero bytes modified.
2. **Application Database:** No database writes occurred. Health endpoint confirms database is disconnected on the local dev machine (`password authentication failed for user postgres`), guaranteeing that no live data was mutated.
3. **Repository State:** Clean. No application source code was modified. Only read-only audit scripts and report artifacts were added under `scripts/` and `docs/reports/phase7_stage2_1/`.

---

## 9. Stage 3 Authorization Warning

> [!CAUTION]
> **PHASE 7 STAGE 3 (DATABASE IMPORT & LEDGER POSTING) IS STRICTLY UNAUTHORIZED.**  
> Under no circumstances should historical transactions be posted to the live append-only inventory ledger until management approves DEC-001 through DEC-008 and formalizes the 12-Oct-2026 Cutoff Policy.
