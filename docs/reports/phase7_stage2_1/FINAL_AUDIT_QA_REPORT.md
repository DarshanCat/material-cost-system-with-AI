# VSPL Material Management & Costing System — Phase 7 Stage 2.1 Final Audit QA & Management Review Pack

**Document ID:** `DOC-P7-S2-1-FINAL-QA`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd. (SG Iron Foundry & Machine Shop, Bangalore)  
**Lead Auditor / QA Lead:** Senior Software Architect, Manufacturing ERP Consultant, Inventory Control Specialist, Cost Accountant, and QA Lead  
**Audit Date:** 2026-10-13  
**Status:** **INDEPENDENT QA COMPLETE — PHASE 7 STAGE 3 REMAINS STRICTLY UNAUTHORIZED**  

---

## 1. Executive Summary & Verification Purpose

This Quality Assurance (QA) Report provides an independent, rigorous audit verification of all deliverables produced for **Phase 7 Stage 2.1: Migration Audit Reconciliation** located in:
`C:\VSPL_MM\Material managment system\docs\reports\phase7_stage2_1\`

### Verification Principles & Safety Boundaries:
- **Strictly Read-Only Execution:** Zero database writes, zero inventory ledger mutations, zero opening balance creation, zero source workbook modifications.
- **Independence:** All arithmetic, row counts, cross-tabulations, day intervals, and checksums were recomputed independently using isolated test scripts directly against the raw source evidence and generated artifacts.
- **Preservation of Audit History:** Pre-existing Stage 1 and Stage 2 reports were preserved in full. Defects in prior generator scripts and narrative documentation are documented openly with root causes and corrective recommendations.

---

## 2. Checks Performed & Verification Results

| # | QA Audit Task | Verification Method | Result | Status |
|---|---|---|---|---|
| **1** | Manifest Row Count Consistency | Re-read `classification_crosswalk.csv`, `stage2_1_metrics.json`, and `proposed_migration_manifest.csv` | Exactly **616 operational transaction rows** across all artifacts | **VERIFIED** |
| **2** | Cross-Tabulation & Transitions | Independent matrix recomputation from row-level records | Verified 545 Candidate / 31 Manual / 37 Invalid / 3 Unmapped against 515 Eligible / 66 Pending / 35 Blocked | **VERIFIED** |
| **3** | Generator Precedence Defect | Inspected `scripts/phase7_stage2_manifest_generator.py` | Verified presence of evaluation-order bugs in Stage 2 generator; documented corrective fix | **VERIFIED** |
| **4** | Date Typo Scope (DEC-004) | Physical inspection of `VSPL_Material_Entry.xlsx` sheet `4. Issue` | Confirmed literal string `7-16-20236` in **exactly 12 physical rows (537–548)**; source unmutated | **VERIFIED** |
| **5** | Decision Register Statuses | Inspected CSV & Markdown registers across DEC-001 to DEC-008 | All 8 decisions confirmed as **PENDING_REVIEW**; zero unauthorized approvals | **VERIFIED** |
| **6** | Cutoff Day Gap Analysis (DEC-002) | Calendar arithmetic against 12-Oct-2026 cutoff date | Reconciled: **82 days** from last transaction (22-Jul-2026); **89 days** from interim ledger (15-Jul-2026) | **VERIFIED** |
| **7** | Negative Stock Proof (DEC-005) | Compared Master Ledger against Heat Log and Store Issues | Verified exact mathematical match to heat charge H-260714-01; distinguished from physical stock | **VERIFIED** |
| **8** | Omitted Store Issues (11,793 kg) | Row-level summation of FDY-RM-008 in worksheet `4. Issue` | Confirmed **54 rows**, UOM 'Kg', exactly **11,793.000 kg** omitted from interim ledger | **VERIFIED** |
| **9** | Negative Melt Loss Heats (DEC-007) | Checked 19 heats in `VSPL_Foundry_Heat_Log.xlsx` | 18 heats record 0 kg charge vs 500+ kg tap weight (-100% to -125% loss); mass balance deficit verified | **VERIFIED** |
| **10** | Artifact Hash Determinism | Repeated execution of audit engine comparing SHA256 hashes | **100% byte-reproducible** across all generated CSV and JSON outputs | **VERIFIED** |
| **11** | Backend Regression Test Suite | Full pytest execution in `backend/` | **68 passed, 0 failures, 3 warnings in 5.32s** | **VERIFIED** |
| **12** | Frontend Production Build | Vite / TypeScript build in `frontend/` | **Built in 504ms. Zero TypeScript errors** | **VERIFIED** |
| **13** | Working Tree & Database Integrity | Git status & local FastAPI health endpoint check | Zero files changed outside audit directories; database disconnected (zero writes) | **VERIFIED** |

---

## 3. Independently Verified Facts vs Unverified Historical Claims

### 3.1 Independently Verified Facts:
1. **Source Immutability:** Checksums of all 5 source workbooks match historical baseline logs (`ITEM_MASTER`: `6005441b7b02...`, `MATERIAL_ENTRY`: `97c6448db72f...`, `HEAT_LOG`: `356e8c536a3c...`, `MASTER_LEDGER`: `7cb034054d5b...`, `STORE_INVENTORY`: `40194dcf05ea...`).
2. **Missing Commercial Rates:** Not a single commercial purchase rate exists in `VSPL_Material_Entry.xlsx`, `VSPL_Item_Master.xlsx` (0/391 items), or legacy `Store Inventory.xlsx`.
3. **Date Typo Physical Boundaries:** Literal text `7-16-20236` occurs on physical rows 537 through 548 (12 rows). Slips: 327, 910, 325, 1149, 326, 2725, 1148. Preceding and succeeding rows are dated `2026-07-15`.
4. **Omitted Store Issues:** 54 issue transactions for `FDY-RM-008` (CRC Scrap-Low MN) totaling **11,793 kg** exist in sheet `4. Issue` but were completely ignored by `VSPL_Master_Ledger.xlsx`.
5. **Exact Heat Charge Equality:** The negative closing figures in `VSPL_Master_Ledger.xlsx` (-500, -300, -150, -5, -3, -15, -2 kg) match the charge quantities of furnace heat `H-260714-01` to the third decimal place.
6. **Furnace Mass Balance Deficit:** 18 of 19 heats on 22-Jul-2026 report 0 kg charge against 504–524 kg tapped, proving furnace records are severely incomplete.
7. **Document Number Collisions:** Row 2 in `3. Receipt GRN` (Emery Paper, GRN 2599, Invoice 096, PO 110726-02) collides with legacy receipt records belonging to 'Cement empty' (s.srinivas) and 'Grinding Wheel 7 Inch' (MM Tools), verifying it is dummy template data.

### 3.2 Unverified / Disproven Historical Claims (Errata):
1. **"12,280 historical transactions":** **DISPROVEN.** Total electronic rows across all 5 workbooks equal 3,675 non-empty rows. The operational manifest comprises exactly 616 rows.
2. **"10 rows with date typo (rows 535-544)":** **DISPROVEN.** Stage 1 cited 10 rows; Stage 2 generator evaluated 10 manual and 2 unmapped. The actual physical range is 12 rows (537 to 548).
3. **"Stage 1 Costing Readiness (0 / 113 / 4 / 25 / 249)":** **WITHDRAWN.** These figures were not output by any script or mathematical formula.
4. **"crca scrap maps to FDY-RM-008":** **UNVERIFIED / AMBIGUOUS.** Item Master has both `FDY-RM-007` (Low High MN) and `FDY-RM-008` (Low MN). Auto-mapping to 008 was an unapproved guess.

---

## 4. Recomputation of Manifest Classifications & Cross-Tabulation

Recomputing the Stage 2 manifest (616 operational rows) directly from row-level records yields the following cross-tabulation:

```
+----------------------+----------+----------------+---------+-------------+
| Primary Class        | ELIGIBLE | PENDING_REVIEW | BLOCKED | Row Total   |
+----------------------+----------+----------------+---------+-------------+
| VALID_NEW_CANDIDATE  |   515    |       30       |    0    |     545     |
| MANUAL_REVIEW        |     0    |       31       |    0    |      31     |
| INVALID_SOURCE       |     0    |        2       |   35    |      37     |
| UNMAPPED             |     0    |        3       |    0    |       3     |
+----------------------+----------+----------------+---------+-------------+
| Column Total         |   515    |       66       |   35    |     616     |
+----------------------+----------+----------------+---------+-------------+
```

### Verification of Exceptional Transitions:
1. **VALID_NEW_CANDIDATE $\rightarrow$ PENDING_REVIEW (30 rows):**
   - 1 GRN row (Row 2, Emery Paper) held due to missing rate (DEC-001).
   - 19 Heat Log rows held due to cutoff (DEC-002) and mass balance deficit (DEC-007).
   - 10 Charge Details rows held due to unlogged heats and negative stock items (DEC-002, DEC-005).
   - Reconciles: $545 - 30 = 515\text{ ELIGIBLE}$.
2. **INVALID_SOURCE $\rightarrow$ PENDING_REVIEW (2 rows):**
   - GRN Row 4 (`Tool Post`) and Row 5 (`crca scrap`) have multiple fatal defects: missing date, missing GRN number, missing rate, and unmapped codes.
   - The Stage 2 generator assigned primary classification `INVALID_SOURCE` due to missing date/doc, but assigned readiness `PENDING_REVIEW` under DEC-001/DEC-003 to permit commercial investigation.
   - Reconciles: $37 - 2 = 35\text{ BLOCKED}$.
3. **UNMAPPED $\rightarrow$ PENDING_REVIEW (3 rows):**
   - GRN Row 3 (`3306PMKT-Generator`, candidate MNT-CN-001).
   - Issue Row 537 (`cable 1.5sq mm`, slip 327).
   - Issue Row 538 (`plug 3 pin`, slip 327).
   - All 3 rows map to `PENDING_REVIEW` under DEC-003 and DEC-004.

---

## 5. Analysis of Generator Evaluation-Order Defects

Inspection of `scripts/phase7_stage2_manifest_generator.py` confirms two active evaluation-order bugs in the Stage 2 implementation:
1. **Issue Worksheet Precedence Defect:**
   - In lines 220–250, the generator evaluates the date typo (`7-16-20236`) and marks the row `MANUAL_REVIEW`.
   - Subsequently, in line 245, it checks `if item_code == "NOT FOUND"`, and unconditionally overwrites `classification = "UNMAPPED"`.
   - *Impact:* Rows 537 and 538 (cable and plug) possess both defects. The typo flag was overwritten by unmapped, splitting the 12 typo rows into 10 `MANUAL_REVIEW` and 2 `UNMAPPED`.
2. **GRN Worksheet Precedence Defect:**
   - In line 185, GRN rows 4 and 5 are evaluated for unmapped codes (`item_code == "NOT FOUND"` $\rightarrow$ `UNMAPPED`).
   - In line 192, a subsequent check `if not date or not grn_no` unconditionally overwrites `classification = "INVALID_SOURCE"`.
   - *Impact:* Overwrote unmapped status to invalid source, shifting the Stage 1 unmapped count from 3 to 1 in GRN.

### Safest Corrective Approach:
- **Do not modify the historical Stage 2 generator script** (`scripts/phase7_stage2_manifest_generator.py`), preserving historical evidence.
- The Stage 2.1 audit engine (`scripts/phase7_stage2_1_audit.py`) provides the authoritative recheck crosswalk by enforcing strict, hierarchical precedence:
  $$\text{INVALID\_SOURCE} > \text{UNMAPPED} > \text{CONFLICT} > \text{MANUAL\_REVIEW} > \text{VALID\_NEW\_CANDIDATE}$$

---

## 6. Costing Cutoff & Day Gap Analysis (DEC-002)

The application configuration enforces `COSTING_START_DATE = date(2026, 10, 12)`.
Historical transactions span **08-Jul-2026 to 22-Jul-2026**.

### Day Interval Clarification:
- **From Last Reliable Transaction Date (22-Jul-2026 to 12-Oct-2026):** **Exactly 82 calendar days.**
  - All 558 Issues, 4 GRNs, 6 Waste notes, and 19 Furnace Heats cease on or before 22-Jul-2026.
  - Zero electronic records exist for 23-Jul-2026 through 11-Oct-2026.
- **From Interim Master Ledger Last Update Date (15-Jul-2026 to 12-Oct-2026):** **Exactly 89 calendar days.**
  - The interim ledger formula was snapshot on 15-Jul-2026 and ignores all subsequent July movements.
- **Cutoff Treatment Implications:**
  - **Scenario A (Recommended):** Ingest July records into read-only archive tables (`historical_migration_archive`). Start live ledger on 12-Oct-2026 with an audited physical stock count as Opening Balance.
  - **Scenario B:** Reconstruct movements through August and September. **BLOCKED** by the complete absence of electronic records for the 82-day void.
  - **Scenario C:** Simulate July balances in a sandbox ledger; post adjustment entry on 12-Oct-2026. High audit complexity.

---

## 7. Negative Stock Analysis & Furnace Isolation (DEC-005)

### Mathematical Equality vs Physical Inventory Position:
The audit confirmed that the negative balances in `VSPL_Master_Ledger.xlsx` exactly equal the charge quantities of furnace heat `H-260714-01`:

| Item Code | Description | Master Ledger Closing | Heat H-260714-01 Charge | Mathematical Variance | Physical Reality |
|---|---|---|---|---|---|
| `FDY-RM-008` | CRC Scrap-Low MN | -500.000 kg | 500.000 kg | **0.000** | Omitted 11,793 kg of store issues; omitted 15,200 kg unapproved receipt |
| `FDY-RM-011` | Gattings-500 | -300.000 kg | 300.000 kg | **0.000** | Internal foundry returns charged without return receipt |
| `FDY-RM-014` | Inoculant 15 | -2.000 kg | 2.000 kg | **0.000** | Unposted legacy physical stock of 92.5 kg exists |
| `FDY-RM-016` | Magnesium | -15.000 kg | 15.000 kg | **0.000** | Unposted legacy physical stock of 550.0 kg exists |
| `FDY-RM-017` | Manganese | -3.000 kg | 3.000 kg | **0.000** | Omitted 278.5 kg of store issues; unposted legacy stock of 20 kg |
| `FDY-RM-019` | Pig Iron | -150.000 kg | 150.000 kg | **0.000** | Zero opening balance recorded; furnace charge posted as store issue |
| `FDY-RM-020` | Silicon | -5.000 kg | 5.000 kg | **0.000** | Omitted 50.2 kg of store issues; unposted legacy stock of 26 kg |

**Critical Audit Distinction:**
Mathematical equality proves that the interim ledger's negative numbers were generated by **a computational defect (charging furnace consumption directly as store issues without opening inventory)**. It does **NOT** prove that the physical inventory in the foundry yard was actually negative. A physical stocktake is mandatory.

---

## 8. Status of Decision Register (DEC-001 through DEC-008)

All eight decisions remain strictly **PENDING_REVIEW**:

```
+----------+--------------------------------------------------------------+--------------------+
| ID       | Title                                                        | Current Status     |
+----------+--------------------------------------------------------------+--------------------+
| DEC-001  | Missing Commercial Ex-GST Purchase Rates on Historical GRNs  | PENDING_REVIEW     |
| DEC-002  | July Historical Data vs 12-Oct-2026 Costing Cutoff (82 Days) | PENDING_REVIEW     |
| DEC-003  | Unmapped GRN Items & Ambiguous Scrap Mapping (007 vs 008)    | PENDING_REVIEW     |
| DEC-004  | Suspected Year Typo (7-16-20236) in Issue Records (12 Rows)  | PENDING_REVIEW     |
| DEC-005  | Reconciliation of Seven Negative Closing Stock Balances      | PENDING_REVIEW     |
| DEC-006  | Sample Template Rows in Material Entry Sheets (Row 2)        | PENDING_REVIEW     |
| DEC-007  | Furnace Heat Log Integrity & Mass Balance Discrepancies      | PENDING_REVIEW     |
| DEC-008  | Legacy Store Inventory Code Inconsistency & Future Dates     | PENDING_REVIEW     |
+----------+--------------------------------------------------------------+--------------------+
```

---

## 9. Prioritized Management Review Checklist

```
[ ] 1. CUTOFF POLICY APPROVAL (DEC-002) — CRITICAL BLOCKER
    Formal approval by Managing Director / Plant Head of Scenario A:
    - July 2026 records ingested into read-only historical archive tables.
    - Live ledger posting begins strictly on 12-Oct-2026 based on audited physical stocktake.

[ ] 2. PHYSICAL INVENTORY STOCKTAKE & OPENING VALUATION (DEC-005)
    Plant-wide physical stock count conducted as of 12-Oct-2026:
    - Count quantities verified by Stores Manager and Plant Head.
    - Ex-GST valuation rates approved by Finance Head.

[ ] 3. COMMERCIAL PURCHASE INVOICE AUDIT (DEC-001)
    Finance Head to audit and supply verified ex-GST purchase rates:
    - Row 2: Vendor MM Tools, Invoice 096, PO 110726-02.
    - Row 3: Vendor sreenathji, Invoice GMP2926002828, PO 300426-10.
    - Row 4: Invoice 454, PO 070726-11.
    - Row 5: Invoice 384, PO 140726-02.

[ ] 4. MASTER DATA APPROVALS (DEC-003)
    - Plant Head approval to create MNT-CN-001 (Generator part) and MCS-CN-002 (Tool Post).
    - Metallurgist written confirmation of chemical grade for crca scrap (FDY-RM-007 vs FDY-RM-008).

[ ] 5. DATE TYPO SIGN-OFF (DEC-004)
    Stores Manager written authorization confirming 7-16-20236 represents 2026-07-16 across rows 537–548.

[ ] 6. TEMPLATE SAMPLE EXCLUSION (DEC-006)
    Systems Architect / Stores Manager sign-off to purge Row 2 sample entries from operational migration.

[ ] 7. FURNACE RECONCILIATION RETENTION (DEC-007)
    Foundry Head written confirmation that 22-Jul-2026 heat log records remain quarantined in staging preview.

[ ] 8. LEGACY ARCHIVE RETIREMENT (DEC-008)
    IT Head sign-off to permanently retire Store Inventory.xlsx from live migration.
```

---

## 10. Explicit Confirmation of Changes & Safety Boundaries

1. **What Was Changed:**
   - Generated audit script: `scripts/phase7_stage2_1_audit.py`.
   - Created reports in dedicated directory: `docs/reports/phase7_stage2_1/`.
2. **What Was NOT Changed:**
   - Original Excel workbooks: Zero bytes modified.
   - Application database: Zero records inserted, updated, or deleted.
   - Append-only inventory ledger: Zero stock movements or adjustments posted.
   - Core application code & migrations: Zero code modified.
   - Prior Stage 1 and Stage 2 report files: Preserved in full.

> [!CAUTION]
> **PHASE 7 STAGE 3 (LIVE DATABASE IMPORT & LEDGER POSTING) IS STRICTLY UNAUTHORIZED.**  
> Execution must halt until management completes the checklist above and provides formal written sign-off.
