# VSPL Material Management & Costing System — Migration Decision Register (Version 2)
**Audit Cycle:** Phase 7 Stage 2.1 Audit & Reconciliation  
**Date:** 2026-10-13  
**Status:** ALL DECISIONS PENDING FORMAL BUSINESS APPROVAL  

---

## Decision Index

| Decision ID | Title | Owning Dept | Approver | Current Status |
|---|---|---|---|---|
| **DEC-001** | Missing Commercial Ex-GST Purchase Rates on Historical Receipts | Finance / Purchase | Finance Head / Purchase Head | **PENDING_REVIEW** |
| **DEC-002** | Treatment of July 2026 Historical Data Relative to 12-Oct-2026 Costing Cutoff | Management / Cost Accounting | Managing Director / Plant Head | **PENDING_REVIEW** |
| **DEC-003** | Unmapped GRN Item Descriptions & Proposed Candidate Codes | Stores / Foundry / Machine Shop | Stores Manager / Plant Head | **PENDING_REVIEW** |
| **DEC-004** | Suspected Year Typo (`7-16-20236`) in Issue Records (Rows 537–548) | Stores / Inventory Control | Stores Manager | **PENDING_REVIEW** |
| **DEC-005** | Reconciliation of Seven Negative Closing Stock Balances | Foundry / Stores / Cost Accounting | Plant Head / Finance Head | **PENDING_REVIEW** |
| **DEC-006** | Sample Template Rows in Material Entry Sheets (Row 2) | Stores / QA | Stores Manager / Systems Architect | **PENDING_REVIEW** |
| **DEC-007** | Furnace Heat Log Integrity and Mass Balance Discrepancies | Foundry / Metallurgy | Foundry Head / Metallurgist | **PENDING_REVIEW** |
| **DEC-008** | Legacy Store Inventory Code Inconsistency and Future Dates (2026-11-07) | Stores / IT Auditor | Inventory Control Specialist / IT Head | **PENDING_REVIEW** |

---

### DEC-001: Missing Commercial Ex-GST Purchase Rates on Historical Receipts
- **Owning Department:** Finance / Purchase
- **Approval Authority:** Finance Head / Purchase Head
- **Original Problem Statement:** External GRN receipts cannot establish weighted-average inventory valuation or cost journals without commercial purchase rates.
- **Verified Source Facts:**
  - Workbook `VSPL_Material_Entry.xlsx`, worksheet `3. Receipt GRN`, contains 4 rows (rows 2 to 5).
  - There is no unit rate or price column in the worksheet. Readme states: *"Phase 1: quantities only (no prices)"*.
  - `VSPL_Item_Master.xlsx` contains 0 populated rates across all 391 items (`Rate (INR)` column is 100% empty).
  - Legacy `Store Inventory.xlsx` contains 0 populated rates in the `Stock Details` worksheet.
- **Outstanding Evidence:** Commercial rates cannot be fabricated or inferred from current market prices. Physical vendor invoices must be audited:
  - Row 2: Vendor MM Tools, Invoice 096, PO 110726-02.
  - Row 3: Vendor sreenathji, Invoice GMP2926002828, PO 300426-10.
  - Row 4: Invoice 454, PO 070726-11.
  - Row 5: Invoice 384, PO 140726-02.
- **Proposed Resolution:** Stage GRN receipts with status `DRAFT` and `rate_ex_gst = NULL`. Require Finance to verify and enter audited ex-GST invoice rates before any live ledger posting.
- **Migration & Ledger Impact:** BLOCKING for live inventory valuation and weighted-average costing (Phase 6).
- **History Log:**
  - *2026-10-13 (Stage 2 v1):* Created as PENDING_REVIEW.
  - *2026-10-13 (Stage 2.1 v2):* Confirmed 0/391 Item Master rates and 0 legacy rates. Preserved PENDING_REVIEW.

---

### DEC-002: Treatment of July 2026 Historical Data Relative to 12-Oct-2026 Costing Cutoff
- **Owning Department:** Management / Cost Accounting
- **Approval Authority:** Managing Director / Plant Head
- **Original Problem Statement:** Costing start date is configured as 12 October 2026 while historical source transactions span 08-Jul-2026 to 22-Jul-2026.
- **Verified Source Facts:**
  - All 558 Issue rows, 4 GRN rows, 6 Waste rows, and 19 Furnace Heats occur exclusively between 08-Jul-2026 and 22-Jul-2026.
  - An **82-day data void** exists between 23-Jul-2026 and 12-Oct-2026 with zero electronic transaction records.
  - Interim Master Ledger balance was last updated 15-Jul-2026.
- **Outstanding Evidence:** Unknown physical stock movements, receipts, issues, scrap generation, and consumption occurred across August and September 2026.
- **Proposed Resolution:** Evaluate three cutoff-policy scenarios (a, b, c) detailed in the Readiness Summary without unauthorized selection.
- **Migration & Ledger Impact:** BLOCKING for all live database posting. Dictates whether July transactions post to the append-only ledger or remain an archived audit trail.
- **History Log:**
  - *2026-10-13 (Stage 2 v1):* Created as PENDING_REVIEW.
  - *2026-10-13 (Stage 2.1 v2):* Formulated 82-day data void analysis and ledger invariant implications. Preserved PENDING_REVIEW.

---

### DEC-003: Unmapped GRN Item Descriptions & Proposed Candidate Codes
- **Owning Department:** Stores / Foundry / Machine Shop
- **Approval Authority:** Stores Manager / Plant Head
- **Original Problem Statement:** Three GRN receipts have Item Code `NOT FOUND`: `3306PMKT-Generator`, `Tool Post`, and `crca scrap` (15,200 kg).
- **Verified Source Facts:**
  - `3306PMKT-Generator`: Matches `2. New Items` row 5 proposing `MNT-CN-001` (Maintenance, Set).
  - `Tool Post`: Matches `2. New Items` row 6 proposing `MCS-CN-002` (Machine Shop, Nos).
  - Neither item exists in canonical `Item Master` (391 items).
  - `crca scrap`: Item Master contains both `FDY-RM-007` (CRC Scrap-Low High MN) and `FDY-RM-008` (CRC Scrap-Low MN).
- **Outstanding Evidence:**
  - `MNT-CN-001` and `MCS-CN-002` require Phase 2 Master Data approval before ledger posting.
  - `crca scrap` is **chemically AMBIGUOUS**. Carbon and Manganese metallurgical specifications from PO 140726-02 and vendor invoice 384 are required to determine whether it is Low MN or Low High MN.
- **Proposed Resolution:** Stores/Plant Head to formally approve creation of `MNT-CN-001` and `MCS-CN-002`. Metallurgist to classify `crca scrap`.
- **Migration & Ledger Impact:** HOLD on GRN rows 3, 4, 5. Prevents foreign key failures and incorrect chemical allocation.
- **History Log:**
  - *2026-10-13 (Stage 2 v1):* Proposed FDY-RM-008 for crca scrap.
  - *2026-10-13 (Stage 2.1 v2):* Downgraded crca scrap to AMBIGUOUS between 007 and 008. Preserved PENDING_REVIEW.

---

### DEC-004: Suspected Year Typo (`7-16-20236`) in Issue Records (Rows 537–548)
- **Owning Department:** Stores / Inventory Control
- **Approval Authority:** Stores Manager
- **Original Problem Statement:** Source worksheet `4. Issue` contains string `7-16-20236` in the Date column.
- **Verified Source Facts:**
  - Exactly **12 physical rows (rows 537 to 548)** contain the literal string `7-16-20236`.
  - Preceding rows 535-536 are dated 2026-07-15; subsequent row 549 is dated 2026-07-15.
  - Affected issue slips: 327 (rows 537-538), 910 (row 539), 325 (rows 540-542), 1149 (row 543), 326 (row 544), 2725 (rows 545-546), 1148 (rows 547-548).
  - Stage 1 report errantly cited rows 535-544 (10 rows).
  - Stage 2 generator marked 10 rows MANUAL_REVIEW and 2 rows UNMAPPED due to an evaluation-order defect.
- **Outstanding Evidence:** Physical store issue books for slips 325, 326, 327, 910, 1148, 1149, 2725 must be inspected to verify date of execution.
- **Proposed Resolution:** Stores Manager to provide written authorization that `7-16-20236` represents `2026-07-16`. Original source text retained in audit crosswalk.
- **Migration & Ledger Impact:** All 12 rows held from live ledger posting.
- **History Log:**
  - *2026-10-13 (Stage 2 v1):* Created covering 10 rows.
  - *2026-10-13 (Stage 2.1 v2):* Corrected scope to exactly 12 physical rows (537-548) and documented Stage 2 generator precedence bug. Preserved PENDING_REVIEW.

---

### DEC-005: Reconciliation of Seven Negative Closing Stock Balances
- **Owning Department:** Foundry / Stores / Cost Accounting
- **Approval Authority:** Plant Head / Finance Head
- **Original Problem Statement:** Interim Master Ledger displays negative closing stock balances for 7 raw materials: `FDY-RM-008` (-500), `FDY-RM-011` (-300), `FDY-RM-014` (-2), `FDY-RM-016` (-15), `FDY-RM-017` (-3), `FDY-RM-019` (-150), `FDY-RM-020` (-5).
- **Verified Source Facts:**
  - These 7 negative balances **identically equal the furnace charge quantities** of heat `H-260714-01` in worksheet `Charge Details`.
  - The interim ledger erroneously deducted furnace charges as store issues.
  - In addition, store issues in worksheet `4. Issue` total 11,793 kg for 008, 278.509 kg for 017, and 50.218 kg for 020, which were completely omitted from the interim ledger.
  - All 7 items had 0 opening stock in the interim ledger.
  - Legacy archive holds unposted physical stock for Inoculant 15 (92.5 kg), Magnesium (550 kg), Manganese (20 kg), and Silicon (26 kg), but 0 for Scrap, Gatings, and Pig Iron.
- **Outstanding Evidence:** Physical stock verification required. Legitimate opening inventory as of the chosen cutoff date has never been approved.
- **Proposed Resolution:** Enforce Phase 5 Rule H1 (furnace charges are NOT store issues). Require comprehensive physical stocktake. Require Plant Head approval for initial stock balances.
- **Migration & Ledger Impact:** BLOCKING for ledger integrity. Negative stock balances violate append-only ledger invariants.
- **History Log:**
  - *2026-10-13 (Stage 2 v1):* Created as PENDING_REVIEW.
  - *2026-10-13 (Stage 2.1 v2):* Full mathematical reconciliation identifying exact heat charge correlation, legacy receipt gaps, and unposted store issues. Preserved PENDING_REVIEW.

---

### DEC-006: Sample Template Rows in Material Entry Sheets (Row 2)
- **Owning Department:** Stores / QA
- **Approval Authority:** Stores Manager / Systems Architect
- **Original Problem Statement:** Worksheet Read Me explicitly notes that row 2 in each transaction sheet contains dummy sample data.
- **Verified Source Facts:**
  - Readme states: *"Row 2 of each sheet is a sample entry — overwrite it or delete it before real use"*.
  - Row 2 of `3. Receipt GRN` (Emery Paper 25 kg, GRN 2599, PO 110726-02), `4. Issue` (Emery Paper 220 kg, Slip 132607), and `5. Waste Disposition` (WD-0001 Emery Paper 5 kg) are documented template samples.
  - Legacy Store Inventory reveals that GRN 2599 & Invoice 096 belong to 'Cement empty' 1000 from s.srinivas, while PO 110726-02 belongs to MM Tools 'Grinding Wheel 7 Inch' 25.
  - Interim Master Ledger incorporated Received 25 and Waste 5 from these sample rows.
- **Outstanding Evidence:** Stores Manager confirmation whether Row 2 records represent real transactions or dummy test entries.
- **Proposed Resolution:** If confirmed as template samples, purge from operational migration manifest to prevent inventory distortion and document number collisions.
- **Migration & Ledger Impact:** Prevents false stock additions and duplicate GRN/slip errors.
- **History Log:**
  - *2026-10-13 (Stage 2.1 v2):* Raised by Stage 2.1 audit based on Read Me documentation and legacy document collision. PENDING_REVIEW.

---

### DEC-007: Furnace Heat Log Integrity and Mass Balance Discrepancies
- **Owning Department:** Foundry / Metallurgy
- **Approval Authority:** Foundry Head / Metallurgist
- **Original Problem Statement:** Furnace heat production logs contain severe internal mass balance contradictions.
- **Verified Source Facts:**
  - `Heat Log` contains 19 heats dated 2026-07-22 (`072613-2092` to `2110`).
  - 18 of the 19 heats record Total Charge = 0 kg, yet record Metal Tapped between 504 and 524 kg, generating negative melt loss (-100% to -125%).
  - `Charge Details` contains only 10 rows: 7 belong to unlogged heat `H-260714-01`, 1 to `L-260722-02`, 1 to `H-200125-05`, and only 1 to logged heat `072613-2092` (4 kg charged vs 507 kg tapped).
  - `Parts Produced` row 2 records 2016 kg of cast parts against 507 kg of tapped metal.
- **Outstanding Evidence:** Physical furnace heat log books and spectrometer chemical logs for 22-Jul-2026 must be audited to obtain true charge weights and tapping logs.
- **Proposed Resolution:** Do not post furnace heats or charge details to live production tables until charge balances reconcile. Retain in staging preview only.
- **Migration & Ledger Impact:** BLOCKING for Phase 5 heat reconciliation and Phase 6 heat costing.
- **History Log:**
  - *2026-10-13 (Stage 2.1 v2):* Raised by Stage 2.1 audit based on mass balance contradiction. PENDING_REVIEW.

---

### DEC-008: Legacy Store Inventory Code Inconsistency and Future Dates
- **Owning Department:** Stores / IT Auditor
- **Approval Authority:** Inventory Control Specialist / IT Head
- **Original Problem Statement:** Legacy archive `Store Inventory.xlsx` contains corrupt item code mappings and future receipt dates.
- **Verified Source Facts:**
  - Worksheet `Old data` contains 585 rows where raw code `Frm08` is assigned to 58 rows of 'Silicon' (Item Master Frm08 is CRC Scrap). 'Crc' rows are assigned to `FRM01` (Bial).
  - Worksheet `Material Receipt` contains 113 rows of physical stock receipts dated `2026-11-07` (future date relative to July 2026 operational records).
  - Two physical stock rows (Magnesium 550 kg and Manganese 20 kg) are completely undated.
- **Outstanding Evidence:** Origin of the 2026-11-07 date string (suspected mm/dd vs dd/mm transposition for 11-Jul-2026).
- **Proposed Resolution:** Exclude legacy sheets from operational migration manifest. Retain strictly as secondary informational evidence. Do not auto-map legacy transactions using raw legacy codes.
- **Migration & Ledger Impact:** Prevents ledger corruption and posting future-dated stock.
- **History Log:**
  - *2026-10-13 (Stage 2.1 v2):* Raised by Stage 2.1 audit based on code analysis and future date findings. PENDING_REVIEW.
