# VSPL Material Management & Costing System — Department-Specific Evidence Checklists

**Document ID:** `DOC-P7-S3A2-DEPT-CHECKLISTS`  
**System:** VSPL Material Management & Costing System  
**Date:** 2026-10-17  
**Governance Scope:** Actionable Evidence Requirements by Department to Resolve Migration Blockers  
**Execution Status:** **EVIDENCE SPECIFICATION ONLY — NO DATA MUTATION OR SYSTEM CHANGES**  

---

## 1. Executive Purpose & Instructions

This document provides actionable, auditable evidence checklists tailored to each operational department of Vijay Spheroidals Pvt. Ltd. (VSPL). These checklists define the precise documentation, physical artifacts, lab test certificates, and management mandates required to resolve the 8 outstanding migration decisions (`DEC-001` through `DEC-008`) and satisfy the 13 Acceptance Gates (`G1` through `G13`).

### Strict Governance Rules:
1. **No Fictitious Entries:** No mock, synthetic, or placeholder data may be entered into these checklists. Every field must be populated solely from authentic, verifiable records.
2. **Dual-Sign-Off Mandate:** Every completed evidence submission must bear the signature of the primary evidence owner and the designated approving authority.
3. **Preservation of Chain of Custody:** Original physical dockets, lab certificates, and tax invoices must remain filed in their respective physical archives after digital scanning and verification.

---

## 2. Purchase / Finance Department Evidence Checklist

### 2.1 Scope & Governing Blockers
- **Primary Decisions:** `DEC-001` (Missing Historical GRN Commercial Rates)
- **Primary Acceptance Gates:** `G1` (Executive Sign-Off), `G3` (Commercial Purchase Rates)
- **Accountable Role:** Finance Head / Purchase Head

### 2.2 Evidence Requirement Specification
The Finance and Purchase departments must retrieve and certify original commercial documentation for historical material receipts recorded in `VSPL_Material_Entry.xlsx` ('3. Receipt GRN', rows 2–5).

| Field Name | Description & Requirement | Acceptance Criteria |
| :--- | :--- | :--- |
| **Vendor Tax Invoice Number** | Original tax invoice issued by the registered vendor | Must be a legitimate GST invoice matching vendor name and transaction period |
| **Vendor Invoice Date** | Date of tax invoice execution | Must precede or match the physical receipt date recorded in the GRN |
| **Vendor GSTIN** | 15-digit Goods and Services Tax Identification Number | Must match the active GST registration of the supplying vendor |
| **Item Description on Invoice** | Exact line item text on supplier invoice | Must unambiguously correspond to the received item |
| **Invoiced Quantity & UOM** | Quantity billed by vendor in supplier UOM | Must reconcile to weighbridge docket or physical receiving count |
| **Ex-GST Unit Purchase Rate** | Net unit price excluding GST | Must be certified in writing; represents base valuation for Rule C1 |
| **Applicable GST Rates** | Percentage and amount of CGST, SGST, or IGST | Must match statutory GST tariff rates for the HSN/SAC code |
| **Input Tax Credit (ITC) Status** | Eligibility of tax credit under GST rules | Must declare whether tax is eligible for ITC or capitalized into cost |
| **Supporting Purchase Order (PO)**| Approved VSPL Purchase Order reference | Must confirm rate was authorized prior to delivery |
| **Delivery Challan Reference** | Vendor delivery challan or weighbridge docket | Must confirm physical goods movement into the foundry premises |

### 2.3 Required Departmental Sign-Off Schedule
- [ ] Physical supplier tax invoice for GRN Row 3 (`3306PMKT-Generator`, 1 Set) retrieved and certified.
- [ ] Physical supplier tax invoice for GRN Row 4 (`Tool Post`, 1 Nos) retrieved and certified.
- [ ] Physical supplier tax invoice and weighbridge docket for GRN Row 5 (`crca scrap`, 15,200 kg) retrieved and certified.
- [ ] Finance Head signs `commercial_rates_staging.csv` certifying ex-GST rates for historical staging.

---

## 3. Stores Department Evidence Checklist

### 3.1 Scope & Governing Blockers
- **Primary Decisions:** `DEC-003` (Item Creation), `DEC-004` (Issue Date Typo), `DEC-005` (Negative Balances & Omitted Scrap), `DEC-006` (Sample Row Purge)
- **Primary Acceptance Gates:** `G4` (Item Additions), `G6` (Issue Date Typo), `G7` (Certified Physical Stocktake), `G8` (Dummy Row Purge)
- **Accountable Role:** Stores Manager / Inventory Supervisor

### 3.2 Evidence Requirement Specification

#### A. Physical Stocktake Protocol Evidence (Gate G7, DEC-005)
| Field Name | Description & Requirement | Acceptance Criteria |
| :--- | :--- | :--- |
| **Count Date and Timestamp** | Exact date and time count was completed | Must align with the designated cutoff date (12-Oct-2026) |
| **Storage Location Identifier** | Physical plant location (e.g., Raw Material Yard, Central Stores, Chemical Godown) | Must specify physical rack, bin, or yard quadrant |
| **Canonical Item Code** | Approved code from Item Master | Must match existing canonical master code exactly |
| **Base UOM** | Canonical Unit of Measure | Must match Item Master base UOM (e.g. KG, NOS, MTR, LTR) |
| **Counted Physical Quantity** | Blind count figure recorded by counting team | Double-blind count certified by independent verifier |
| **Count Team Signatures** | Signatures of Primary Counter and Independent Verifier | Both signatures present on physical tally sheet |
| **Variance Investigation Report**| Formal explanation for any variance against book stock | Required for any variance exceeding 0.00% on controlled alloys |

#### B. Issue Slip Date Typo Normalization Evidence (Gate G6, DEC-004)
| Field Name | Description & Requirement | Acceptance Criteria |
| :--- | :--- | :--- |
| **Physical Issue Slip Number** | Hardcopy docket numbers (327, 910, 325, 1149, 326, 2725, 1148) | Physical paper slip retrieved from warehouse store archive |
| **Physical Written Date** | Date handwritten or stamped on the physical slip | Must confirm calendar date `16-07-2026` |
| **Material Description & Qty** | Item text and issued quantity on physical slip | Must match exactly cells in rows 537–548 of `VSPL_Material_Entry.xlsx` |
| **Issuing Storekeeper Signature**| Signature on original physical slip | Verifiable signature of storekeeper on duty |
| **Receiving Indentor Signature** | Signature of department supervisor receiving goods | Verifiable indentor signature confirming physical receipt |
| **Date Normalization Certificate**| Formal memo authorizing correction of year `20236` to `2026` | Signed by Stores Manager and Lead QA Auditor |

---

## 4. Foundry / Quality Department Evidence Checklist

### 4.1 Scope & Governing Blockers
- **Primary Decisions:** `DEC-003` (Scrap Grade Ambiguity), `DEC-007` (18 Heats with 0 Charge)
- **Primary Acceptance Gates:** `G5` (Scrap Metallurgy Certification), `G9` (Furnace Heat Log Quarantine)
- **Accountable Role:** Foundry Head / Chief Metallurgist / Quality Lab In-Charge

### 4.2 Evidence Requirement Specification

#### A. Scrap Metallurgy Spectrometry Certification (Gate G5, DEC-003)
| Field Name | Description & Requirement | Acceptance Criteria |
| :--- | :--- | :--- |
| **Sample Identification** | Traceable sample ID representing the 15,200 kg CRCA scrap | Tagged to GRN Row 5 delivery docket / yard heap |
| **Spectrometer Test Date** | Date optical emission spectrometry (OES) was conducted | Verified against Foundry Quality Lab logbook |
| **Carbon Content (%C)** | Measured carbon percentage | Recorded to 3 decimal places |
| **Silicon Content (%Si)** | Measured silicon percentage | Recorded to 3 decimal places |
| **Manganese Content (%Mn)** | Critical discriminating element for scrap grade | Must definitively classify sample: **0.15–0.25%** (`RM-SC-007`) vs **0.35–0.50%** (`RM-SC-008`) |
| **Phosphorus & Sulfur (%P, %S)**| Measured trace elements | Must satisfy SG iron melting base stock limits |
| **Metallurgist Certification** | Formal laboratory certificate signed by Metallurgist | Signed physical test certificate attached to staging manifest |

#### B. Furnace Charge Mass-Balance & Heat Records (Gate G9, DEC-007)
| Field Name | Description & Requirement | Acceptance Criteria |
| :--- | :--- | :--- |
| **Physical Heat Log Sheet** | Hardcopy paper heat sheet from furnace control deck | Must cover heats 2–20 from 22-Jul-2026 (`VSPL_Foundry_Heat_Log.xlsx`) |
| **Furnace Identification** | Induction furnace ID (e.g. F-01, F-02) | Must match furnace operational logs |
| **Charge Components Breakdown** | Detailed weight of Scrap, Pig Iron, Returns, Ferro-Alloys | Sum of charge components must equal total charge weight |
| **Liquid Metal Tapped Weight** | Crane weigh scale or ladle tare/gross weight | Tapped weight must show realistic melting recovery (95–98%) |
| **Strict Rule H1 Compliance** | Separation of heat charge records from stock ledger | Confirms charge records are for melt costing only, NOT stock ledger issues |
| **Quarantine Mandate** | If physical sheets missing, formal quarantine order | Signed order by Foundry Head holding 18 heats in staging tables |

---

## 5. Master-Data Owner Evidence Checklist

### 5.1 Scope & Governing Blockers
- **Primary Decisions:** `DEC-003` (Unmapped GRN Items), `DEC-006` (Sample Row Purge)
- **Primary Acceptance Gates:** `G4` (Item Master Additions), `G8` (Dummy Row Purge)
- **Accountable Role:** Master Data Lead / ERP Data Governance Administrator

### 5.2 Evidence Requirement Specification
| Field Name | Description & Requirement | Acceptance Criteria |
| :--- | :--- | :--- |
| **Canonical Item Code** | Systematic code following VSPL naming standard | `MNT-CN-001` (3306PMKT-Generator) and `MCS-CN-002` (Tool Post) |
| **Canonical Item Name** | Full descriptive specification of the material | Standardized title without ambiguous vendor jargon |
| **Department Assignment** | Owning operational department | Maintenance (`MNT`) and Machine Shop (`MCS`) |
| **Inventory Category** | Material classification category | `CAPITAL_SPARES` or `CONSUMABLES` |
| **Base Unit of Measure (UOM)** | Standard storage unit | `SET` for generator package; `NOS` for tool post |
| **Material Alias Mapping** | Alternative names mapped in `material_aliases` | Exact match to historical spreadsheet text |
| **Phase 2 Workflow Approval** | Official approval record under Phase 2 Item Request workflow | System approval record signed by Department Head and Stores Manager |

---

## 6. Management & Executive Governance Evidence Checklist

### 6.1 Scope & Governing Blockers
- **Primary Decisions:** `DEC-001` through `DEC-008` (All Pending Decisions)
- **Primary Acceptance Gates:** `G1` (Executive Decision Sign-Off), `G2` (Cutoff Policy Authorization)
- **Accountable Role:** Managing Director / Plant Head / Finance Head

### 6.2 Evidence Requirement Specification
| Field Name | Description & Requirement | Acceptance Criteria |
| :--- | :--- | :--- |
| **Cutoff Policy Mandate** | Executive policy memorandum adopting **Scenario A** | Signed by Managing Director; establishes 12-Oct-2026 physical cutoff |
| **82-Day Void Treatment** | Formal declaration regarding unlogged July–October operations | Confirms July data is historical audit archive only, not live starting stock |
| **Opening Stock Approval** | Authorization of Sheet D counts in `VSPL_Physical_Stocktake_Register.xlsx` | Formal approval by Plant Head and Managing Director |
| **Costing Baseline Mandate** | Mandate authorizing Phase 6 Rule C1 weighted-average costing | Signed authorization by Finance Head and Managing Director |
| **Management Sign-Off Form** | Fully executed [`MANAGEMENT_SIGNOFF_TEMPLATE.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_management_signoff/MANAGEMENT_SIGNOFF_TEMPLATE.md) | Physical signatures and dates for all 8 decision cards |

---

## 7. IT / Database Infrastructure Evidence Checklist

### 7.1 Scope & Governing Blockers
- **Primary Decisions:** `DEC-008` (Legacy Archive Retirement)
- **Primary Acceptance Gates:** `G10` (Legacy Archive Retired), `G12` (PostgreSQL Non-Prod Verification), `G13` (Backup Rehearsal)
- **Accountable Role:** IT Head / Lead DBA / Systems Architect

### 7.2 Evidence Requirement Specification
| Field Name | Description & Requirement | Acceptance Criteria |
| :--- | :--- | :--- |
| **Dedicated Port Availability** | TCP socket verification for port `5439` | Port `5439` completely free; zero conflict with port `5432` container (`backend-db-1`) |
| **Loopback Network Binding** | Docker Compose binding restriction | Strictly bound to `127.0.0.1:5439:5432` |
| **Named Volume Isolation** | Dedicated Docker persistent volume | Isolated volume `vspl_mm_pg16_nonprod_data` created |
| **Alembic Schema Head** | Migration chain verification on PostgreSQL | All 5 migrations applied; 36 tables; 114 indexes; head `005_cost_history` |
| **Pre-Migration Backup Archive** | Binary dump captured via `pg_dump -Fc` | Verified `.dump` file with SHA-256 sidecar digest |
| **Scratch Restore Rehearsal** | Complete restore rehearsal into `vspl_mm_restore_test` | Programmatic verification: 36 tables, 114 indexes certified |
| **Legacy File Retirement Lock** | Read-only archive lock on `Store Inventory.xlsx` | Formal IT memorandum retiring file; file excluded from ETL configuration |

---

## 8. Summary of Checklists Status

All departments have distinct, non-overlapping checklists. **No checklist has been marked approved or completed**, preserving strict audit integrity until original evidence is physically and digitally produced.
