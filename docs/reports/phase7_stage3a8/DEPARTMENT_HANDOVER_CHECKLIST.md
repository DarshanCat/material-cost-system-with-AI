# VSPL Material Management & Costing System
## Phase 7 — Stage 3A.8: Departmental Evidence Handover Checklist

**Document ID:** `VSPL-P7-S3A8-DHC-001`  
**Security Classification:** Controlled Operational Document  
**Date of Issue:** October 2026  
**Auditor:** Data Migration Audit Team & Senior Manufacturing ERP Specialist  
**Governing Protocol:** [STAGE3A8_EVIDENCE_INTAKE_PROTOCOL.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a8/STAGE3A8_EVIDENCE_INTAKE_PROTOCOL.md)  
**Intake Register:** [EVIDENCE_INTAKE_REGISTER.csv](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a8/EVIDENCE_INTAKE_REGISTER.csv)  

---

### Executive Purpose

This document provides actionable, field-level handover instructions for each operational department at Vijay Spheroidals Pvt Ltd (VSPL). It defines exactly which files, paper dockets, and laboratory assets must be inspected, the precise deliverable required from each department head, objective validation criteria, and formal sign-off blocks.

No migration into live databases, opening balance postings, or Docker container launches may occur until each departmental checklist is fulfilled and verified according to the 6-state evidence intake lifecycle.

---

### Summary of Departmental Assignments

| Department | Custodian Role | Assigned Actions | Related Decisions | Related Gates | Target Output Document |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Finance & Purchase** | Finance Head | `ACT-02` | `DEC-001` | `G3`, `G1` | Supplier Invoices & `commercial_rates_staging.csv` |
| **Stores & Master Data** | Stores Manager | `ACT-03`, `ACT-05` | `DEC-003`, `DEC-004` | `G4`, `G6`, `G1` | Item Master Forms & Date Normalization Cert |
| **Foundry & Quality** | Foundry Metallurgist / Foundry Head | `ACT-04`, `ACT-08` | `DEC-003`, `DEC-007` | `G5`, `G9`, `G1` | OES Spectrometry Cert & Furnace Quarantine Order |
| **Plant Leadership** | Plant Head | `ACT-06` | `DEC-005` | `G7`, `G1` | Certified Sheet D of Stocktake Register |
| **Executive Management**| Managing Director | `ACT-01`, `ACT-10 (Gov)` | `DEC-002`, `DEC-001..008`| `G2`, `G1` | Scenario A Policy Memo & `MANAGEMENT_SIGNOFF_TEMPLATE.md` |
| **IT & Systems Architecture**| Systems Architect / IT Head | `ACT-07`, `ACT-09` | `DEC-006`, `DEC-008` | `G8`, `G10`, `G1` | Template Exclusion Directive & IT Retirement Memo |
| **Lead DBA / DevOps** | Lead DBA | `ACT-10 (DBA)` | Technical Readiness | `G12`, `G13` | Port 5439 PostgreSQL 16 Deployment & Verification |

---

### 1. Finance & Purchase Department Handover

#### Action: `ACT-02` — Historical GRN Commercial Purchase Rates
* **Responsible Head:** Finance Head / Senior Cost Controller  
* **Evidence Custodian:** Senior Accounts Officer (Invoicing)  
* **Independent Reviewer:** Internal Cost Auditor  
* **Related Governance:** `DEC-001`, Acceptance Gate `G3`, Tracking Item `TRK-01`  

##### Physical & Digital Files to Examine
1. **Spreadsheet Reference:** `data/raw/VSPL_Material_Entry.xlsx`, Sheet `3. Receipt GRN`, Rows 2–5.
2. **Exception Register:** [grn_mapping_pricing_exceptions.csv](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2_1/grn_mapping_pricing_exceptions.csv).
3. **Physical Storage Location:** Accounts Department Archive Vault, Box labeled `FY 2026-27 GRN Invoices & Supplier Delivery Challans`.

##### Required Deliverables
1. **Primary Evidence:** Original vendor tax invoice hardcopies (or certified digital tax invoices from GST portal) corresponding to:
   - GRN Row 3: Generator maintenance spare (`3306PMKT-Generator`, Qty 1 EA, Vendor: Power Electrics / Cat Spares)
   - GRN Row 4: Machine shop consumable tool (`Tool Post`, Qty 2 EA, Vendor: Precision Tooling)
   - GRN Row 5: Raw material scrap (`crca scrap`, Qty 15,200 kg, Vendor: Steel Traders Corp)
2. **Structured Rate Schedule:** Completed [commercial_rates_staging.csv](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a8/commercial_rates_staging.csv) detailing:
   - `Item_Code`, `Vendor_Invoice_No`, `Invoice_Date`, `Ex_GST_Unit_Rate`, `GST_Percentage`, `Total_Amount`, `Certification_Ref`.

##### Validation & Rejection Criteria
* **Validation (Pass):** Unit rates must be net **ex-GST** (the core costing engine strictly requires base purchase price). Invoice numbers and dates must match delivery records. Dual signature of Accounts Officer and Finance Head required.
* **Rejection (Fail):** Estimated or average rates; GST-inclusive totals without breakdown; pro-forma invoices; unsigned spreadsheets.

##### Departmental Sign-Off Block
```text
[ ] Primary Invoices Retrieved & Scanned (SHA-256 Calculated)
[ ] commercial_rates_staging.csv Populated with Net Ex-GST Rates
[ ] Internal Cost Auditor Review Completed

Finance Head Signature: ___________________________    Date: _______________
Printed Name:           ___________________________
Verification Hash:      ___________________________ (SHA-256 of rate package)
```

---

### 2. Stores & Master Data Department Handover

#### Action: `ACT-03` — Item Master Additions (MNT-CN-001 & MCS-CN-002)
* **Responsible Head:** Stores Manager  
* **Evidence Custodian:** Master Data Controller  
* **Independent Reviewer:** Lead Inventory Accountant  
* **Related Governance:** `DEC-003`, Acceptance Gate `G4`, Tracking Item `TRK-03`  

##### Physical & Digital Files to Examine
1. **Spreadsheet Reference:** `data/raw/VSPL_Item_Master.xlsx`, Columns A through K.
2. **Engineering Specs:** Foundry and maintenance consumable equipment specifications.

##### Required Deliverables
1. **Item Master Creation Record:** Completed and approved Phase 2 Item Request forms assigning:
   - `MNT-CN-001`: Refractory Castable LC-60 (Category: Maintenance Consumables, UOM: `KGS`, Standard Valuation).
   - `MCS-CN-002`: Inoculant FeSi 75% (Category: Machine Consumables / Foundry Alloys, UOM: `KGS`).
2. **Item Catalog Entry:** Formal insertion payload formatted for `app/models/inventory.py`.

##### Validation & Rejection Criteria
* **Validation (Pass):** Unique Item Codes conforming to VSPL taxonomy; standard UOM defined; zero-rate flag resolved; approved by Stores Manager and Plant Metallurgist.
* **Rejection (Fail):** Missing technical specifications; duplicate item codes; ambiguous UOMs (e.g., "bags" or "boxes" instead of canonical `KGS`).

---

#### Action: `ACT-05` — Issue Date Typo Physical Docket Reconciliation
* **Responsible Head:** Stores Manager  
* **Evidence Custodian:** Stores Supervisor  
* **Independent Reviewer:** Lead Migration Auditor  
* **Related Governance:** `DEC-004`, Acceptance Gate `G6`, Tracking Item `TRK-02`  

##### Physical & Digital Files to Examine
1. **Spreadsheet Reference:** `data/raw/VSPL_Material_Entry.xlsx`, Sheet `4. Issue`, Rows 537–548 (Date string: `7-16-20236`).
2. **Docket Reference:** Stores Issue Slips `327`, `910`, `325`, `1149`, `326`, `2725`, `1148`.
3. **Physical Storage Location:** Central Stores Paper Docket Room, File Binder `Stores Issue Slips — July 2026`.

##### Required Deliverables
1. **Physical Inspection Log:** Tabulated report detailing the physical condition, docket numbers, and handwritten dates on the 7 paper issue slips.
2. **Date Normalization Certificate:** Signed certificate confirming that all slips bear the physical date `16-07-2026` and authorizing the database mapping from `7-16-20236` to `2026-07-16`.

##### Validation & Rejection Criteria
* **Validation (Pass):** 100% of physical dockets inspected; photographic evidence attached; dual signatures of Stores Supervisor and Migration Auditor.
* **Rejection (Fail):** Sampling less than 100%; missing dockets; dockets showing different calendar dates.

##### Stores Department Sign-Off Block
```text
[ ] Item Master Phase 2 Forms Approved (MNT-CN-001 & MCS-CN-002)
[ ] Physical Paper Dockets 327-1148 Inspected & Photographed
[ ] Date Normalization Certificate Signed (Confirming 2026-07-16)

Stores Manager Signature: ___________________________    Date: _______________
Printed Name:             ___________________________
Verification Hash:        ___________________________ (SHA-256 of certificate)
```

---

### 3. Foundry & Quality Department Handover

#### Action: `ACT-04` — CRCA Scrap Chemical Composition Certification
* **Responsible Head:** Foundry Head  
* **Evidence Custodian:** Chief Metallurgist / Foundry Quality Lab Head  
* **Independent Reviewer:** Quality Assurance Head  
* **Related Governance:** `DEC-003`, Acceptance Gate `G5`, Tracking Item `TRK-03`  

##### Physical & Digital Files to Examine
1. **Physical Scrap Pile:** Raw Material Yard Scrap Bay #3 (15,200 kg CRCA steel scrap delivered in July 2026).
2. **Lab Spectrometer:** Foundry Quality Optical Emission Spectrometer (OES) calibrated against certified reference standard.

##### Required Deliverables
1. **Spectrometer Lab Certificate:** Certified OES Laboratory Analysis Report containing:
   - Chemical analysis: %C, %Si, **%Mn**, %S, %P, %Cr, %Ni.
   - Definitive classification:
     - If Mn <= 0.35%: Classify as `RM-SC-007` (Commercial CRCA Scrap).
     - If Mn > 0.35%: Classify as `RM-SC-008` (Special Grade Manganese Scrap).
2. **Lab Printout Trace:** Original instrument printout attached and countersigned.

---

#### Action: `ACT-08` — Furnace Charge Mass-Balance Deficit Resolution
* **Responsible Head:** Foundry Head  
* **Evidence Custodian:** Melt Shop Superintendent  
* **Independent Reviewer:** Senior Cost Controller  
* **Related Governance:** `DEC-007`, Acceptance Gate `G9`, Tracking Item `TRK-04`  

##### Physical & Digital Files to Examine
1. **Spreadsheet Reference:** `data/raw/VSPL_Foundry_Heat_Log.xlsx`, Sheet `Heat Log Summary`, 18 Heats dated 22-Jul-2026 (Heats 2 through 20 with `Total Charge = 0 kg` but tapped metal 504–524 kg).
2. **Physical Storage Location:** Furnace Melt Deck Cabin, Paper Melt Log Book `Furnace 1 & 2 Log Book — July 2026`.

##### Required Deliverables
* **Option A (Charge Data Found):** Physical furnace charge log sheets showing handwritten raw material additions (pig iron, scrap, returns, alloys) signed by melter and metallurgist.
* **Option B (Data Unrecoverable — Mandatory Fallback):** Signed **Furnace Quarantine Order** formally directing that the 18 incomplete heats be placed in a quarantined staging schema and excluded from live production tables.

##### Foundry Department Sign-Off Block
```text
[ ] OES Spectrometer Certificate Executed (Definitive Grade 007 vs 008)
[ ] Furnace Log Sheets Recovered OR Formal Quarantine Order Issued
[ ] Cost Controller & QA Head Review Completed

Foundry Head Signature:   ___________________________    Date: _______________
Chief Metallurgist Sign:  ___________________________    Date: _______________
Verification Hash:        ___________________________ (SHA-256 of lab & order)
```

---

### 4. Plant Leadership Handover

#### Action: `ACT-06` — Plant-Wide Physical Stocktake Execution
* **Responsible Head:** Plant Head  
* **Evidence Custodian:** Stocktake Lead / Stores Manager  
* **Independent Reviewer:** External Inventory Auditor  
* **Related Governance:** `DEC-005`, Acceptance Gate `G7`, Tracking Item `TRK-05`  
* **Upstream Prerequisite:** `ACT-01` (Executive Cutoff Mandate adopting Scenario A)  

##### Physical & Digital Files to Examine
1. **Audit Protocol:** [PHYSICAL_STOCKTAKE_PROTOCOL.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stocktake_preparation/PHYSICAL_STOCKTAKE_PROTOCOL.md).
2. **Master Stocktake Workbook:** `docs/reports/phase7_stocktake_preparation/VSPL_Physical_Stocktake_Register.xlsx`, Sheets A, B, C, and D.

##### Required Deliverables
1. **Double-Blind Tally Sheets:** Certified Sheet A (First Count) and Sheet B (Second Blind Count) covering all raw materials, melting alloys, consumables, and scrap.
2. **Arbitration Log:** Sheet C detailing third supervisor counts for all variances > 0.5%.
3. **Certified Sheet D:** Fully completed, reconciled Sheet D representing the final opening stock quantities as of the certified cutoff date, with zero uncounted locations.

##### Validation & Rejection Criteria
* **Validation (Pass):** 100% active items counted; double-blind count protocol verified; dual certification by Plant Head and Independent Inventory Auditor.
* **Rejection (Fail):** Single-blind counts; unverified bulk scrap estimates without weighbridge slips; missing signatures; unresolved discrepancies.

##### Plant Leadership Sign-Off Block
```text
[ ] Physical Stocktake Executed Across All Active Yards & Warehouses
[ ] Double-Blind Counts Reconciled with Zero Unresolved Variances
[ ] Sheet D Certified as Authoritative System Opening Balances

Plant Head Signature:     ___________________________    Date: _______________
External Auditor Sign:    ___________________________    Date: _______________
Verification Hash:        ___________________________ (SHA-256 of final Sheet D)
```

---

### 5. Executive Management Handover

#### Action: `ACT-01` & `ACT-10 (Governance Phase)` — Cutoff Policy & Master Gate Sign-Off
* **Responsible Head:** Managing Director  
* **Evidence Custodian:** Executive Assistant to MD / Project Manager  
* **Independent Reviewer:** Data Migration Audit Lead  
* **Related Governance:** `DEC-002`, Acceptance Gates `G1`, `G2`, Tracking Item `TRK-06`  

##### Files to Examine
1. **Executive Brief:** [DEC002_EXECUTIVE_DECISION_BRIEF.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a4/DEC002_EXECUTIVE_DECISION_BRIEF.md).
2. **Authoritative Review:** [AUTHORITATIVE_READINESS_REVIEW.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a6/AUTHORITATIVE_READINESS_REVIEW.md).
3. **Master Sign-Off Form:** [MANAGEMENT_SIGNOFF_TEMPLATE.md](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a7/MANAGEMENT_SIGNOFF_TEMPLATE.md).

##### Required Deliverables
1. **Scenario A Executive Policy Memorandum:** Signed corporate memorandum:
   - Formally adopting Scenario A (Historical Audit Archive & Certified Physical Cutoff).
   - Declaring the 82-day period (28-Jul-2026 to 18-Oct-2026) an unrecorded void to remain unbackfilled.
   - Mandating the certified physical stocktake count as live opening balances.
2. **Master Management Sign-Off Package:** Formal execution of `MANAGEMENT_SIGNOFF_TEMPLATE.md` with physical signatures from MD, Plant Head, and Finance Head across all 8 decisions.

##### Executive Sign-Off Block
```text
[ ] Scenario A Executive Policy Memorandum Signed & Sealed
[ ] 82-Day Void Treatment Formally Authorized (No Synthetic Data)
[ ] MANAGEMENT_SIGNOFF_TEMPLATE.md Fully Executed Across DEC-001..008

Managing Director Sign:   ___________________________    Date: _______________
Plant Head Sign:          ___________________________    Date: _______________
Finance Head Sign:        ___________________________    Date: _______________
Verification Hash:        ___________________________ (SHA-256 of signed pack)
```

---

### 6. IT & Lead DBA Handover

#### Action: `ACT-07` & `ACT-09` — Governance Directives & Legacy Retirement
* **Responsible Head:** Systems Architect & IT Head  
* **Evidence Custodian:** IT Systems Administrator  
* **Related Governance:** `DEC-006`, `DEC-008`, Acceptance Gates `G8`, `G10`, Tracking Item `TRK-07`  

##### Required Deliverables
1. **Template Exclusion Directive (`ACT-07`):** Signed policy memorandum authorizing exclusion of dummy row 2 records from operational manifest.
2. **IT Retirement Memorandum (`ACT-09`):** Signed IT policy memorandum declaring `Store Inventory.xlsx` permanently obsolete, revoking network write permissions, and locking file to Read-Only.

---

#### Action: `ACT-10 (DBA Phase)` — Dedicated PostgreSQL 16 Deployment
* **Responsible Head:** Lead DBA / DevOps Architect  
* **Related Governance:** Acceptance Gates `G12`, `G13`  
* **Strict Prerequisite:** Gate `G1` must be formally **ACCEPTED** (Management Sign-Off Package executed).

##### Deployment & Verification Tasks
1. Deploy PostgreSQL 16 on dedicated non-production port **5439** (port 5432 remains isolated).
2. Execute Alembic migrations `001` through `005`. Verify 36 tables and 114 indexes created.
3. Execute automated test suite against port 5439 PostgreSQL instance (verify 68/68 tests pass).
4. Execute backup and restore rehearsal into scratch database per `BACKUP_RESTORE_VERIFICATION_PLAN.md`.

##### IT & DBA Sign-Off Block
```text
[ ] Template Exclusion Directive Signed & Script Generator Updated
[ ] Store Inventory.xlsx Permanently Retired & NTFS Permissions Locked
[ ] Gate G1 Verified Prior to Container Launch
[ ] PostgreSQL 16 Deployed on Port 5439; 36 Tables Verified; Rehearsal Passed

IT Head Signature:        ___________________________    Date: _______________
Lead DBA Signature:       ___________________________    Date: _______________
Verification Hash:        ___________________________ (SHA-256 of DB dump)
```
