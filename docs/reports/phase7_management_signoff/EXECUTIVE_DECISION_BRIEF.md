# VSPL Material Management & Costing System — Phase 7 Executive Decision Brief

**Document ID:** `DOC-P7-EXEC-DECISION-BRIEF`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd. (SG Iron Foundry & Machine Shop, Peenya, Bangalore)  
**Governance Scope:** Executive Leadership Briefing for Phase 7 Migration Decisions (DEC-001 through DEC-008)  
**Date:** 2026-10-13  
**Status:** **PENDING FORMAL MANAGEMENT REVIEW & SIGN-OFF — LIVE MIGRATION STRICTLY UNAUTHORIZED**  

---

## 1. Executive Purpose & Project Status

This briefing presents the executive leadership of Vijay Spheroidals Pvt. Ltd. (Managing Director, Plant Head, Finance Head, Operations Heads) with the verified facts, risks, decision alternatives, and governance boundaries required to resolve eight outstanding data migration decisions (DEC-001 through DEC-008).

### Current Project Milestone Status:
- **Phases 1–6 (Core ERP Application):** Successfully completed, verified, and committed to repository master branch (`dd85bcc`). All 68 backend regression tests pass. The application shell, append-only inventory ledger, furnace heat logging, weighted-average costing, and role-based access control engines are fully implemented and verified.
- **Phase 7 (Historical Data Migration & Reconciliation):**
  - **Stage 1 (Read-Only Dry Run):** Completed. 3,675 non-empty rows across five historical workbooks audited; initial variances documented.
  - **Stage 2 (Staged Manifest & Decision Register):** Completed. 616 operational transaction rows staged.
  - **Stage 2.1 (Audit Reconciliation & Final QA):** Completed and permanently frozen in an immutable package (`VSPL_Phase7_Stage2_1_Evidence_Freeze_20261013.zip`, verified SHA-256: `033684d8b26dc65e9c67b569e48991b07c0d0909c2cc37717b5d3485d922c5c5`).
- **Live Historical Migration Readiness:** **0% (BLOCKED).**
- **Phase 7 Stage 3 (Live Database Import & Ledger Posting):** **STRICTLY UNAUTHORIZED.**

---

## 2. Summary of Decisions Requiring Leadership Attention

Management action is required across eight specific operational and financial areas:

```
+----------+--------------------------------------------------------------+---------------------------------------+---------------------+
| Decision | Title & Scope                                                | Accountable Authority                 | Governance Category |
+----------+--------------------------------------------------------------+---------------------------------------+---------------------+
| DEC-001  | Missing Historical Commercial Purchase Rates (GRN Rows 2–5)  | Finance Head / Purchase Head          | Financial Valuation |
| DEC-002  | Historical Data vs 12-Oct-2026 Costing Cutoff (82-Day Void)  | Managing Director / Plant Head        | Executive Policy    |
| DEC-003  | Unmapped GRN Items & Ambiguous Scrap Grade (007 vs 008)      | Plant Head / Metallurgist             | Master Data / Chem  |
| DEC-004  | Suspected Issue Date Typo (7-16-20236 across Rows 537–548)   | Stores Manager                        | Inventory Control   |
| DEC-005  | Seven Negative Stock Balances & 11,793 kg Omitted Issues     | Plant Head / Inventory Auditor        | Physical Stocktake  |
| DEC-006  | Sample Template Dummy Rows (Row 2 across Sheets)             | Stores Manager / Systems Architect    | Data Cleansing      |
| DEC-007  | Furnace Heat Log Integrity Deficit (18 Heats with 0 Charge)  | Foundry Head / Metallurgist           | Production Audit    |
| DEC-008  | Legacy Store Inventory Inconsistency & Future Stored Dates   | IT Head / Inventory Auditor           | Archive Governance  |
+----------+--------------------------------------------------------------+---------------------------------------+---------------------+
```

---

## 3. Principal Inventory, Costing, and Migration Risks

If historical records are imported into the live system prematurely without formal management resolution:

1. **Negative Inventory Contagion (Severe Operational Risk):**
   - The interim Master Ledger shows negative balances for 7 raw materials because furnace charges were subtracted directly as store issues without opening inventory.
   - Posting these movements into the append-only ledger without an audited physical opening stocktake would violate core ledger invariants and permanently distort stock availability.
2. **Weighted-Average Costing Corruption (Severe Financial Risk):**
   - Under Phase 6 Rule C1, inventory valuation requires commercial ex-GST purchase rates. With zero rates available in historical GRNs or Item Master, moving average rates cannot be computed. Consumed materials and cast parts would inherit zero valuation, corrupting financial statements.
3. **The 82-Day Inventory Void (Severe Audit & Compliance Risk):**
   - Electronic transaction records cease on 22-Jul-2026. Live system go-live is 12-Oct-2026. Zero electronic records exist for August or September 2026.
   - Attempting to use July 2026 closing balances as October 2026 opening balances without accounting for 82 days of plant consumption violates statutory manufacturing audit standards.
4. **Metallurgical Grade Misallocation (Production Quality Risk):**
   - Auto-mapping 15,200 kg of `crca scrap` to `FDY-RM-008` (Low MN) when it could be `FDY-RM-007` (Low High MN) risks incorrect manganese recovery calculations during furnace melting.

---

## 4. Decision Dependencies & Sequencing

Decisions are interconnected and should be addressed in the following logical sequence:

```
                      ┌────────────────────────────────────────────────────────┐
                      │    STEP 1: EXECUTIVE CUTOFF POLICY SIGN-OFF (DEC-002)  │
                      │    Select Scenario A (Historical Archive - Recommended)│
                      └───────────────────────────┬────────────────────────────┘
                                                  │
         ┌────────────────────────────────────────┴────────────────────────────────────────┐
         │                                                                                 │
         ▼                                                                                 ▼
┌─────────────────────────────────┐                               ┌─────────────────────────────────┐
│ STEP 2: PHYSICAL AUDIT (DEC-005)│                               │ STEP 3: MASTER DATA (DEC-003)   │
│ Conduct plant-wide stocktake on │                               │ Approve MNT-CN-001 & MCS-CN-002;│
│ cutoff date; certify valuation. │                               │ Chemically classify scrap.      │
└────────────────┬────────────────┘                               └────────────────┬────────────────┘
                 │                                                                 │
                 └────────────────────────────────┬────────────────────────────────┘
                                                  │
                                                  ▼
                      ┌────────────────────────────────────────────────────────┐
                      │ STEP 4: OPERATIONAL CLEANSING (DEC-001, 004, 006, 007, 008)│
                      │ - Audit vendor invoices for ex-GST rates (DEC-001)     │
                      │ - Normalize issue dates with Stores sign-off (DEC-004) │
                      │ - Purge dummy sample row 2 records (DEC-006)           │
                      │ - Quarantine incomplete furnace heats (DEC-007)        │
                      │ - Formally retire legacy spreadsheets (DEC-008)        │
                      └───────────────────────────┬────────────────────────────┘
                                                  │
                                                  ▼
                      ┌────────────────────────────────────────────────────────┐
                      │ STEP 5: TECHNICAL EXECUTION AUTHORIZATION (LAYER 2)    │
                      │ Written authorization for staging import & dry run.    │
                      └────────────────────────────────────────────────────────┘
```

---

## 5. Non-Negotiable Safety Boundaries & Next Steps

> [!CAUTION]
> **PHASE 7 STAGE 3 (LIVE MIGRATION & DATABASE WRITES) REMAINS STRICTLY UNAUTHORIZED.**  
> - Business approval of DEC-001 through DEC-008 does **NOT** automatically authorize live database importing.
> - Technical deployment requires a separate, explicit operational mandate following database backup verification and staging test execution.

### Next Actions for Executive Leadership:
1. Review the detailed briefs in [`MANAGEMENT_DECISION_BRIEFS.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_management_signoff/MANAGEMENT_DECISION_BRIEFS.md).
2. Review the scenario analysis in [`CUTOFF_SCENARIO_COMPARISON.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_management_signoff/CUTOFF_SCENARIO_COMPARISON.md).
3. Execute the physical inventory count protocol in `docs/reports/phase7_management_review/OPENING_INVENTORY_EVIDENCE_CHECKLIST.md`.
4. Record formal business decisions using [`MANAGEMENT_SIGNOFF_TEMPLATE.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_management_signoff/MANAGEMENT_SIGNOFF_TEMPLATE.md).
