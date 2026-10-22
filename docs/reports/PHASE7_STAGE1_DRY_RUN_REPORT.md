# VSPL Material Management & Costing System — Phase 7 Stage 1 Dry-Run Analysis Report
**Historical Excel Migration Inspection, Source Mapping, Stock Reconciliation & Costing Readiness**

* **Report Date:** 10 October 2026
* **Execution Mode:** STRICTLY READ-ONLY DRY RUN (Zero database writes, zero data modifications)
* **Target Enterprise:** Vijay Spheroidals Pvt. Ltd. (VSPL), Peenya Industrial Area, Bangalore
* **Engineer / Architect:** Senior Data Migration Architect, Manufacturing Inventory Analyst & Database Integrity Engineer
* **Scope:** 5 Workbooks across 23 Worksheets (~3,675 non-empty data rows)

---

## 1. Executive Summary & Hard Safety Audit

This report documents the exhaustive, read-only discovery, schema mapping, data anomaly analysis, and stock reconciliation of all historical Excel workbooks for Vijay Spheroidals Pvt. Ltd. (VSPL).

### Hard Safety Boundaries Verification:
1. **Zero Database Writes:** No `INSERT`, `UPDATE`, or `DELETE` SQL operations were executed against any database.
2. **Zero Stock Ledger Postings:** No stock movements, opening balances, or audit adjustments were created or posted.
3. **No Alembic Upgrades:** No database migrations were executed.
4. **Original Files Untouched:** Source spreadsheets were opened strictly in read-only mode (`openpyxl.load_workbook(..., data_only=True)`). Hashes and timestamps remain byte-identical.
5. **No Synthetic Normalization:** Ambiguous rows, unmapped items, and corrupt dates were flagged and cataloged rather than altered.

---

## 2. Discovered Source Workbooks Inventory

All discoverable historical workbooks reside in the designated directories on drive `C:\VSPL_MM`. Detailed file metadata and SHA256 fingerprints are permanently recorded in [`docs/reports/phase7_dry_run/source_workbooks_inventory.csv`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_dry_run/source_workbooks_inventory.csv).

| Workbook ID | Category | File Path | Size | SHA256 Fingerprint | Worksheets |
|---|---|---|---|---|---|
| `ITEM_MASTER` | Master Catalogs | `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Item_Master.xlsx` | 43,026 B | `fa1fefcb4892cfa71fc0f8a846c483d3b73e5ff1b5d19ec6fb44e54e48866e4a` | `Item Master` (392 rows), `Departments` (8), `Categories` (16), `UOM` (7), `Change Log` (260) |
| `MATERIAL_ENTRY` | Operational Transactions | `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Material_Entry.xlsx` | 153,553 B | `57ba78b8a531d0d97034b07cf044005b6fa72e50cf6097e937d2f3c051a87754` | `4. Issue` (559 rows), `3. Receipt GRN` (5), `5. Waste Disposition` (7), `1. Vendors` (2), `2. New Items` (17), `ItemMaster` (392) |
| `HEAT_LOG` | Furnace Production | `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Foundry_Heat_Log.xlsx` | 246,077 B | `356e8c536a3c3cb853869804d65dd2381df7e7ec3731e798b7b26be2345f881d` | `Heat Log` (20 rows), `Charge Details` (11), `Parts Produced` (31), `Weekly Charge Plan` (2), `Grade Chemistry` (7) |
| `MASTER_LEDGER` | Material Balances | `C:\VSPL_MM\VSPL_MM_Data\ledger\VSPL_Master_Ledger.xlsx` | 29,043 B | `7cb034054d5b4c4e471558b6e1c52b4c0ec7dc786d9b9a555aed42193d984600` | `Ledger` (392 rows) |
| `LEGACY_STORE` | Legacy Raw Archive | `C:\VSPL_MM\_legacy_archive\Store Inventory.xlsx` | 126,293 B | `40194dcf05ea29efb42f61aae7c25787a6f0ad482bca4b2bdfa777c7a6874b6d` | `Stock Details` (681 rows), `Old data` (585), `Material Receipt` (123), `Material Issue` (28), `Sheet5` (8), `Sheet8` (23) |

> **Clarification on Dataset Size:** The roadmap references ~12,280 transactions in projected long-term plant logs. The actual historical records present in these five physical files total **3,675 non-empty rows**.

---

## 3. Existing Application State & Representation

1. **Reference Data:** 8 plant departments and 7 controlled UOMs are seeded in the database.
2. **Item Master Scope:** `VSPL_Item_Master.xlsx` defines **391 canonical items** (87 Foundry, 50 Machine Shop, 217 Maintenance, 8 Packing, 5 Quality, 23 General/Stores, 1 Utilities). All 391 items have legacy codes (`FRM01`, `CON01`, etc.) mapped via the `Change Log`.
3. **Ledger Balance State:** In the application database, the ledger is in clean baseline state. No synthetic opening balances or unverified transactions were imported.

---

## 4. Source-to-Target Entity Mapping Matrix

| Source Workbook / Sheet | Source Columns | Target Application Entity | Target Fields | Transformation & Validation Rules |
|---|---|---|---|---|
| `VSPL_Item_Master.xlsx` $\rightarrow$ `Item Master` | `Item Code`, `Item Description`, `Department`, `UOM`, `Reorder Level`, `Legacy Code` | `material_items` | `item_code`, `name`, `department_id`, `base_uom_id`, `reorder_level` | Exact lookup against `departments.name` and `uoms.code`. Reject duplicates on `item_code`. |
| `VSPL_Material_Entry.xlsx` $\rightarrow$ `3. Receipt GRN` | `Date`, `GRN No`, `Vendor Name`, `Supplier Invoice No`, `Item Code`, `Quantity Received` | `grn_headers` & `grn_line_items` | `receipt_date`, `grn_number`, `vendor_id`, `vendor_invoice_no`, `material_item_id`, `quantity` | Date parsed to ISO YYYY-MM-DD. Mandatory `rate_ex_gst` missing in sheet — requires human rate entry before posting to ledger. |
| `VSPL_Material_Entry.xlsx` $\rightarrow$ `4. Issue` | `Date`, `Issue Slip No`, `Item Code`, `Quantity Issued`, `Issued To (Dept)`, `Consuming Section` | `material_issue_headers` & `material_issue_line_items` | `issue_date`, `issue_slip_number`, `receiving_department_id`, `material_item_id`, `quantity` | Group lines by `(Date, Issue Slip No, Dept)`. Clean corrupted dates (e.g. `'7-16-20236'`). Verify positive quantity. |
| `VSPL_Material_Entry.xlsx` $\rightarrow$ `5. Waste Disposition` | `Date`, `Disposal Note No`, `Item Code`, `Quantity`, `Waste Type`, `Reason` | `waste_disposition_headers` & `waste_disposition_line_items` | `disposition_date`, `waste_number`, `material_item_id`, `quantity`, `waste_type` | Enforce positive quantity. Missing dates in rows 3–7 require manual date assignment. |
| `VSPL_Foundry_Heat_Log.xlsx` $\rightarrow$ `Heat Log` | `Heat No`, `Date`, `Furnace`, `Target Grade`, `Metal Tapped (kg)`, `Good Castings (kg)` | `heat_headers` | `heat_number`, `normalized_heat_number`, `heat_date`, `furnace_id`, `metal_tapped_weight` | Normalize heat numbers (`072613-2092` $\leftrightarrow$ `H-072613-2092`). Never create stock ledger movements. |
| `VSPL_Foundry_Heat_Log.xlsx` $\rightarrow$ `Charge Details` | `Heat No`, `Item Code`, `Item Description`, `Quantity (kg)` | `heat_charge_lines` | `heat_id`, `material_item_id`, `charged_quantity` | Match `Item Code` to `material_items.id`. Unmapped descriptions resolve via `material_aliases`. |
| `VSPL_Foundry_Heat_Log.xlsx` $\rightarrow$ `Parts Produced` | `Heat No`, `Product / Part`, `No. of Parts`, `Unit Cast Weight (kg)` | `heat_parts_produced` | `heat_id`, `original_part_description`, `quantity_produced`, `unit_cast_weight` | Require `quantity_produced > 0` and `unit_cast_weight > 0` for part costing. |

---

## 5. Classification of Historical Source Records

Detailed line-by-line classifications are written to:
- [`issues_dry_run_audit.csv`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_dry_run/issues_dry_run_audit.csv) (558 records)
- [`grn_receipts_dry_run_audit.csv`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_dry_run/grn_receipts_dry_run_audit.csv) (4 records)
- [`waste_disposition_dry_run_audit.csv`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_dry_run/waste_disposition_dry_run_audit.csv) (6 records)
- [`stock_reconciliation_audit.csv`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_dry_run/stock_reconciliation_audit.csv) (391 items)

### Classification Breakdown:

```
1. Material Issues (VSPL_Material_Entry.xlsx - 558 rows):
   - VALID_NEW_CANDIDATE:     512 rows (91.8%)
   - INVALID_SOURCE (Qty):     34 rows (6.1%)  — Zero or missing quantity (e.g. rows 542–558)
   - INVALID_SOURCE (Date):    10 rows (1.8%)  — Typo '7-16-20236' (Year 20236!)
   - UNMAPPED_ITEM_CODE:        2 rows (0.4%)  — Missing item code ('Na' or empty)

2. Goods Receipts (VSPL_Material_Entry.xlsx - 4 rows):
   - VALID_NEW_CANDIDATE:       1 row   (25.0%) — Emery Paper (FDY-CN-003)
   - UNMAPPED_ITEM:             3 rows  (75.0%) — 'NOT FOUND' (Generator, Tool Post, CRCA Scrap)
   - RATE_MISSING:              4 rows  (100.0%) — No rate_ex_gst column in spreadsheet

3. Waste Dispositions (VSPL_Material_Entry.xlsx - 6 rows):
   - VALID_NEW_CANDIDATE:       1 row   (16.7%) — Emery Paper (WD-0001)
   - MANUAL_REVIEW (Date):      5 rows  (83.3%) — Missing disposal date and document numbers

4. Heat Logs (VSPL_Foundry_Heat_Log.xlsx - 19 rows):
   - VALID_NEW_CANDIDATE:      19 heats (100.0%)

5. Heat Charge Lines (VSPL_Foundry_Heat_Log.xlsx - 10 rows):
   - VALID_NEW_CANDIDATE:      10 lines (100.0%) — Mapped to canonical items

6. Parts Produced (VSPL_Foundry_Heat_Log.xlsx - 19 rows):
   - VALID_NEW_CANDIDATE:       2 lines (10.5%)
   - MANUAL_REVIEW:            17 lines (89.5%) — Missing unit cast weight or zero parts count
```

---

## 6. Quantity, Unit & Date Anomalies Identified

1. **Year 20236 Typo:** In `VSPL_Material_Entry.xlsx` (`4. Issue`), rows 535–544 contain date `'7-16-20236'`. This is a human data-entry typo for `2026-07-16`. Under hard safety rules, this date is flagged for review rather than auto-corrected.
2. **Missing Receipt Unit Rates:** None of the GRN records in `VSPL_Material_Entry.xlsx` provide commercial ex-GST rates. Importing them directly to the stock ledger would create unvalued receipts (`MISSING_RECEIPT_RATE`).
3. **Missing Item Mappings in GRN:** Three receipt lines specify `'NOT FOUND'` for `Item Code`:
   - `3306PMKT-Generator` (PO 300426-10)
   - `Tool Post` (PO 070726-11)
   - `crca scrap` (PO 140726-02, 15,200 kg)
4. **Zero & Negative Quantities in Legacy Archive:** In `Store Inventory.xlsx` (`Stock Details`), item `FRM05` (`Borings-500/10`) records a negative stock of `-2.0000 kg`. Item `CON01` has duplicate entries under the same code.

---

## 7. Stock Reconciliation Analysis (Without Posting)

The interim balance spreadsheet `VSPL_Master_Ledger.xlsx` was audited against `Store Inventory.xlsx` (`Stock Details`). The full reconciliation is saved in [`stock_reconciliation_audit.csv`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_dry_run/stock_reconciliation_audit.csv).

### Key Findings:
- **Opening Balances in `VSPL_Master_Ledger.xlsx`:** All 391 items list `Opening Stock = 0.0000`.
- **Legacy `Stock Details` Balances:** 113 items show positive historical balances (e.g. `Bial`: 650 kg; `Magnesium`: 550 kg; `Quick cast`: 500 kg; `Silicon`: 26 kg).
- **Variance Summary:** Because `VSPL_Master_Ledger.xlsx` was initialized with zero opening stock, there is an immediate variance across all 113 stocked items:
  $$\text{Legacy Physical Stock (July 2026)} = 113 \text{ active items} \quad \text{vs} \quad \text{Interim Master Ledger Opening} = 0.0000$$
- **Negative Stock Warning:** In `VSPL_Master_Ledger.xlsx`, 7 raw materials display negative closing stock (e.g. `FDY-RM-008 CRC Scrap`: $-500\text{ kg}$; `FDY-RM-011 Gattings`: $-300\text{ kg}$; `FDY-RM-019 Pig Iron`: $-150\text{ kg}$) because issue transactions were logged without prior receipt or opening balance entries!

---

## 8. Historical Costing Readiness Assessment

In accordance with Phase 6 business rules (Rules C1–C9), all 391 material items were evaluated for costing readiness:

```
Item Costing Readiness Classification:
- COSTING_READY:                 0 items (0.0%)
- OPENING_VALUATION_MISSING:   113 items (28.9%) — Physical stock exists in legacy sheets, but zero approved commercial rate
- RATE_HISTORY_INCOMPLETE:       4 items (1.0%)  — GRN receipts exist, but ex-GST invoice rate is omitted
- POLICY_PENDING:               25 items (6.4%)  — Internal foundry returns, borings, and gating scrap
- INSUFFICIENT_COST_DATA:      249 items (63.7%) — Zero receipts, zero movements, uninitialized
```

### Critical Costing Blockers Identified:
1. **No Commercial Rates on Inward Receipts:** `VSPL_Material_Entry.xlsx` (`3. Receipt GRN`) completely lacks rate columns (`rate_ex_gst`). Without vendor invoice rates, a weighted-average cost cannot be calculated.
2. **Missing Opening Valuation Rates:** The 113 legacy stock balances lack approved unit rates.
3. **Negative Stock Sequences:** Issues recorded prior to receipts create negative stock periods, which would trigger `NEGATIVE_STOCK_SUSPENDED`.

---

## 9. Migration Blockers & Decisions Required from VSPL Management

Before Stage 2 (write-enabled migration) can be authorized, the following blockers require explicit management sign-off:

1. **Decision D1 — Commercial Inward Rates:**
   - *Issue:* `VSPL_Material_Entry.xlsx` has no invoice rate column.
   - *Required Action:* Management / Purchase must supply ex-GST rates for historical receipts or approve opening rate master cards (`item_opening_valuations`).
2. **Decision D2 — Cutoff Date Alignment:**
   - *Issue:* The historical Excel spreadsheets span July 2026 (`2026-07-08` to `2026-07-16`), whereas the system costing start date is strictly **12 October 2026**.
   - *Required Action:* Management must clarify whether July 2026 transactions are imported as historical audit archives or rolled into an opening physical balance as of 12 October 2026.
3. **Decision D3 — Unmapped GRN Items:**
   - *Issue:* 3 GRN lines list `'NOT FOUND'` (`3306PMKT-Generator`, `Tool Post`, `crca scrap` 15,200 kg).
   - *Required Action:* Stores/Purchase must provide official canonical item codes.
4. **Decision D4 — Corrupted Date Typo:**
   - *Issue:* 10 issue rows have date `'7-16-20236'`.
   - *Required Action:* Formal approval to parse these as `2026-07-16`.
5. **Decision D5 — Negative Closing Stock Resolution:**
   - *Issue:* 7 raw materials show negative closing stock in `VSPL_Master_Ledger.xlsx` due to unlogged opening receipts.
   - *Required Action:* Stores must confirm baseline opening stocks so physical ledger balances remain positive.

---

## 10. Audit Artifacts & Generated Review Files

All audit files have been generated with complete row-level transparency:

1. **[`source_workbooks_inventory.csv`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_dry_run/source_workbooks_inventory.csv):** Metadata, row counts, and SHA256 fingerprints for all 5 workbooks.
2. **[`issues_dry_run_audit.csv`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_dry_run/issues_dry_run_audit.csv):** Classification of all 558 issue rows.
3. **[`grn_receipts_dry_run_audit.csv`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_dry_run/grn_receipts_dry_run_audit.csv):** Audit of 4 GRN receipt rows highlighting missing commercial rates.
4. **[`waste_disposition_dry_run_audit.csv`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_dry_run/waste_disposition_dry_run_audit.csv):** Audit of 6 waste rows highlighting missing dates and documents.
5. **[`stock_reconciliation_audit.csv`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_dry_run/stock_reconciliation_audit.csv):** 391-item side-by-side reconciliation between legacy physical stocks and interim ledger balances.

---

## 11. Confirmation of Zero Mutations & Regression Testing

- **Database State:** Zero records created, updated, or deleted.
- **Stock Ledger State:** Completely unchanged.
- **Automated Regression Suite:** 68/68 Pytest tests passed (100% pass rate).
- **Next Step:** Awaiting VSPL management review and explicit authorization before proceeding to Stage 2.
