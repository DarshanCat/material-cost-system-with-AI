# VSPL Material Management & Costing System — Physical Stocktake Readiness QA Audit Report

**Document ID:** `QA-P7-STOCKTAKE-READINESS`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd. (Peenya Industrial Area, Bangalore)  
**Audit Date & Time:** 2026-10-13 17:05:00 IST  
**Audit Scope:** Independent Read-Only Quality Assurance & Readiness Verification of the Physical Stocktake Preparation Package  
**Target Cutoff:** 12 October 2026, 23:59:59 IST  
**Auditor Role:** Senior Manufacturing ERP Quality Assurance Lead & Migration Auditor (Antigravity)  
**Overall Readiness Verdict:** **CONDITIONAL GO (OPERATIONAL CONTROLS REQUIRED BEFORE FIELD COUNT)**  

---

## 1. Executive Summary & Audit Mandate

This report provides an independent, evidence-backed quality assurance audit of the physical stocktake preparation package generated in:
`C:\VSPL_MM\Material managment system\docs\reports\phase7_stocktake_preparation\`

The audit evaluates whether the preparation package is safe, robust, and auditable before physical stock counting commences on the factory floor or opening balances are submitted for management sign-off.

### Mandatory Safety Confirmation:
- **Strict Read-Only Execution:** Zero modifications were made to `VSPL_Physical_Stocktake_Register.xlsx`, original workbooks, historical archives, application source code, or migrations.
- **Transactional Isolation:** The PostgreSQL database was not connected; zero stock ledger entries or opening inventory transactions were posted.
- **Phase 7 Stage 3 Status:** **STRICTLY UNAUTHORIZED.**

---

## 2. Evidence Inspected & Audit Methodology

### 2.1 Artifacts Inspected:
1. **Master Stocktake Workbook:** [`docs/reports/phase7_stocktake_preparation/VSPL_Physical_Stocktake_Register.xlsx`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stocktake_preparation/VSPL_Physical_Stocktake_Register.xlsx) (94,879 bytes, MD5/SHA verified).
2. **Standard Operating Procedure:** [`docs/reports/phase7_stocktake_preparation/PHYSICAL_STOCKTAKE_PROTOCOL.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stocktake_preparation/PHYSICAL_STOCKTAKE_PROTOCOL.md) (12,704 bytes).
3. **Historical Exception Register:** [`docs/reports/phase7_stocktake_preparation/EXCEPTION_RECONCILIATION_REGISTER.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stocktake_preparation/EXCEPTION_RECONCILIATION_REGISTER.md) (11,911 bytes).
4. **Stocktake README:** [`docs/reports/phase7_stocktake_preparation/README.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stocktake_preparation/README.md) (10,331 bytes).
5. **Workbook Generation Script:** [`scripts/build_stocktake_workbook.py`](file:///C:/VSPL_MM/Material%20managment%20system/scripts/build_stocktake_workbook.py).
6. **Primary Source Workbooks:**
   - Canonical Item Master: `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Item_Master.xlsx` (391 items).
   - Material Entry Log: `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Material_Entry.xlsx` (`2. New Items` 16 rows, `3. Receipt GRN`, `4. Issue`).
   - Master Ledger: `C:\VSPL_MM\VSPL_MM_Data\ledger\VSPL_Master_Ledger.xlsx` (391 items, 8 active rows).
   - Legacy Archive: `C:\VSPL_MM\_legacy_archive\Store Inventory.xlsx` (`Material Receipt` 123 rows).
   - Management Sign-Off Register: `docs/reports/phase7_management_signoff/MANAGEMENT_DECISION_REGISTER.csv`.

### 2.2 Verification Scripts Executed:
- Automated openpyxl AST and XML inspector: [`scripts/audit_stocktake_readiness.py`](file:///C:/VSPL_MM/Material%20managment%20system/scripts/audit_stocktake_readiness.py).

---

## 3. Detailed Audit Findings by Assessment Dimension

### Dimension 1: Double-Blind Counting Feasibility
- **Severity:** **CRITICAL**
- **Verified Facts:**
  1. In Worksheet A (`A. Stocktake Register`), Column E contains `Source-Supported Book Qty`. Column E is **completely visible** (`hidden=False`, width = 26.0) and sits immediately adjacent to Column F (`Physical Counted Qty`).
  2. For 8 items (`FDY-RM-008`, `011`, `014`, `016`, `017`, `019`, `020`, `FDY-CN-003`), exact interim ledger balances (-500, -300, -2, -15, -3, -150, -5, +18) are displayed. For all other items, Column M displays `UNKNOWN (82-DAY OPERATIONAL VOID)`.
  3. Worksheets B (`Variance Investigation`), C (`Valuation Register`), and D (`Opening Inventory Approval`) are all located within the same unencrypted workbook file, with all tabs visible and accessible.
  4. There are no print boundaries defined (`print_title_rows=None`, `print_title_cols=None`).
- **Audit Conclusion:**  
  **A genuinely double-blind physical count is IMPOSSIBLE if this workbook file is provided directly to physical counters on laptops or tablets, or if Sheet A is printed without manually hiding Column E.**
- **Mitigating Factor:** The protocol document ([`PHYSICAL_STOCKTAKE_PROTOCOL.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stocktake_preparation/PHYSICAL_STOCKTAKE_PROTOCOL.md)) correctly specifies a physical two-part perforated tag system (`TAG-20261012-xxxx`). Therefore, the workbook is safe **only** when restricted to the central Audit Control Desk as a consolidation register.

---

### Dimension 2: Formula Integrity & Protection
- **Severity:** **HIGH**
- **Verified Facts:**
  1. **Sheet A (Variance Formula):** Exactly 407 rows contain:
     `=IF(ISBLANK(F{r}),"",IF(ISNUMBER(E{r}),F{r}-E{r},"PENDING_BOOK_QTY"))`
     Zero syntax or reference errors found.
  2. **Sheet B (Variance Formula):** Exactly 20 rows contain:
     `=IF(ISBLANK(C{r}),"",IF(ISNUMBER(B{r}),C{r}-B{r},""))`
     Zero syntax errors found. Column C (`Counted Qty`) is blank across all 20 rows.
  3. **Sheet C (Extended Value Formula):** Exactly 407 rows contain:
     `=IF(OR(ISBLANK(E{r}),ISBLANK('A. Stocktake Register'!F{r})),"",'A. Stocktake Register'!F{r}*E{r})`
     Zero syntax errors found.
  4. **Sheet D (Proposed Qty & Value Formulas):**
     `Col D: =IF(ISBLANK('A. Stocktake Register'!F{r}),"",'A. Stocktake Register'!F{r})`
     `Col E: =IF(ISBLANK('C. Valuation Register'!H{r}),"",'C. Valuation Register'!H{r})`
     Zero syntax errors found.
  5. **Lack of Cell Protection:** **`ws.protection.sheet == False` across all 4 worksheets.** None of the formula cells are locked against editing. Any data entry operator typing into Column K (Sheet A), Column D (Sheet B), Column H (Sheet C), or Columns D–E (Sheet D) will permanently overwrite the formulas.

---

### Dimension 3: Blank versus Zero Handling
- **Severity:** **INFORMATIONAL (VERIFIED CORRECT)**
- **Verified Facts:**
  1. **Sheet A:** If `Physical Counted Qty` (Col F) is left blank, formula `=IF(ISBLANK(F{r}),...)` evaluates to `""` (empty string). If a counter records a true physical zero (`0`), `ISBLANK(0)` evaluates to `FALSE`, correctly triggering variance arithmetic ($0 - \text{Book Qty}$).
  2. **Book Quantity Blank:** For 383 items with unknown book quantities, Col E is blank. Formula `=IF(ISNUMBER(E{r}),...)` evaluates to `FALSE`, displaying `"PENDING_BOOK_QTY"` instead of treating blank as zero.
  3. **Sheet C:** If `Physical Counted Qty` is 0 and a rate exists, extended value correctly computes as `0 * Rate = 0.00`. If rate is blank, extended value evaluates to `""` (unvalued).
- **Audit Conclusion:** The workbook cleanly distinguishes between `0` (counted zero stock), `blank` (uncounted), and `blank book` (unknown historical balance).

---

### Dimension 4: Item Segregation & Candidate Item Isolation
- **Severity:** **LOW (VERIFIED SOUND)**
- **Verified Facts:**
  1. **Canonical Master Items (Rows 6 to 396):** Exactly 391 items directly traceable to `VSPL_Item_Master.xlsx`.
  2. **Candidate Items (Rows 397 to 412):** Exactly 16 items sourced from `VSPL_Material_Entry.xlsx` sheet `2. New Items`.
  3. **Visual & Status Distinction:** All 16 candidate rows have distinct light yellow shading (`#FFF2CC`), explicit status `PENDING_MASTER_CREATION`, and evidence text `DEC-003: Candidate new item...`.
  4. In Sheet D (`Opening Inventory Approval`), Outstanding Exceptions (Col H) is explicitly set to `PENDING MASTER CREATION` for these 16 items, preventing them from being approved as active inventory without formal master data creation.

---

### Dimension 5: Duplicate Prevention & Description Collisions
- **Severity:** **HIGH**
- **Verified Facts:**
  1. **Item Code Uniqueness:** Zero duplicate item codes exist across all 407 rows (`Duplicate Codes = []`).
  2. **Description Collisions:** Exactly **15 descriptions appear multiple times across 33 rows**:
     - `m12 washer` appears 3 times (`MNT-BN-004`, `MNT-BN-085`, `MNT-BN-102`).
     - `cotton waste` appears 3 times (`MNT-CN-004`, `PKD-CN-004`, `MCS-CN-004`).
     - `borings-450/10` appears 2 times (`FDY-RM-002`, `FDY-RM-003`).
     - `gattings-450/10` appears 2 times (`FDY-RM-009`, `FDY-RM-010`).
     - `tempo brush` appears 2 times (`FDY-CN-004`, `FDY-CN-018`).
     - `aluminium paint` appears 2 times (`FDY-PT-013`, `FDY-PT-024`).
     - Bolts, nuts, washers (`m12x50 ms bolt`, `m12 nut`, `m16 washer`, `m30 nut`, `m12x50 allen bolt`, `m12x40 allen bolt`).
- **Risk:** Field counters locating items by physical description alone risk entering counts against the wrong code, creating artificial matching variances.

---

### Dimension 6: Unit of Measure (UOM) Integrity
- **Severity:** **MEDIUM**
- **Verified Facts:**
  1. Canonical UOMs in Item Master are strictly `Kg` (61), `Nos` (318), `Ltr` (17), `Pack` (2).
  2. **Non-Canonical UOMs Introduced via Candidate Items:**
     - `Roll`: 1 item (`PKD-CN-001` Foam Sheet).
     - `Set`: 1 item (`MNT-CN-001` 3306PMKT-Generator).
     - `nos` (lowercase): 3 items (`PKD-CN-002`, `MNT-CN-002`, `MNT-CN-003`).
     - `kg` (lowercase): 3 items (`MNT-CN-004`, `PKD-CN-004`, `MCS-CN-004`).
     - `nos.` (trailing period): 1 item (`MCS-CN-003` boring tool).
- **Risk:** Inconsistent casing and unapproved UOMs will fail database schema constraints upon eventual import.

---

### Dimension 7: Data Validation & Workbook Controls
- **Severity:** **MEDIUM**
- **Verified Facts:**
  1. `data_validations.dataValidation == []` across all four worksheets.
  2. Zero dropdown lists are configured for:
     - UOM selection.
     - Storage location codes.
     - Investigation status.
     - Count date format enforcement (`YYYY-MM-DD`).
- **Risk:** Operators can enter malformed dates, invalid UOMs, or arbitrary status text.

---

### Dimension 8: Timestamp, Cutoff & Post-Cutoff Movement Controls
- **Severity:** **HIGH**
- **Verified Facts:**
  1. Sheet A contains Column G (`Count Date & Time`), which is currently blank. There is no automated formula linking or comparing this field to the target cutoff (`2026-10-12 23:59:59`).
  2. **Absence of Roll-Back / Roll-Forward Reconciliation:** If the physical count takes place on 14-Oct or 15-Oct, any plant consumption or emergency receipts occurring between 12-Oct 23:59:59 and the count timestamp cannot be reconciled within the workbook structure. The workbook has no columns for "Post-Cutoff Issues" or "Post-Cutoff Receipts".
- **Risk:** Unless the factory maintains an absolute operational shutdown during the count, physical inventory counted on 14-Oct cannot be assumed equal to the 12-Oct position without a formal roll-back schedule.

---

### Dimension 9: Approval Gate Independence & Blank Field Audit
- **Severity:** **INFORMATIONAL (VERIFIED SOUND)**
- **Verified Facts:**
  1. Sheet A Col N (`Approval Status`): Exactly 0 cells populated (100% blank).
  2. Sheet B Col I (`Approval Status`): Exactly 0 cells populated (100% blank).
  3. Sheet C Col I (`Approval Reference`): Exactly 0 cells populated (100% blank).
  4. Sheet D Cols I, J, K, L (`Stores Approval`, `Plant Head Approval`, `Finance Approval`, `Final Authorization`): **Exactly 0 cells populated across all 407 rows (100% blank).**
- **Audit Conclusion:** The four-layer approval gates are physically isolated and completely unexecuted. Zero approval fields can be misinterpreted as authorized.

---

### Dimension 10: Reconciliation of Exceptions & Historical Counts
- **Severity:** **LOW (VERIFIED ACCURATE)**
- **Verified Facts:**
  1. **Canonical Items:** Exactly 391 rows matched against `VSPL_Item_Master.xlsx`.
  2. **Candidate Items:** Exactly 16 rows matched against `VSPL_Material_Entry.xlsx` sheet `2. New Items`.
  3. **Total Register Rows:** Exactly 407 items ($391 + 16 = 407$).
  4. **Investigation Exceptions:** Exactly 20 forensic records populated in Sheet B.
  5. **Legacy Store Inventory:** Confirmed presence of 115 rows with `Supplier = 'Physical stock'`, of which **113 rows contain Timestamp = 2026-11-07**, and 2 rows (Magnesium 550 kg, Manganese 20 kg) have null timestamps.

---

### Dimension 11: Governance Status of DEC-001 through DEC-008
- **Severity:** **HIGH (PENDING EXECUTIVE SIGN-OFF)**
- **Verified Facts:**
  - Audit of [`docs/reports/phase7_management_signoff/MANAGEMENT_DECISION_REGISTER.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_management_signoff/MANAGEMENT_DECISION_REGISTER.csv) confirms:
    - `DEC-001`: Current Status = `PENDING_REVIEW`, Approval Status = `PENDING_REVIEW`, Approver = `''`
    - `DEC-002`: Current Status = `PENDING_REVIEW`, Approval Status = `PENDING_REVIEW`, Approver = `''`
    - `DEC-003`: Current Status = `PENDING_REVIEW`, Approval Status = `PENDING_REVIEW`, Approver = `''`
    - `DEC-004`: Current Status = `PENDING_REVIEW`, Approval Status = `PENDING_REVIEW`, Approver = `''`
    - `DEC-005`: Current Status = `PENDING_REVIEW`, Approval Status = `PENDING_REVIEW`, Approver = `''`
    - `DEC-006`: Current Status = `PENDING_REVIEW`, Approval Status = `PENDING_REVIEW`, Approver = `''`
    - `DEC-007`: Current Status = `PENDING_REVIEW`, Approval Status = `PENDING_REVIEW`, Approver = `''`
    - `DEC-008`: Current Status = `PENDING_REVIEW`, Approval Status = `PENDING_REVIEW`, Approver = `''`
- **Audit Conclusion:** Management has **not yet signed off** on any of the eight decisions, nor officially confirmed the adoption of Scenario A over Scenarios B or C.

---

## 4. Comprehensive Findings Summary Table

| Finding ID | Dimension | Description & Evidence | Severity | Impact on Stocktake Readiness |
| :--- | :--- | :--- | :--- | :--- |
| **F-01** | Double-Blind Counting | Col E (Book Qty) is unhidden and visible in Sheet A. Sheets B, C, D are visible. | **CRITICAL** | Direct shop-floor use of the workbook invalidates blind counting integrity. |
| **F-02** | Cell Protection | Formula cells across all sheets are unlocked (`ws.protection.sheet == False`). | **HIGH** | High risk of accidental formula deletion during count data entry. |
| **F-03** | Roll-Back Controls | Workbook lacks post-cutoff movement roll-back schedule for counts after 12-Oct. | **HIGH** | Requires factory shutdown or manual paper roll-back if counting spans multiple days. |
| **F-04** | Duplicate Descriptions | 15 descriptions are duplicated across 33 item codes in Item Master. | **HIGH** | High risk of counters recording stock against wrong canonical item codes. |
| **F-05** | Governance Approvals | DEC-001 through DEC-008 remain `PENDING_REVIEW` in official register. | **HIGH** | Stocktake can proceed, but opening balances cannot be posted until signed. |
| **F-06** | UOM Normalization | Non-canonical UOMs (`Roll`, `Set`, `nos`, `kg`, `nos.`) present in candidate rows. | **MEDIUM** | Requires master data cleaning before opening inventory database import. |
| **F-07** | Data Validation | Zero dropdowns or input validation rules configured in the Excel sheets. | **MEDIUM** | Risk of free-text typographical errors during count transcription. |
| **F-08** | Blank vs Zero Handling | Blank physical count evaluates to `""`; zero evaluates to `0`. Blank book evaluates to `"PENDING_BOOK_QTY"`. | **INFORMATIONAL** | Functioning correctly; no silent zero conversions detected. |
| **F-09** | Approval Gates | All approval fields across all 4 worksheets are 100% blank. | **INFORMATIONAL** | Functioning correctly; strict transactional isolation preserved. |

---

## 5. Required Remediation Before Physical Counting

The following operational remediations must be enforced prior to physical counting:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                   MANDATORY OPERATIONAL REMEDIATION PLAN                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 1. FIELD COUNT SEGREGATION (MANDATORY):                                         │
│    - DO NOT distribute VSPL_Physical_Stocktake_Register.xlsx to field counters. │
│    - Counters must use paper count tags (Part A/B per SOP-P7) OR a generated    │
│      blind counting slip that omits Column E, Column K, and Sheets B, C, D.     │
│                                                                                 │
│ 2. SPREADSHEET PROTECTION (RECOMMENDED):                                        │
│    - Before entering data, lock all formula columns (Col K in A, Col D in B,    │
│      Col H in C, Cols D-E in D) and enable Excel Sheet Protection.              │
│                                                                                 │
│ 3. DUPLICATE CODE WARNING LABELS:                                               │
│    - Issue count sheets sorted by Storage Location/Bin rather than description. │
│    - Provide counters with the specific list of 15 duplicate descriptions.      │
│                                                                                 │
│ 4. FORMAL MANAGEMENT SIGN-OFF (PREREQUISITE FOR STAGE 3):                       │
│    - Execute formal management signatures for DEC-001 through DEC-008 using     │
│      docs/reports/phase7_management_signoff/MANAGEMENT_SIGNOFF_TEMPLATE.md.     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Explicit Recommendation: CONDITIONAL GO

### Audit Recommendation: **CONDITIONAL GO**

1. **Permission to Count:** **GRANTED**, provided that physical counting is executed strictly via the two-part count tag protocol ([`PHYSICAL_STOCKTAKE_PROTOCOL.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stocktake_preparation/PHYSICAL_STOCKTAKE_PROTOCOL.md)) and the master workbook is retained exclusively at the Audit Control Desk.
2. **Permission to Post Opening Balances:** **STRICTLY WITHHELD (NO-GO)** until:
   - Physical count data is entered and verified.
   - Variances are investigated in Sheet B.
   - Commercial purchase invoices are audited by Finance to populate Sheet C rates.
   - Formal 3-way signatures are affixed to Sheet D.
   - Executive sign-off on DEC-001 through DEC-008 is recorded in the register.

---

## 7. Audit Limitations

1. **Excel Environment:** Audit was executed using Python `openpyxl` AST analysis; formula rendering and calculation results were simulated and verified against standard Excel calculation rules.
2. **Source Data Immutability:** Historical Excel workbooks were inspected in read-only mode without executing external database queries or altering cell bytes.
3. **Physical Reality:** This audit verifies the mathematical and governance readiness of the preparation artifacts; it cannot physically verify whether stock bins on the Peenya factory floor are tagged until plant teams execute SOP-P7.

---

**Auditor Sign-off:** Lead Migration Quality Assurance Auditor (Antigravity)  
**Status:** Frozen & Archived in `docs/reports/phase7_stocktake_preparation/STOCKTAKE_READINESS_QA_REPORT.md`
