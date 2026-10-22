# VSPL Material Management & Costing System — Phase 7 Management Decision Pack

**Document ID:** `DOC-P7-MGMT-DECISION-PACK`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd. (SG Iron Foundry & Machine Shop, Peenya, Bangalore)  
**Governance Scope:** Executive & Operational Decision Briefs (DEC-001 through DEC-008)  
**Date:** 2026-10-13  
**Status:** **PENDING FORMAL MANAGEMENT REVIEW & SIGN-OFF — LIVE DATABASE MIGRATION (STAGE 3) IS STRICTLY UNAUTHORIZED**  

---

## 1. Executive Summary & Governance Notice

This document constitutes the formal management review package for executive and operational leaders of Vijay Spheroidals Pvt. Ltd. (VSPL). It provides decision briefs for eight critical data governance, costing, and inventory issues discovered during the Phase 7 historical audit.

### Critical Safety & Authority Warning:
> [!CAUTION]
> **PHASE 7 STAGE 3 (DATABASE IMPORT & LEDGER POSTING) IS STRICTLY UNAUTHORIZED.**  
> - **Zero Live Data Writes:** No historical transaction records have been imported into the application database.
> - **Append-Only Ledger Safety:** The live inventory ledger remains unaltered. No stock movements, opening balances, or artificial balancing journals have been posted.
> - **Separation of Concerns:** Business approval of any decision brief does **NOT** authorize live database writing. Technical deployment requires separate execution authorization, backup verification, and staging validation.

### Evidence Freeze Baseline:
The entire audit evidence chain has been frozen and verified byte-for-byte in:
- **Package Directory:** [`C:\VSPL_MM\VSPL_Phase7_Stage2_1_Evidence_Freeze_20261013\`](file:///C:/VSPL_MM/VSPL_Phase7_Stage2_1_Evidence_Freeze_20261013/)
- **ZIP Archive:** [`C:\VSPL_MM\VSPL_Phase7_Stage2_1_Evidence_Freeze_20261013.zip`](file:///C:/VSPL_MM/VSPL_Phase7_Stage2_1_Evidence_Freeze_20261013.zip)  
  *(Verified SHA-256 Digest: `033684d8b26dc65e9c67b569e48991b07c0d0909c2cc37717b5d3485d922c5c5`)*

---

## 2. Decision Briefs (DEC-001 through DEC-008)

---

### DEC-001: Missing Commercial Ex-GST Purchase Rates on Historical Receipts

#### 1. Context & Source References
- **Source Worksheet:** `VSPL_Material_Entry.xlsx`, Sheet `3. Receipt GRN`, physical rows 2 through 5.
- **Affected Records:**
  - Row 2: Date `2026-07-14`, GRN `2599`, Vendor `MM Tools`, Inv `096`, PO `110726-02`, Item `Emery Paper` (`FDY-CN-003`), Qty `25 Kg`.
  - Row 3: Date `2026-07-14`, GRN `2622`, Vendor `sreenathji`, Inv `GMP2926002828`, PO `300426-10`, Item `3306PMKT-Generator`, Qty `1` (no UOM).
  - Row 4: Undated, GRN `None`, Vendor `None`, Inv `454`, PO `070726-11`, Item `Tool Post`, Qty `4` (no UOM).
  - Row 5: Undated, GRN `None`, Vendor `None`, Inv `384`, PO `140726-02`, Item `crca scrap`, Qty `15200 kg`.

#### 2. Verified Evidence of Rate Unavailability
- The source worksheet `3. Receipt GRN` **contains no unit price, rate, or amount column** by design. The workbook Read Me explicitly states: *"Phase 1: quantities only (no prices)"*.
- Canonical `Item Master` (`VSPL_Item_Master.xlsx`) contains **0 populated rates across all 391 items** (`Rate (INR)` column is 100% empty).
- Legacy archive `Store Inventory.xlsx` contains **0 populated purchase rates** across all sheets.

#### 3. Financial & Costing Implications
- **Phase 6 Costing Rule C1:** Inward receipts require an approved commercial rate excluding GST to establish the weighted-average inventory valuation pool.
- Without purchase rates, the costing engine cannot compute weighted-average rates for consumed materials or determine melting cost per kg for furnace heats.
- Material issues consumed against these receipts would either inherit zero valuation or cause costing pipeline failures.

#### 4. Required Evidence from Finance / Purchase
- Original commercial tax invoices and Purchase Orders matching the document numbers:
  - PO `110726-02` / Invoice `096` from MM Tools.
  - PO `300426-10` / Invoice `GMP2926002828` from sreenathji.
  - PO `070726-11` / Invoice `454`.
  - PO `140726-02` / Invoice `384` for 15,200 kg scrap.
- Approved commercial rate per unit excluding GST for each line item.

#### 5. Proposed Dispositions & Options
- **Option 1 (Audit & Rate Entry - Recommended if Invoices Found):** Purchase/Finance audits physical files, verifies ex-GST unit rates, and enters rates into draft GRN staging tables.
- **Option 2 (Quarantine / Archive Only):** If original invoices cannot be located, retain records as uncosted physical audit history without posting to live valuation ledgers.
- **Option 3 (Independent Valuation Appraisal):** Finance Head approves a certified benchmark valuation rate based on contemporaneous market records. *(Prohibited without written Finance Head justification).*

#### 6. Governance & Approval
- **Accountable Approver:** Finance Head / Purchase Head.
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-002: Historical Data and the 12 October 2026 Costing Cutoff

#### 1. Context & The Calendar Void
- The application configuration mandates: `COSTING_START_DATE = date(2026, 10, 12)`.
- All electronic historical transaction records (558 Issues, 4 GRNs, 6 Waste, 19 Heats) span **08-Jul-2026 to 22-Jul-2026**.
- **The 82-Day Void:** Exactly **82 calendar days** elapse between the last recorded transaction (22-Jul-2026) and the live costing start date (12-Oct-2026). Zero electronic transaction records exist for August or September 2026.
- **The 89-Day Interval:** Exactly **89 calendar days** elapse between the interim Master Ledger balance date (15-Jul-2026) and the 12-Oct-2026 cutoff.

#### 2. Comparison of Cutoff Scenarios (Objective Presentation)
- **Scenario A: Historical Audit Archive (No Live Ledger Movement Posting)**
  - *Mechanism:* July 2026 records are ingested into dedicated read-only historical archive tables for traceability and reporting. Live ledger posting commences strictly on 12-Oct-2026 using an independently verified physical stocktake as Opening Balance.
  - *Traceability:* Full inquiry capability for July transactions; zero historical cost recalculation.
  - *Risk:* Zero risk of negative inventory or ledger invariant violations.
  - *Effort:* Low technical complexity; requires thorough physical stocktake on 12-Oct-2026.
- **Scenario B: Reconstructed Opening Position (Full Movement Roll-Forward)**
  - *Mechanism:* Post July records to the ledger, then reconstruct and post all intervening movements across August and September forward to 12-Oct-2026.
  - *Traceability:* End-to-end continuous transaction history.
  - *Risk:* **CRITICAL / EXTREME RISK.** Current electronic files contain zero records for August/September. Reconstructing an 82-day period without primary electronic records introduces severe inventory divergence.
  - *Effort:* Very high; requires auditing thousands of physical paper slips across August and September.
- **Scenario C: Two-Phase Transition (Staged Simulation with Adjustment)**
  - *Mechanism:* Simulate July transactions in a staging sandbox to establish preliminary July closing balances. Post a formal reconciliation adjustment entry on 12-Oct-2026 absorbing the variance against the October physical stocktake.
  - *Traceability:* Reconstructs July operational performance; isolates variance.
  - *Risk:* Moderate to high; variance between July and October must be expensed as an unclassified inventory adjustment, potentially distorting period consumption.
  - *Effort:* Moderate; requires sandbox ledger execution and variance reconciliation.

#### 3. Required Management Decisions
- Management must formally select **Scenario A, B, or C**.
- Management must mandate how opening physical inventory as of 12-Oct-2026 will be established and certified.

#### 4. Governance & Approval
- **Accountable Approver:** Managing Director / Plant Head / Finance Head.
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-003: Unmapped GRN Items and Ambiguous Scrap Grade

#### 1. Context & Unmapped Items
Workbook `VSPL_Material_Entry.xlsx`, Sheet `3. Receipt GRN`, records Item Code `NOT FOUND` for three items:
1. **Row 3 (`3306PMKT-Generator`, Qty 1):** Description matches `2. New Items` row 5 proposing code `MNT-CN-001` (Maintenance, Set).
2. **Row 4 (`Tool Post`, Qty 4):** Description matches `2. New Items` row 6 proposing code `MCS-CN-002` (Machine Shop, Nos).
3. **Row 5 (`crca scrap`, Qty 15,200 kg):** Vendor Invoice `384`, PO `140726-02`.

#### 2. The Ambiguous Scrap Grade Problem
- Stage 2 tentatively suggested mapping `crca scrap` to `FDY-RM-008` (CRC Scrap-Low MN).
- **Audit Fact:** Canonical `Item Master` contains two distinct CRC scrap items:
  - `FDY-RM-007`: *CRC Scrap-Low High MN* (Legacy `FRM07`)
  - `FDY-RM-008`: *CRC Scrap-Low MN* (Legacy `FRM08`)
- The Heat Log Read Me equates CRCA loosely to "steel scrap".
- Without chemical analysis (Carbon/Manganese percentages) from PO `140726-02`, auto-mapping to 008 is an unverified metallurgical assumption.

#### 3. Master Data Prerequisites & Approvals
- Formal creation of `MNT-CN-001` and `MCS-CN-002` in Item Master requires Phase 2 approval workflow (Plant Head sign-off).
- Scrap classification requires Metallurgist / Foundry Head review of vendor chemical certificates.

#### 4. Proposed Dispositions & Options
- **Option 1 (Approve Candidate Codes):** Plant Head approves creation of `MNT-CN-001` and `MCS-CN-002`. Metallurgist inspects PO 140726-02 and designates either `FDY-RM-007` or `FDY-RM-008`.
- **Option 2 (Quarantine / Hold):** Keep rows 3, 4, 5 in draft staging until master data is created and chemical grade is certified.

#### 5. Governance & Approval
- **Accountable Approver:** Stores Manager / Plant Head (Item Master) + Metallurgist (Chemical Grade).
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-004: Malformed Issue Dates (`7-16-20236`)

#### 1. Context & Scope
- **Source Location:** `VSPL_Material_Entry.xlsx`, Sheet `4. Issue`, Column A (`Date`).
- **Physical Rows:** Exactly **12 physical rows (rows 537 through 548)** contain the literal text string `7-16-20236`.
- **Associated Issue Slips:** Slip 327 (rows 537-538), Slip 910 (row 539), Slip 325 (rows 540-542), Slip 1149 (row 543), Slip 326 (row 544), Slip 2725 (rows 545-546), Slip 1148 (rows 547-548).

#### 2. Supporting Evidence for `2026-07-16`
- Preceding rows 535 and 536 are dated `2026-07-15`.
- Subsequent row 549 is dated `2026-07-15` (Slips 328, 329).
- The numerical sequence of physical issue book slips indicates transactions executed on 16-Jul-2026.

#### 3. Audit & System Integrity Rules
- The source spreadsheet **must not be edited** or silently altered.
- Under Phase 3 and Phase 4 ledger posting rules, posting an issue with year 20236 would violate ledger date sequencing and period closing controls.

#### 4. Proposed Dispositions & Options
- **Option 1 (Authorized Normalization):** Stores Manager inspects physical issue slip books, signs written confirmation that `7-16-20236` represents `2026-07-16`. The migration staging pipeline applies `2026-07-16` while recording the original string in the audit log.
- **Option 2 (Quarantine):** If physical slips cannot be confirmed, exclude rows 537–548 from operational migration and hold in exception review.

#### 5. Governance & Approval
- **Accountable Approver:** Stores Manager.
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-005: Seven Negative Closing Stock Balances

#### 1. Context & Verified Mathematical Mechanism
Workbook `VSPL_Master_Ledger.xlsx` displays negative closing balances for seven raw materials:
- `FDY-RM-008` (CRC Scrap-Low MN): **-500 kg**
- `FDY-RM-011` (Gattings-500): **-300 kg**
- `FDY-RM-014` (Inoculant 15): **-2 kg**
- `FDY-RM-016` (Magnesium): **-15 kg**
- `FDY-RM-017` (Manganese): **-3 kg**
- `FDY-RM-019` (Pig Iron): **-150 kg**
- `FDY-RM-020` (Silicon): **-5 kg**

**The Mathematical Mechanism:**
These seven figures **identically match the charged quantities** of furnace heat `H-260714-01` in worksheet `Charge Details`. The interim master ledger subtracted furnace charge quantities directly as store issues, violating **Phase 5 Rule H1**.

#### 2. Massive Omission of Store Issues
In addition to the computational flaw above, the interim ledger completely ignored actual store issues recorded in sheet `4. Issue`:
- `FDY-RM-008`: **11,793 kg** issued across 54 issue slips (omitted from ledger).
- `FDY-RM-017`: **278.509 kg** issued across 97 slips (omitted from ledger).
- `FDY-RM-020`: **50.218 kg** issued across 44 slips (omitted from ledger).

#### 3. Mathematical Reconciliation vs Physical Reality
- **Mathematical proof** establishes why the spreadsheet showed negative numbers (charging furnace consumption without opening stock).
- **Physical reality** remains unverified: physical scrap, pig iron, and alloys existed in the yard, but were never counted or entered into electronic opening stock.

#### 4. Required Management Action
- Do not manufacture opening balances or post artificial balancing entries.
- Conduct a formal plant-wide physical inventory count to establish verified physical opening quantities and valuation.

#### 5. Governance & Approval
- **Accountable Approver:** Plant Head / Inventory Control Auditor / Finance Head.
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-006: Sample Template Rows in Material Entry Sheets

#### 1. Context & Read Me Rule
- Worksheet Read Me line 8 explicitly states: *"Row 2 of each sheet is a sample entry — overwrite it or delete it before real use"*.
- **Affected Rows:**
  - `3. Receipt GRN` Row 2: Emery Paper 25 kg, GRN 2599, Invoice 096, PO 110726-02.
  - `4. Issue` Row 2: Emery Paper 220 kg, Slip 132607.
  - `5. Waste Disposition` Row 2: Emery Paper 5 kg, Disposal Note WD-0001.

#### 2. Document Number Collisions with Legacy Files
- Legacy `Store Inventory.xlsx` reveals that GRN `2599` & Invoice `096` belong to *Cement empty (1000 nos)* from supplier `s.srinivas`.
- PO `110726-02` belongs to MM Tools for *Grinding Wheel 7 Inch (25 nos)*.
- The interim Master Ledger incorporated Received 25 kg and Waste 5 kg from these dummy rows.

#### 3. Proposed Dispositions & Options
- **Option 1 (Exclude Template Rows - Recommended):** Formally mark Row 2 across GRN, Issue, and Waste sheets as `TEMPLATE_SAMPLE` and purge from the operational migration manifest. Reverse dummy quantities in interim figures.
- **Option 2 (Verify Physical Delivery):** If Stores asserts that Emery Paper was physically received and issued on those slips, obtain certified physical slips.

#### 4. Governance & Approval
- **Accountable Approver:** Stores Manager / Systems Architect.
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-007: Furnace Heat Log Integrity & Mass Balance Discrepancies

#### 1. Context & Mass Balance Deficit
Workbook `VSPL_Foundry_Heat_Log.xlsx` contains 19 logged heats on `2026-07-22` (`072613-2092` to `2110`):
- **18 of the 19 heats record Total Charge = 0 kg**, yet report Metal Tapped between 504 and 524 kg, generating negative melt loss (-100% to -125%).
- `Charge Details` contains only 10 rows: 7 belong to unlogged heat `H-260714-01`, 1 to `L-260722-02`, 1 to `H-200125-05`, and only 1 to logged heat `072613-2092` (4 kg charge vs 507 kg tapped).
- `Parts Produced` Row 2 records 2016 kg of cast parts against 507 kg of tapped metal.

#### 2. Technical & Costing Impact
- Phase 5 reconciliation cannot balance furnace charges against store issues when 99% of furnace charges are missing from electronic sheets.
- Phase 6 heat costing cannot calculate melting cost per kg or part cost without raw material charge weights.

#### 3. Proposed Dispositions & Options
- **Option 1 (Quarantine Production Records - Recommended):** Ingest heat log records into staging preview only. Do not post furnace heats or charge lines into live production tables until complete physical heat log sheets are audited.
- **Option 2 (Complete Physical Log Audit):** Foundry Head retrieves physical paper heat logs for 22-Jul-2026 and provides true charge details before Phase 5 live activation.

#### 4. Governance & Approval
- **Accountable Approver:** Foundry Head / Metallurgist.
- **Current Status:** `PENDING_REVIEW`.

---

### DEC-008: Legacy Store Inventory Archive Integrity

#### 1. Context & Corruption in Legacy Files
Workbook `Store Inventory.xlsx` represents pre-migration spreadsheets from early July 2026:
- Worksheet `Old data` (585 rows) contains corrupt code mappings: raw code `Frm08` is assigned to 58 rows of 'Silicon' (Item Master Frm08 is CRC Scrap). 'Crc' rows are mapped to `FRM01` (Bial).
- Worksheet `Material Receipt` contains 113 physical stock rows dated `2026-11-07` (future date relative to July 2026 operational records, likely a mm/dd transposition of 11-Jul-2026).
- Magnesium (550 kg) and Manganese (20 kg) have physical stock entries with zero date and zero supplier.

#### 2. Preservation vs Migration Separation
- Legacy spreadsheets are vital historical evidence for physical stock context.
- However, attempting to automatically ingest legacy transaction rows into the live system would inject corrupt item codes and future transaction dates.

#### 3. Proposed Dispositions & Options
- **Option 1 (Exclude from Live Migration - Recommended):** Permanently exclude `Store Inventory.xlsx` from operational data migration. Retain workbook strictly as immutable read-only audit evidence.
- **Option 2 (Manual Selective Mapping):** Manually audit individual physical stock rows (e.g. Magnesium 550 kg) to inform initial physical stocktake counts.

#### 4. Governance & Approval
- **Accountable Approver:** Inventory Control Specialist / IT Head / Plant Head.
- **Current Status:** `PENDING_REVIEW`.

---

## 3. Consolidated Management Approval Checklist

This checklist must be formally completed and signed by designated corporate authorities before any technical execution authorization is granted:

```
====================================================================================================
                        VSPL MANAGEMENT DECISION SIGN-OFF REGISTER
====================================================================================================

[ ] DEC-001: Commercial GRN Purchase Rates
    Selected Option: [  ] Option 1 (Audit Invoices)  [  ] Option 2 (Archive Only)  [  ] Option 3 (Appraisal)
    Finance Head Approval: ___________________________    Date: ______________
    Purchase Head Approval: __________________________    Date: ______________

[ ] DEC-002: Historical Cutoff Policy (12-Oct-2026)
    Selected Option: [  ] Scenario A (Archive Only)  [  ] Scenario B (Roll-Forward) [  ] Scenario C (Sandbox Adj)
    Managing Director Approval: ______________________    Date: ______________
    Plant Head Approval: _____________________________    Date: ______________
    Finance Head Approval: ___________________________    Date: ______________

[ ] DEC-003: Unmapped GRN Items & Scrap Grade
    Selected Option: [  ] Option 1 (Approve Codes)   [  ] Option 2 (Quarantine Draft)
    Plant Head Approval (Item Master): _______________    Date: ______________
    Metallurgist Approval (Scrap Grade): _____________    Date: ______________

[ ] DEC-004: Issue Date Typo Normalization (7-16-20236 -> 2026-07-16)
    Selected Option: [  ] Option 1 (Normalize)       [  ] Option 2 (Quarantine)
    Stores Manager Approval: _________________________    Date: ______________

[ ] DEC-005: Resolution of Seven Negative Stock Balances
    Selected Action: Mandatory Physical Inventory Stocktake & Opening Valuation
    Plant Head Approval: _____________________________    Date: ______________
    Inventory Auditor Approval: ______________________    Date: ______________
    Finance Head Approval: ___________________________    Date: ______________

[ ] DEC-006: Sample Template Rows Treatment (Row 2 Purge)
    Selected Option: [  ] Option 1 (Purge Samples)   [  ] Option 2 (Verify Real)
    Stores Manager Approval: _________________________    Date: ______________
    Systems Architect Approval: ______________________    Date: ______________

[ ] DEC-007: Furnace Heat Log Mass Balance Quarantine
    Selected Option: [  ] Option 1 (Quarantine Heats) [  ] Option 2 (Audit Physical Logs)
    Foundry Head Approval: ___________________________    Date: ______________
    Metallurgist Approval: ___________________________    Date: ______________

[ ] DEC-008: Legacy Store Inventory Archive Retirement
    Selected Option: [  ] Option 1 (Exclude Archive)  [  ] Option 2 (Selective Audit)
    IT Head Approval: ________________________________    Date: ______________
    Plant Head Approval: _____________________________    Date: ______________

====================================================================================================
```
