# VSPL Material Management & Costing System — Phase 7 Stage 2.1 Readiness Summary

**Document ID:** `DOC-P7-S2-1-READINESS`  
**Audit Scope:** Historical Data Migration Readiness & Classification Reconciliation  
**Date:** 2026-10-13  
**Status:** AUDIT COMPLETE — LIVE MIGRATION BLOCKED PENDING DECISIONS  

---

## 1. Executive Migration Readiness Position

**Current Live Migration Readiness:** **0% (BLOCKED)**  
*No historical transactions can be imported into the live application database, posted to the inventory ledger, or used for weighted-average valuation at this stage.*

All 616 operational manifest rows and secondary legacy records are subject to blocking governance decisions, incomplete commercial evidence, or cut-off policy ambiguities:
1. **Commercial Rates:** 0 of 4 historical GRN receipts have commercial ex-GST purchase rates (DEC-001).
2. **Cutoff Policy:** 82-day data void between July 2026 transactions and the 12-Oct-2026 costing start date has no approved policy (DEC-002).
3. **Item Master Mapping:** 3 GRN descriptions lack approved canonical item master records; 1 is chemically ambiguous (DEC-003).
4. **Date Integrity:** 12 physical Issue rows contain literal year typo `7-16-20236` (DEC-004).
5. **Negative Balances:** 7 raw materials display negative closing balances due to furnace charges being posted as store issues without opening balances (DEC-005).
6. **Template Artifacts:** Row 2 in all transaction sheets contains dummy sample template data with legacy document collisions (DEC-006).
7. **Furnace Mass Balances:** 18 of 19 heats record 0 kg charge against 500+ kg metal tapped (DEC-007).
8. **Legacy Code Corruption:** Legacy spreadsheets contain corrupt item codes and future-dated receipt strings (DEC-008).

---

## 2. Reconciled Manifest Classification Crosswalk

### 2.1 Explanation of Discrepancies between Stage 1, Stage 2, and Recheck Counts

The previous Stage 2 report cited:
- **Primary Classifications:** 545 `VALID_NEW_CANDIDATE`, 31 `MANUAL_REVIEW`, 37 `INVALID_SOURCE`, 3 `UNMAPPED` (Sum = 616).
- **Readiness Classifications:** 515 `ELIGIBLE`, 66 `PENDING_REVIEW`, 35 `BLOCKED` (Sum = 616).

These totals differed because **Primary Classification** and **Readiness Status** represent two distinct, overlapping dimensions evaluated by different business rules:
- **Primary Classification** reflects row-level syntactic and schema validity.
- **Readiness Status** reflects operational suitability for ledger posting, incorporating external decision blockers.

#### Dimensional Reconciliation Matrix (Stage 2 Manifest):

| Primary Classification | ELIGIBLE | PENDING_REVIEW | BLOCKED | Total |
|---|---|---|---|---|
| **VALID_NEW_CANDIDATE** | **515** | **30** *(a)* | 0 | **545** |
| **MANUAL_REVIEW** | 0 | **31** *(b)* | 0 | **31** |
| **INVALID_SOURCE** | 0 | **2** *(c)* | **35** *(d)* | **37** |
| **UNMAPPED** | 0 | **3** *(e)* | 0 | **3** |
| **Total** | **515** | **66** | **35** | **616** |

**Specific Reconciliation Drivers:**
- *(a) 545 Candidate vs 515 Eligible (Difference = 30):*
  - Exactly 30 rows classified as `VALID_NEW_CANDIDATE` were held in `PENDING_REVIEW`:
    - 1 GRN row (Row 2, Emery Paper) held due to missing rate (DEC-001).
    - 19 Heat Log rows held due to furnace reconciliation dependencies (DEC-002, DEC-005).
    - 10 Charge Details rows held due to unlogged heats and mass balance gaps (DEC-002, DEC-005).
  - $545 - 30 = 515\text{ ELIGIBLE}$.
- *(b) 31 Manual Review Rows:*
  - Comprises 10 Issue rows with year typo, 4 Waste rows with missing dates/notes, and 17 Parts Produced rows with missing parts data. All 31 map to `PENDING_REVIEW`.
- *(c) & (d) 37 Invalid Source vs 35 Blocked (Difference = 2):*
  - 34 Issue rows with zero quantity and 1 Waste row with destroyed null quantity map to `BLOCKED` ($34 + 1 = 35$).
  - 2 GRN rows (Rows 4 & 5, Tool Post and crca scrap) have multiple fatal defects: missing date, missing GRN number, missing rate, and unmapped codes. The Stage 2 generator classified them as `INVALID_SOURCE` but assigned readiness `PENDING_REVIEW` under DEC-001/DEC-003. Hence, $37 - 2 = 35\text{ BLOCKED}$.
- *(e) 3 Unmapped Rows:*
  - Comprises 1 GRN row (Row 3, 3306PMKT-Generator) and 2 Issue rows (Rows 537 & 538, cable and plug). All 3 map to `PENDING_REVIEW` under DEC-003 and DEC-004.

---

## 3. Rigorous Audit Recheck Classification

Stage 2.1 re-evaluated all 616 rows with strict precedence, resolving evaluation-order defects in previous scripts:
- **Evaluation Precedence:** `INVALID_SOURCE` > `UNMAPPED` > `CONFLICT` > `MANUAL_REVIEW` > `VALID_NEW_CANDIDATE`.
- **Readiness Governance:** No row is marked ELIGIBLE while cutoff policy (DEC-002) is unapproved.

### Recheck Cross-Tabulation:

| Recheck Primary Classification | BLOCKED_SOURCE_DEFECT | HELD_MANUAL_REVIEW | HELD_PENDING_DECISION | ROW_CLEAN_PENDING_CUTOFF_POLICY | Total |
|---|---|---|---|---|---|
| **INVALID_SOURCE** | 38 | 0 | 0 | 0 | **38** |
| **UNMAPPED** | 0 | 3 | 0 | 0 | **3** |
| **CONFLICT** | 0 | 2 | 0 | 0 | **2** |
| **MANUAL_REVIEW** | 0 | 63 | 0 | 0 | **63** |
| **VALID_NEW_CANDIDATE** | 0 | 0 | 163 | 347 | **510** |
| **Total** | **38** | **68** | **163** | **347** | **616** |

**Key Recheck Observations:**
1. **Clean Rows Pending Cutoff Policy (347 rows):** 347 Issue rows have valid document numbers, valid item codes, valid quantities, valid dates, and no negative-stock item references. They are syntactically clean but cannot post until management approves a cutoff policy.
2. **Held Pending Decision (163 rows):** 163 Issue rows reference raw materials currently in negative stock (FDY-RM-008, FDY-RM-017, FDY-RM-020). Posting these issues without resolving opening balances would immediately drive live ledger balances further negative.
3. **Held for Manual Review (68 rows):** Includes 12 date-typo rows, 4 unmapped/ambiguous items, 2 conflicting document rows (GRN row 2 and Parts row 2), 19 heat log rows, 10 charge detail rows, 17 parts rows, and 4 waste rows.
4. **Blocked Source Defects (38 rows):** Includes 34 zero-quantity issue rows, 1 null-quantity waste row, 2 undated/unnumbered GRN rows, and 1 zero-quantity parts row.

---

## 4. Cutoff-Policy Scenario Analysis (Costing Start Date: 12-Oct-2026)

The application configuration defines:
```python
COSTING_START_DATE = date(2026, 10, 12)
```
Historical source records span **08-Jul-2026 to 22-Jul-2026**, followed by an **82-day undocumented void** (23-Jul-2026 to 11-Oct-2026). Management must choose one of three policy scenarios.

### Scenario A: Historical Audit Archive (Read-Only)
- **Concept:** July 2026 records are ingested into dedicated read-only historical archive tables (`historical_migration_archive`) without posting any entries to the live append-only inventory ledger.
- **Cutoff Treatment:** Live ledger posting commences strictly on **12-Oct-2026** using an independently audited physical stock count as Opening Balance.
- **Required Source Evidence:**
  - Approved physical inventory stocktake conducted as of 12-Oct-2026 (or nearest weekend).
  - Approved valuation rates for opening stock.
- **Stock & Costing Effects:**
  - Preserves ledger invariants: ZERO risk of negative stock or unposted movement distortions.
  - Weighted-average costing begins cleanly on 12-Oct-2026 based on verified opening valuation.
  - Zero retroactive cost journal postings.
- **Risks & Limitations:** July transactions cannot be viewed in standard live operational screens; they reside in historical inquiry views.
- **Required Approvals:** Managing Director, Finance Head.
- **Implementation Support:** Fully supported by current architecture without schema changes.

### Scenario B: Reconstructed Opening Position as of 12-Oct-2026
- **Concept:** Reconstruct inventory balances from July transactions forward to October, accounting for intervening movements.
- **Cutoff Treatment:** July transactions are posted to the ledger, but intervening movements across August and September must be provided and posted.
- **Required Source Evidence:**
  - Complete August and September GRN, Issue, and Scrap registers (currently missing from electronic files).
  - Purchase invoices for all intervening receipts.
- **Stock & Costing Effects:**
  - Enables historical cost reconstruction back to July 2026.
  - High risk of inventory ledger divergence if any intervening movement is missing or miscalculated.
- **Risks & Limitations:** **EXTREME RISK.** Current electronic files contain zero records for August or September 2026. Reconstructing an 82-day period without primary records violates audit standards.
- **Required Approvals:** Statutory Auditor, Managing Director, Finance Head.
- **Implementation Support:** Current codebase supports ledger posting, but execution is physically blocked by the complete absence of August/September source data.

### Scenario C: Two-Phase Transition (Staged Movement Import where Evidence Supports)
- **Concept:** Import validated July transactions into a staged sandbox ledger to simulate July closing balances. Use July closing balances as preliminary working figures for plant operations, followed by a formal reconciliation adjustment against the 12-Oct-2026 stocktake.
- **Cutoff Treatment:** July transactions posted with effective dates in July 2026. An opening adjustment entry posted on 12-Oct-2026 reconciles the difference between simulated July closing and audited October opening.
- **Required Source Evidence:**
  - Resolving DEC-001 (GRN rates), DEC-003 (mappings), DEC-004 (date typo), and DEC-005 (opening stock).
  - Full physical stocktake on 12-Oct-2026 to calculate the variance.
- **Stock & Costing Effects:**
  - Generates ledger entries for July, creating preliminary cost figures.
  - Variance between July closing and October opening must be absorbed as an unclassified inventory adjustment, potentially distorting consumption cost.
- **Risks & Limitations:** Ledger invariants may be violated if July stock goes negative before October adjustments.
- **Required Approvals:** Plant Head, Cost Accountant, Finance Head.
- **Implementation Support:** Supported by ledger schema, but requires extensive human verification.

---

## 5. Migration Blocking Issues Summary

| Issue Reference | Nature of Blocker | Impacted Rows | Responsible Owner | Next Action |
|---|---|---|---|---|
| **DEC-001** | Missing Commercial Purchase Rates | 4 GRN rows | Finance Head | Audit vendor invoices (Invoices 096, GMP2926002828, 454, 384) |
| **DEC-002** | 82-Day Costing Cutoff Gap | All 616 rows | Managing Director | Formally select Scenario A, B, or C |
| **DEC-003** | Unmapped Items & Scrap Ambiguity | 3 GRN rows | Stores / Metallurgist | Approve `MNT-CN-001`, `MCS-CN-002`; assign grade for `crca scrap` |
| **DEC-004** | Issue Year Typo (`7-16-20236`) | 12 Issue rows | Stores Manager | Formally confirm normalization to `2026-07-16` |
| **DEC-005** | Negative Stock Balances | 7 Items (163 Issue rows) | Plant Head | Physical stock count; enforce Rule H1 (segregate furnace charges) |
| **DEC-006** | Template Dummy Rows (Row 2) | 3 Rows | Systems Architect | Authorize exclusion of template sample rows |
| **DEC-007** | Furnace Mass Balance Deficit | 19 Heats, 10 Charges | Foundry Head | Provide physical heat log sheets for 22-Jul-2026 |
| **DEC-008** | Corrupt Legacy Sheet References | Legacy Archive | IT Auditor | Authorize permanent exclusion of legacy spreadsheets |

---

## 6. Audit Recommendation

**The Senior Migration Auditor recommends Scenario A (Historical Audit Archive):**
1. Do not post July 2026 records to the live append-only inventory ledger.
2. Ingest July 2026 records into read-only audit tables for historical traceability.
3. Conduct a physical stock count as of 12 October 2026, approved by the Plant Head and Finance Head.
4. Establish live ledger opening balances on 12 October 2026 using verified stock quantities and audited valuation rates.
5. Begin live transactions and weighted-average costing from 12 October 2026 forward.
