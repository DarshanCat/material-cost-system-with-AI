# VIJAY SPHEROIDALS PVT. LTD. (VSPL)
## STANDARD WORK INSTRUCTION & PROJECT FLOW DOCUMENT
**Document ID:** VSPL-WI-MM-001  
**Revision:** 2.0  
**Effective Date:** 28-October-2026  
**Subject:** End-to-End Material Management, Inventory Valuation & Cost Accounting System  
**Units Covered:** Peenya Foundry (Plant 1), Tumkur Machine Shop (Plant 2), Central Stores, Melt Shop, Quality Assurance, Finance & Accounts  

---

## 1. Executive Summary & Purpose

This Standard Work Instruction (WI) defines the operational, technical, and calculation framework for Vijay Spheroidals Pvt. Ltd.’s (VSPL) Material Management & Costing System.

### Core Control Principle
**Inventory movements have exactly ONE authoritative posting path.**  
Heat Log records describe production and crucible charge execution; they **must not independently deduct stock** when the approved Stores issue has already done so.

### Primary Objectives
1. **Total Material Traceability**: Seamless audit trail from raw material inward goods receipt (GRN) to shop floor issue, furnace charge consumption, heat tap, and finished machined casting.
2. **Standardized Nomenclature**: Strict enforcement of VSPL Material Nomenclature Standard v1.0 (`DEP-CAT-XXX`) across all supplier challans and shop floor tags.
3. **Daily 1 PM – 1 PM Accounting Cycle**: A synchronized 24-hour continuous rolling cycle that replaces disconnected monthly batches with daily closed-loop accountability.
4. **Moving Weighted-Average Rate (MWAR) Costing**: Real-time moving average inventory valuation, automated heat liquid metal costing, and melt loss tracking.
5. **Three-Pass Reconciliation**: Systematic matching of Stores issue slips against Heat Log crucible charges.

---

## 2. System Architecture & Tech Stack

```
+-----------------------------------------------------------------------------------------+
|                                    USER INTERFACES                                      |
|  - Stores Tablet / Desktop: GRN, Inward Inspection, Stock Ledger                       |
|  - Melt Shop Terminal: Heat Log, Raw Material & Ferroalloy Charging                     |
|  - Management & Finance Dashboard: Vercel Live Web App (https://frontend-rouge-xi-35.vercel.app/) |
+--------------------------------------------+--------------------------------------------+
                                             | REST API / JSON
                                             v
+-----------------------------------------------------------------------------------------+
|                                 BACKEND SERVICES (FastAPI)                              |
|  - Core Service: FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async                           |
|  - Authentication: Supabase Auth / Dev Auth Engine                                      |
|  - Material Ledger Engine: Append-Only Immutable Transaction Ledger (006 Guard Trigger) |
|  - Costing Engine: Moving Weighted-Average Rate (MWAR) Evolution & Heat Costing Run     |
|  - Reconciliation Engine: 3-Pass Matching (Exact, Batch, Fuzzy Candidate)               |
+--------------------------------------------+--------------------------------------------+
                                             | Connection Pooler (Port 5432 / SSL)
                                             v
+-----------------------------------------------------------------------------------------+
|                            ENTERPRISE DATABASE (Supabase PostgreSQL)                    |
|  - Relational Schema: Verified Production Tables                                        |
|    * departments, uoms, vendors, items, material_aliases                                |
|    * goods_receipt_notes, grn_lines, material_issues, material_issue_lines              |
|    * waste_dispositions, waste_disposition_lines, physical_audits, audit_lines         |
|    * stock_ledger_entries (Append-Only Trigger Guarded)                                 |
|    * heats, heat_charge_lines, heat_production_records                                  |
|    * reconciliation_runs, reconciliation_matches, reconciliation_exceptions             |
|    * costing_runs, costing_run_item_valuations, costing_run_heat_costs                  |
+-----------------------------------------------------------------------------------------+
```

---

## 3. How All Has To Be Done (Step-by-Step Operating Guide)

### Step 1: Master Data & Nomenclature Setup
- **Format**: Every item follows `DEP-CAT-XXX` (e.g., `FDY-RM-001` for Foundry Pig Iron).
- **Rule**: Missing items require a formal Item Code Request. Maker-checker prevents self-approval.
- **Immutability**: Codes are never renamed or deleted; retired items are marked `is_active = False`.

### Step 2: Gate Weighment & Goods Receipt Note (GRN)
- **Weighbridge**: Trucks weighed loaded (Gross) and empty (Tare). Net weight verified against supplier delivery challan.
- **Stores GRN Entry**: Stores records GRN with vendor, invoice number, and mandatory positive `unit_rate_ex_gst`.
- **Ledger Posting**: Upon approval by Stores Manager, appends `MovementType.RECEIPT` (`+Q`) to `stock_ledger_entries`.

### Step 3: Material Issue Slip Execution (The Sole Authority for Inventory Reduction)
- **Request**: Melt shop raises material requisition slip.
- **Verification**: Stores verifies stock availability with row-level database locks (`SELECT FOR UPDATE`).
- **Ledger Posting**: Upon approval, appends `MovementType.ISSUE` (`-Q`) to `stock_ledger_entries`.
- **Control**: **This is the ONLY backend service that deducts inventory.**

### Step 4: Waste Disposition & Remelt Recovery
- **Scrap Outward**: Unusable floor scrap or waste sold outward deducts stock (`MovementType.WASTE`, `-Q`).
- **Internal Recovery**: Runners and risers recovered from casting and returned to melting charge bay add stock (`MovementType.RECEIPT`, `+Q`).

### Step 5: Physical Stock Audit
- **Floor Count**: Periodic physical stock count conducted on warehouse floor.
- **Adjustment**: System compares physical count against live system snapshot:
  $$\Delta Q = Q_{\text{physical}} - Q_{\text{system}}$$
- **Ledger Posting**: Posts `MovementType.ADJUSTMENT_IN` (`+|ΔQ|`) if positive variance, or `MovementType.ADJUSTMENT_OUT` (`-|ΔQ|`) if negative.

### Step 6: Foundry Heat Log & Melt Shop Execution
- **Crucible Charging**: Melt shop operators record furnace, shift, operator, tapped weight, and raw material additions.
- **Ledger Impact**: **ZERO stock ledger movements.** Heat logs capture melting execution for traceability, not stores inventory.

### Step 7: Three-Pass Reconciliation Engine
- **Pass 1 (Exact)**: Matches issue slips and heat logs sharing the exact heat number.
- **Pass 2 (Batch)**: Matches same-day bulk issues against daily crucible charges without heat slips.
- **Pass 3 (Advisory Fuzzy)**: Highlights similar names or typing errors for human review.
- **Tolerance**: Evaluates difference against tolerance threshold ($\max(0.5\text{ kg}, 0.02 \times Q_{\text{issued}})$).

### Step 8: 13:00 Hard Cut-Off & Daily Costing Run
- **Cut-Off**: Strict 13:00 daily freeze. Transactions after 13:00 roll into the next 24-hour cycle.
- **Costing Execution**: Chronological sequencing (`OB -> RCPT -> ADJ_IN -> ISS -> WST -> ADJ_OUT`). Recalculates moving weighted-average rate, derives liquid metal cost per kg, and allocates exact part costs.

### Step 9: Document Reversals & Immutability Guard
- **No In-Place Edits**: `stock_ledger_entries` cannot be modified or deleted (PostgreSQL trigger blocked).
- **Compensating Entries**: Approved documents are reversed by appending counter-movements with opposite signs.

---

## 4. Comprehensive Formula Register

| Formula ID | Metric | Exact Formula | Notes & Zero Handling |
| :--- | :--- | :--- | :--- |
| **F-01** | Closing Stock Quantity | $Q_{\text{closing}} = Q_{\text{opening}} + \sum \Delta Q_{\text{signed}}$ | Aggregates all receipts, issues, and adjustments. Negative balances blocked. |
| **F-02** | Moving Weighted-Average Rate | $R_{\text{new}} = \dfrac{(Q_{\text{prev}} \times R_{\text{prev}}) + (Q_{\text{rcpt}} \times R_{\text{rcpt}})}{Q_{\text{prev}} + Q_{\text{rcpt}}}$ | Recalculated on each receipt. 4 decimal precision (`0.0001`). If $Q_{\text{prev}} \le 0$, rate resets to $R_{\text{rcpt}}$. |
| **F-03** | Outward Issue Valuation | $\text{Val}_{\text{issue}} = \text{round}(Q_{\text{issue}} \times R_{\text{prev}},\; 2)$ | Consumes stock at current MWAR rate. Rate remains unchanged upon issue. |
| **F-04** | Heat Charge Variance | $\Delta W = \sum Q_{\text{issued}} - \sum W_{\text{charge}}$ | Aggregates repeated additions of same item within a heat before comparison. |
| **F-05** | Reconciliation Tolerance Limit | $\text{Tol} = \max\left(0.5000\text{ kg},\; 0.02 \times Q_{\text{issued}}\right)$ | Minimum floor of 0.5 kg. Beyond tolerance flags `EXCESS_ISSUE` or `SHORT_ISSUE`. |
| **F-06** | Decimal Suspect Ratio | $\text{Ratio} = \dfrac{W_{\text{charge}}}{Q_{\text{issued}}}$ | Ratio $\ge 9.5$ or $\le 0.105$ flags 10x order-of-magnitude decimal typo. |
| **F-07** | Melt Loss (kg & %) | $\text{Loss}_{\text{kg}} = W_{\text{charge}} - W_{\text{tapped}}$<br>$\text{Loss}_{\%} = \left[\dfrac{\text{Loss}_{\text{kg}}}{W_{\text{charge}}}\right] \times 100$ | Standard target: 3.0% to 6.5%. $>6.5\%$ triggers warning; $>8.0\%$ critical hold. |
| **F-08** | Liquid Metal Cost Rate | $R_{\text{liquid}} = \dfrac{\text{Total Heat Material Cost}}{W_{\text{tapped}}}$ | Dividing by tapped weight automatically absorbs melting loss into liquid rate. |
| **F-09** | Finished Part Unit Cost | $\text{Cost}_{\text{part}} = \text{round}(W_{\text{cast\_kg}} \times R_{\text{liquid}},\; 2)$ | Multiplies good unit cast weight by liquid metal rate. |
| **F-10** | Opening Balance Valuation | $\text{Val}_{\text{opening}} = Q_{\text{certified}} \times R_{\text{approved}}$ | Requires management-certified physical stock count as of 12 October 2026. |

---

## 5. Phase 5 Source Issue Rows Accounting (1,183 Audited Rows)

Every source issue row from the daily workbooks has been classified into a mutually exclusive category:

| Classification | Rows | Net Quantity | UOM | Handling |
| :--- | :---: | :---: | :---: | :--- |
| **VALID_FURNACE_CHARGE** | 1,044 | 57,519.20 kg | KG | Included in crucible charge reconciliation comparison |
| **ZERO_QUANTITY_PLACEHOLDER** | 43 | 0.00 kg | KG | Excluded from charge weight; preserved in audit record |
| **NON_CHARGE_SUPPLY_VOUCHER** | 21 | 187.00 kg + 478.00 Nos | Mixed | Excluded from crucible bath; treated as stores supply |
| **FLOOR_CONSUMABLE_BLANK_SLIP** | 13 | Various | Mixed | Floor consumable supplies without heat slips |
| **MISSING_ITEM_CODE** | 1 | 177.00 kg (Gattings) | KG | Heat 102608-3920 held pending code approval |
| **GENERAL_ISSUE** | 61 | Various | Mixed | Departmental issues outside melt shop |
| **TOTAL AUDITED ROWS** | **1,183** | **57,519.20 kg Valid Metal** | **Separated** | **100% Accounted For • Zero Overlaps** |

> **Arithmetic Warning**: The preliminary figure 58,361.20 kg combined 187 kg of non-charge supplies with 478 count units. Pure verified metallic charge is exactly 57,519.20 kg.

---

## 6. Daily 1 PM – 1 PM Accounting Timeline

- **13:00 (Day T)**: Cycle start. Previous cycle archived.
- **13:00 – 12:30 (Day T+1)**: Real-time logging of receipts (GRN) and heat charges.
- **12:30 – 13:00**: Pre-closing sanity check by Stores Supervisor and Melting Lead.
- **13:00 (Day T+1)**: **HARD CUT-OFF**. Transactions freeze; subsequent entries roll into next cycle.
- **13:15**: Automated MWAR Costing Run and liquid metal rate calculation.
- **13:20 – 14:00**: Anomaly resolution and formal sign-off window.

---

## 7. RACI Responsibility & Governance Matrix

| Workflow Operation | Stores | Melt Shop | Quality (QA) | Cost Accounts | Plant Head |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Item Code Creation & Registry | **R** | C | C | I | **A** |
| Inward Material Receipts (GRN) | **R** | I | C | I | I |
| Stores Issue Slip Deduction | **R** | C | I | I | **A** |
| Furnace Heat Log Charging | I | **R** | C | I | **A** |
| 13:00 Hard Cut-Off Execution | C | C | I | **R** | **A** |
| Three-Pass Reconciliation | C | C | I | **R** | **A** |
| MWAR Costing Run & Valuation | I | I | I | **R** | **A** |

---

## 8. Web App & Jetro Links

- **Interactive Jetro Frame Document**:  
  [`frontend/public/work-instruction.html`](https://frontend-rouge-xi-35.vercel.app/work-instruction.html)
- **Live Production Application**:  
  [`https://frontend-rouge-xi-35.vercel.app/`](https://frontend-rouge-xi-35.vercel.app/)
- **GitHub Repository**:  
  [`https://github.com/DarshanCat/material-cost-system-with-AI`](https://github.com/DarshanCat/material-cost-system-with-AI)
- **Comprehensive Process Trace**:  
  [`docs/process-trace/MM_BACKEND_PROCESS_TRACE.md`](file:///c:/VSPL_MM/Material%20managment%20system/docs/process-trace/MM_BACKEND_PROCESS_TRACE.md)
