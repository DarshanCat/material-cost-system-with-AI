# Item Code Generator — VSPL Item Nomenclature Standard v1.0

Status: implemented in code, **not deployed**. Migration `008_item_code_registry` is written but **not executed**.
Migration `009_material_item_cost_head` is a **proposal only** (in `backend/migrations/proposed/`, outside Alembic's
version location). No database was written while building this.

Source of truth: `VSPL_Item_Nomenclature_Standard.docx` (Version 1.0, Phase 1, owner Stores). Machine-readable copy:
`backend/app/services/item_nomenclature.py`. Business rules: `docs/BUSINESS_RULES.md` M1–M1d, M2–M4.

## 1. Workflow

1. **Search the master** (active and retired items). If the item exists, use its code.
2. **Choose the owning department**, then a **category owned by it**. The cost head is derived from the category.
3. **Write the description** to the category pattern; choose an approved **UOM**.
4. **Preview** (`POST /api/v1/item-codes/preview`): errors, warnings, duplicates and the **provisional** code. Nothing is reserved.
5. **Stores submits**; **Management approves** (never the requester). The code is allocated at approval, recorded in
   the permanent registry, and the item history gets a `REGISTERED` entry.
6. **Retire** = mark Inactive with a reason (Management/Admin). The code stays consumed for ever.

## 2. Rules and approved decisions

| # | Decision | Implementation |
|---|---|---|
| 2.1 | Stores raises requests; Management approves; no self-approval. | Existing RBAC unchanged (`item:approve` = Management, Admin). Self-approval → 403. Request row locked during decisions. |
| 2.2 | Next serial = highest serial ever issued + 1; never fill gaps or reuse. | `ItemCodeService.allocate_code`: max of existing item codes (any status), `item_code_registry`, and `item_code_sequences.last_serial`, under `SELECT … FOR UPDATE`. |
| 2.3 | Preserve retired codes; absence from a workbook ≠ retirement. | Registry is append-only. No workbook-derived retirement exists anywhere in code. |
| 2.4 | v1.0 strictly for new items; new departments/categories need a standard update. | `validate_proposal` rejects anything outside the tables in `item_nomenclature.py`. |
| 2.5 | Reject when serial 999 is exhausted; no four-digit serials. | `409` from allocation; preview shows `serial_exhausted`. |
| 2.6 | Only Kg, Nos, Ltr, Pack, Roll, Mtr for new items; legacy aliases mapped. | `APPROVED_UOMS`, `UOM_ALIASES`, `normalize_uom_code`. Requests carry a UOM id, so the alias map applies to text input (rules endpoint publishes it). |
| 2.7 | Reuse `material_aliases` only if safe; otherwise propose a dedicated table. | **Not reused for writing.** See §3.3. Approved aliases *are* searched (read-only) for duplicates. |
| 2.8 | Reject missing fields / invalid whitespace; Title Case is a warning; keep ISO designations and abbreviations. | `validate_description`. IT (Inserts & Tools) skips Title Case advice. Acronyms/grade codes without vowels (CRC, SVLHTC) do not trigger ALL CAPS. |
| 2.9 | Do not edit `seed.py`; add standard references via reviewed migration or guarded loader, not executed. | Nothing inserted by migration 008. Standard departments/UOMs come from the existing guarded loader (see §5). |
| 2.10 | Flag code/description inconsistencies; corrections only through an auditable path. | Report in Appendix B. Renames require `change_reason`, are limited to Management/Admin and are recorded with old/new values. |
| 2.11 | Work in the main checkout. | Done. |
| **2.12** | **Legacy data reconciliation.** Existing items with department/category codes outside v1.0 are grandfathered: not rejected, modified, renamed, deleted or deactivated because of it. New requests are validated strictly; legacy compatibility is kept separate and never weakens new-item validation. | Legacy items remain readable/editable (`GET/PUT /items`) without new-item validation. `GET /api/v1/item-codes/compliance` lists non-standard items **with item IDs** (read-only). Workbook findings are in Appendix A. |

## 3. Schema decisions

### 3.1 `MaterialItem.cost_head` — does not exist (proposal only)

`material_items` has **no** `cost_head` column. Per instruction, a migration is **proposed but not applied**:
`backend/migrations/proposed/009_material_item_cost_head.py`.

- **Column:** `cost_head VARCHAR(50) NULL`, `CHECK (cost_head IS NULL OR cost_head IN (<10 cost heads>))`.
- **Why nullable:** grandfathered items whose code/category do not map to v1.0 have no derivable cost head, and the
  standard forbids entering it by hand. `NOT NULL` would force guessing.
- **Mapping (Standard Section 4):**

  | Cat | Category | Dept | Cost head |
  |---|---|---|---|
  | RM | Raw Material | FDY | Material Cost |
  | LN | Lining Material | FDY | Lining Cost |
  | MD | Moulding Material | FDY | Moulding Cost |
  | CN | Consumables | FDY | Foundry Consumables |
  | PT | Paints & Coatings | FDY | Foundry Consumables |
  | CB | Cutting Blades | MCS | Machining Consumables |
  | IT | Inserts & Tools | MCS | Machining Consumables |
  | OL | Oils & Lubricants | MNT | Maintenance Cost |
  | BR | Bearings | MNT | Maintenance Cost |
  | BL | Belts | MNT | Maintenance Cost |
  | BN | Bolts & Nuts | MNT | Maintenance Cost |
  | QC | Quality Material | QLY | Quality Consumables |
  | PK | Packing Material | PKD | Packing Cost |
  | FU | Fuel | UTL | Energy / Fuel |
  | SF | Safety Material | GEN | Safety Cost |

- **Ambiguity:** `material_items.category` is free text with mixed conventions — standard names from the approved
  loader (`Bolts & Nuts`), legacy keys from the old request flow (`RAW_MATERIAL`, `ALLOY`, `CONSUMABLE`), names outside
  v1.0 (`General Consumables`, `Machine Spareparts`) and category/code disagreements (`QLY-QC-027` stored as
  `Consumables`). **Resolution proposed:** backfill only rows where the code is `<DEPT>-<CAT>-NNN` for a v1.0 pair
  **and** the category text equals that category's v1.0 name or code; everything else stays `NULL` for review.
  Legacy keys are not mapped (e.g. `CONSUMABLE` spans departments; v1.0 `CN` is Foundry-only).
- **Not done (needs approval):** applying it, and the application follow-up (set on registration, expose on read).
  Today the application derives the cost head from the selected category only for previews/rules — it does **not**
  infer cost heads for existing items.

### 3.2 Revision `008_item_code_registry` (written, not executed)

New tables only; no existing table, column or row is touched; no backfill.

| Table | Purpose |
|---|---|
| `item_code_sequences` | PK `(department_code, category_code)`, `last_serial` CHECK 0–999. Row created lazily at first allocation. |
| `item_code_registry` | Every generator-issued code: unique `item_code`, unique `material_item_id`, serial CHECK 1–999, request, standard version, issuer, time. **Append-only.** |
| `item_master_audit_logs` | REGISTERED / RENAMED / RETIRED / REACTIVATED / METADATA_UPDATED with old/new values, reason, actor. **Append-only.** |

Append-only is enforced three ways (as for the stock ledger): ORM guard (`app/db/item_code_guard.py`), SQLite triggers
(tests), PostgreSQL triggers in the migration. Recommended DBA step: `REVOKE UPDATE, DELETE, TRUNCATE` on the two
history tables from the application role.

### 3.3 Alternate names — `material_aliases` is not safe to reuse for writing

`material_aliases` maps raw **heat-log** text to an item; an approved alias auto-resolves heat charge lines and so
affects costing (`PARTIAL_COST` vs costed). It requires an existing item (cannot hold names proposed on a request), has
its own approval lifecycle, and a global unique key. Writing the standard's "Alternate Names" there would silently
change heat-log mapping. **Proposed** (not created): a dedicated `item_alternate_names` table
(`id, material_item_id FK, alternate_name, normalized_key UNIQUE, created_by, created_at`, append-only history),
captured on the request and written at approval. Until then, approved `material_aliases` are searched read-only for
duplicates, and the registration form does not capture alternate names.

## 4. API

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/api/v1/item-codes/rules` | `item_request:read` | Standard tables plus database IDs and which v1.0 departments/UOMs are not provisioned. |
| POST | `/api/v1/item-codes/preview` | `item_request:read` | Non-reserving; body fields optional; `exclude_request_id` for reviewing a request. |
| GET | `/api/v1/item-codes/compliance` | `item:read` | Read-only list of non-standard existing items with IDs and reasons. |
| GET | `/api/v1/items/{id}/history` | `item:read` | Registry entry (if generator-issued) and item history. |
| GET | `/api/v1/items/categories` | `item:read` | Now the 15 v1.0 categories (`category` = stored name, plus code, department, cost head). |
| PUT | `/api/v1/items/{id}` | `item:update` | Unchanged permission. Now audited; `change_reason` required to rename or retire/reactivate. |

## 5. Deployment dependencies and safe rollout

1. **Provision standard references first.** The seed (`app/db/seed.py`, not edited) carries pre-standard department
   codes `MSP`, `GNS`, `PKG`, `QLT`, `HMC`, `CNC` and lacks `MCS`, `QLY`, `PKD`, `UTL`, `GEN` and UOMs `PACK`, `ROLL`.
   Until those exist, new requests can only target FDY and MNT (and KG/NOS/LTR/MTR). The guarded loader
   `backend/scripts/load_reference_master.py` inserts them, **but** `departments.name` is unique and the seed already
   uses `Machine Shop` (MSP) and `General/Stores` (GNS); the loader will abort on those name conflicts. A decision is
   needed (rename the seeded rows, or approve different names) — not made here.
2. **Run the loader before revision 008.** The loader accepts only revision `007_opening_val_versioning` and counts
   rows in every model table; with this code deployed against a 007 database it will refuse (new tables missing), and
   against 008 it will refuse (revision mismatch). Both fail closed. Either run it before deploying this change, or
   have its approved revision re-reviewed.
3. **Apply revision 008** (non-production first), then deploy the backend and frontend. Without 008, previews work
   (with a warning) but approvals and `PUT /items` return `503` rather than allocating or editing unsafely.
4. **Reject legacy open requests.** Requests drafted/submitted before v1.0 enforcement (e.g. category `ALLOY`) fail
   re-validation with `422`; reject them with a reason and raise them again.
5. **Review the compliance report** (`GET /item-codes/compliance`) for the actual database and decide on Appendix B.

## 6. Open items

- Stores is not given `item:update`, so retirement is done by Management/Admin. The standard says "Only Stores creates or
  retires item codes"; a Stores-initiated retirement/correction request with Management approval is not built.
- Foundry and Purchase keep their existing `item_request:create` permission (RBAC unchanged). Restricting new requests to
  Stores only is a policy decision.
- Alternate names table (§3.3) and `cost_head` (§3.1) await approval.
- Live PostgreSQL concurrency test (`test_postgres_concurrent_allocation_never_duplicates`) is opt-in and needs revision
  008 on the disposable test database.

## Appendix A/B — Existing non-standard codes and inconsistencies (from the workbooks, not modified)

Generated read-only from the two workbooks with `item_nomenclature.classify_existing_item`. Workbooks have no database
IDs; the row number is the Excel row. Database item IDs are returned by `GET /api/v1/item-codes/compliance` against the
real database (not queried here, per the no-database-access constraint).

### Approved workbook (loader source, SHA-256 6005441b…)

391 item rows; **0 non-standard**.


### Updated workbook `VSPL_Item_Master_updated (6) (4).xlsx`

761 item rows; **152 non-standard**.

| Row | Item code | Department | Category | Status | Reasons |
|---|---|---|---|---|---|
| 466 | `GEN-GC-001` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 467 | `GEN-GC-002` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 478 | `GEN-GC-003` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 479 | `GEN-GC-004` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 480 | `GEN-GC-005` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 481 | `MNT-PF-001` | Maintenance | Pneumatic Fittings | Active | Category 'PF' is not a v1.0 category. Stored category 'Pneumatic Fittings' is not a v1.0 category name or code. |
| 487 | `GEN-GC-006` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 488 | `GEN-GC-007` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 490 | `GEN-GC-008` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 491 | `GEN-GC-009` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 494 | `GEN-GC-010` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 496 | `MNT-EL-001` | Maintenance | Electrical | Active | Category 'EL' is not a v1.0 category. Stored category 'Electrical' is not a v1.0 category name or code. |
| 497 | `GEN-GC-011` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 498 | `GEN-GC-012` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 499 | `GEN-GC-013` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 500 | `GEN-GC-014` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 501 | `GEN-GC-015` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 502 | `GEN-GC-016` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 503 | `GEN-GC-017` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 511 | `GEN-GC-018` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 512 | `GEN-GC-019` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 513 | `GEN-GC-020` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 514 | `GEN-GC-021` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 515 | `GEN-GC-022` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 523 | `FDY-CH-001` | Foundry | Chemical | Active | Category 'CH' is not a v1.0 category. Stored category 'Chemical' is not a v1.0 category name or code. |
| 524 | `FDY-CH-002` | Foundry | Chemical | Active | Category 'CH' is not a v1.0 category. Stored category 'Chemical' is not a v1.0 category name or code. |
| 525 | `FDY-CH-003` | Foundry | Chemical | Active | Category 'CH' is not a v1.0 category. Stored category 'Chemical' is not a v1.0 category name or code. |
| 526 | `FDY-CH-004` | Foundry | Chemical | Active | Category 'CH' is not a v1.0 category. Stored category 'Chemical' is not a v1.0 category name or code. |
| 529 | `MNT-ES-001` | Maintenance | Electrical Spares | Active | Category 'ES' is not a v1.0 category. Stored category 'Electrical Spares' is not a v1.0 category name or code. |
| 530 | `MNT-MS-001` | Maintenance | Mechanical Spares | Active | Category 'MS' is not a v1.0 category. Stored category 'Mechanical Spares' is not a v1.0 category name or code. |
| 531 | `VSPL-DV-72` | Quality | Quality Material | Active | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). |
| 533 | `MCS-IT-TNMG160408` | Machine Shop | Inserts & Tools | Active | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Code appears 2 times in the workbook. |
| 534 | `MCS-IT-WNMG080408` | Machine Shop | Inserts & Tools | Active | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Code appears 2 times in the workbook. |
| 535 | `MCS-IT-TNMG160404` | Machine Shop | Inserts & Tools | Active | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). |
| 536 | `MCS-IT-TDXU3E03` | Machine Shop | Inserts & Tools | Active | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). |
| 547 | `MNT-FL-001` | Maintenance | Filters | Active | Category 'FL' is not a v1.0 category. Stored category 'Filters' is not a v1.0 category name or code. |
| 548 | `MNT-FL-002` | Maintenance | Filters | Active | Category 'FL' is not a v1.0 category. Stored category 'Filters' is not a v1.0 category name or code. |
| 549 | `GEN-GC-023` | General/Stores | General Consumables | Active | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 551 | `MNT-BN-134` | Foundry | Bolts & Nuts | Active | Code prefix 'MNT' differs from the item's department code 'FDY'. |
| 553 | `MNT-EL-002` | Maintenance | Electrical Use | Active | Category 'EL' is not a v1.0 category. Stored category 'Electrical Use' is not a v1.0 category name or code. |
| 554 | `SEG-MS-001` | Segregation | Machine Spareparts | Active | Department prefix 'SEG' is not a v1.0 department. Category 'MS' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. Department 'Segregation' is not on the workbook's Departments sheet. |
| 555 | `ADM-GC-001` | Admin | General Consumables | Active | Department prefix 'ADM' is not a v1.0 department. Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. Department 'Admin' is not on the workbook's Departments sheet. |
| 556 | `MCS-CN-001` | Machine Shop | Consumables | Active | Category 'CN' belongs to department 'FDY', not 'MCS'. |
| 604 | `MNT-FL-003` | Maintenance | Filters | Active | Category 'FL' is not a v1.0 category. Stored category 'Filters' is not a v1.0 category name or code. |
| 605 | `MCS-PS-001` | Machine Shop | Printing & Stationery | Active | Category 'PS' is not a v1.0 category. Stored category 'Printing & Stationery' is not a v1.0 category name or code. |
| 606 | `MCS-PS-002` | Machine Shop | Printing & Stationery | Active | Category 'PS' is not a v1.0 category. Stored category 'Printing & Stationery' is not a v1.0 category name or code. |
| 607 | `MCS-PS-003` | Machine Shop | Printing & Stationery | Active | Category 'PS' is not a v1.0 category. Stored category 'Printing & Stationery' is not a v1.0 category name or code. |
| 611 | `F3H-SP-001` | F3 HMC | Machine Spare Part | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F3 HMC' is not on the workbook's Departments sheet. |
| 612 | `F3H-CM-001` | F3 HMC | Machine Consumable | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F3 HMC' is not on the workbook's Departments sheet. |
| 613 | `MNT-MS-002` | Plant Maintenance | Machine Spare Part | (blank) | Category 'MS' is not a v1.0 category. Stored category 'Machine Spare Part' is not a v1.0 category name or code. Department 'Plant Maintenance' is not on the workbook's Departments sheet. |
| 614 | `MCS-SP-001` | F2 Machine Shop | Machine Spare Part | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spare Part' is not a v1.0 category name or code. Department 'F2 Machine Shop' is not on the workbook's Departments sheet. |
| 622 | `GEN-GC-024` | General/Stores | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 623 | `GEN-GC-025` | General/Stores | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 625 | `GEN-GC-026` | General/Stores | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 626 | `GEN-GC-027` | General/Stores | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 629 | `GEN-GC-028` | General/Stores | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 630 | `GEN-GC-029` | General/Stores | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 631 | `MCS-SP-002` | F2 HMT | Machine Consumable | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Consumable' is not a v1.0 category name or code. Department 'F2 HMT' is not on the workbook's Departments sheet. |
| 635 | `SEG-MS-002` | Segregation | Machine Spareparts | (blank) | Department prefix 'SEG' is not a v1.0 department. Category 'MS' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. Department 'Segregation' is not on the workbook's Departments sheet. |
| 642 | `MNT-CN-001` | Maintenance | Consumables | (blank) | Category 'CN' belongs to department 'FDY', not 'MNT'. |
| 643 | `MNT-CN-002` | Maintenance | Consumables | (blank) | Category 'CN' belongs to department 'FDY', not 'MNT'. |
| 644 | `MNT-CN-003` | Maintenance | Consumables | (blank) | Category 'CN' belongs to department 'FDY', not 'MNT'. |
| 645 | `MNT-MS-003` | Maintenance | Mechanical Spares | (blank) | Category 'MS' is not a v1.0 category. Stored category 'Mechanical Spares' is not a v1.0 category name or code. |
| 647 | `FDY-SP-001` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 648 | `FDY-SP-002` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 649 | `MCS-SP-003` | Machine Shop | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 650 | `MCS-SP-004` | Machine Shop | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 651 | `MCS-SP-005` | Machine Shop | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 656 | `MNT-MS-004` | Maintenance | Mechanical Spares | Active | Category 'MS' is not a v1.0 category. Stored category 'Mechanical Spares' is not a v1.0 category name or code. |
| 657 | `FDY-MS-001` | Foundry | Machine Spareparts | (blank) | Category 'MS' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 658 | `MNT-MS-005` | Maintenance | Machine Spareparts | (blank) | Category 'MS' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 659 | `MCS-IT-WNMG080408` | Machine Shop | Inserts & Tools | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Code appears 2 times in the workbook. |
| 660 | `MCS-IT-TNMG160408` | Machine Shop | Inserts & Tools | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Code appears 2 times in the workbook. |
| 663 | `GEN-GC-030` | General/Stores | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 665 | `MNT-MS-006` | Maintenance | Machine Spareparts | (blank) | Category 'MS' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 666 | `MNT-MS-007` | Maintenance | Machine Spareparts | (blank) | Category 'MS' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 669 | `MCS-SP-006` | Machine Shop | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 670 | `MCS-SP-007` | Machine Shop | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 671 | `MCS-SP-008` | Machine Shop | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 672 | `MCS-SP-009` | Machine Shop | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 673 | `MCS-SP-010` | Machine Shop | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 674 | `MCS-SP-011` | Machine Shop | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 675 | `MCS-SP-012` | Machine Shop | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 676 | `F3H-SP-002` | F3 HMC | Machine Spareparts | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F3 HMC' is not on the workbook's Departments sheet. |
| 677 | `F3H-SP-003` | F3 HMC | Machine Spareparts | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F3 HMC' is not on the workbook's Departments sheet. |
| 678 | `F3H-SP-004` | F3 HMC | Machine Spareparts | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F3 HMC' is not on the workbook's Departments sheet. |
| 679 | `MNT-MS-008` | Maintenance | Machine Spareparts | (blank) | Category 'MS' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 680 | `MCS-PS-004` | Machine Shop | Printing & Stationery | (blank) | Category 'PS' is not a v1.0 category. Stored category 'Printing & Stationery' is not a v1.0 category name or code. |
| 681 | `GEN-GC-031` | General/Stores | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 682 | `GEN-GC-032` | General/Stores | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 683 | `GEN-GC-033` | General/Stores | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 684 | `F2-CN-001` | F2 | Consumables | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F2' is not on the workbook's Departments sheet. |
| 685 | `F2-CN-002` | F2 | Consumables | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F2' is not on the workbook's Departments sheet. |
| 686 | `F2-SP-001` | F2 | Machine Spareparts | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F2' is not on the workbook's Departments sheet. Code appears 2 times in the workbook. |
| 692 | `GEN-GC-034` | General/Stores | Consumables | (blank) | Category 'GC' is not a v1.0 category. |
| 693 | `GEN-GC-035` | General/Stores | Consumables | (blank) | Category 'GC' is not a v1.0 category. |
| 694 | `GEN-GC-036` | General/Stores | Consumables | (blank) | Category 'GC' is not a v1.0 category. |
| 695 | `GEN-GC-037` | General/Stores | Consumables | (blank) | Category 'GC' is not a v1.0 category. |
| 696 | `ADM-GC-002` | Admin | Printing & Stationery | (blank) | Department prefix 'ADM' is not a v1.0 department. Category 'GC' is not a v1.0 category. Stored category 'Printing & Stationery' is not a v1.0 category name or code. Department 'Admin' is not on the workbook's Departments sheet. |
| 698 | `MNT-ES-002` | Maintenance | Electrical Spares | Active | Category 'ES' is not a v1.0 category. Stored category 'Electrical Spares' is not a v1.0 category name or code. |
| 700 | `MNT-MS-009` | Maintenance | Machine Spareparts | (blank) | Category 'MS' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 701 | `MNT-MS-010` | Maintenance | Machine Spareparts | (blank) | Category 'MS' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 702 | `F3D-CN-001` | F3 Deburing | Consumables | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F3 Deburing' is not on the workbook's Departments sheet. |
| 703 | `F2-SP-001` | F2 MACHINE SHOP | Machine Spareparts | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F2 MACHINE SHOP' is not on the workbook's Departments sheet. Code appears 2 times in the workbook. |
| 704 | `F2-SP-002` | F2 MACHINE SHOP | Machine Spareparts | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F2 MACHINE SHOP' is not on the workbook's Departments sheet. |
| 705 | `PM-MC-001` | Plant Maintenance | Machine Consumable | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'Plant Maintenance' is not on the workbook's Departments sheet. |
| 706 | `PM-MC-002` | Plant Maintenance | Machine Consumable | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'Plant Maintenance' is not on the workbook's Departments sheet. |
| 707 | `PM-MC-003` | Plant Maintenance | Machine Consumable | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'Plant Maintenance' is not on the workbook's Departments sheet. |
| 708 | `PM-MC-004` | Plant Maintenance | Machine Consumable | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'Plant Maintenance' is not on the workbook's Departments sheet. |
| 709 | `PM-MC-005` | Plant Maintenance | Machine Consumable | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'Plant Maintenance' is not on the workbook's Departments sheet. |
| 710 | `PM-MC-006` | Plant Maintenance | Machine Consumable | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'Plant Maintenance' is not on the workbook's Departments sheet. |
| 711 | `PM-MC-007` | Plant Maintenance | Machine Consumable | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'Plant Maintenance' is not on the workbook's Departments sheet. |
| 712 | `PM-SP-001` | Plant Maintenance | Machine Spareparts | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'Plant Maintenance' is not on the workbook's Departments sheet. |
| 713 | `PM-SP-002` | Plant Maintenance | Machine Spareparts | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'Plant Maintenance' is not on the workbook's Departments sheet. |
| 715 | `QLY-QC-027` | Quality | Consumables | (blank) | Stored category 'Consumables' (CN) differs from the code's category 'QC'. |
| 717 | `F2-SP-003` | F2 MACHINE SHOP | Machine Spareparts | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F2 MACHINE SHOP' is not on the workbook's Departments sheet. |
| 718 | `F2-SP-004` | F2 MACHINE SHOP | Machine Spareparts | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F2 MACHINE SHOP' is not on the workbook's Departments sheet. |
| 719 | `FDY-SP-003` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 720 | `FDY-SP-004` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 721 | `FDY-SP-005` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 722 | `FDY-SP-006` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 723 | `FDY-SP-007` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 724 | `FDY-SP-008` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 725 | `FDY-SP-009` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 726 | `FDY-SP-010` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 727 | `FDY-SP-011` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 728 | `FDY-SP-012` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 729 | `FDY-SP-013` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 730 | `FDY-SP-014` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 731 | `FDY-SP-015` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 732 | `FDY-SP-016` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 733 | `FDY-SP-017` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 734 | `FDY-SP-018` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 735 | `FDY-SP-019` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 736 | `FDY-SP-020` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 737 | `FDY-SP-021` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 738 | `FDY-SP-022` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 739 | `FDY-SP-023` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 742 | `F3H-CN-001` | F3 HMC | Consumables | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F3 HMC' is not on the workbook's Departments sheet. |
| 743 | `F3C-CN-001` | F3 CNC | Consumables | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F3 CNC' is not on the workbook's Departments sheet. |
| 744 | `F3C-CN-002` | F3 CNC | Consumables | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F3 CNC' is not on the workbook's Departments sheet. |
| 745 | `F3C-CN-003` | F3 CNC | Consumables | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department 'F3 CNC' is not on the workbook's Departments sheet. |
| 746 | `FDY-SP-024` | Foundry | Machine Spareparts | (blank) | Category 'SP' is not a v1.0 category. Stored category 'Machine Spareparts' is not a v1.0 category name or code. |
| 752 | `MNT-ES-003` | Maintenance | Electrical Spares | (blank) | Category 'ES' is not a v1.0 category. Stored category 'Electrical Spares' is not a v1.0 category name or code. |
| 753 | `MNT-ES-004` | Maintenance | Electrical Spares | (blank) | Category 'ES' is not a v1.0 category. Stored category 'Electrical Spares' is not a v1.0 category name or code. |
| 754 | `MNT-ES-005` | Maintenance | Electrical Spares | (blank) | Category 'ES' is not a v1.0 category. Stored category 'Electrical Spares' is not a v1.0 category name or code. |
| 755 | `GEN-GC-038` | General/Stores | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 756 | `GEN-GC-039` | General/Stores | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 757 | `GEN-GC-040` | General/Stores | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 760 | `MNT-CN-004` | Maintenance | Consumables | (blank) | Category 'CN' belongs to department 'FDY', not 'MNT'. |
| 761 | `GEN-GC-041` | Maintenance | General Consumables | (blank) | Category 'GC' is not a v1.0 category. Code prefix 'GEN' differs from the item's department code 'MNT'. Stored category 'General Consumables' is not a v1.0 category name or code. |
| 767 | `` |  |  | (blank) | Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits). Department '' is not on the workbook's Departments sheet. |

### Code ↔ description inconsistencies between the workbooks

| Item code | Approved description | Updated description |
|---|---|---|
| `FDY-RM-007` | CRC Scrap-Low High MN | CRC Scrap- High MN |
| `FDY-CN-003` | Emery Paper | Emery Paper 600 grade |
| `FDY-CN-016` | Flop Disk 5 Inch | Flap Disk 5 Inch |
| `FDY-CN-017` | Flop Disk 4 Inch | Flap Disk 4 Inch |
| `PKD-PK-005` | Bubble Roll | Air Bubble Roll |
| `PKD-PK-006` | Cutan Box | Curtan Box |

**Approved codes absent from the updated workbook (16):** `FDY-RM-003`, `FDY-RM-010`, `FDY-CN-018`, `MNT-OL-016`, `PKD-PK-001`, `PKD-PK-003`, `PKD-PK-004`, `MNT-BN-035`, `MNT-BN-085`, `MNT-BN-102`, `MNT-BN-105`, `MNT-BN-108`, `MNT-BN-110`, `MNT-BN-117`, `MNT-BN-118`, `FDY-PT-024`

Absence is **not** treated as retirement. These codes remain consumed (never reissued) and need a recorded decision.

**Duplicate descriptions in the updated workbook:** 'nylon brush 6mm' → FDY-PT-027, FDY-PT-034
