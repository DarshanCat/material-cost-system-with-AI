# VSPL Data Loading — Source Inventory, Reconciliation and Safe Import Plan

**Date:** 2026-10-26 · **Scope:** read-only inspection, reconciliation and plan · **Status:** NO DATA LOADED

No database write, migration, seed or import (commit mode) was executed. The database was inspected only through
a session forced read-only (`default_transaction_read_only=on`) inside a READ ONLY transaction that was rolled back.
The reference loader was run only in its default dry-run mode (READ ONLY transaction, rolled back). Source files were
opened read-only and were not modified.

Companion files in this folder:
- `ledger_item_reconciliation.csv` — all 757 items in the 16-Oct Master Ledger with master/nomenclature status and proposed action.
- `opening_stock_candidates.csv` — all 226 non-zero "Opening Stock" rows with their blocking status.

---

## 1. Source-file inventory

The `data` folder (moved during this review from `C:\VSPL_MM\data` to `C:\VSPL_MM\Material managment system\data`;
hashes verified identical before and after the move) contains **four workbooks, all of them outputs of the external
`material_ledger_engine.py`, not primary records**. It does **not** contain an item master, vendor master, raw
transaction register, stocktake or price list.

| File | SHA-256 (prefix) | Sheets (non-empty rows) | What it is | Use for import |
|---|---|---|---|---|
| `VSPL_Master_Ledger_2026-10-16.xlsx` | `72e6aeb75d3b45b4` | Ledger (757 items + header), Purchase Register (header only), Vendor Summary (header only) | Per-item **aggregates**: Opening Stock (manually set, undated), Total Received/Issued/Waste, Closing Stock, Reorder Level. All 11 price/value columns empty for every item (only "Price Status = NO PRICE" on 26 rows). | Reference only. Aggregates cannot become ledger transactions without inventing dates/documents. |
| `Anomaly_Report_2026-10-16.xlsx` | `f3b136a19f04678f` | Anomalies (2,636), Summary (9) | Data-quality findings from the engine run | Evidence only; never imported |
| `Daily_Activity_Report_2026-10-12.xlsx` | `35afca839715a0dc` | Overview, Dept Balance, Issued Summary (42 items), Issued by Dept, Waste by Reason, Parts/Heat (no data), Reorder Alerts (58) | Daily summary: 268 issue transactions on 12-Oct | Evidence only |
| `Daily_Activity_Report_2026-10-15.xlsx` | `3cd299a82fda7202` | Same layout; Issued Summary (33 items incl. `NOT FOUND` "BODY FILLER") | Daily summary: 264 issue transactions on 15-Oct | Evidence only |

Other sources consulted (read-only) to establish authority:

| Source | SHA-256 (prefix) | Role |
|---|---|---|
| `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Item_Master.xlsx` | `6005441b7b022cc8` | **Approved item master** (391 items, 7 departments, 6 UOMs, 15 categories); the only workbook the guarded loader accepts (hash pinned). 100% v1.0-compliant. |
| `VSPL_Item_Master_updated (6) (4).xlsx` (repo root, untracked) | `bcb79b9ba8cba43b` | Unapproved extended master (761 rows; 152 non-standard rows). Matches the Master Ledger item list. |
| `C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Material_Entry.xlsx` | — | Raw July entries only (GRN 4 rows 14-Jul; Issue 558 rows 13–15-Jul + typo dates; Waste 6). **Not** the source of the October aggregates. |
| `VSPL_Foundry_Heat_Log.xlsx` (same folder) | — | July heats (DEC-007 mass-balance defects). |
| `docs/reports/phase7_*`, `VSPL_Phase7_Stage2_1_Evidence_Freeze_20261013` | — | Prior audits, decision register DEC-001..008, gate register G1..G13. |
| `docs/reports/phase7_stocktake_preparation/VSPL_Physical_Stocktake_Register.xlsx` | — | Stocktake template; **Sheet D (Opening Inventory Approval) has 0 counts entered.** |
| `C:\VSPL_MM\backups\vspl_material_management_rev006_pre007_20261025_173249.dump` | `3d840cd2…` | Existing backup taken at revision 006 (before 007). No backup at 007 yet. |

**Missing primary source:** the Master Ledger and daily reports were generated from a newer `VSPL_Material_Entry.xlsx`
that includes October transactions (e.g. 268 issues on 12-Oct). That workbook is **not** in the data folder; only the
July version exists. Without it, no transaction can be reconciled or imported.

## 2. Current database state (read-only)

Target: `127.0.0.1:5439 / vspl_material_management` (non-production), `ENVIRONMENT=development`.

| Item | Value |
|---|---|
| Alembic revision | `007_opening_val_versioning` |
| Rows in every application table (37 tables, incl. departments, uoms, material_items, vendors, stock_ledger_entries, item_opening_valuations, all documents, heats, costing, audit logs) | **0** |
| Revision-008 tables (`item_code_*`, `item_master_audit_logs`) | Not present (migration 008 not applied) |

Consequences: nothing has been loaded before; there are no "already present" records and no seed-data conflicts
(the test seed codes MSP/GNS/QLT were never written to this database).

## 3. Source-versus-database reconciliation and dry-run counts

| Entity | Authoritative source | Source records | In DB | Insert | Update | Skip (already present) | Reject / Hold |
|---|---|---|---|---|---|---|---|
| Departments | Approved item master (sheet Departments) | 7 (FDY, MCS, MNT, QLY, PKD, UTL, GEN) | 0 | **7** | 0 | 0 | 0 |
| UOMs | Approved item master (sheet UOM) | 6 (Kg, Nos, Ltr, Pack, Roll, Mtr → KG, NOS, LTR, PACK, ROLL, MTR) | 0 | **6** | 0 | 0 | 0 |
| Material items — approved | Approved item master | 391 | 0 | **391** | 0 | 0 | 0 |
| Material items — beyond approved, v1.0-format codes | Updated workbook / Master Ledger (unapproved) | 236 | 0 | 0 | 0 | 0 | **236 HOLD** (no approved source) |
| Material items — non-standard codes | Updated workbook / Master Ledger (unapproved) | 145 | 0 | 0 | 0 | 0 | **145 HOLD** (grandfathering needs approval) |
| Vendors | none (Purchase Register empty; 12 vendor names only in anomaly text) | 0 | 0 | 0 | 0 | 0 | 12 names HOLD |
| Opening balances (quantity) | none certified (Gate G7) | 226 non-zero ledger "Opening Stock" values | 0 | **0** | 0 | 0 | **226 HOLD** (128 candidate-if-certified, 8 UOM mismatch, 90 item not in approved master) |
| Opening valuations (rate) | none (0 rates in any source) | 0 | 0 | 0 | 0 | 0 | — (`OPENING_VALUATION_MISSING` by rule C3) |
| GRN / Issue / Waste documents | missing (October entry workbook not supplied) | 0 primary rows | 0 | 0 | 0 | 0 | — |
| Heats | missing | 0 | 0 | 0 | 0 | 0 | — |
| Master-ledger aggregates (Received/Issued/Waste totals) | n/a | 757 | — | **never** | — | — | not importable (would fabricate transactions) |

The approved-master counts were confirmed by the loader's source validation (dry run printed
`departments=7 uoms=6 items=391`, workbook hash verified). Its server stage then **rejected the target** — see §6 blocker B1.

## 4. Data-quality and business-rule exceptions

### 4.1 Item master and nomenclature
- Approved master: 391/391 conform to Nomenclature Standard v1.0; UOMs all approved (Nos 313, Kg 61, Ltr 17).
- Ledger items not in the approved master: **381** (236 v1.0-format, 145 non-standard: categories GC/SP/MS/CH/EL/ES/FL/PF/PS, departments ADM/SEG/F2/F3H/F3D/PM/VSPL, non-serial codes like `MCS-IT-TNMG160408`, `VSPL-DV-72`). 50 of the non-standard items carry stock or movements.
- **Serial-order risk for the 236 v1.0-format extras:** they already carry codes used on the floor. The generator issues highest+1 in approval order, so codes would only match if requests are approved in exact serial order; for `FDY-CN` (extras start at 022 then jump to 025) and `UTL-FU` the floor codes are **not contiguous** and cannot be reproduced by the generator. These need a decision (see Q3).
- Attribute conflicts, ledger vs approved master (376 shared items): **UOM 13** (e.g. `FDY-CN-013/014/016/017` Kg→Nos, `MNT-OL-002` Ltr→Nos, `PKD-PK-007` Nos→Pack), **description 6** (`FDY-RM-007`, `FDY-CN-003/016/017`, `PKD-PK-005/006`), reorder level 7 (blank→0).
- 15 approved codes are absent from the ledger (`FDY-RM-003/010`, `FDY-CN-018`, `FDY-PT-024`, `MNT-OL-016`, `PKD-PK-003/004`, 8 × `MNT-BN`). Absence is **not** retirement; they load as approved and stay consumed.
- Ledger UOM values outside v1.0: Kgs (2), Box (1), Set (2), FT (1).

### 4.2 Stock and valuation
- **No certified opening stock.** Ledger "Opening Stock" is the engine's manually set, undated value, not a 12-Oct stocktake (Gate G7 BLOCKED; stocktake Sheet D empty).
- **Closing stock negative for 90 items** (45 in the approved master), e.g. Borings-500/10 −34,333 kg, Borings-450/10 −25,994 kg, Gattings-450/10 −19,078 kg — evidence that receipts/opening are incomplete. The application forbids negative stock (`ALLOW_NEGATIVE_STOCK=False`).
- **Zero prices anywhere** (Opening Rate, Avg Rate, Purchase Register all empty) → no opening valuations; costing would report `OPENING_VALUATION_MISSING` / `INSUFFICIENT_COST_DATA`, which is correct behaviour, not something to fill in.

### 4.3 Transactions (from the anomaly report; primary rows unavailable)
| Category | Count | Note |
|---|---|---|
| Invalid quantity | 1,166 | 897 missing/non-numeric, 269 zero/negative (ISSUE 1,151) |
| Unknown item | 831 | 264 distinct descriptions; "Silicon" alone 471 rows; some rows carry codes in the description field |
| Heat check | 456 | 332 "metal tapped > total charge"; 124 melt-loss out of range |
| Negative stock | 90 | as above |
| Possible duplicate | 51 | RECEIPT 28, ISSUE 22, WASTE 1 (same date/item/ref/qty) |
| Missing price | 15 | raw-material receipts without rate (violates Rule 6) |
| Unregistered vendor | 12 | e.g. "mahalakshmi packin works", "TECHNOVATIVE ENGG" |

### 4.4 Governance status (from `docs/reports/phase7_stage3a8`, 22-Oct)
DEC-001…DEC-008 all `PENDING_REVIEW`; gates G1 (executive sign-off), G2 (cutoff policy, Scenario A recommended),
G3 (commercial rates), G7 (certified stocktake), G12 (PostgreSQL verified), G13 (backup/restore rehearsal) **BLOCKED**.
`AUTHORIZATION_BOUNDARIES.md` forbids opening balances except from certified Sheet D counts and forbids synthetic
data for the 82-day gap.

### 4.5 Application-side risks found while mapping import paths (verified in code)
| Path | Risk |
|---|---|
| `POST /opening-balances/post` | No maker-checker (single Admin); `baseline_date` not enforced to 2026-10-12; item `is_active` and item-base-UOM compatibility not checked (Rule L7 requires both). Posts directly to the append-only ledger; can only be reversed. |
| Costing (`costing_service.py`) | `COSTING_CUTOFF_DATE` defined but never applied — pre-12-Oct movements would be valued (contradicts Rule C3). |
| `POST /excel-import/commit` | Trusts client JSON (partial re-validation), unparseable dates silently become today, no batch idempotency (re-commit creates duplicate DRAFT documents). Documents stay DRAFT until submit/approve, so the ledger is protected by the approval steps. |
| `POST /heats/import/commit` | Commits heat-by-heat (not atomic). |
| Authentication | `AUTH_PROVIDER=none` in the running configuration → every protected endpoint returns 401; API-based loading is impossible until an approved provider is configured. |
| `scripts/run-migrations.ps1` | Runs `alembic upgrade head` against whatever `.env` points to, with no target guard. `config.py` default port is 5432 (production OMS per boundaries doc); `.env` correctly sets 5439. |

## 5. Recommended import sequence (each stage gated; none authorized yet)

| # | Stage | Prerequisites | Mechanism | Dry run |
|---|---|---|---|---|
| 0 | Backup at revision 007 + restore rehearsal | G13 | `pg_dump -Fc` to `C:\VSPL_MM\backups` + SHA-256; restore into a scratch DB | n/a |
| 1 | Reference masters: 7 departments, 6 UOMs, 391 approved items | B1 resolved; G1 sign-off for master data | `backend/scripts/load_reference_master.py` (guarded, insert-only, single transaction) | yes (default mode) |
| 2 | Migration 008 (item code registry) | Stage 1 done (loader requires revision 007) | `alembic upgrade 008_item_code_registry` | `alembic upgrade 007:008 --sql` (offline SQL only) |
| 3 | Additional items (236 v1.0-format, 145 non-standard) | Q2/Q3 decided; approved master v2 with new hash, **or** item requests | Approved loader workbook revision **or** item request → Management approval | `POST /item-codes/preview` per item |
| 4 | Vendors | Vendor master from Purchase | `POST /vendors` (dedupe by normalised name) | none (409 on duplicate) |
| 5 | Opening balances as of 2026-10-12 | G2 (Scenario A), G7 certified Sheet D counts, opening-balance fixes (§4.5) | `POST /opening-balances/preview` then `/post` with `audit_reference` | yes (`/preview`) |
| 6 | Opening valuations | G3 approved ex-GST rates | `POST /costing/opening-valuations` (propose) → different user `/approve` | PROPOSED state is the review step |
| 7 | Post-cutoff transactions (GRN/Issue/Waste from 12-Oct) | Primary October entry workbook; vendors; stock baseline; cutoff fix in costing | `POST /excel-import/validate` → `/commit` (DRAFT) → submit → approve by a second user | yes (`/validate`) |
| 8 | Heats | DEC-007 resolution; aliases approved | `POST /heats/import/preview` → `/commit` | yes (`/preview`) |
| — | July 2026 history | DEC-002 (Scenario A = archive, no ledger posting) | not loaded to the live ledger | — |

## 6. Blockers and unresolved questions

**Blockers (technical)**
- **B1 — Loader vs migration 008 ordering.** The uncommitted Item Code Generator added three models. The loader requires revision 007 *and* every model table to exist, so today it fails closed against this database (`expected tables are missing: item_code_registry, item_code_sequences, item_master_audit_logs`, exit 2), and after 008 it would fail on the revision check. Options: (a) review and update the loader to accept revision 008 and treat the new tables as protected (count-unchanged); or (b) run the loader from a checkout without the 008 models before applying 008. Either needs your approval.
- **B2 — Authentication.** `AUTH_PROVIDER=none`; no API import (stages 4–8) is possible. Configuring a provider means editing `backend/.env` (protected) or an approved deployment setting.
- **B3 — Opening-balance and costing-cutoff gaps** (§4.5) should be fixed and tested before stages 5–7.
- **B4 — Primary October entry workbook missing.** Transactions cannot be reconciled or imported from aggregates.
- **B5 — No backup at revision 007** (only the 006 dump exists).

**Questions for you / management**
1. Is the approved 391-item workbook (hash `6005441b…`) still the master to load first, or has an extended master been approved? If approved, please supply it with its approval record so a new hash can be pinned.
2. For the 145 non-standard items: grandfather them (load with existing codes after approval) or re-register them under v1.0 codes? 50 of them hold stock/movements.
3. For the 236 v1.0-format extras already in floor use: load with their existing codes via an approved master revision (recommended; preserves codes on labels and reports), or re-request through the generator (codes may change; FDY-CN and UTL-FU cannot be reproduced)?
4. Which UOM is correct for the 8 conflicting opening-stock items (`FDY-CN-003/008/013/014/016/017`, `MNT-OL-002`, `PKD-PK-007`) and the 13 UOM conflicts overall?
5. Which descriptions are authoritative for the 6 changed codes (notably `FDY-RM-007` "CRC Scrap-Low High MN" vs "CRC Scrap- High MN")?
6. Has DEC-002 / Scenario A been signed, and has the 12-Oct physical stocktake been performed and certified (Sheet D)? Until then no opening balance can be posted.
7. Can Purchase/Finance supply ex-GST opening rates (G3) and the vendor master?
8. Please supply the current `VSPL_Material_Entry.xlsx` (with October entries) and heat log if post-cutoff transactions are to be loaded.

## 7. Commands (NOT executed)

Run from `C:\VSPL_MM\Material managment system\backend` with the virtual environment. Do not set `DATABASE_URL`
or any `PG*` variable in the loader's shell (the loader refuses them).

```powershell
# Stage 0 — backup at revision 007 (credentials supplied interactively / via a secured .pgpass, never on the command line)
pg_dump -h 127.0.0.1 -p 5439 -U <db_user> -d vspl_material_management -Fc -f C:\VSPL_MM\backups\vspl_material_management_rev007_pre_load_<YYYYMMDD_HHMMSS>.dump
certutil -hashfile C:\VSPL_MM\backups\vspl_material_management_rev007_pre_load_<...>.dump SHA256

# Stage 1 — reference masters (after B1 is resolved)
.\.venv\Scripts\python.exe scripts\load_reference_master.py            # dry run (READ ONLY, rolled back)
.\.venv\Scripts\python.exe scripts\load_reference_master.py --commit   # WRITE — requires explicit approval

# Stage 2 — migration 008
.\.venv\Scripts\alembic.exe upgrade 007_opening_val_versioning:008_item_code_registry --sql   # offline SQL review only
.\.venv\Scripts\alembic.exe upgrade 008_item_code_registry                                    # WRITE — requires approval
```

Stages 4–8 are API calls (HTTP, authenticated, after B2): dry runs `POST /api/v1/opening-balances/preview`,
`POST /api/v1/excel-import/validate`, `POST /api/v1/heats/import/preview`, `POST /api/v1/item-codes/preview`;
writes `POST /api/v1/opening-balances/post`, `POST /api/v1/excel-import/commit` (+ submit/approve),
`POST /api/v1/costing/opening-valuations` (+ approve by a second user), `POST /api/v1/vendors`.

**Transaction boundaries and rollback.** Loader: one transaction, verified counts, other tables unchanged, abort →
nothing written. Opening balances: one transaction per batch; after commit only ledger reversals (append-only).
Excel import: DRAFT documents only; cancel before approval. Full rollback for any stage = restore the Stage 0 dump.

## 8. Post-import validation checks

After Stage 1:
- `SELECT count(*) FROM departments` = 7, `uoms` = 6, `material_items` = 391; every other table 0.
- `GET /api/v1/item-codes/compliance` → `non_standard_count = 0`.
- Item codes, names, departments, UOMs match the approved workbook row for row (loader post-verification).

After Stage 2:
- `alembic_version` = `008_item_code_registry`; append-only triggers present on `item_code_registry` and `item_master_audit_logs`.
- `POST /item-codes/preview` for FDY/RM proposes `FDY-RM-027` (approved max 026 + 1).

After Stages 5–6:
- Exactly one `OPENING_BALANCE` row per counted item, all dated 2026-10-12, quantities equal to certified Sheet D.
- Sum of opening quantities per item equals the stocktake; no negative balances.
- Every positive opening balance has an APPROVED valuation, or appears in `GET /costing/exceptions` as `OPENING_VALUATION_MISSING`.

After Stage 7:
- Document counts and quantities per item equal the source register; no duplicate (date, item, ref, qty) rows.
- Closing balance per item = opening + receipts − issues − scrap; none negative.

## 9. Change statement

- **Database:** no records inserted, updated or deleted; no migration or seed run; loader executed only in dry-run mode (READ ONLY, rolled back, exit 2 at target checks).
- **Source data files:** not modified (hashes unchanged; the `data` folder was moved by the user during the review, not by this work).
- **Repository:** only this report folder (`docs/reports/data_loading_reconciliation_20261026/`) was added. No protected file, seed, `.env`, `conftest.py` or existing change was touched; no Git staging, commit, push, reset, stash, discard or revert.
- **Running application:** an existing backend (port 8000) and frontend (port 5173) started at 13:24 were found running and were only probed with GET requests.
