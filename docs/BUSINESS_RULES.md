# VSPL Material Management & Costing System — Business Rules Specification

## 1. Core Foundational Accounting & Inventory Rules

The following business rules are non-negotiable and govern all modules, database operations, and algorithmic routines within the VSPL Material Management & Costing System.

### Rule 1: Stock Depletion Exclusively via Authorized Issues
* **Statement:** Only authorized `Issue` transactions move stock out of inventory.
* **Enforcement:** Direct balance reductions from ad-hoc operational logs, informal verbal requisitions, or unapproved draft slips are strictly rejected. Every outward stock movement requires a validated, authorized Issue Slip linked to a plant department.

### Rule 2: Heat Log Charges Do Not Move Inventory
* **Statement:** Heat Log charge records do NOT independently deplete warehouse inventory.
* **Enforcement:** The furnace Heat Log is a metallurgical production record, not an inventory ledger mutation. Material is deducted from inventory when issued to the Foundry department via an Issue Slip. The Heat Log charge details are subsequently reconciled against issued quantities in Module 3.

### Rule 3: Full Auditability and Traceability
* **Statement:** All stock movements must be traceable and auditable.
* **Enforcement:** Every transaction must record the author (user ID), originating department, physical timestamp (UTC), business transaction date, and referencing document identifier (GRN number, Issue Slip number, Audit voucher).

### Rule 4: Absolute Immutability of Transaction History
* **Statement:** Never clear transaction history or delete ledger records to correct stock balances.
* **Enforcement:** `DELETE` and `UPDATE` operations are forbidden on ledger and posted transaction tables. Administrative scripts or UI actions that truncate or purge transaction history to "reset" inventory are blocked by database constraints.

### Rule 5: Physical Stock Corrections via Adjustment Entries
* **Statement:** Physical stock corrections must eventually be represented by explicit adjustment entries.
* **Enforcement:** Any discrepancy discovered during physical stock audits must be accounted for using a signed `PHYSICAL_AUDIT_ADJUSTMENT` journal entry. This entry records the book quantity, physical count, delta, authorized supervisor signature, and variance explanation.

### Rule 6: Raw-Material Receipts Require Rate Excluding GST
* **Statement:** Raw-material receipts require a rate per UOM excluding GST, except qualifying internal inward movements from VSPL or the segregation yard.
* **Enforcement:**
  - Standard external vendor GRNs must include a mandatory `unit_rate_ex_gst` (> 0). Receipts with null or zero rates are rejected unless explicitly tagged as qualifying internal movements.
  - Qualifying internal movements (e.g., returns from the segregation yard, runner/riser remelts) require explicit source documentation.

### Rule 7: Costing Baseline Cutoff Date
* **Statement:** The costing start date is strictly **12 October 2026**.
* **Enforcement:** Transactions and movements prior to this date represent historical opening balances or legacy records and must not be used to calculate weighted-average production costing without authorized transition policies.

### Rule 8: Phased Isolation of Weighted-Average Costing
* **Statement:** Weighted-average costing must be implemented in a later, separately tested phase (Phase 6).
* **Enforcement:** No interim costing shortcuts or naive moving averages may be introduced into the master data or material entry modules until the dedicated costing engine and test harness are formally initialized and verified.

### Rule 9: Strict Import Validation (No Silent Column Skips)
* **Statement:** Receipt and historical imports must strictly validate headers and data types rather than silently skipping columns or dropping unparseable rows.
* **Enforcement:** Any Excel/CSV import containing unexpected columns, missing required headers, malformed dates, or unparseable quantities must reject the entire file or raise a detailed row-by-row error report. Silent truncation or assumption-based default values are prohibited.

### Rule 10: Decimal Precision Validation
* **Statement:** Quantity precision must be validated to catch decimal-entry errors.
* **Enforcement:** The system must validate input precision against defined item UOM limits (e.g., kilograms limited to 4 decimal places, pieces limited to whole integers). Erroneous decimal entries (such as entry of 1000 instead of 10.00) must be flagged with threshold warnings.

### Rule 11: Duplicate Batch and Source Record Detection
* **Statement:** Duplicate batches and duplicate source records must be detected and blocked.
* **Enforcement:** The system checks composite uniqueness on `(vendor_id, invoice_number, item_id)` for receipts, and `(heat_number, furnace_id, heat_date)` for heat logs. Repeated uploads of identical transactions are rejected with clear duplication alerts.

### Rule 12: Zero Data Fabrication
* **Statement:** Historical data and financial metrics must not be fabricated.
* **Enforcement:** At no point during development or initial deployment should mock balances, synthetic costs, or estimated historical records be inserted into production tables. Where data is not yet migrated, systems must display clear empty states.

---

## 2. Explicitly Unresolved Business & Costing Decisions

The following items are officially classified as **PENDING MANAGEMENT DECISION** and must NOT be implemented with unapproved assumptions:

1. **Internal-Material Valuation Rates:**
   - *Status:* **PENDING**
   - *Detail:* The precise valuation rate per kg for foundry returns (runners, risers, rejected castings, machine shop borings) transferred from the segregation yard back into the furnace charge has not been finalized.
   - *Constraint:* Do not hardcode arbitrary percentage discounts (e.g., 80% of pig iron rate) until approved in writing.

2. **Costing Denominator Standard:**
   - *Status:* **PENDING**
   - *Detail:* Clarification is required whether cost per kg is calculated over *Gross Liquid Metal Tapped* or *Net Good Casting Weight* for specific SG iron part grades.
   - *Constraint:* Both metrics must be calculated and displayed distinctly without conflation.

3. **Additional Production Overheads Apportionment:**
   - *Status:* **PENDING**
   - *Detail:* How furnace electrical power (kWh/heat), refractory liner wear, and labor overheads are apportioned into individual heat costs.
   - *Constraint:* Module 6 must isolate raw material metal cost from conversion overheads until an overhead allocation method is formally designated.

4. **Historical Pricing Reconciliation Prior to Cutoff:**
   - *Status:* **PENDING**
   - *Detail:* Method of establishing opening stock unit rates for the 741 items on 12 October 2026.
   - *Constraint:* Historical transactions prior to 12 October 2026 must be preserved as quantity-only or with explicit legacy flags until valuation basis is approved.
