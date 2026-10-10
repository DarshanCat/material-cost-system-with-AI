# VSPL Material Management & Costing System — Business Rules Specification

## 1. Master Data & Requisition Rules (Established in Phase 2)

### Rule M1: Item Code Format Convention
* **Statement:** All material master items must follow the standard identifier pattern: `DEPT-CATEGORY-SERIAL`.
* **Format:** `^[A-Z0-9]{2,5}-[A-Z0-9]{2,5}-[0-9]{3,6}$` (e.g., `FDY-RM-001`, `MSP-BOR-012`).
* **Enforcement:** Generated automatically by the `ItemRequestService` upon request approval. Serial numbers increment per `(department, category)` partition. Duplicate item codes are rejected at the database constraint level.

### Rule M2: Separation of Duties — Prohibition of Self-Approval
* **Statement:** No actor may approve an item creation request that they themselves initiated.
* **Enforcement:** If `reviewer_id == requester_id` during an approval call, the backend immediately halts the transaction and returns `HTTP 403 Forbidden` (`Self-approval violation: Requester cannot approve their own item request`).

### Rule M3: Mandatory Rejection Justification
* **Statement:** Rejection of an item creation request requires an explicit, non-empty explanation reason.
* **Enforcement:** The rejection endpoint validates that `decision_comments` contains substantive text. Empty or whitespace-only comments return `HTTP 400 Bad Request`.

### Rule M4: Atomic Approval & Singleton Material Item Creation
* **Statement:** Approving an item creation request must create exactly one material master record and transition the request state in an atomic transaction.
* **Enforcement:** Repeated approval calls on an already `APPROVED` request fail with `HTTP 400 Bad Request`. Cancelled or rejected requests never generate material items.

### Rule M5: Vendor Name Normalization and Deduplication
* **Statement:** Vendor duplicate detection relies on a normalized search key while preserving original legal names for invoicing and audit trails.
* **Enforcement:** `normalized_name = lowercase(remove_punctuation(collapse_whitespace(name)))`. Insertion of duplicate normalized keys is blocked at the database level (`409 Conflict`). Automatic merging of historical vendor spellings is prohibited without human review.

### Rule M6: Optional GSTIN with Syntactic Validation
* **Statement:** GSTIN is optional for vendor registration, but when provided, it must conform to the 15-character Indian GST format.
* **Format:** `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$`.
* **Constraint:** The system validates formatting syntactically and does not claim to verify live registration against external GSTN APIs.

### Rule M7: Extensible UOM Precision Governance
* **Statement:** Each unit of measurement specifies an integer decimal precision (e.g., `KG`: 4, `MT`: 4, `NOS`: 0, `LTR`: 3).
* **Enforcement:** All financial and inventory calculations use `NUMERIC` / `Decimal`. IEEE 754 binary floating-point (`FLOAT`/`DOUBLE PRECISION`) is strictly prohibited. Values like `5014` vs `5.014` are flagged for review by future transaction validation and never silently auto-converted.

---

## 2. Material Entry & Transaction Validation Rules (Established in Phase 3)

### Rule T1: Human-Readable Sequential Document Numbering
* **Statement:** All transaction headers generate distinct, tamper-evident document serials:
  - Goods Receipt Notes: `GRN-YYYYMMDD-XXXX` (e.g., `GRN-20261010-0001`)
  - Material Issue Slips: `ISS-YYYYMMDD-XXXX` (e.g., `ISS-20261010-0001`)
  - Waste & Scrap Slips: `WST-YYYYMMDD-XXXX` (e.g., `WST-20261010-0001`)
* **Enforcement:** Enforced at database table level via unique indexed constraints.

### Rule T2: Receipt Sourcing & Rate Mandate
* **Statement:** Receipts support three mutually exclusive sources:
  1. `EXTERNAL_VENDOR`: Requires valid registered Vendor reference and rate per UOM (excluding GST) > 0 for raw materials.
  2. `INTERNAL_VSPL`: Internal factory transfers; vendor and commercial rate are optional.
  3. `SEGREGATION_YARD`: Inward recovery from scrap segregation; rate optional.
* **GST Treatment:** Pre-GST material rate (`rate_ex_gst`) and GST tax percentage (`gst_percent`) are strictly separated into independent `NUMERIC` columns. Tax is never blended into material inventory rates.

### Rule T3: Heat Reference Standardization
* **Statement:** Melting issue slips record furnace heat numbers using convention `H-XXXXXX-XXXX` (e.g. `H-102603-3721`). Raw user entries without prefix are normalized automatically without destructive data alteration.

### Rule T4: Suspect Quantity Entry Detection
* **Statement:** Quantities violating UOM decimal precision limits are strictly blocked (`422 Unprocessable`). Suspected scale errors (e.g., entering 5014 kg as 5014 MT, or entering 290 kg as whole MT) trigger explicit human confirmation warnings without silent auto-division.

### Rule T5: Transaction Lifecycle & Ledger Boundary
* **Statement:** Transactions originate in `DRAFT`, undergo verification to `SUBMITTED`, and achieve finalization on `APPROVED`.
* **Scope Boundary:** Phase 3 transactions do **NOT** move warehouse inventory ledger balances or post accounting journal entries. Ledger movements are strictly isolated to Phase 4.

### Rule T6: Atomic All-or-Nothing Excel Import Engine
* **Statement:** Multi-row batch imports validate entire worksheets across headers, master data references, duplicate document numbers, and decimal precision.
* **Enforcement:** If even a single row contains a blocking error, the batch is rejected (`can_commit = false`). Commit executes inside a single database transaction rollback boundary—zero partial or orphaned writes.

---

## 3. Foundational Accounting & Inventory Ledger Rules

### Rule 1: Stock Depletion Exclusively via Authorized Issues
* Only authorized `Issue` transactions move stock out of inventory.

### Rule 2: Heat Log Charges Do Not Move Inventory
* Heat Log charge records do NOT independently deplete warehouse inventory. Depletion occurs via Issue Slips.

### Rule 3: Full Auditability and Traceability
* Every transaction records user ID, originating department, UTC timestamp, and document reference.

### Rule 4: Absolute Immutability of Transaction History
* Never clear transaction history or delete ledger records to correct stock balances.

### Rule 5: Physical Stock Corrections via Adjustment Entries
* Physical stock count discrepancies are accounted for using signed `PHYSICAL_AUDIT_ADJUSTMENT` journal entries.

### Rule 6: Raw-Material Receipts Require Rate Excluding GST
* Receipts require rate per UOM excluding GST, except qualifying internal inward movements from VSPL segregation yard.

### Rule 7: Costing Baseline Cutoff Date
* The costing start date is strictly **12 October 2026**.

### Rule 8: Phased Isolation of Weighted-Average Costing
* Weighted-average costing is implemented exclusively in Phase 6.

### Rule 9: Strict Import Validation (No Silent Column Skips)
* Receipt and historical imports strictly validate headers and types without silent column skips.

### Rule 10: Decimal Precision Validation
* Quantity precision is validated against UOM limits to catch decimal-entry anomalies.

### Rule 11: Duplicate Batch and Source Record Detection
* Composite uniqueness on `(vendor_id, invoice_number, item_id)` and `(heat_number, furnace_id, heat_date)`.

### Rule 12: Zero Data Fabrication
* No synthetic mock inventory quantities, fictitious rates, or invented transactions are displayed.

---

## 4. Live Inventory Ledger & Stock Governance Rules (Established in Phase 4)

### Rule L1: Immutable Append-Only Ledger Journal
* **Statement:** The `stock_ledger_entries` table is strictly append-only. No application API or user interface provides `UPDATE` or `DELETE` endpoints for posted ledger records.
* **Database Constraint:** Each movement record stores an immutable transaction timestamp, posting user, source document reference, source line reference, material reference, movement type, and signed quantity delta.
* **Audit Trail:** Any modification or correction must be represented as a new, traceable ledger movement. Never clear or overwrite historical records.

### Rule L2: Derived Stock Balance Engine
* **Statement:** Inventory stock balances are never stored as mutable scalar columns or manually overwritten. Current on-hand stock and point-in-time stock are calculated by aggregating the ledger journal:
  $$\text{Balance}(\text{item\_id}, t) = \sum_{entry.created\_at \le t} \text{entry.quantity\_delta}$$
* **Point-in-Time Traceability:** Stock balances can be reconstructed for any historical date and time with exact audit fidelity.

### Rule L3: Stock Status Classifications
* **Statement:** Stock balances are classified into four mutually exclusive operational states:
  1. `UNINITIALIZED`: Zero ledger records have ever been posted for this item.
  2. `IN_STOCK`: Derived balance is strictly greater than zero ($\text{balance} > 0$).
  3. `OUT_OF_STOCK`: Derived balance is exactly zero ($\text{balance} = 0$), having had previous movements.
  4. `NEGATIVE_STOCK`: Derived balance is strictly less than zero ($\text{balance} < 0$).

### Rule L4: Transactional Idempotency & Unique Source Constraints
* **Statement:** To prevent duplicate stock postings when network timeouts or retries occur, every source line maps to at most one forward ledger entry.
* **Enforcement:** Enforced at database level via a composite unique constraint: `UNIQUE(source_document_type, source_line_id)`.
* **Forward Movement Mapping:**
  - `GRN` (External Vendor): `INWARD_RECEIPT` ($+\Delta$)
  - `GRN` (Internal VSPL / Segregation Yard): `INTERNAL_INWARD` ($+\Delta$)
  - `ISSUE`: `OUTWARD_ISSUE` ($-\Delta$)
  - `WASTE` (Scrap disposal / Offsite sale): `SCRAP_OUTWARD` ($-\Delta$)
  - `WASTE` (Floor recovery / Internal reuse): `INTERNAL_RECOVERY` ($0\Delta$, net-neutral non-movement)
  - `WASTE` (Inspection Hold): Non-movement quarantine record.

### Rule L5: Compensating Reversal Lifecycle
* **Statement:** Transaction cancellation or correction does not purge existing ledger entries. Instead, an authorized supervisor posts a compensating `REVERSAL` journal movement.
* **Mechanism:**
  - Opposite algebraic sign of the original `quantity_delta`.
  - Foreign key link `reversal_of_entry_id` pointing directly to the original ledger entry.
  - Mandatory justification notes and audit log record.
  - Original entries and reversals cannot be reversed more than once.

### Rule L6: Configurable Negative Stock Prevention
* **Statement:** The system defaults to strict negative stock prevention (`settings.ALLOW_NEGATIVE_STOCK = False`).
* **Enforcement:**
  - Any issue slip that would cause derived balance to drop below zero is blocked (`409 Conflict: Insufficient stock`).
  - Issuing an item that is `UNINITIALIZED` is strictly blocked (`409 Conflict: Cannot issue item with uninitialized stock`).
  - Reversals that would cause stock to drop below zero are blocked.
  - Can be toggled for controlled plant migration scenarios if explicitly sanctioned by management.

### Rule L7: Baseline Opening Balance Governance (12 October 2026 Baseline)
* **Statement:** The operational costing and inventory baseline begins on **12 October 2026**.
* **Workflow:**
  1. Upload CSV/Excel containing `[item_code, uom_code, quantity, optional_unit_rate, optional_batch_number]`.
  2. Perform preview validation checking item active status, UOM compatibility, decimal precision, and existing initialization.
  3. Post atomically inside a single transaction. Each valid line creates an `OPENING_BALANCE` ledger entry with transaction date set to `2026-10-12`.
  4. Duplicate opening balance entries for an already initialized item are rejected.

### Rule L8: Physical Stock Audit Variance & Cutoff Mechanics
* **Statement:** Physical stock counts are recorded and reconciled without manual balance overrides.
* **Cutoff Calculation:** The system computes the system balance at the exact audit cutoff date:
  $$\text{System Cutoff Balance} = \sum_{\text{transaction\_date} \le \text{audit\_date}} \text{quantity\_delta}$$
* **Variance Formula:**
  $$\text{Variance} = \text{Physical Count} - \text{System Cutoff Balance}$$
* **Approval & Ledger Adjustment:**
  - Draft audits do NOT affect inventory.
  - On approval by Management or Admin, non-zero variances generate a `PHYSICAL_AUDIT_ADJUSTMENT` ledger entry with $\text{quantity\_delta} = \text{Variance}$.
  - Zero-variance items are recorded as verified without generating redundant zero deltas.

---

## 5. Induction Furnace Heat Log & Reconciliation Rules (Established in Phase 5)

### Rule H1: Strict Inventory Non-Movement (Critical Directive)
* **Statement:** Induction Furnace Heat Log charge details and reconciliation runs NEVER create inventory movements or alter stock ledger balances.
* **Enforcement:**
  - Only authorized Stores `MaterialIssueHeader` transactions post outward stock ledger entries (`OUTWARD_ISSUE`).
  - Furnace charge records represent floor metallurgical consumption, not warehouse stock dispatches.
  - Reconciliation results identify consumption variances without synthesizing ledger balance adjustments.
  - Dedicated regression tests (`test_reconciliation_isolation.py`) enforce zero stock movements across heat creation, editing, importing, reconciling, and candidate match confirmation.

### Rule H2: Heat Reference Normalization Convention
* **Statement:** Furnace heats follow the standard convention `H-XXXXXX-XXXX` (e.g. `H-102603-3721`).
* **Preservation Rule:**
  - Raw user inputs (e.g. `102603-3721`) are preserved in `original_heat_number`.
  - Normalized uppercase reference (`H-102603-3721`) is stored separately in `normalized_heat_number`.
  - Normalization collisions are rejected with `409 Conflict`.
  - Issue slip numbers and heat log numbers are never silently rewritten.

### Rule H3: Controlled Material Alias Dictionary
* **Statement:** Raw textual descriptions in historical furnace sheets (e.g. `CRC Scrap-Low High MN`) map to official `material_items` through an auditable alias master (`material_aliases`).
* **Governance:**
  - Original alias text is preserved alongside a normalized key (`normalize_alias_key(text)`).
  - Ambiguous mappings (mapping the same alias text to multiple items) are blocked at the database level (`409 Conflict`).
  - Silent fuzzy matching to auto-create aliases is strictly prohibited.
  - Alias lifecycle (`PENDING` $\rightarrow$ `APPROVED` / `REJECTED`) requires supervisor review, with mandatory justification comments on rejection.

### Rule H4: Deterministic Three-Pass Reconciliation Engine
* **Statement:** Floor issues and melt charges are reconciled via a deterministic, explainable algorithm:
  1. **Pass 1 (Exact Heat-Slip Matching):** Matches `issue.heat_reference_number` against `heat.heat_number` / `heat.normalized_heat_number`. Compares common items item-by-item. Allocated lines are marked and excluded from subsequent passes.
  2. **Pass 2 (Same-Day Batch Aggregation):** For unallocated records, aggregates issues and charges by `(transaction_date == heat_date)` and resolved `material_item_id`. Prevents double-counting lines allocated in Pass 1.
  3. **Pass 3 (Advisory Fuzzy Suggestions):** For remaining unallocated lines, proposes suggestions based on date proximity ($\pm 1$ day for shift crossovers), reference similarity, and quantity proximity. **Never auto-confirms.**

### Rule H5: Unambiguous Tolerance Precedence Formula
* **Statement:** In foundry charge reconciliation, tolerances accommodate both small inoculants ($5\text{ kg}$) and bulk scrap ($1,000\text{ kg}$) via:
  $$\text{Tolerance Limit} = \max(\text{Absolute Tolerance } (0.5\text{ kg}), \text{Relative Tolerance } (2\%) \times \text{Issued Quantity})$$
* **Zero Handling:** When Issued Quantity is zero, the threshold defaults to the absolute tolerance ($0.5\text{ kg}$).
* **Explainability:** The applied numerical tolerance and comparison basis string are permanently persisted with each reconciliation result.

### Rule H6: Signed Variance Convention
* **Statement:** Discrepancy variance is defined consistently across all APIs, models, and UI as:
  $$\text{Variance} = \text{Issued Quantity} - \text{Charged Quantity}$$
* **Classification Rules:**
  - If $|\text{Variance}| \le \text{Tolerance Limit} \implies \text{OK}$
  - If $\text{Variance} > \text{Tolerance Limit} \implies \text{EXCESS\_ISSUE}$ (Stores issued more than logged as charged)
  - If $\text{Variance} < -\text{Tolerance Limit} \implies \text{SHORT\_ISSUE}$ (More logged as charged than officially issued)
  - If magnitude ratio $\ge 10$ or $\le 0.1 \implies \text{DECIMAL\_SUSPECT}$ (flagged for order-of-magnitude scale review without auto-division)

### Rule H7: Human-Confirmed Advisory Suggestions
* **Statement:** Fuzzy candidate matches are strictly advisory and require human confirmation by an authorized supervisor (`Foundry`, `Management`, or `Admin`).
* **Audit Trail:** Confirmed candidates record reviewer ID, review timestamp, and justification remarks.

### Rule H8: Versioned Immutable Reconciliation Runs
* **Statement:** Re-running reconciliation never overwrites historical results. Each execution creates a new `reconciliation_runs` record preserving exact run numbers, parameters, algorithm version, and line comparisons.

---

## 6. Explicitly Unresolved Business & Costing Decisions (Pending Management Sign-off)

1. **Internal-Material Valuation Rates:**
   - *Status:* **PENDING**
   - *Detail:* Valuation rate per kg for foundry returns (runners, risers, rejected castings, borings from Machine Shop) transferred back into furnace charges. Governed by Rule C7 (logged with zero quantity delta and status `POLICY_PENDING`).
2. **Costing Denominator Standard:**
   - *Status:* **PENDING**
   - *Detail:* Defaulted to `METAL_TAPPED` (liquid metal tapped from furnace). Management sign-off pending for switching to `GOOD_CASTING_WEIGHT` once yield reporting is formalized.
3. **Additional Production Overheads Apportionment:**
   - *Status:* **PENDING**
   - *Detail:* How furnace electrical power (kWh/heat), refractory liner wear, and direct labor overheads are apportioned. Currently flagged as `MATERIAL_ONLY` scope (Rule C8).
4. **Historical Pricing Reconciliation Prior to Cutoff:**
   - *Status:* **PENDING**
   - *Detail:* Method of establishing opening stock unit rates for the items on 12 October 2026. Handled via Rule C3 with `OPENING_VALUATION_MISSING` until approved via `item_opening_valuations`.

---

## 7. Phase 6: Weighted-Average Costing & Valuation Rules

### Rule C1: Ex-GST Weighted-Average Material Unit Rate
* **Formula:**
  $$\bar{R}_{\text{new}} = \frac{(Q_{\text{prev}} \times \bar{R}_{\text{prev}}) + (Q_{\text{receipt}} \times R_{\text{receipt}})}{Q_{\text{prev}} + Q_{\text{receipt}}}$$
* **Rate Scope:** Commercial receipt rates strictly represent ex-GST invoice values (`rate_ex_gst`).
* **Rounding Convention:** Rounded deterministically to 4 decimal places (`NUMERIC(14, 4)`) using Python `Decimal` and `ROUND_HALF_UP`.
* **Zero Floating-Point Policy:** All rates, valuations, and extended values use arbitrary-precision `Decimal` objects. Floating-point arithmetic is strictly forbidden.

### Rule C2: Same-Day Transaction Ordering & Deterministic Tie-Breaking
* **Ordering Hierarchy:** When multiple stock movements share the same transaction date, they are processed in deterministic sequential order:
  1. `OPENING_BALANCE`
  2. `INWARD_RECEIPT` / `INTERNAL_INWARD`
  3. `PHYSICAL_AUDIT_ADJUSTMENT` ($+\Delta$)
  4. `OUTWARD_ISSUE` / `SCRAP_OUTWARD`
  5. `PHYSICAL_AUDIT_ADJUSTMENT` ($-\Delta$)
  6. `REVERSAL`
  7. `INTERNAL_RECOVERY`
* **Tie-Breaking:** Movements within the same class on the same date order strictly by `StockLedgerEntry.id` ascending.
* **Economic Rationale:** External receipts arrive and enter stock before same-day floor issues take place, ensuring outward issues are priced at the updated blended rate.

### Rule C3: Strict Cutoff Date & Opening Balance Valuation
* **Baseline Cutoff:** Costing calculations strictly start on **12 October 2026** (`settings.COSTING_START_DATE`). Movements prior to this date are excluded from inventory valuation.
* **Separation of Stock & Valuation:** Opening stock quantities from Phase 4 are distinct from commercial valuations. If an opening balance has no approved `item_opening_valuations` record, its valuation status is explicitly flagged as `OPENING_VALUATION_MISSING`.
* **Zero Stock Handling:** Items with a balance of $0.0000$ are reported with extended value ₹0.00 and status `ZERO_STOCK`, distinct from uninitialized items (`UNINITIALIZED`).

### Rule C4: Outward Issue Consumption & Zero-Stock Rate Restart
* **Issue Pricing:** Outward issues (`OUTWARD_ISSUE`, `SCRAP_OUTWARD`) consume inventory at the current running weighted-average rate without altering the unit rate.
* **Restart on Zero/Negative Stock:** When existing stock balance is $\le 0.0000$, a subsequent inward receipt restarts the running weighted-average rate directly at the receipt's commercial rate ($R_{\text{receipt}}$) rather than blending with past rates.

### Rule C5: Ledger Non-Mutation Guarantee
* **Strict Read-Only Ledger Invariant:** The append-only stock ledger (`stock_ledger_entries`) is the authoritative physical movement record.
* Costing runs, rate reconstruction queries, and valuation reports **never mutate, delete, or create** stock ledger records.

### Rule C6: Induction Furnace Heat Costing
* **Formula:**
  $$\text{Heat Material Cost} = \sum_{i=1}^{n} (Q_{\text{charged}, i} \times \bar{R}_{i}(\text{heat\_date}))$$
* **Rate As-Of Date:** Charge lines are priced at the item's weighted-average rate effective on the heat date (`heat_date`).
* **Cost Per kg:**
  $$\text{Cost per kg} = \frac{\text{Heat Material Cost}}{\text{Metal Tapped Weight}}$$
* **Missing Data Invariants:**
  - If a charge line uses an unmapped alias or an unpriced item, the heat status is set to `PARTIAL_COST`.
  - If `metal_tapped_weight` is null or zero, cost per kg is withheld (`None`) with status `MISSING_TAPPED_WEIGHT`.

### Rule C7: Part Material Unit Costing
* **Formula:**
  $$\text{Part Material Cost per Unit} = \text{Unit Cast Weight} \times \text{Heat Cost per kg}$$
* **Scope:** Labeled strictly as `MATERIAL_ONLY`. Does not generate finished-goods stock movements.
* **Prerequisites:** Requires a completed parent heat cost (`HeatCostStatus.COMPLETE`) and valid `unit_cast_weight`.

### Rule C8: Explicit Pending Policy Flags
* Any valuation scenario without approved management sign-off (internal recovery scrap, borings, overheads) must be exposed via explicit enum statuses: `POLICY_PENDING`, `OPENING_VALUATION_MISSING`, or `INSUFFICIENT_COST_DATA`. Silent defaults (e.g. ₹0.00) are forbidden.

### Rule C9: Versioned, Immutable Costing Runs
* Every costing execution generates a permanent, sequential `costing_runs` record (`CR-YYYYMMDD-XXXX`).
* Recalculations create new runs and never overwrite historical snapshots, rate journals, or heat costs.
* Side-by-side run comparisons expose valuation, rate, and cost deltas between any two runs.

