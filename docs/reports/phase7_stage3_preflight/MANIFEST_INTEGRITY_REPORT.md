# VSPL Material Management & Costing System — Historical Manifest Integrity Report

**Document ID:** `DOC-P7-S3A-MANIFEST-INTEGRITY`  
**System:** VSPL Material Management & Costing System  
**Date:** 2026-10-17  
**Governance Scope:** Manifest Verification, Determinism & Completeness Evaluation  
**Status:** **616 OPERATIONAL ROWS VERIFIED — DETERMINISTIC BUT NOT LIVE-ELIGIBLE**  

---

## 1. Executive Summary

A comprehensive integrity audit of the Stage 2 proposed migration manifest ([`docs/reports/phase7_stage2/proposed_migration_manifest.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2/proposed_migration_manifest.csv)) and its generator ([`scripts/phase7_stage2_manifest_generator.py`](file:///C:/VSPL_MM/Material%20managment%20system/scripts/phase7_stage2_manifest_generator.py)) was executed.

### Core Findings:
1. **Source Hash Stability:** All five primary Excel workbooks match their recorded SHA-256 fingerprints 100%.
2. **Determinism:** The manifest generator executes deterministically, producing the exact same **616 operational rows** across identical source row references.
3. **Dataset Completeness Boundary:** The 616 manifest rows represent only the staged subset of operational transactions from July 2026; they **do not represent the entire historical dataset** of Vijay Spheroidals Pvt. Ltd. (which contains 3,675 non-empty rows across discovered workbooks and an 82-day operational void).
4. **Live Ingestion Readiness:** **0% (BLOCKED).** Zero manifest rows can be posted to the live append-only inventory ledger at this stage.

---

## 2. Source Worksheets and Row Composition

The 616 operational manifest rows are derived from the following specific worksheets:

```
+---------------------------+------------------------+------------------+-------------------+------------------------------------------+
| Source Workbook           | Source Worksheet       | Physical Rows    | Staged Row Count  | Operational Scope                        |
+---------------------------+------------------------+------------------+-------------------+------------------------------------------+
| VSPL_Material_Entry.xlsx  | 3. Receipt GRN         | Rows 2 to 5      | 4 rows            | Inward vendor deliveries (July 2026)     |
| VSPL_Material_Entry.xlsx  | 4. Issue               | Rows 2 to 562    | 561 rows          | Material store issue slips (July 2026)   |
| VSPL_Material_Entry.xlsx  | 5. Waste Disposition   | Rows 2 to 7      | 6 rows            | Scrap, defective & damaged materials     |
| VSPL_Foundry_Heat_Log.xlsx| Heat Log               | Rows 2 to 20     | 19 rows           | Induction furnace daily heats (22-Jul)   |
| VSPL_Foundry_Heat_Log.xlsx| Charge Details         | Rows 2 to 11     | 10 rows           | Material charge weight breakdown lines   |
| VSPL_Foundry_Heat_Log.xlsx| Parts Produced         | Rows 2 to 17     | 16 rows           | Finished ductile iron castings produced  |
+---------------------------+------------------------+------------------+-------------------+------------------------------------------+
| Total Operational Rows    |                        |                  | 616 rows          | Staged Historical Manifest               |
+---------------------------+------------------------+------------------+-------------------+------------------------------------------+
```

---

## 3. Forensic Manifest Findings by Audit Dimension

### 3.1 Unique Source-Record Identifiers
- Every row in the manifest is assigned an immutable composite key:
  `{source_workbook_code}_{worksheet_code}_{source_row_number}` (e.g. `ME_ISS_0537`).
- In the Stage 2.1 crosswalk, this is normalized to canonical format:
  `MANIFEST-ROW-{index:04d}` (e.g. `MANIFEST-ROW-0001` to `MANIFEST-ROW-0616`).
- **Idempotency Safeguard:** This unique identifier directly maps to the `source_document_id` and `source_line_id` fields in `stock_ledger_entries`, guaranteeing that no source line can ever be posted twice.

### 3.2 Commercial Rate Availability
- **Operational GRNs (Rows 2 to 5):** 0 of 4 rows have commercial unit rates.
- **Item Master Baseline:** Column K (`Rate (INR)`) is `None` across all 391 items in `VSPL_Item_Master.xlsx`.
- **Costing Impact:** Under Phase 6 Rule C1, moving weighted average rates cannot be calculated without commercial purchase rates. Importing these receipts with zero rates would cause the entire costing engine to collapse to ₹0.00 valuations.

### 3.3 Item & Vendor Mapping Exceptions
- **Row 3 (`MNT-CN-001`):** `3306PMKT-Generator` (1 Set) from vendor *sreenathji*. Code missing from canonical Item Master; exists in `2. New Items` Row 5.
- **Row 4 (`MCS-CN-002`):** `Tool Post` (4 Nos) on PO `070726-11`. Date and vendor blank in source spreadsheet; code missing from Item Master; exists in `2. New Items` Row 6.
- **Row 5 (`FDY-RM-007 / 008`):** `crca scrap` (15,200 kg) on PO `140726-02`. Date and vendor blank; chemically ambiguous between Low MN (`FDY-RM-008`) and Low High MN (`FDY-RM-007`).

### 3.4 Invalid Dates and Quantities
- **Date Typo (Rows 537 to 548):** Exactly 12 physical rows in `4. Issue` have stored text `'7-16-20236'`.
- **Zero Quantity Rows:** Exactly 34 Issue rows record `Quantity = 0.0`. These are blocked source defects that cannot create ledger movements.
- **Destroyed/Null Waste Rows:** Row 4 of `5. Waste Disposition` records `Quantity = None` for Borings. Blocked.

### 3.5 Furnace Heat Log Integrity Deficit
- **18 Heats with 0 Charge:** Rows 3 to 20 of `Heat Log` report `Total Charge = 0 kg` but liquid metal tapped between 504 and 524 kg (generating negative melt loss of -100% to -125%).
- **Charge Details Deficit:** Only 10 charge rows exist in the entire workbook. Only 1 row belongs to a logged heat.

---

## 4. Reconciled Manifest Crosswalk Distribution

| Recheck Primary Classification | BLOCKED_SOURCE_DEFECT | HELD_MANUAL_REVIEW | HELD_PENDING_DECISION | ROW_CLEAN_PENDING_CUTOFF_POLICY | Total |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **INVALID_SOURCE** | 38 | 0 | 0 | 0 | **38** |
| **UNMAPPED** | 0 | 3 | 0 | 0 | **3** |
| **CONFLICT** | 0 | 2 | 0 | 0 | **2** |
| **MANUAL_REVIEW** | 0 | 63 | 0 | 0 | **63** |
| **VALID_NEW_CANDIDATE** | 0 | 0 | 163 | 347 | **510** |
| **Total** | **38** | **68** | **163** | **347** | **616** |

### Critical Takeaway:
Even the 347 "clean" issue rows cannot be posted to the live ledger because posting store issues without establishing certified opening stock will immediately plunge inventory balances into negative territory, corrupting the append-only stock ledger.
