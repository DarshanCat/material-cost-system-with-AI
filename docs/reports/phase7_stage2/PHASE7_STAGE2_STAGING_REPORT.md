# VSPL Material Management & Costing System — Phase 7 Stage 2 Staging & Governance Report
**Staged Migration Preparation, Decision Register & Human-Supervised Validation**

* **Report Date:** 10 October 2026
* **Execution Status:** STAGE 2 STAGING COMPLETE — ZERO APPLICATION WRITES PERFORMED
* **Architect / Lead:** Senior Data Migration Architect & Database Integrity Engineer
* **Target Environment:** Vijay Spheroidals Pvt. Ltd. (VSPL), Bangalore

---

## 1. Executive Summary

In accordance with strict data integrity requirements for VSPL's foundry material management system, **Stage 2: Staged Migration & Human-Supervised Validation** has been successfully established as an **isolated, read-only staging workflow**.

No records have been written to the live application database, no stock ledger entries have been created, and no historical transactions have been reposted. All proposed mappings, duplicate detections, and anomaly classifications have been encapsulated into durable review artifacts.

---

## 2. Hard Safety Boundary Compliance

1. **Zero Database Modifications:** No `INSERT`, `UPDATE`, or `DELETE` SQL operations were executed against any database.
2. **Zero Stock Movement Postings:** No stock ledger entries were created. Existing append-only ledger history remains untouched.
3. **No Synthetic Rate or Quantity Generation:** Missing rates, prices, and quantities remain explicitly marked as missing.
4. **No Automatic Fuzzy Merges:** Unmapped items are held for human approval rather than automatically coerced.
5. **Durable Review Artifacts:** All staging results are stored as standalone CSV and Markdown documents in `docs/reports/phase7_stage2/`.

---

## 3. Migration Decision Register (The 5 Critical Blockers)

A durable decision register governing all five critical blockers was established in:
- [`docs/reports/phase7_stage2/migration_decision_register.csv`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2/migration_decision_register.csv)
- [`docs/reports/phase7_stage2/MIGRATION_DECISION_REGISTER.md`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2/MIGRATION_DECISION_REGISTER.md)

| Issue ID | Problem Summary | Source Location | Decision Status | Required Approver | Migration Impact |
|---|---|---|---|---|---|
| **DEC-001** | Missing commercial ex-GST rates on GRN receipts | `VSPL_Material_Entry.xlsx` $\rightarrow$ `3. Receipt GRN` (Rows 2–5) | `PENDING_REVIEW` | Finance Head / Purchase Head | **BLOCKING for live costing.** Staging allows physical tracking; costing engine requires purchase rates. |
| **DEC-002** | July 2026 transactions treatment vs 12-Oct-2026 cutoff | Spans all operational sheets (`2026-07-08` to `2026-07-22`) | `PENDING_REVIEW` | Managing Director / Architect | **BLOCKING.** Requires decision whether July data is an audit archive or rolled into opening physical stock on 12-Oct. |
| **DEC-003** | 3 Unmatched GRN item descriptions (`'NOT FOUND'`) | `3. Receipt GRN`: `3306PMKT-Generator`, `Tool Post`, `crca scrap` (15,200 kg) | `PENDING_REVIEW` | Stores Manager / Plant Head | **BLOCKING.** Map to proposed codes (`MNT-CN-001`, `MCS-CN-002`, `FDY-RM-008`). |
| **DEC-004** | Date string typo `'7-16-20236'` in 12 issue rows | `4. Issue` (Rows 537–548) | `PENDING_REVIEW` | Stores Supervisor / QA Lead | **NON-BLOCKING once approved.** Parse as `2026-07-16` with audit remark. |
| **DEC-005** | 7 Negative closing stocks in interim master ledger | `VSPL_Master_Ledger.xlsx` & `Charge Details` (Heat `H-260714-01`) | `PENDING_REVIEW` | Plant Head / Inventory Auditor | **BLOCKING.** Furnace charges must not be posted as store issues (Rule H1 / Rule C5). |

---

## 4. Proposed Migration Manifest Analysis

The staging engine parsed and evaluated **616 operational transaction rows** across issues, receipts, waste, heats, and charge lines.

The complete manifest is available in [`docs/reports/phase7_stage2/proposed_migration_manifest.csv`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2/proposed_migration_manifest.csv).

### Manifest Classification Breakdown:
- **`VALID_NEW_CANDIDATE`:** **545 rows (88.5%)**
  - Conforms to schema, item codes resolve to canonical Item Master, dates and quantities valid.
- **`MANUAL_REVIEW`:** **31 rows (5.0%)**
  - 12 rows with date typo `'7-16-20236'` (DEC-004)
  - 17 parts produced rows with missing unit cast weight
  - 2 waste disposition rows with missing dates/slip numbers
- **`INVALID_SOURCE`:** **37 rows (6.0%)**
  - 34 issue rows with zero, negative, or malformed quantities
  - 3 rows with unparseable data
- **`UNMAPPED`:** **3 rows (0.5%)**
  - 3 GRN receipt rows with `'NOT FOUND'` item code (DEC-003)

### Migration Readiness Status:
- **ELIGIBLE (Clean candidate rows ready for staged commit upon approval):** **515 rows**
- **PENDING_REVIEW (Held awaiting Decision Register sign-off):** **66 rows**
- **BLOCKED (Corrupted / non-conforming source rows):** **35 rows**

---

## 5. Technical Environment & Regression Testing

- **Backend Test Suite:** Executed full regression suite (`pytest backend/tests -v`). **68/68 tests passed (100% pass rate)**.
- **Database Status:** PostgreSQL offline state respected; zero writes executed.
- **Repeatability:** Re-running `phase7_stage2_manifest_generator.py` produces identical deterministic outputs and hashes.

---

## 6. Stop Condition & Recommended Next Action

In accordance with Section 8 Stop Conditions, **execution has stopped prior to any database write or data import**.

### Recommended Next Action:
1. VSPL Management reviews the decision register at [`docs/reports/phase7_stage2/MIGRATION_DECISION_REGISTER.md`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_stage2/MIGRATION_DECISION_REGISTER.md).
2. Once sign-offs on DEC-001 through DEC-005 are recorded, proceed to **Phase 7 Stage 3: Controlled Batch Import with Database Pre-flight Checks**.
