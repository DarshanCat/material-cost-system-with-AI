# VSPL Material Management & Costing System — Departmental Evidence Collection Tracker

**Document ID:** `DOC-P7-S3A5-EVIDENCE-TRACKER`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd., Peenya Industrial Area, Bangalore  
**Repository Baseline:** `master` — `dd85bcc64e1da9268075077159ccd2abf6a94f0b`  
**Source Baseline:** `docs/reports/phase7_stage3a4/DEC002_EXECUTIVE_DECISION_BRIEF.md`  
**Operational Scope:** Cross-Departmental Evidence Collection & Acceptance Gate Verification Tracker  
**Governance Status:** **ACTIVE TRACKER — ZERO OPERATIONAL MUTATIONS — STAGE 3B STRICTLY UNAUTHORIZED**  

---

## 1. Executive Summary & Verification Invariants

This tracker establishes the operational evidence ledger for Vijay Spheroidals Pvt. Ltd. (VSPL). It monitors the physical artifacts, laboratory reports, hardcopy dockets, executive sign-offs, and technical infrastructure required to resolve all open Phase 7 migration decisions (`DEC-001` through `DEC-008`) and satisfy the 13 Acceptance Gates (`G1` through `G13`).

### Core Audit Principles:
1. **Zero Evidence Fabrication:** No receipt dates, signatures, invoice rates, chemical test percentages, stock count figures, or test execution timestamps may be recorded without physical or verified digital proof.
2. **Strict Status Segregation:** Evidence is tracked as `NO`, `PARTIAL`, or `YES`. Validation status remains `NOT REVIEWED` until primary source documents are inspected and attested by authorized reviewers.
3. **Preservation of Readiness Boundaries:** This document is an audit instrument. It does **not** authorize historical ledger mutation, database population, or live Stage 3 execution.

---

## 2. Master Departmental Evidence Collection Tracker

| Item # | Decision / Gate ID | Department & Accountable Role | Exact Evidence Required | Evidence Received | Primary Evidence File / Physical Location | Validation Status | Outstanding Discrepancy / Deficiency | Upstream Dependency & Next Safe Action | Reviewer Name & Review Date |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TRK-01** | `DEC-001` / Gate `G3` | **Finance / Purchase**<br>Finance Head / Purchase Head | Original vendor tax invoices for GRN rows 2, 3, 4, and 5 (`VSPL_Material_Entry.xlsx`); certified ex-GST purchase rates; GST breakdown schedule (`commercial_rates_staging.csv`) | **NO** | *Missing*<br>(Accounts Department physical invoice archives / vendor purchase files) | `NOT REVIEWED` | Historical GRN rows 2–5 lack unit rates; Col K of Item Master is unpopulated (`None`) across all 391 items. Rule C1 weighted-average unit rate collapses to zero without ex-GST rates. | **Dep:** None.<br>**Action:** Finance team pulls vendor invoices for Emery paper, Generator set, Tool post, and CRCA scrap; enters ex-GST rates into staging schedule. | *Reviewer:* _______________<br>*Date:* ____________ |
| **TRK-02** | `DEC-004` / Gate `G6` | **Stores**<br>Stores Manager / Lead QA Auditor | Hardcopy physical store issue slips 327, 910, 325, 1149, 326, 2725, and 1148; signed Date Normalization Certificate authorizing automated ETL mapping to `2026-07-16` | **NO** | *Missing*<br>(Central Stores paper archive box: 'Store Issue Slips — July 2026') | `NOT REVIEWED` | Text string `'7-16-20236'` across cells A537:A548 of `VSPL_Material_Entry.xlsx`; year 20236 causes parser failure; physical paper dockets uninspected. | **Dep:** None.<br>**Action:** Stores supervisor locates physical slips 327–1148, inspects written date, photographs dockets, and executes Date Normalization Certificate. | *Reviewer:* _______________<br>*Date:* ____________ |
| **TRK-03** | `DEC-003` / Gate `G5` | **Foundry / Quality**<br>Foundry Head / Chief Metallurgist | Optical Emission Spectrometry (OES) chemical analysis certificate for 15,200 kg CRCA scrap consignment (GRN row 5); formal Item Master additions for `MNT-CN-001` & `MCS-CN-002` | **NO** | *Missing*<br>(Foundry Quality Control Laboratory OES test logbook / spectrometer reports) | `NOT REVIEWED` | GRN row 5 lists generic `'crca scrap'` matching both `RM-SC-007` (0.15–0.25% Mn) and `RM-SC-008` (0.35–0.50% Mn). Ambiguity distorts melt manganese recovery and heat costing. | **Dep:** TRK-01 (for item valuation).<br>**Action:** Quality Lab executes OES spectrometer test on scrap sample; Stores submits Phase 2 item additions. | *Reviewer:* _______________<br>*Date:* ____________ |
| **TRK-04** | `DEC-007` / Gate `G9` | **Melt Deck Operations**<br>Foundry Head / Melt Supervisor | Hardcopy paper furnace heat log sheets for 22-Jul-2026 heats 2–20 (`VSPL_Foundry_Heat_Log.xlsx`); OR signed quarantine order holding 18 heats in staging preview | **NO** | *Missing*<br>(Induction furnace control deck logbook / shift charge sheets) | `NOT REVIEWED` | 18 heats on 22-Jul-2026 report Total Charge = 0 kg but tapped 504–524 kg liquid metal; missing material charge weights prevent liquid metal batch costing. | **Dep:** None.<br>**Action:** Melt supervisor searches furnace deck archives for charge sheets; if lost, Foundry Head signs formal quarantine order. | *Reviewer:* _______________<br>*Date:* ____________ |
| **TRK-05** | `DEC-005` / Gate `G7` | **Plant Operations / Stores**<br>Plant Head / Lead Inventory Auditor | Certified Physical Stocktake Register (`VSPL_Physical_Stocktake_Register.xlsx` Sheet D); double-blind physical count tally sheets; weighbridge calibration logs | **PARTIAL**<br>(Protocols & blank templates created; zero physical counts executed) | `docs/reports/phase7_stocktake_preparation/`<br>• `PHYSICAL_STOCKTAKE_PROTOCOL.md`<br>• `VSPL_Physical_Stocktake_Register.xlsx` | `NOT REVIEWED` | 7 negative balances (-500 to -2 kg) in interim ledger; 11,793 kg scrap issues omitted; physical counts not yet conducted; Sheet D remains completely unpopulated. | **Dep:** TRK-06 (DEC-002 Cutoff Mandate).<br>**Action:** Mobilize physical stocktake teams under `SOP-P7-PHYSICAL-STOCKTAKE` upon executive cutoff authorization. | *Reviewer:* _______________<br>*Date:* ____________ |
| **TRK-06** | `DEC-002` / Gates `G1`, `G2` | **Executive Management**<br>Managing Director / Plant Head | Formally signed Executive Policy Memorandum adopting **Scenario A**; executed Decision Record Template with physical signatures for `DEC-001` through `DEC-008` | **PARTIAL**<br>(Brief & blank decision template prepared; zero signatures executed) | `docs/reports/phase7_stage3a4/`<br>• `DEC002_EXECUTIVE_DECISION_BRIEF.md`<br>`docs/reports/phase7_management_signoff/`<br>• `MANAGEMENT_SIGNOFF_TEMPLATE.md` | `NOT REVIEWED` | 82-day operational void (23-Jul to 11-Oct-2026) unaddressed by formal policy; executive mandate for Scenario A cutoff remains unapproved. | **Dep:** None (Root Governance Mandate).<br>**Action:** Managing Director and Plant Head convene executive session, deliberate 6 policy questions, and sign Decision Record. | *Reviewer:* _______________<br>*Date:* ____________ |
| **TRK-07** | `DEC-008` / Gates `G10`, `G12`, `G13` | **IT & Database Operations**<br>IT Head / Lead DBA / Systems Architect | 1. Signed retirement memo for `Store Inventory.xlsx`. 2. Isolated PostgreSQL 16 container running on port `5439`. 3. Alembic schema realized (36 tables). 4. Backup rehearsal certificate | **PARTIAL**<br>(Docker Compose & setup plans drafted; zero containers deployed) | `docs/reports/phase7_stage3a1/`<br>• `POSTGRESQL_NONPROD_SETUP_PLAN.md`<br>• `BACKUP_RESTORE_VERIFICATION_PLAN.md`<br>`legacy_archive/Store Inventory.xlsx` | `NOT REVIEWED` | Port 5432 claimed by OMS container `backend-db-1`; port 5439 unallocated but unprovisioned; Alembic migrations unapplied in PostgreSQL; test suite unexecuted on PG. | **Dep:** TRK-06 (Gate G1 Executive Sign-Off).<br>**Action:** IT signs legacy retirement memo; DBA deploys PG on port 5439; runs Alembic; captures baseline backup. | *Reviewer:* _______________<br>*Date:* ____________ |

---

## 3. Departmental Evidence Status Breakdown

### 3.1 Finance & Purchase Department
- **Assigned Item:** `TRK-01` (`DEC-001`, Gate `G3`)
- **Required Deliverables:**
  - Original tax invoices from suppliers for:
    - Row 3: `3306PMKT-Generator` (1 Set)
    - Row 4: `Tool Post` (1 Nos)
    - Row 5: `crca scrap` (15,200 kg)
  - Completed `commercial_rates_staging.csv` with net ex-GST rates and GST treatment.
- **Current Deficit:** No invoices retrieved. Invoices must be pulled from physical filing cabinets in the accounts department.

### 3.2 Stores Department
- **Assigned Items:** `TRK-02` (`DEC-004`, Gate `G6`), `TRK-05` (`DEC-005`, Gate `G7`)
- **Required Deliverables:**
  - Physical inspection and signed verification of paper issue slips 327, 910, 325, 1149, 326, 2725, and 1148.
  - Signed Date Normalization Certificate for rows 537–548.
  - Phase 2 Item Request submissions for canonical items `MNT-CN-001` and `MCS-CN-002`.
- **Current Deficit:** Physical slips remain uninspected in warehouse storage boxes. Item creation requests not yet entered into the staging master.

### 3.3 Foundry Operations & Quality Laboratory
- **Assigned Items:** `TRK-03` (`DEC-003`, Gate `G5`), `TRK-04` (`DEC-007`, Gate `G9`)
- **Required Deliverables:**
  - Optical Emission Spectrometry (OES) chemical analysis certificate for 15,200 kg scrap sample.
  - Paper furnace melt charge sheets for 22-Jul-2026 heats 2–20 (`072622-2093` through `072622-2110`).
  - If charge sheets are unretrievable: formal signed Quarantine Order issued by Foundry Head.
- **Current Deficit:** Scrap sample not yet tested on laboratory spectrometer; paper heat sheets not yet retrieved from furnace control room.

### 3.4 Master Data Administration
- **Assigned Item:** Associated with `TRK-03` (`DEC-003`, Gate `G4`) and `DEC-006` (Gate `G8`)
- **Required Deliverables:**
  - Formal creation of canonical codes `MNT-CN-001` (Generator Set) and `MCS-CN-002` (Tool Post).
  - Updated manifest generator script filtering out template dummy row 2 across all sheets.
- **Current Deficit:** Manifest generator still includes row 2 candidate entries; item codes not yet provisioned.

### 3.5 Executive Management
- **Assigned Item:** `TRK-06` (`DEC-002`, Gates `G1`, `G2`)
- **Required Deliverables:**
  - Formally executed `DEC002_EXECUTIVE_DECISION_BRIEF.md` (Decision Record Template).
  - Signed executive policy memorandum adopting Scenario A (Historical Audit Archive & Certified Physical Cutoff).
  - Signed `MANAGEMENT_SIGNOFF_TEMPLATE.md` across decisions `DEC-001` through `DEC-008`.
- **Current Deficit:** Briefing delivered; awaiting formal convening of the executive review session.

### 3.6 IT & Database Infrastructure Operations
- **Assigned Item:** `TRK-07` (`DEC-008`, Gates `G10`, `G12`, `G13`)
- **Required Deliverables:**
  - Signed IT policy memorandum formally retiring `Store Inventory.xlsx`.
  - Deployment of isolated PostgreSQL 16 Alpine container on port `5439` via `docker-compose.nonprod.yml`.
  - Realization of Alembic revisions 001–005 (36 public tables, 114 indexes).
  - 68/68 regression tests passing against live PostgreSQL.
  - Pre-migration baseline backup (`pg_dump -Fc`) and verified scratch restore into `vspl_mm_restore_test`.
- **Current Deficit:** All technical infrastructure remains in design state. Zero containers launched; zero databases provisioned.

---

## 4. Summary of Blocked Decisions and Acceptance Gates

### 4.1 Decision Register Status Summary (8 Decisions)
| Decision ID | Scope & Title | Current Status | Primary Blocker |
| :--- | :--- | :--- | :--- |
| **DEC-001** | Missing Historical GRN Commercial Rates | `PENDING_REVIEW` | Missing physical vendor tax invoices |
| **DEC-002** | 82-Day Void & Costing Cutoff Policy | `PENDING_REVIEW` | Missing executive signature on Scenario A memorandum |
| **DEC-003** | Unmapped GRN Items & Ambiguous Scrap Grade | `PENDING_REVIEW` | Missing OES lab spectrometer test certificate |
| **DEC-004** | Suspected Issue Date Typo (Year 20236) | `PENDING_REVIEW` | Missing physical inspection of store slips 327–1148 |
| **DEC-005** | Seven Negative Stock Balances & Omitted Scrap | `PENDING_REVIEW` | Physical stocktake not yet executed |
| **DEC-006** | Template Dummy Rows Purged (Row 2) | `PENDING_REVIEW` | Manifest generator script filter not yet committed |
| **DEC-007** | Furnace Charge Deficit (18 Heats with 0 Charge)| `PENDING_REVIEW` | Missing paper heat sheets or quarantine authorization |
| **DEC-008** | Legacy Archive Future Dates (2026-11-07) | `PENDING_REVIEW` | Missing IT archive retirement memorandum |

**Scorecard:** **0 of 8 Approved** (All 8 remain strictly `PENDING_REVIEW`).

### 4.2 Acceptance Gate Status Summary (13 Gates)
| Gate ID | Area / Scope | Current Status | Evaluation Finding |
| :--- | :--- | :--- | :--- |
| **G1** | Executive Decision Sign-Off | `BLOCKED` | Awaiting physical signatures on DEC-001 through DEC-008 |
| **G2** | Cutoff Policy Authorization | `BLOCKED` | Awaiting executive policy memorandum adopting Scenario A |
| **G3** | Commercial Purchase Rates | `BLOCKED` | Awaiting certified vendor tax invoice schedule |
| **G4** | Item Master Additions | `BLOCKED` | Awaiting approval of MNT-CN-001 and MCS-CN-002 |
| **G5** | Scrap Metallurgy Certification | `BLOCKED` | Awaiting lab OES test certificate for 15,200 kg scrap |
| **G6** | Issue Date Typo Authorization | `BLOCKED` | Awaiting physical store slips audit for date 2026-07-16 |
| **G7** | Certified Physical Stocktake | `BLOCKED` | Awaiting physical stocktake execution as of 12-Oct cutoff |
| **G8** | Template Dummy Rows Purged | `BLOCKED` | Awaiting script update filtering row 2 from manifest |
| **G9** | Furnace Heat Log Quarantine | `BLOCKED` | Awaiting melt deck sheets or signed quarantine order |
| **G10** | Legacy Archive Formally Retired | `BLOCKED` | Awaiting formal IT policy retirement memo |
| **G11** | Source Hashes Re-Verified | **`VERIFIED`** | **100% SHA-256 match on all 5 workbooks and freeze archive** |
| **G12** | PostgreSQL Non-Prod Verification | `BLOCKED` | Container unprovisioned; Alembic unapplied on PG |
| **G13** | Backup Rehearsal Certified | `BLOCKED` | Blocked downstream of Gate G12 provisioning |

**Scorecard:** **1 of 13 Satisfied** (Gate `G11` is Verified; Gates `G1`–`G10` and `G12`–`G13` remain `BLOCKED`).

---

## 5. The Critical Path to Migration Readiness

The critical path governs the minimum sequence of dependent events required before write-enabled Stage 3 migration can be proposed:

```
[TRK-06: DEC-002 Executive Policy Mandate (Scenario A)]
                          │
                          ▼
[TRK-05: SOP-P7-PHYSICAL-STOCKTAKE Execution (12-Oct Cutoff)]
                          │
                          ▼
[TRK-05: Sheet D Certified Opening Inventory Realized]
                          │
                          ▼
[TRK-01: Commercial Invoice Rates Certified (DEC-001)]
                          │
                          ▼
[G1: Executive Management Sign-Off Package Executed]
                          │
                          ▼
[TRK-07: PostgreSQL Provisioned on Port 5439 (Gate G12)]
                          │
                          ▼
[TRK-07: Backup & Restore Rehearsal Certified (Gate G13)]
                          │
                          ▼
[ALL 13 GATES SATISFIED -> STAGE 3B LIVE MIGRATION REQUEST]
```

---

## 6. Next Three Safe Actions

To methodically advance evidence collection without violating read-only constraints:

1. **Action 1 (Executive Review Session):** Managing Director and Plant Head convene to deliberate on the six executive questions in [`DEC002_EXECUTIVE_DECISION_BRIEF.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage3a4/DEC002_EXECUTIVE_DECISION_BRIEF.md) and execute the Decision Record Template to unblock **`TRK-06` (DEC-002)**.
2. **Action 2 (Commercial & Docket Physical Audit):**
   - Finance Department pulls vendor tax invoices for historical GRN rows 2–5 to unblock **`TRK-01` (DEC-001)**.
   - Stores Department inspects hardcopy store issue slips 327–1148 to unblock **`TRK-02` (DEC-004)**.
3. **Action 3 (Scrap Testing & Stocktake Mobilization):**
   - Foundry Quality Lab pulls a physical sample of the 15,200 kg CRCA scrap and executes optical emission spectrometry testing to unblock **`TRK-03` (DEC-003)**.
   - Stores and Plant leadership initiate physical stocktake site preparations (tag printing, scale calibrations, quarantine bay marking) per [`PHYSICAL_STOCKTAKE_PROTOCOL.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stocktake_preparation/PHYSICAL_STOCKTAKE_PROTOCOL.md).

---

## 7. Safety Attestation & Stop Conditions

### Operational Attestation:
- **Zero Database Operations:** No database records, stock ledger postings, or opening balances were created.
- **Zero Infrastructure Changes:** No Docker containers were started, stopped, or altered. Host port 5432 and external services remain untouched.
- **Documentation Only:** This tracker records evidence status. All unverified evidence fields remain marked as missing or blank.
- **Prohibition Enforced:** **Stage 3B live historical migration remains strictly unauthorized until all 13 Acceptance Gates are certified in writing.**
