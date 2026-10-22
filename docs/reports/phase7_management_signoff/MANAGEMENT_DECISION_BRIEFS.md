# VSPL Material Management & Costing System — Phase 7 Management Decision Briefs

**Document ID:** `DOC-P7-MGMT-DECISION-BRIEFS`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd. (SG Iron Foundry & Machine Shop, Peenya, Bangalore)  
**Scope:** Substantive Operational & Governance Decision Briefs (DEC-001 through DEC-008)  
**Date:** 2026-10-13  
**Status:** **PENDING FORMAL MANAGEMENT REVIEW & SIGN-OFF — LIVE MIGRATION STRICTLY UNAUTHORIZED**  

---

## Decision Brief Index

1. [DEC-001: Missing Historical Commercial Purchase Rates](#dec-001-missing-historical-commercial-purchase-rates)
2. [DEC-002: Historical Data vs 12 October 2026 Costing Cutoff](#dec-002-historical-data-vs-12-october-2026-costing-cutoff)
3. [DEC-003: Unmapped Items & Ambiguous Scrap Classification](#dec-003-unmapped-items--ambiguous-scrap-classification)
4. [DEC-004: Suspected Issue Date Typo (`7-16-20236`)](#dec-004-suspected-issue-date-typo-7-16-20236)
5. [DEC-005: Seven Negative Closing Stock Balances & Omitted Issues](#dec-005-seven-negative-closing-stock-balances--omitted-issues)
6. [DEC-006: Sample Template Dummy Rows in Material Entry](#dec-006-sample-template-dummy-rows-in-material-entry)
7. [DEC-007: Furnace Heat Log Integrity & Mass Balance Deficit](#dec-007-furnace-heat-log-integrity--mass-balance-deficit)
8. [DEC-008: Legacy Store Inventory Records & Future Stored Dates](#dec-008-legacy-store-inventory-records--future-stored-dates)

---

### DEC-001: Missing Historical Commercial Purchase Rates

#### 1. Background & Nature of Problem
External Goods Receipt Notes (GRNs) establish the commercial valuation baseline for inventory. Under **Phase 6 Costing Rule C1**, all inward material receipts must capture the commercial purchase rate per unit excluding GST. This rate forms the moving weighted-average valuation pool used to cost store issues, work-in-progress heats, and finished cast parts. Historical receipts recorded in spreadsheet data lack this commercial valuation.

#### 2. Verified Facts & Source Evidence
- **Workbook:** `VSPL_Material_Entry.xlsx`, Worksheet `3. Receipt GRN`, physical rows 2 through 5.
  - **Row 2:** Date `2026-07-14`, GRN `2599`, Vendor `MM Tools`, Invoice `096`, PO `110726-02`, Item `Emery Paper` (`FDY-CN-003`), Qty `25 Kg`.
  - **Row 3:** Date `2026-07-14`, GRN `2622`, Vendor `sreenathji`, Invoice `GMP2926002828`, PO `300426-10`, Item `3306PMKT-Generator`, Qty `1` (no UOM).
  - **Row 4:** Undated, GRN `None`, Vendor `None`, Invoice `454`, PO `070726-11`, Item `Tool Post`, Qty `4` (no UOM).
  - **Row 5:** Undated, GRN `None`, Vendor `None`, Invoice `384`, PO `140726-02`, Item `crca scrap`, Qty `15200 kg`.
- **Complete Rate Absence:**
  - `3. Receipt GRN` **contains no rate or price column** by design. Read Me line 2 confirms: *"Phase 1: quantities only (no prices)"*.
  - `VSPL_Item_Master.xlsx` contains **0 populated rates across all 391 items** (`Rate (INR)` column K is 100% empty).
  - Legacy `Store Inventory.xlsx` contains **0 populated rates** across all sheets.
- **Evidence Reference:** Frozen artifact [`grn_mapping_pricing_exceptions.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/grn_mapping_pricing_exceptions.csv).

#### 3. Uncertainties & Evidence Gaps
- Physical tax invoices and purchase order contracts have not been retrieved or audited.
- It is unknown whether vendor discounts, freight charges, or non-creditable taxes applied to these receipts.

#### 4. Operational, Financial, and Costing Implications
- **Severe Financial Risk:** If records are imported with rate = 0, moving average rates crash to zero. Store issues consumed from these receipts inherit zero valuation, understating production cost and overstating gross margins.
- **Costing Pipeline Failure:** The Phase 6 valuation engine flags unpriced receipts as blocking valuation exceptions.

#### 5. Available Options & Trade-Offs
- **Option 1 (Audit Invoices & Enter ex-GST Rates - Recommended):** Purchase and Finance retrieve physical paper invoices matching Invoices `096`, `GMP2926002828`, `454`, and `384`. Commercial ex-GST unit rates are audited, approved, and entered into staging tables.
- **Option 2 (Quarantine / Archive Only):** If original invoices cannot be located, retain records as uncosted physical audit history without posting to live valuation ledgers.
- **Option 3 (Certified Benchmark Valuation Appraisal):** Finance Head approves an appraised valuation rate based on contemporaneous market records. *(Strictly prohibited without written Finance Head justification).*

#### 6. Governance & Accountable Authority
- **Accountable Authority:** Finance Head / Purchase Head.
- **Action Required:** Audit physical vendor tax invoices and provide certified ex-GST rates.
- **Blocking Condition:** Blocks live weighted-average costing and inventory valuation for receipted materials.
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-002: Historical Data vs 12 October 2026 Costing Cutoff

#### 1. Background & The Calendar Void
The application configuration mandates:
```python
COSTING_START_DATE = date(2026, 10, 12)
```
Historical source records span **08-Jul-2026 to 22-Jul-2026**. Management must establish the formal cutoff policy governing the relationship between July transactions and the October live go-live date.

#### 2. Verified Facts & Source Evidence
- All 616 electronic operational transaction records occur in a 15-day window ending on **22-Jul-2026**.
- **The 82-Day Void:** Exactly **82 calendar days** elapse between the last recorded transaction (22-Jul-2026) and the live costing start date (12-Oct-2026). Zero electronic transaction records exist for August or September 2026.
- **The 89-Day Interval:** Exactly **89 calendar days** elapse between the interim Master Ledger formula snapshot date (15-Jul-2026) and the 12-Oct-2026 cutoff.
- **Evidence Reference:** Frozen artifact [`READINESS_SUMMARY.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/READINESS_SUMMARY.md) and [`CUTOFF_SCENARIO_COMPARISON.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_management_signoff/CUTOFF_SCENARIO_COMPARISON.md).

#### 3. Uncertainties & Evidence Gaps
- Physical consumption, scrap generation, purchase deliveries, and customer dispatches occurred continuously across August and September 2026, but exist solely on paper registers, informal slips, or have not been digitized.
- July closing balances cannot be mathematically equated to October opening balances without reconciling 82 days of operations.

#### 4. Available Options & Trade-Offs (Neutral Presentation)
- **Scenario A: Historical Audit Archive (Recommended by Technical Audit)**
  - *Mechanism:* July 2026 records ingested into dedicated read-only historical archive tables. Live append-only ledger begins cleanly on 12-Oct-2026 using an independently verified physical stocktake as Opening Balance.
  - *Risk:* Zero risk of ledger corruption or negative stock; clean weighted-average costing.
  - *Trade-off:* July transactions cannot be viewed in standard live operational screens; they reside in historical inquiry views.
- **Scenario B: Reconstructed Opening Position (Roll-Forward)**
  - *Mechanism:* Post July records to the ledger, then reconstruct and post all intervening movements across August and September forward to 12-Oct-2026.
  - *Risk:* **CRITICAL / EXTREME RISK.** Current electronic files contain zero records for August/September. Reconstructing an 82-day period without primary electronic records introduces severe inventory divergence.
- **Scenario C: Two-Phase Transition (Staged Simulation with Adjustment)**
  - *Mechanism:* Simulate July transactions in a staging sandbox to establish preliminary July closing balances. Post a formal reconciliation adjustment entry on 12-Oct-2026 absorbing the variance against the October physical stocktake.
  - *Risk:* Moderate to high; variance between July and October must be expensed as an unclassified inventory adjustment, potentially distorting period consumption.

#### 5. Governance & Accountable Authority
- **Accountable Authority:** Managing Director / Plant Head / Finance Head.
- **Action Required:** Formally select Scenario A, B, or C, and authorize the physical stocktake date.
- **Blocking Condition:** Blocks all live database importing and ledger movement posting.
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-003: Unmapped Items & Ambiguous Scrap Classification

#### 1. Background & Technical Problem
Inward receipts recorded three items with Item Code `NOT FOUND`. Two items represent potential new consumables, while one represents a massive raw material scrap delivery (15,200 kg) that is chemically ambiguous.

#### 2. Verified Facts & Source Evidence
- **Workbook:** `VSPL_Material_Entry.xlsx`, Worksheet `3. Receipt GRN`, rows 3, 4, 5.
- **Row 3 (`3306PMKT-Generator`, Qty 1):** Exact text match in `2. New Items` row 5 proposing code `MNT-CN-001` (Maintenance, Set).
- **Row 4 (`Tool Post`, Qty 4):** Exact text match in `2. New Items` row 6 proposing code `MCS-CN-002` (Machine Shop, Nos).
- **Row 5 (`crca scrap`, Qty 15,200 kg):** Vendor Invoice `384`, PO `140726-02`.
- **The Chemical Ambiguity:**
  - Canonical `Item Master` contains two distinct CRC scrap items:
    - `FDY-RM-007`: *CRC Scrap-Low High MN* (Legacy `FRM07`)
    - `FDY-RM-008`: *CRC Scrap-Low MN* (Legacy `FRM08`)
  - The Heat Log Read Me equates CRCA loosely to "steel scrap".
  - Auto-mapping to `FDY-RM-008` (as tentatively suggested in Stage 2) is an unverified assumption. Carbon and Manganese specifications must be reviewed.
- **Evidence Reference:** Frozen artifact [`grn_mapping_pricing_exceptions.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/grn_mapping_pricing_exceptions.csv).

#### 3. Uncertainties & Evidence Gaps
- Chemical Mill Test Certificates and purchase specifications for PO `140726-02` have not been examined by a metallurgist.
- Phase 2 master data approval forms for `MNT-CN-001` and `MCS-CN-002` have not been signed.

#### 4. Operational & Metallurgical Implications
- Misclassifying Low High MN scrap as Low MN scrap skews manganese calculations during furnace charge planning, risking out-of-spec SG iron chemistry.
- Posting unmapped items causes foreign key constraint violations in the relational database.

#### 5. Available Options & Trade-Offs
- **Option 1 (Approve Candidate Codes & Chemical Grade):** Plant Head approves Phase 2 master data creation of `MNT-CN-001` and `MCS-CN-002`. Metallurgist inspects PO `140726-02` specifications and designates either `FDY-RM-007` or `FDY-RM-008`.
- **Option 2 (Quarantine / Hold):** Keep rows 3, 4, 5 in draft staging until master data is created and chemical grade is certified.

#### 6. Governance & Accountable Authority
- **Accountable Authority:** Plant Head (Item Master) + Metallurgist (Chemical Grade).
- **Action Required:** Formally approve item creation and sign chemical grade designation.
- **Blocking Condition:** Blocks canonical item foreign key validation and scrap receipt posting.
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-004: Suspected Issue Date Typo (`7-16-20236`)

#### 1. Background & The Typo
Worksheet `4. Issue` records issue transactions with a malformed date string containing the year `20236`.

#### 2. Verified Facts & Source Evidence
- **Source Location:** `VSPL_Material_Entry.xlsx`, Worksheet `4. Issue`, physical rows 537 through 548 (12 physical rows).
- **Stored String:** Exact literal text `'7-16-20236'` (data type string, cell format `mm-dd-yy`).
- **Complete Slip Reconciliation:** The seven listed issue slips account for all 12 rows without exception:
  - Slip `327`: 2 items (Row 537 cable, Row 538 plug)
  - Slip `910`: 1 item (Row 539 Belt B-44)
  - Slip `325`: 3 items (Row 540 Grinding Wheel, Row 541 Blade, Row 542 Grinding Wheel)
  - Slip `1149`: 1 item (Row 543 Mould Sealing Rope)
  - Slip `326`: 1 item (Row 544 Blue Paint)
  - Slip `2725`: 2 items (Row 545 Cutan Box, Row 546 Bubble Roll)
  - Slip `1148`: 2 items (Row 547 Holcote-100, Row 548 Blue Paint)
- **Circumstantial Chronology:**
  - Preceding rows 535–536 are dated `2026-07-15`.
  - Subsequent row 549 is dated `2026-07-15`.
  - Slips follow the sequential issue book voucher order for the morning of 16-Jul-2026.
- **Evidence Reference:** Frozen artifact [`date_discrepancy_report.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/date_discrepancy_report.csv) and [`DEC004_ROW_RECONCILIATION.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_management_review_consistency_audit/DEC004_ROW_RECONCILIATION.csv).

#### 3. Uncertainties & Normalization Boundary
- Normalization to `2026-07-16` is a **proposed interpretation**, not established fact.
- Under strict audit rules, the source spreadsheet must remain unaltered. Normalization cannot occur without Stores Manager written authorization.

#### 4. Operational & Ledger Implications
- Posting an issue with year 20236 would violate ledger period-closing rules and distort monthly consumption reporting.

#### 5. Available Options & Trade-Offs
- **Option 1 (Authorized Normalization - Recommended):** Stores Manager inspects physical issue slip books, signs written confirmation that `7-16-20236` represents `2026-07-16`. The migration staging pipeline applies `2026-07-16` while recording the original string in the audit log.
- **Option 2 (Quarantine):** If physical slips cannot be confirmed, exclude rows 537–548 from operational migration and hold in exception review.

#### 6. Governance & Accountable Authority
- **Accountable Authority:** Stores Manager.
- **Action Required:** Inspect physical slip books and sign date normalization authorization.
- **Blocking Condition:** Blocks live posting of rows 537–548.
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-005: Seven Negative Closing Stock Balances & Omitted Issues

#### 1. Background & The Computational Flaw
Workbook `VSPL_Master_Ledger.xlsx` displays negative closing balances for seven raw materials:
- `FDY-RM-008` (CRC Scrap-Low MN): **-500 kg**
- `FDY-RM-011` (Gattings-500): **-300 kg**
- `FDY-RM-014` (Inoculant 15): **-2 kg**
- `FDY-RM-016` (Magnesium): **-15 kg**
- `FDY-RM-017` (Manganese): **-3 kg**
- `FDY-RM-019` (Pig Iron): **-150 kg**
- `FDY-RM-020` (Silicon): **-5 kg**

#### 2. Verified Facts & Mathematical Proof
- **Exact Heat Charge Equality:** These seven negative figures **identically match the charged quantities of furnace heat `H-260714-01`** in worksheet `Charge Details`.
- **Root Cause:** The interim spreadsheet mistakenly subtracted furnace charge quantities directly as store issues, violating **Phase 5 Rule H1** (furnace charges are NOT store issues). Because zero opening inventory was entered in the interim ledger, the balances went negative.
- **Omitted Store Issues (Reconciliation Finding):**
  - In addition, the interim ledger completely ignored actual store issues recorded in sheet `4. Issue`:
    - `FDY-RM-008`: **11,793 kg** issued across 54 issue slips (omitted from ledger).
    - `FDY-RM-017`: **278.509 kg** issued across 97 slips (omitted from ledger).
    - `FDY-RM-020`: **50.218 kg** issued across 44 slips (omitted from ledger).
  - *Critical Clarification:* The 11,793 kg figure is a **reconciliation finding explaining why the interim ledger was incomplete**, NOT an instruction to post those issues again.
- **Evidence Reference:** Frozen artifact [`negative_stock_reconciliation.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/negative_stock_reconciliation.csv).

#### 3. Mathematical Reconciliation vs Physical Inventory Reality
- Mathematical proof establishes that the negative numbers were caused by a spreadsheet formula error.
- **It does NOT prove that physical stock was negative.** Physical scrap, pig iron, and alloys existed in the yard, but opening balances were never counted or entered.

#### 4. Available Options & Required Management Action
- **Mandatory Action:** Plant-Wide Physical Inventory Stocktake & Certified Opening Valuation Schedule as of Cutoff Date.
- Manufacturing opening balances or posting balancing adjustments is strictly prohibited.

#### 5. Governance & Accountable Authority
- **Accountable Authority:** Plant Head / Inventory Auditor / Finance Head.
- **Action Required:** Execute physical stocktake, investigate variances, and certify opening stock schedule.
- **Blocking Condition:** Blocks inventory ledger integrity (append-only ledger forbids negative balances).
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-006: Sample Template Dummy Rows in Material Entry

#### 1. Background & Read Me Rule
Workbook `VSPL_Material_Entry.xlsx`, Read Me line 8 explicitly states:
> *"Row 2 of each sheet is a sample entry — overwrite it or delete it before real use"*

#### 2. Verified Facts & Document Collisions
- **Affected Rows:**
  - `3. Receipt GRN` Row 2: Emery Paper 25 kg, GRN `2599`, Invoice `096`, PO `110726-02`.
  - `4. Issue` Row 2: Emery Paper 220 kg, Slip `132607`.
  - `5. Waste Disposition` Row 2: Emery Paper 5 kg, Disposal Note `WD-0001`.
- **Legacy Document Collisions:**
  - Legacy `Store Inventory.xlsx` reveals that GRN `2599` & Invoice `096` belong to *Cement empty (1000 nos)* from supplier `s.srinivas`.
  - PO `110726-02` belongs to MM Tools for *Grinding Wheel 7 Inch (25 nos)*.
  - The interim Master Ledger incorporated Received 25 kg and Waste 5 kg from these dummy rows.
- **Evidence Reference:** Frozen artifact [`grn_mapping_pricing_exceptions.csv`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/grn_mapping_pricing_exceptions.csv).

#### 3. Available Options & Trade-Offs
- **Option 1 (Purge Sample Rows from Staging - Recommended):** Formally mark Row 2 across GRN, Issue, and Waste sheets as `TEMPLATE_SAMPLE` and purge from the operational migration manifest. Reverse dummy quantities in interim figures.
- **Option 2 (Verify Physical Delivery):** If Stores asserts that Emery Paper was physically received and issued on those slips, obtain certified physical slips.

#### 4. Governance & Accountable Authority
- **Accountable Authority:** Stores Manager / Systems Architect.
- **Action Required:** Sign confirmation of dummy template status.
- **Blocking Condition:** Prevents artificial inventory additions and duplicate document collisions.
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-007: Furnace Heat Log Integrity & Mass Balance Deficit

#### 1. Background & Production Discrepancy
Workbook `VSPL_Foundry_Heat_Log.xlsx` captures induction furnace heats, charge details, and cast parts production.

#### 2. Verified Facts & Source Evidence
- **Heat Log:** Contains 19 logged heats on `2026-07-22` (`072613-2092` to `2110`).
  - **18 of the 19 heats record Total Charge = 0 kg**, yet report Metal Tapped between 504 and 524 kg, generating negative melt loss (-100% to -125%).
- **Charge Details:** Contains only 10 rows:
  - 7 rows belong to unlogged heat `H-260714-01`.
  - 1 row belongs to unlogged heat `L-260722-02`.
  - 1 row belongs to unlogged heat `H-200125-05` (null quantity).
  - Only 1 row belongs to a logged heat: `072613-2092` (4 kg charge vs 507 kg tapped).
- **Parts Produced:** Row 2 records 2016 kg of cast parts against 507 kg of tapped metal.
- **Evidence Reference:** Frozen artifact [`PHASE7_STAGE2_1_AUDIT_REPORT.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/PHASE7_STAGE2_1_AUDIT_REPORT.md).

#### 3. Operational & Costing Implications
- Incomplete charge records make Phase 5 issue-to-heat reconciliation impossible.
- Phase 6 heat costing cannot calculate melting cost per kg without charge weights.

#### 4. Available Options & Trade-Offs
- **Option 1 (Controlled Staging Quarantine - Recommended):** Ingest heat log records into staging preview only. Do not post furnace heats or charge lines into live production tables until complete physical heat log sheets are audited.
- **Option 2 (Complete Physical Log Audit):** Foundry Head retrieves physical paper heat logs for 22-Jul-2026 and provides true charge details before Phase 5 live activation.

#### 5. Governance & Accountable Authority
- **Accountable Authority:** Foundry Head / Metallurgist.
- **Action Required:** Retrieve physical furnace logs and authorize staging quarantine.
- **Blocking Condition:** Blocks Phase 5 issue-to-heat reconciliation and Phase 6 heat costing.
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-008: Legacy Store Inventory Records & Future Stored Dates

#### 1. Background & Spreadsheet Corruption
Workbook `Store Inventory.xlsx` represents pre-migration spreadsheets from early July 2026.

#### 2. Verified Facts & Source Evidence
- **Old Data Worksheet (585 rows):** Contains corrupt code mappings: raw code `Frm08` is assigned to 58 rows of 'Silicon' (Item Master Frm08 is CRC Scrap). 'Crc' rows are mapped to `FRM01` (Bial).
- **Material Receipt Worksheet (123 rows):**
  - **113 physical stock rows (rows 9 to 121)** contain the stored date `datetime(2026, 11, 7, 0, 0)` (`mm/dd/yyyy` format).
  - All 113 rows contain `Supplier Name = 'Physical stock'`. They represent **physical stock count entries**, not vendor purchase deliveries.
  - Magnesium (550 kg) and Manganese (20 kg) have physical stock entries with zero date and zero supplier.
- **The Date Conflict:**
  - Relative to the 12-Oct-2026 cutoff and 13-Oct-2026 audit date, `2026-11-07` is nearly **one month in the future**.
  - While it likely reflects an Indian date transposition (`11-Jul-2026` entered into US-formatted Excel), this remains an **unproven hypothesis**. The literal stored byte value is November 7, 2026.
- **Evidence Reference:** Frozen artifact [`DEC008_DATE_RECONCILIATION.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_management_review_consistency_audit/DEC008_DATE_RECONCILIATION.md).

#### 3. Available Options & Trade-Offs
- **Option 1 (Permanently Exclude Legacy Archive - Recommended):** Exclude `Store Inventory.xlsx` from operational data migration. Retain workbook strictly as immutable read-only audit evidence.
- **Option 2 (Selective Manual Extraction):** Manually audit individual physical stock rows (e.g. Magnesium 550 kg) to inform initial physical stocktake counts.

#### 4. Governance & Accountable Authority
- **Accountable Authority:** IT Head / Inventory Auditor / Plant Head.
- **Action Required:** Formally sign off on retiring legacy spreadsheets from operational migration.
- **Blocking Condition:** Prevents corrupting Item Master mappings and posting future-dated inventory receipts.
- **Current Status:** `PENDING_REVIEW`.
