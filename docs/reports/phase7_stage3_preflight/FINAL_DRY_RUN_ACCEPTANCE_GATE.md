# VSPL Material Management & Costing System — Final Dry-Run Acceptance Gate

**Document ID:** `DOC-P7-S3A-ACCEPTANCE-GATE`  
**System:** VSPL Material Management & Costing System  
**Date:** 2026-10-17  
**Governance Scope:** Mandatory Pre-Requisite Conditions for Future Write-Enabled Migration  
**Status:** **GATE ACTIVE (BLOCKED) — 0 OF 13 ACCEPTANCE GATES SATISFIED**  

---

## 1. Executive Purpose

This document establishes the definitive, non-negotiable **13-Point Acceptance Gate** that must be fully satisfied and signed off before any write-enabled migration script can be proposed, scheduled, or executed for Vijay Spheroidals Pvt. Ltd. (VSPL).

### Fundamental Rule:
> [!IMPORTANT]
> **No Premature Readiness Declarations:**  
> A high percentage of syntactically valid rows (e.g. 510 of 616 candidate rows) does **not** constitute migration readiness. A single unapproved rate, an unresolved negative balance, or an ambiguous metallurgical grade invalidates live inventory and financial costing.

---

## 2. The 13-Point Pre-Flight Acceptance Checklist

Every single condition below must be verified and supported by documentary evidence:

```
+----+------------------------------------+---------------------------------------------------------------+-------------------+----------------+
| #  | Governance Gate Area               | Mandatory Acceptance Condition                                | Verifying Lead    | Current Status |
+----+------------------------------------+---------------------------------------------------------------+-------------------+----------------+
| G1 | Executive Decision Sign-Off        | DEC-001 through DEC-008 formally signed by accountable leads  | Managing Director | BLOCKED        |
| G2 | Cutoff Policy Authorization        | Scenario A formally authorized; 82-day void policy certified   | Plant Head        | BLOCKED        |
| G3 | Commercial Purchase Rates          | Verified ex-GST invoice rates provided for GRNs and Item Master| Finance Head      | BLOCKED        |
| G4 | Item Master Additions              | MNT-CN-001 and MCS-CN-002 formally created in Item Master     | Stores Manager    | BLOCKED        |
| G5 | Scrap Metallurgy Certification     | Spectrometry report classifying 15,200 kg scrap grade (007/008)| Foundry Met       | BLOCKED        |
| G6 | Issue Date Typo Authorization      | Physical store slips audited; date 2026-07-16 sign-off signed | Stores Manager    | BLOCKED        |
| G7 | Certified Physical Stocktake       | Certified 12-Oct-2026 physical stocktake executed per SOP-P7  | Plant Head        | BLOCKED        |
| G8 | Template Dummy Rows Purged         | Row 2 records formally purged from migration manifest         | Systems Architect | BLOCKED        |
| G9 | Furnace Heat Log Quarantine        | Incomplete heats on 22-Jul quarantined in staging preview     | Foundry Head      | BLOCKED        |
| G10| Legacy Archive Formally Retired    | Store Inventory.xlsx formally excluded from operational import | IT Head           | BLOCKED        |
| G11| Source Hashes Re-Verified          | All 5 Excel workbook hashes match baseline SHA-256 digests    | Lead QA Auditor   | VERIFIED       |
| G12| PostgreSQL Non-Prod Verification   | Dedicated PG 16 instance running; Alembic upgrade verified    | Lead DBA          | BLOCKED        |
| G13| Backup Rehearsal Certified         | Pre-migration backup taken; restore rehearsal certified       | Systems Architect | BLOCKED        |
+----+------------------------------------+---------------------------------------------------------------+-------------------+----------------+
```

---

## 3. Detailed Gate Criteria & Required Evidence

### Gate G1 to G3: Commercial & Executive Clearance
1. **Decision Sign-off (G1):** The Managing Director, Plant Head, and Finance Head must affix physical/digital signatures to [`docs/reports/phase7_management_signoff/MANAGEMENT_SIGNOFF_TEMPLATE.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_management_signoff/MANAGEMENT_SIGNOFF_TEMPLATE.md).
2. **Cutoff Policy (G2):** Written adoption of Scenario A (Historical Audit Archive & Certified Physical Cutoff) as executive policy.
3. **Commercial Invoice Rates (G3):** Original supplier tax invoices verified for ex-GST base prices to support Phase 6 Rule C1 weighted-average calculations.

### Gate G4 to G6: Master Data & Store Operational Integrity
4. **Master Creation (G4):** Items `MNT-CN-001` (3306PMKT-Generator) and `MCS-CN-002` (Tool Post) approved via Phase 2 Item Request workflow.
5. **Spectrometry Testing (G5):** Lab analysis certificate signed by the chief metallurgist classifying CRC scrap manganese content (0.15–0.25% vs 0.35–0.50%).
6. **Date Slips Audit (G6):** Physical issue slips 327, 910, 325, 1149, 326, 2725, and 1148 inspected in hardcopy archive to prove date normalization to `2026-07-16`.

### Gate G7 to G10: Physical Stock & Historical Cleansing
7. **Physical Stocktake (G7):** Double-blind physical count executed per [`PHYSICAL_STOCKTAKE_PROTOCOL.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stocktake_preparation/PHYSICAL_STOCKTAKE_PROTOCOL.md), establishing certified opening quantities on Sheet D of `VSPL_Physical_Stocktake_Register.xlsx`.
8. **Dummy Row Purge (G8):** Generator script updated to filter out template sample row 2 under DEC-006.
9. **Heat Log Staging Quarantine (G9):** Heat records for 22-Jul held in staging preview tables; zero furnace charges posted to live production tables until paper logs are retrieved.
10. **Legacy Archive Exclusion (G10):** Written sign-off retiring `Store Inventory.xlsx` from operational migration under DEC-008.

### Gate G11 to G13: Technical & Database Infrastructure
11. **Cryptographic Verification (G11):** Source workbook hashes matching baseline SHA-256 digests immediately prior to execution.
12. **Dedicated PostgreSQL Verification (G12):** Isolated PostgreSQL 16 non-production database provisioned, `alembic upgrade head` executed successfully, and regression test suite passing against PostgreSQL.
13. **Backup Rehearsal (G13):** Pre-migration `pg_dump` binary backup executed and successfully restored into a scratch database with 36 tables verified.

---

## 4. Final Verdict & Stop Condition

- **Current Status:** **GATE LOCKED (BLOCKED).**
- **Readiness Score:** **1 of 13 gates satisfied** (G11 Cryptographic Hashes verified; G1–G10 and G12–G13 remain blocked).
- **Prohibition:** Phase 7 Stage 3 live migration remains **strictly unauthorized** until all 13 gates are certified in writing.
