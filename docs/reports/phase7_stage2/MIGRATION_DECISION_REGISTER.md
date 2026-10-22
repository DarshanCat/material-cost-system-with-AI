# VSPL Material Management & Costing System — Historical Migration Decision Register

**Status:** OFFICIAL MIGRATION GOVERNANCE ARTIFACT (STAGE 2)
**Generated:** 2026-10-10T11:53:06.523578+00:00

This register governs the five critical blockers identified during Phase 7 Stage 1. Under hard safety requirements, **no pending decision may be treated as approved**.

---

### DEC-001: Missing Commercial Ex-GST Rates on Historical Receipts
- **Workbook & Sheet:** `VSPL_Material_Entry.xlsx` $\rightarrow$ `3. Receipt GRN` (Rows 2 to 5)
- **Original Source Value:** `No rate_ex_gst or unit rate column exists in sheet`
- **Problem Nature:** External GRN receipts cannot establish weighted-average inventory valuation or cost journals without commercial purchase rates.
- **Proposed Resolution:** Stage GRN receipts with status 'DRAFT' and rate_ex_gst=NULL. Require Purchase/Finance to approve commercial rates via Purchase Order or Vendor Invoice audit before posting to live ledger.
- **Required Approver:** `Finance Head / Purchase Head`
- **Decision Status:** `PENDING_REVIEW`
- **Evidence / Reference:** Rule C1 (ex-GST receipt rate mandatory for weighted-average cost calculation); VSPL_Material_Entry.xlsx sheet '3. Receipt GRN'
- **Quantity Impact:** None (quantities can be staged and tracked in physical units).
- **Costing Impact:** BLOCKING: Costing engine cannot compute weighted-average rates or inventory value for receipted items.
- **Blocks Migration:** **YES (for live costing); NO (for staging preview only)**

---

### DEC-002: Treatment of July 2026 Transactions Relative to 12-Oct-2026 Cutoff
- **Workbook & Sheet:** `VSPL_Material_Entry.xlsx, Store Inventory.xlsx, VSPL_Foundry_Heat_Log.xlsx` $\rightarrow$ `4. Issue, Old data, Material Receipt, Heat Log` (All transaction rows spanning 2026-07-08 to 2026-07-22)
- **Original Source Value:** `Dates in range 2026-07-08 to 2026-07-22`
- **Problem Nature:** All historical source spreadsheets date from July 2026, whereas settings.COSTING_START_DATE is strictly 12 October 2026 (~3 months gap).
- **Proposed Resolution:** Designate July 2026 records as 'Historical Audit Archive'. Net closing stock as of July 2026 must be audited and rolled forward to form the authoritative 'Opening Stock' baseline on 12-Oct-2026.
- **Required Approver:** `Managing Director / Systems Architect`
- **Decision Status:** `PENDING_REVIEW`
- **Evidence / Reference:** settings.COSTING_START_DATE = '2026-10-12'; Rule C3 (strict cutoff date governance)
- **Quantity Impact:** Determines whether opening stock on 12-Oct-2026 is derived from July roll-forward or a new physical count.
- **Costing Impact:** BLOCKING: Without roll-forward or October physical audit, opening balances lack verified quantities and valuation.
- **Blocks Migration:** **YES**

---

### DEC-003: Unmatched Item Descriptions in GRN Receipts
- **Workbook & Sheet:** `VSPL_Material_Entry.xlsx` $\rightarrow$ `3. Receipt GRN` (Rows 3, 4, 5)
- **Original Source Value:** `Item Code = 'NOT FOUND' for '3306PMKT-Generator' (Row 3), 'Tool Post' (Row 4), 'crca scrap' (Row 5)`
- **Problem Nature:** Receipt lines carry 'NOT FOUND' as Item Code and do not match canonical items in VSPL_Item_Master.xlsx.
- **Proposed Resolution:** Approve new item codes from '2. New Items' sheet: map '3306PMKT-Generator' -> 'MNT-CN-001', 'Tool Post' -> 'MCS-CN-002', and map 'crca scrap' (15,200 kg) -> 'FDY-RM-008' (CRC Scrap-Low MN).
- **Required Approver:** `Stores Manager / Plant Head`
- **Decision Status:** `PENDING_REVIEW`
- **Evidence / Reference:** VSPL_Material_Entry.xlsx sheet '2. New Items' defines MNT-CN-001 and MCS-CN-002; FDY-RM-008 is canonical CRCA scrap
- **Quantity Impact:** Directly impacts stock ledger for Maintenance, Machine Shop, and Foundry raw materials (15,200 kg scrap).
- **Costing Impact:** HIGH: 15,200 kg CRCA scrap receipt would dramatically impact weighted-average melt rate.
- **Blocks Migration:** **YES (until item codes are formally approved)**

---

### DEC-004: Corrupted Date Typo '7-16-20236' in Issue Slips
- **Workbook & Sheet:** `VSPL_Material_Entry.xlsx` $\rightarrow$ `4. Issue` (Rows 537 to 548 (12 rows))
- **Original Source Value:** `Date = '7-16-20236'`
- **Problem Nature:** Year 20236 is a human typographical error for 2026-07-16 occurring on slips 325, 326, 327, 910, 1148, 1149, 2725.
- **Proposed Resolution:** Approve transformation rule: Parse string '7-16-20236' as date '2026-07-16'. Preserve original string in audit remarks.
- **Required Approver:** `Stores Supervisor / QA Lead`
- **Decision Status:** `PENDING_REVIEW`
- **Evidence / Reference:** Sequential context: row 536 is 2026-07-15, row 549 is 2026-07-15; slips match July 2026 serial numbers
- **Quantity Impact:** Enables 12 issue transactions (slips for paint, rope, grinding wheels, belts) to be dated and sequenced correctly.
- **Costing Impact:** LOW (consumables and packing; does not affect furnace melt rate directly).
- **Blocks Migration:** **NO (if approved prior to migration)**

---

### DEC-005: Negative Closing Stock Balances in Interim Master Ledger
- **Workbook & Sheet:** `VSPL_Master_Ledger.xlsx & VSPL_Foundry_Heat_Log.xlsx` $\rightarrow$ `Ledger & Charge Details` (Ledger rows 9, 12, 15, 17, 18, 20, 21 (FDY-RM-008, 011, 014, 016, 017, 019, 020))
- **Original Source Value:** `Closing stock: -500 kg, -300 kg, -2 kg, -15 kg, -3 kg, -150 kg, -5 kg`
- **Problem Nature:** Interim Master Ledger logged furnace heat issue quantities (from Heat H-260714-01) starting from zero opening stock without prior receipt, causing negative closing inventory.
- **Proposed Resolution:** Stock ledger rule enforcement: Do not post furnace charge lines as independent issues (Rule H1 / Rule C5). Establish verified opening balances from legacy 'Stock Details' (FRM14: 92.5 kg, FRM16: 550 kg, FRM17: 20 kg, FRM20: 26 kg) and record external GRN for CRCA scrap (15,200 kg) to maintain strictly positive stock.
- **Required Approver:** `Plant Head / Senior Inventory Auditor`
- **Decision Status:** `PENDING_REVIEW`
- **Evidence / Reference:** VSPL_Foundry_Heat_Log.xlsx sheet 'Charge Details' Heat H-260714-01 exactly matches the 7 negative ledger quantities!
- **Quantity Impact:** CRITICAL: Resolves false negative stock balances across all 7 foundry raw materials.
- **Costing Impact:** CRITICAL: Negative stock suspends costing under Rule C4. Establishing positive baseline allows continuous rate calculation.
- **Blocks Migration:** **YES (negative stock must be resolved before write-enabled ledger posting)**

---

