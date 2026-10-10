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

## 3. Explicitly Unresolved Business & Costing Decisions (Pending Management Sign-off)

1. **Internal-Material Valuation Rates:**
   - *Status:* **PENDING**
   - *Detail:* Valuation rate per kg for foundry returns (runners, risers, rejected castings, borings from Machine Shop) transferred back into furnace charges.
2. **Costing Denominator Standard:**
   - *Status:* **PENDING**
   - *Detail:* Clarification whether cost per kg for casting part numbers uses *Gross Liquid Metal Tapped* or *Net Good Casting Weight*.
3. **Additional Production Overheads Apportionment:**
   - *Status:* **PENDING**
   - *Detail:* How furnace electrical power (kWh/heat), refractory liner wear, and direct labor overheads are apportioned.
4. **Historical Pricing Reconciliation Prior to Cutoff:**
   - *Status:* **PENDING**
   - *Detail:* Method of establishing opening stock unit rates for the 741 items on 12 October 2026.
