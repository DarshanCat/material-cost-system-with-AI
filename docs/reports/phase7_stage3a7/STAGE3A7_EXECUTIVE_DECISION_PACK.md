# VSPL Material Management & Costing System — Executive Decision Pack (DEC-001 to DEC-008)

**Document ID:** `DOC-P7-S3A7-EXEC-PACK`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd., Peenya Industrial Area, Bangalore  
**Target Executive Decision-Makers:** Managing Director, Plant Head, Finance Head  
**Operational Scope:** Comprehensive Executive Determination Dossier for All 8 Phase 7 Decisions  
**Governance Status:** **PENDING_REVIEW — BLANK DECISION DOSSIER FOR EXECUTIVE DETERMINATION**  
**Execution Authority:** **READ-ONLY BRIEFING — ZERO OPERATIONAL MUTATIONS — STAGE 3B STRICTLY UNAUTHORIZED**  

---

## 1. Executive Purpose & Instructions

This document provides the executive leadership of Vijay Spheroidals Pvt. Ltd. (VSPL)—specifically the **Managing Director** and **Plant Head**—with an actionable, evidence-backed decision dossier covering all eight open Phase 7 migration decisions (`DEC-001` through `DEC-008`).

### How Management Should Use This Pack:
1. **Deliberate on Options:** Review the verified facts, documented alternatives, and cross-functional consequences for each decision card.
2. **Execute Formal Determinations:** For each decision card, mark the selected policy choice in the accompanying decision record template ([`EXECUTIVE_DECISION_RECORD_TEMPLATES.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a7/EXECUTIVE_DECISION_RECORD_TEMPLATES.md)).
3. **Affix Physical Signatures:** Affix physical or verified cryptographic signatures to the designated signature lines. Do not alter existing source workbooks or ledger entries.
4. **Mandatory Audit Notice:** Approval fields in this dossier are intentionally left blank. No decision is considered approved until signed physical or digital documentary evidence is filed in the project audit repository.

---

## 2. Decision Card DEC-001: Missing Historical GRN Commercial Rates

### 2.1 The Question Requiring Decision
> **Executive Question:** How shall VSPL establish ex-GST base purchase valuations for historical Goods Receipt Note (GRN) items recorded in `VSPL_Material_Entry.xlsx` and populate Item Master default valuation rates to enable Phase 6 Rule C1 moving-average costing?

### 2.2 Verified Facts & Source References
- `VSPL_Material_Entry.xlsx` sheet `'3. Receipt GRN'` contains four operational receipt rows (rows 2–5):
  - Row 2: `FDY-CN-003` (Emery Paper, 25 nos) — *Template sample row per Read Me*.
  - Row 3: `3306PMKT-Generator` (1 Set).
  - Row 4: `Tool Post` (1 Nos).
  - Row 5: `crca scrap` (15,200 kg).
- None of these four receipt rows contain unit price, rate per UOM, or GST breakdown columns.
- `VSPL_Item_Master.xlsx` sheet `'Item Master'` Column K (`Default Rate`) is unpopulated (`None`) across all 391 canonical items.
- In `backend/app/services/decimal_validator.py` (lines 111–115) and `backend/app/services/grn_service.py` (line 102), external raw material receipts with missing or zero rates are strictly rejected with `HTTP_422_UNPROCESSABLE_ENTITY`.
- In `backend/app/services/costing_service.py` (lines 191–197), unrated receipts cannot blend into moving weighted-average rates, setting `valuation_status = INSUFFICIENT_COST_DATA`.

### 2.3 Documented Choices Available to Management
- **Choice A (Recommended):** Mandate that the Finance Department retrieve original supplier tax invoices from accounts archives for GRN rows 3–5, extract verified net ex-GST purchase rates, and compile an approved commercial rate schedule (`commercial_rates_staging.csv`).
- **Choice B:** Finance Head and Plant Head convene a formal valuation committee to establish a certified Fair Market Valuation (FMV) schedule for unrated items under written executive waiver.
- **Choice C (Rejected by Audit):** Ingest GRN items at zero rate ($\text{Rate} = 0.00$). *Audit Consequence:* Rule C1 collapses unit rates to zero; finished casting cost rollups and balance sheet inventory values are corrupted.

### 2.4 Cross-Functional Implications
- **Inventory Quantity:** Zero impact (quantities are physically documented: 1 Set, 1 Nos, 15,200 kg).
- **Financial & Costing:** Critical. Ex-GST rates form the baseline for inventory asset value on the balance sheet and liquid metal melt costing.
- **Audit Defensibility:** Invoices are legally required to claim GST Input Tax Credit (ITC) and satisfy statutory tax and cost audit standards.

### 2.5 Required Evidence & Accountable Authority
- **Required Evidence:** Original vendor tax invoices, purchase orders, delivery challans, and signed `commercial_rates_staging.csv`.
- **Accountable Decision-Maker:** **Finance Head** (Countersigned by **Managing Director**).

### 2.6 Decision Record Fields (To be executed in Template)
- **Selected Choice:** `[ ] Choice A` | `[ ] Choice B`
- **Approver:** Finance Head & Managing Director
- **Signature & Date:** _____________________________ | Date: ______________
- **Evidence Reference:** Physical Accounts Invoice File Ref: ______________________

---

## 3. Decision Card DEC-002: Cutoff Policy & 82-Day Operational Void

### 3.1 The Question Requiring Decision
> **Executive Question:** What legal and audit policy shall govern the 82-day operational void between 22 July 2026 (source spreadsheet cutoff) and 12 October 2026 (target costing go-live), and what establishes authoritative opening inventory?

### 3.2 Verified Facts & Source References
- Primary digital logging terminates on **22-Jul-2026** (`VSPL_Material_Entry.xlsx` cell `A601`; `VSPL_Foundry_Heat_Log.xlsx` row 20).
- ERP costing go-live target is **12-Oct-2026** (`backend/app/core/config.py` defines `COSTING_START_DATE = "2026-10-12"`).
- Exactly **82 calendar days** elapsed during which shop-floor melt operations, raw material consumption, and store issues occurred without electronic tracking.
- Interim ledger `VSPL_Master_Ledger.xlsx` subtracted furnace charges for heat `H-260714-01` directly from zero opening stock, creating 7 negative balances (-500 to -2 kg) and omitting 11,793 kg of store scrap issues.

### 3.3 Documented Choices Available to Management
- **Scenario A (Recommended by Implementation & Audit):** Classify all records prior to 23-Jul-2026 as a **Historical Audit Archive**. Do not attempt retrospective ledger reconstruction of the 82-day void. Mandate that an independent double-blind physical stocktake as of 12-Oct-2026 cutoff establishes live opening inventory balances.
- **Scenario B:** Undertake a full retrospective manual reconstruction of all physical paper slips across the 82-day void (estimated 6–8 week delay, substantial audit cost, high risk of missing dockets).
- **Scenario C (Strictly Prohibited by Audit):** Carry July 2026 spreadsheet balances forward directly into October without physical counts (Guarantees immediate statutory audit rejection; injects 7 negative balances and false stockouts).

### 3.4 Cross-Functional Implications
- **Operational:** Scenario A allows clean ERP cutover without stopping plant production for historical paper reconstruction.
- **Financial:** Historical discrepancies are isolated to the legacy archive; opening balances are clean and defensible.
- **Audit Defensibility:** Highest possible audit rating; satisfies Ind AS 2 requirements for physical inventory verification.

### 3.5 Required Evidence & Accountable Authority
- **Required Evidence:** Signed Executive Policy Memorandum adopting Scenario A; certified Sheet D of `VSPL_Physical_Stocktake_Register.xlsx`.
- **Accountable Decision-Maker:** **Managing Director** and **Plant Head**.

### 3.6 Decision Record Fields (To be executed in Template)
- **Selected Choice:** `[ ] Scenario A` | `[ ] Scenario B`
- **Approver:** Managing Director & Plant Head
- **Signature & Date:** _____________________________ | Date: ______________
- **Evidence Reference:** Executive Board Resolution Ref: ______________________

---

## 4. Decision Card DEC-003: Unmapped GRN Items & Ambiguous Scrap Grade

### 4.1 The Question Requiring Decision
> **Executive Question:** How shall the unmapped maintenance items (`3306PMKT-Generator` and `Tool Post`) and the ambiguous 15,200 kg `crca scrap` receipt in historical GRNs be classified in the Item Master?

### 4.2 Verified Facts & Source References
- `VSPL_Material_Entry.xlsx` sheet `'3. Receipt GRN'` rows 3 and 4 list items absent from `VSPL_Item_Master.xlsx`:
  - Row 3: `3306PMKT-Generator` (1 Set) — Proposed canonical code: `MNT-CN-001`.
  - Row 4: `Tool Post` (1 Nos) — Proposed canonical code: `MCS-CN-002`.
- Row 5 lists `crca scrap` (15,200 kg) which matches two distinct canonical codes with different manganese chemistry:
  - `RM-SC-007` (CRC Scrap Low MN: $\text{Mn} = 0.15\text{--}0.25\%$).
  - `RM-SC-008` (CRC Scrap Low High MN: $\text{Mn} = 0.35\text{--}0.50\%$).
- An incorrect scrap grade distorts manganese recovery calculations during furnace melting, risking out-of-spec SG iron heats.

### 4.3 Documented Choices Available to Management
- **Item Master Additions:** Approve Phase 2 Item Request workflows formally adding `MNT-CN-001` (Maintenance) and `MCS-CN-002` (Machine Shop) to the canonical catalog.
- **Scrap Grade Classification:**
  - **Choice A (Recommended):** Foundry Quality Lab conducts optical emission spectrometry (OES) testing on a retained sample or reviews vendor mill test certificates to definitively classify the 15,200 kg consignment.
  - **Choice B:** In the absence of physical sample/mill certs, Chief Metallurgist issues an engineering determination assigning the consignment to conservative grade `RM-SC-007` under written technical waiver.

### 4.4 Required Evidence & Accountable Authority
- **Required Evidence:** Approved Phase 2 Item Requests; signed OES laboratory test certificate or Metallurgist Determination Memo.
- **Accountable Decision-Maker:** **Plant Head** and **Chief Metallurgist**.

---

## 5. Decision Card DEC-004: Suspected Issue Date Typo (Year 20236)

### 5.1 The Question Requiring Decision
> **Executive Question:** Shall cells `A537:A548` in `VSPL_Material_Entry.xlsx` containing date string `'7-16-20236'` be formally normalized to calendar date `2026-07-16` based on physical warehouse paper dockets?

### 5.2 Verified Facts & Source References
- `VSPL_Material_Entry.xlsx` sheet `'4. Issue'` cells `A537:A548` record 12 issue lines with date string `'7-16-20236'`.
- Associated physical store issue slips: 327, 910, 325, 1149, 326, 2725, and 1148.
- Physical quantities and item descriptions are valid (e.g. 4m cotton waste, 1L thinner, 50kg lubricant).
- Year `20236` causes standard Python/database date parsers to crash (`ValueError: year 20236 is out of range`).

### 5.3 Documented Choices Available to Management
- **Choice A (Recommended):** Stores supervisor inspects physical paper slips in central stores archive box `'July 2026'`, verifies handwritten date `16-07-2026`, and signs a Date Normalization Certificate authorizing automated ETL mapping to `2026-07-16`.
- **Choice B:** Quarantine the 12 rows in staging tables pending individual re-authorization by indenting department heads.

### 5.4 Required Evidence & Accountable Authority
- **Required Evidence:** Physical inspection log of paper slips 327–1148; signed Date Normalization Certificate.
- **Accountable Decision-Maker:** **Stores Manager** and **Lead QA Auditor**.

---

## 6. Decision Card DEC-005: Seven Negative Balances & Omitted Scrap Issues

### 6.1 The Question Requiring Decision
> **Executive Question:** How shall VSPL resolve the seven negative raw material book balances (-500 to -2 kg) and the 11,793 kg of omitted scrap store issues reported in `VSPL_Master_Ledger.xlsx`?

### 6.2 Verified Facts & Source References
- `VSPL_Master_Ledger.xlsx` reports negative closing stock for 7 materials: `RM-SC-001` (-500 kg), `RM-SC-003` (-300 kg), `RM-SC-005` (-100 kg), `RM-FA-001` (-10 kg), `RM-FA-002` (-4 kg), `RM-FA-003` (-4 kg), `RM-TR-002` (-2 kg).
- Cause: Maintainer subtracted furnace charge weights for heat `H-260714-01` directly from zero opening balances.
- Simultaneously, 11,793 kg of scrap issues on slips 315–320 were recorded in `VSPL_Material_Entry.xlsx` but omitted from `VSPL_Master_Ledger.xlsx`.
- Live ERP database strictly prevents negative balances (`HTTP 409 Conflict`), making direct import of these balances impossible.

### 6.3 Documented Choices Available to Management
- **Choice A (Recommended — Aligns with DEC-002 Scenario A):** Supercede historical spreadsheet balances entirely via plant-wide physical stocktake under `SOP-P7-PHYSICAL-STOCKTAKE`. Populate certified opening balances on Sheet D as of 12-Oct-2026, permanently retiring the flawed interim ledger.
- **Choice B:** Attempt retrospective bookkeeping reconciliation by posting artificial balancing receipts to negate the negative balances prior to live import. *(Rejected by Audit: Falsifies ledger audit trail).*

### 6.4 Required Evidence & Accountable Authority
- **Required Evidence:** Certified physical count tally sheets; weighbridge printouts; fully signed Sheet D of `VSPL_Physical_Stocktake_Register.xlsx`.
- **Accountable Decision-Maker:** **Plant Head** and **Lead Inventory Auditor**.

---

## 7. Decision Card DEC-006: Template Dummy Row 2 Purge

### 7.1 The Question Requiring Decision
> **Executive Question:** Shall template dummy records on row 2 across all sheets in `VSPL_Material_Entry.xlsx` be permanently purged from the operational migration manifest?

### 7.2 Verified Facts & Source References
- `VSPL_Material_Entry.xlsx` sheet `'Read Me'` cell `A14` explicitly states: *"Row 2 of each sheet is a sample entry — overwrite it or delete it before real use."*
- Row 2 of `'3. Receipt GRN'` contains an artificial receipt for `FDY-CN-003` (Emery Paper, 25 nos) that conflicts with legacy cement records.
- Row 2 of `'4. Issue'` and `'5. Scrap'` similarly contain development placeholder entries.
- The operational manifest currently includes these sample entries, bringing candidate row count to 616 rows instead of 613 true operational rows.

### 7.3 Documented Choices Available to Management
- **Choice A (Recommended):** Formally authorize filtering `row_number != 2` across all sheets in `scripts/phase7_stage2_manifest_generator.py`, reducing candidate rows cleanly from 616 to 613 rows.
- **Choice B:** Retain row 2 records and require manual line-item exceptions.

### 7.4 Required Evidence & Accountable Authority
- **Required Evidence:** Updated manifest generator script; signed QA verification memo certifying 613 operational rows.
- **Accountable Decision-Maker:** **Systems Architect** and **Lead QA Auditor**.

---

## 8. Decision Card DEC-007: Furnace Charge Mass-Balance Deficit (18 Heats with 0 Charge)

### 8.1 The Question Requiring Decision
> **Executive Question:** How shall the 18 heats on 22 July 2026 recorded in `VSPL_Foundry_Heat_Log.xlsx` with Total Charge = 0 kg but tapped liquid metal of 504–524 kg be treated in production costing?

### 8.2 Verified Facts & Source References
- `VSPL_Foundry_Heat_Log.xlsx` sheet `'Heat Log'` rows 2–20 show 18 heats on 22-Jul with Total Charge = 0.00 kg.
- Tapped liquid metal is recorded between 504 kg and 524 kg per heat.
- Sheet `'Charge Details'` contains only 10 total charge lines covering heats 072613-2092, 072614-2093, and 072614-2094; charges for heats 072622-2095 through 072622-2110 are missing.
- In `backend/app/services/costing_service.py` (line 450), attempting to calculate liquid metal cost per kg with zero material charge raises `InsufficientMeltDataError`.

### 8.3 Documented Choices Available to Management
- **Choice A (Recommended):** Melt supervisor searches furnace control room archives for paper melt charge sheets. If found, charge lines are transcribed into staging. If unretrievable, Foundry Head signs a formal Quarantine Order holding all 18 heats in `QUARANTINED_STAGING`, preventing them from posting to live production tables.
- **Choice B:** Synthesize average charge weights based on heat metallurgical grade. *(Rejected by Metallurgical Audit: Violates traceability and material-balance rules).*

### 8.4 Required Evidence & Accountable Authority
- **Required Evidence:** Physical paper furnace heat sheets; OR signed Quarantine Authorization Order by Foundry Head.
- **Accountable Decision-Maker:** **Foundry Head** and **Chief Metallurgist**.

---

## 9. Decision Card DEC-008: Legacy Archive Future Dates (Store Inventory.xlsx)

### 9.1 The Question Requiring Decision
> **Executive Question:** Shall `Store Inventory.xlsx` be formally retired as an obsolete legacy archive and permanently excluded from the operational ERP migration pipeline?

### 9.2 Verified Facts & Source References
- `Store Inventory.xlsx` sheet `'Material Receipt'` rows 9–121 contain stored datetime `'2026-11-07'` with supplier marked `'Physical stock'`.
- Date `2026-11-07` is post-dated relative to the July source cutoff and October go-live date.
- The workbook is an unlinked, legacy desktop backup that conflicts with `VSPL_Master_Ledger.xlsx` and `VSPL_Material_Entry.xlsx`.
- In `backend/app/services/excel_import_service.py`, future transaction dates exceeding `current_date` are strictly rejected.

### 9.3 Documented Choices Available to Management
- **Choice A (Recommended):** Formally retire `Store Inventory.xlsx` into read-only historical archive storage (`_legacy_archive/`); configure ETL migration pipelines to permanently ignore the file.
- **Choice B:** Attempt reconciliation of future-dated rows. *(Rejected: Unnecessary effort on an obsolete desktop file).*

### 9.4 Required Evidence & Accountable Authority
- **Required Evidence:** Signed IT and Audit Retirement Memorandum; ETL pipeline configuration verification.
- **Accountable Decision-Maker:** **IT Head** and **Lead Internal Auditor**.

---

## 10. Summary of Executive Decision Matrix

| Card ID | Decision Topic | Recommended Policy Choice | Primary Accountable Authority | Primary Downstream Impact |
| :--- | :--- | :--- | :--- | :--- |
| **DEC-001** | Missing GRN Purchase Rates | Retrieve vendor tax invoices; certify ex-GST rates | Finance Head & MD | Unblocks Rule C1 moving-average costing (Gate G3) |
| **DEC-002** | 82-Day Void & Cutoff Policy | Adopt Scenario A (Physical Cutoff as of 12-Oct) | Managing Director & Plant Head | **THE CRITICAL PATH:** Establishes live opening stock (Gate G2) |
| **DEC-003** | Unmapped Items & Scrap Grade | Approve item additions; test scrap on OES lab unit | Plant Head & Metallurgist | Unblocks melt manganese recovery & catalog integrity (Gates G4, G5) |
| **DEC-004** | Issue Date Typo (Year 20236) | Inspect paper slips 327–1148; sign normalization cert | Stores Manager & QA Lead | Unblocks date parsing & ledger chronological order (Gate G6) |
| **DEC-005** | Negative Stock & Omitted Scrap | Supercede spreadsheet balances via physical stocktake | Plant Head & Lead Auditor | Eliminates 7 negative balances; populates Sheet D (Gate G7) |
| **DEC-006** | Template Dummy Row 2 Purge | Update generator script to filter row 2 (613 rows) | Systems Architect & QA Lead | Prevents dummy development entries in live ledger (Gate G8) |
| **DEC-007** | 18 Uncharged Furnace Heats | Retrieve paper melt sheets or sign quarantine order | Foundry Head & Metallurgist | Prevents division-by-zero melt costing errors (Gate G9) |
| **DEC-008** | Legacy Archive Future Dates | Formally retire Store Inventory.xlsx from ETL | IT Head & Lead Auditor | Eliminates post-dated duplicate receipts (Gate G10) |

---

## 11. Safety Attestation & Stop Conditions

- **Documentation Only:** This pack provides the objective briefing materials. No decision has been selected, signed, or executed on management's behalf.
- **Zero System Mutations:** No database records, stock ledger entries, or opening balances were created.
- **Prohibition Enforced:** **Stage 3B live historical migration remains strictly unauthorized until all 8 decisions are formally executed and all 13 Acceptance Gates are certified in writing.**
