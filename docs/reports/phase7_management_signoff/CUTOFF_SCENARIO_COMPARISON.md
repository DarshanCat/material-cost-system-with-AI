# VSPL Material Management & Costing System — Cutoff Scenario Comparison

**Document ID:** `DOC-P7-CUTOFF-SCENARIO-COMPARISON`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd. (SG Iron Foundry & Machine Shop, Peenya, Bangalore)  
**Governance Scope:** Evaluation of Historical Cutoff Policy Alternatives (DEC-002)  
**Date:** 2026-10-13  
**Status:** **OBJECTIVE ANALYSIS FOR EXECUTIVE REVIEW — ZERO PRE-SELECTED POLICY**  

---

## 1. Executive Context & The Cutoff Dilemma

The live costing start date is established in core application configuration:
```python
COSTING_START_DATE = date(2026, 10, 12)
```

### The Electronic Evidence Timeline:
- **08-Jul-2026 to 22-Jul-2026:** All 616 electronic operational transaction records occur in this 15-day window (558 Issues, 4 GRNs, 6 Waste notes, 19 Heats).
- **15-Jul-2026:** Interim Master Ledger balance formula was last refreshed.
- **22-Jul-2026:** Last recorded operational transactions (19 furnace heats and parts production).
- **23-Jul-2026 to 11-Oct-2026 (The 82-Day Void):** **Zero electronic records exist.** Unknown physical receipts, store issues, melting operations, scrap generation, and customer dispatches occurred during August and September 2026.
- **12-Oct-2026:** Live system operational go-live date.

### Reconciling the Two Critical Calendar Intervals:
1. **82 Calendar Days (The Transaction Void):** Measured from the **last reliable operational transaction date (22-Jul-2026)** to the cutoff date (12-Oct-2026). This represents 82 days of unrecorded physical movements.
2. **89 Calendar Days (The Interim Ledger Interval):** Measured from the **interim Master Ledger formula update date (15-Jul-2026)** to the cutoff date (12-Oct-2026).

---

## 2. Objective Comparison of Policy Scenarios

Management must evaluate three distinct policy alternatives without pre-selection:

| Dimension | Scenario A: Historical Audit Archive (No Live Movement Posting) | Scenario B: Reconstructed Opening Position (Roll-Forward) | Scenario C: Two-Phase Transition (Staged Simulation with Adjustment) |
|---|---|---|---|
| **Core Concept** | July 2026 records ingested into dedicated read-only historical archive tables. Live append-only ledger begins cleanly on 12-Oct-2026 using an audited physical stocktake as Opening Balance. | July records posted to live ledger, followed by reconstructing and posting all intervening movements across August and September up to 12-Oct-2026. | July records simulated in a staging sandbox ledger to establish July closing balances. A formal variance adjustment entry is posted on 12-Oct-2026 against the October stocktake. |
| **Historical Traceability** | High for audit inquiry. July transactions are fully searchable in historical report screens, but do not affect live ledger balances. | High end-to-end continuous transaction history across all months. | Moderate. July simulated performance is recorded; variance between July and October is isolated in an adjustment journal. |
| **Opening Inventory Mechanism** | 100% established via physical stocktake conducted as of 12-Oct-2026. | Derived mathematically from July opening + reconstructed movements across August/September. | Opening balance on 12-Oct-2026 is mathematically linked to July closing plus a balancing variance adjustment. |
| **Valuation Impact** | Clean weighted-average costing starts on 12-Oct-2026 based on certified opening valuation rates. Zero retrospective cost distortion. | Reconstructs historical cost per kg back to July. Highly vulnerable to missing purchase rates in August/September. | Preliminary cost per kg calculated for July heats. Variance must be expensed, potentially distorting period consumption. |
| **Ledger Invariant Safety** | **100% SAFE.** Zero risk of negative stock or foreign key violations in the append-only ledger. | **CRITICAL RISK.** High likelihood of driving ledger balances negative due to out-of-order or missing intervening paper slips. | **MODERATE RISK.** Staging sandbox may encounter negative stock; requires manual overriding adjustments. |
| **Source Evidence Prerequisites** | Approved physical stocktake as of 12-Oct-2026; approved ex-GST valuation rates. | Complete physical GRN books, Issue books, and Heat logs for August and September 2026 (currently 100% missing electronically). | Resolving DEC-001, DEC-003, DEC-004, DEC-005 in July; audited physical stocktake on 12-Oct-2026 to measure variance. |
| **Reconciliation Effort** | Low to moderate. Focuses effort on certifying current physical inventory on the plant floor. | **EXTREME.** Requires locating, keying, validating, and reconciling thousands of physical paper slips across 82 days. | Moderate to high. Requires maintaining two ledger environments and auditing the intervening variance. |
| **Implementation Risk** | Minimal technical risk. Fully supported by existing codebase without database modifications. | **UNACCEPTABLY HIGH.** Missing a single receipt or slip causes ledger reconciliation failure. | Moderate technical complexity; requires managing sandbox staging runs and adjustment journals. |
| **Required Business Approvals** | Managing Director, Plant Head, Finance Head. | Statutory Auditor, Managing Director, Plant Head, Finance Head. | Plant Head, Cost Accountant, Finance Head. |

---

## 3. Conditions Making Scenarios Unsuitable

### Conditions Making Scenario B Unsuitable:
- If physical paper slips for August and September cannot be completely assembled, audited, and digitized.
- If Finance cannot supply commercial invoices for all August/September purchases.
- If management cannot delay system go-live for 4 to 6 weeks to key in intervening transactions.

### Conditions Making Scenario C Unsuitable:
- If statutory auditors reject a bulk multi-month inventory adjustment journal on 12-Oct-2026.
- If preliminary cost per kg calculated for July heats cannot be substantiated due to missing commercial rates (DEC-001).

### Conditions Making Scenario A Unsuitable:
- If corporate management or auditors legally mandate that July production heats must be incorporated into official general ledger inventory journals.

---

## 4. Key Questions Executive Leadership Must Answer

1. Does executive management approve **Scenario A (Historical Audit Archive)** as the official migration baseline?
2. On what exact date was (or will) the plant-wide physical stocktake be conducted to establish Opening Stock for the live ledger?
3. Who is authorized to sign off on the ex-GST opening valuation rate schedule?
4. Is retention of July 2026 transactions in dedicated read-only historical archive tables acceptable to statutory auditors and plant management?
