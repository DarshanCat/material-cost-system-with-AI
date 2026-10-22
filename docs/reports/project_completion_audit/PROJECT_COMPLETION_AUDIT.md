# VSPL Material Management & Costing System — Project Completion Audit

**Audit date:** 2026-10-22 · **Mode:** read-only audit (no fixes, no migrations, no database writes)
**Companion file:** [REMAINING_WORK_BACKLOG.csv](REMAINING_WORK_BACKLOG.csv) (32 items, IDs referenced below)

## 1. Bottom line

* The **business logic of Phases 1–6 exists and is well tested on SQLite** (68/68 backend tests pass; frontend type-check and production build pass).
* The application is **not deployable and not PostgreSQL-verified**. Three software problems outrank everything else: authentication is spoofable (SW-01), most stock-moving endpoints have no authorization at all (SW-02), and the Costing UI sends no identity so it is refused by the backend (SW-03).
* **Phase 7 Stage 3B stays unauthorized.** All 8 decisions are `PENDING_REVIEW`; 12 of 13 gates are `BLOCKED` (only G11 source-hash verification is `VERIFIED`). Every blocker is human evidence or a signature; no code change unblocks them. This audit does not authorize Stage 3B or change any decision status.

## 2. Repository state (verified)

| Item | Value |
|---|---|
| Worktree | `C:\VSPL_MM\Material managment system\.claude\worktrees\vspl-mm-completion-audit-80f36a` |
| Branch | `claude/vspl-mm-completion-audit-80f36a` |
| HEAD | `d84d67460e95cf0e957346788a62774a869447e0` (docs: animated README and Phase 7 migration audit deliverables) |
| Baseline commit named in the brief | `dd85bcc` is the **parent** of HEAD, not HEAD. HEAD adds only README/docs/scripts on top; no application code differs (`dd85bcc` = Phase 6 feature commit). |
| Working tree | Clean (worktree and main checkout `git status --short` both empty before this audit) |
| Remote | `origin` → `https://github.com/DarshanCat/material-cost-system-with-AI.git` (not fetched or pushed) |
| Other worktree | main checkout on branch `main` at `d84d674` |
| History | 7 commits: Phase 1 `6a8be05`, Phase 2 `537caa0`, Phase 3 `af87681`, Phase 4 `f3002e3`, Phase 5 `eacd626`, Phase 6 `dd85bcc`, docs `d84d674` |
| Size | 254 tracked files; backend: 15 models, 17 services, 19 endpoint modules (≈100 routes), 5 Alembic revisions, 24 test files; frontend: 21 components, 0 test files |

## 3. Functional audit by area

Legend: ✅ implemented and tested · 🟡 implemented with gaps · ❌ missing

| Area | Status | Evidence | Gaps (backlog ID) |
|---|---|---|---|
| Master data (items, depts, UOM, vendors) | ✅ | `test_master_data.py`, `test_vendors.py`; seeds in `app/db/seed.py` | No direct item/vendor edit routes (by design: items only via approved request) |
| Item-request approval workflow | ✅ | `test_item_request_full_approval_lifecycle`, `test_self_approval_prevention`, `test_unauthorized_approval_attempt`, `test_rejection_workflow_with_mandatory_reason`, `test_duplicate_item_conflict_detection` | Only workflow with real RBAC + separation of duties (SW-04) |
| GRN / issue / waste transactions | 🟡 | `test_grn.py`, `test_issues.py`, `test_waste.py`, `test_excel_import.py` | No authz (SW-02), no maker-checker (SW-04), no reversal of approved documents (SW-07), no RBAC tests (TST-01) |
| Append-only ledger + reversal | 🟡 | `test_ledger_posting.py::test_compensating_reversal_lifecycle`; unique `(source_document_type, source_line_id)` | Immutability not DB-enforced; entry number by COUNT+1; no locking (SW-05); `/reverse` open to anyone, default actor "Admin", no UI (SW-02, SW-07) |
| Opening stock | 🟡 | `test_opening_balance_preview_and_posting_lifecycle` (duplicate-per-item guard verified) | Unauthenticated post endpoint (SW-02); cutoff date conflict (SW-10/BIZ-02) |
| Physical stocktake | 🟡 | `test_physical_audit_variance_and_adjustment_posting` (single happy-path test) | Variance frozen at draft, not rechecked at approval (SW-08) |
| Heat logs | ✅ | `test_heats.py`, `test_heat_import.py` | Role gate is ad-hoc string tuple; GETs open (SW-02) |
| Reconciliation (3-pass) | ✅ | `test_reconciliation.py`, `test_reconciliation_isolation.py` (heat/recon never writes ledger) | Run-number collision (SW-09); GETs open |
| Weighted-average costing, valuation | ✅ | `test_weighted_average_costing.py`, `test_inventory_valuation.py` | Opening valuation auto-approved and overwritten in place (SW-06); policies deliberately `POLICY_PENDING` (BIZ-09) |
| Heat / part costing | ✅ | `test_heat_costing.py`, `test_part_costing.py` | MATERIAL_ONLY scope until overhead policy decided (BIZ-09) |
| Costing exceptions + audit trail | 🟡 | `/costing/exceptions`, `test_costing_audit.py` (run versioning, compare, API permissions) | Exceptions cover valuation only; no cross-module audit API (SW-11) |
| Authentication / authorization | ❌ | `app/core/security.py` | SW-01, SW-02, SW-11. 11 of 27 permissions (e.g. `RECEIPT_CREATE`, `ISSUE_CREATE`, `STOCK_ADJUST`, `LEDGER_READ`, `AUDIT_READ`, `USER_MANAGE`) are referenced by no endpoint |
| Frontend pages | 🟡 | 21 components, all modules have a view; production build passes | Costing UI unusable under real RBAC (SW-03); no tests, 27 lint warnings, role is a client-side dropdown (SW-12); no reversal UI |
| DB models vs Alembic | ✅ (static) | Script comparing `Base.metadata` to migration `create_table` columns: 36 model tables = 36 migration tables, **zero column differences**; single linear chain 001→002→003→004→005 | Never executed on any database in this audit (TST-02, INF-01); index count (114 claimed) not verified |

## 4. Runtime and database readiness — what was and was not run

| Check | Result | Notes |
|---|---|---|
| Backend `pytest tests -q -p no:cacheprovider` | **68 passed, 3 warnings, 12.9 s** | In-memory SQLite (`StaticPool`) only. First attempt failed at collection: `ModuleNotFoundError: psycopg` (not installed in this machine's Python); I installed `psycopg[binary]` into a scratchpad directory outside the repo and passed it via `PYTHONPATH`. No connection to any PostgreSQL was made. (SW-13) |
| Frontend `npm ci` + `npm run build` (`tsc -b && vite build`) | **Passed** (1928 modules, 450 kB JS) | Run on a **copy** of `frontend/` in the scratchpad so the worktree gained no `node_modules`/`dist`. |
| Frontend `npm run lint` (oxlint) | **0 errors, 27 warnings (baseline; an earlier note of 15 came from truncated output)** | See SW-12. |
| Frontend unit tests | **Not applicable — none exist** | |
| Alembic ↔ models consistency | Static comparison only | `alembic upgrade/check` was **not** run (would need a database). |
| PostgreSQL compatibility | **Unverified** | No PG instance exists (Stage 3A.6 report; port 5439 unallocated). SQLite passing does not demonstrate PG behaviour: row locking, concurrent numbering (SW-05), timestamptz, varchar limits, index behaviour. |
| Live API / integration against a running server | **Not run** | Backend API tests use FastAPI `TestClient` against SQLite; the Vite→uvicorn path was not started. |
| Deployment readiness | **Not ready** | No CI, Dockerfile, compose or production serve config tracked (INF-03); `docker-compose.nonprod.yml` cited by Stage 3A.1 is absent from the repo (SW-14); auth missing (SW-01). |

Explicitly not done: no Docker commands, no migrations, no production connection, no database writes.

## 5. Software defects and gaps (summary; details in CSV)

**P0**
* **SW-01** Auth fail-open: headers `X-User-*`; missing/invalid role → Stores; default `SECRET_KEY` (`security.py`, `config.py`).
* **SW-02** No `require_permission` on GRN/issue/waste/audit/ledger-reverse/opening-balance/excel-import routes; actor from `?actor_id=…` / `?created_by=…` defaulting to `"Admin"` (e.g. `grn.py:81,126`, `ledger.py:196`).
* **SW-03** `CostingDashboard.tsx` makes 7 costing `fetch()` calls with no identity headers → resolved as Stores → 403 under the backend's own permission matrix. Found by inspection; passing backend test `test_costing_api_permissions` injects headers itself. Not executed in a browser in this audit.

**P1** SW-04 no maker-checker outside item requests · SW-05 ledger immutability/numbering/negative-stock race · SW-06 opening valuation overwritten in place, self-approved · SW-07 no reversal workflow for approved documents (`grn_service.py:208`, `issue_service.py:180`) · SW-08 stale stocktake variance · TST-01 no RBAC tests · TST-02 no PostgreSQL test mode.

**P2/P3** SW-09 reconciliation run-number collision (`ts % 10000`) · SW-10 hard-coded dates/policies in UI · SW-11 no user/audit administration · SW-12 frontend quality · SW-13 unpinned deps/driver import at bootstrap · TST-03/04 coverage · SW-14 stale doc identifiers (`005_cost_history` vs real `005_phase6_costing_valuation`).

## 6. Phase 7 blocker reconciliation (Stage 2.1 → 3A.8)

Sources read: `phase7_stage3a8/DECISION_AND_GATE_RECONCILIATION.csv`, `EVIDENCE_INTAKE_REGISTER.csv`, `AUTHORIZATION_BOUNDARIES.md`, `phase7_stage3a7/HUMAN_ACTION_REGISTER.csv`, `phase7_stage3a6/POSTGRESQL_READINESS_STATUS.md`, `docs/BUSINESS_RULES.md §6`. Statuses below are copied, not changed.

| Decision | Gate(s) | Action | Owner | Recorded status | Evidence still missing |
|---|---|---|---|---|---|
| DEC-001 historical GRN rates | G3 | ACT-02 | Finance Head | PENDING_REVIEW / BLOCKED | Supplier tax invoices; signed `commercial_rates_staging.csv` |
| DEC-002 cutoff vs 82-day void | G2 | ACT-01 | MD / Plant Head | PENDING_REVIEW / BLOCKED | Signed Executive Policy Memorandum (Scenario A) |
| DEC-003 unmapped items + scrap grade | G4, G5 | ACT-03, ACT-04 | Stores Mgr; Foundry Metallurgist | PENDING_REVIEW / BLOCKED | Approved item requests MNT-CN-001, MCS-CN-002; OES certificate (15,200 kg) |
| DEC-004 date typo `7-16-20236` | G6 | ACT-05 | Stores Manager | PENDING_REVIEW / BLOCKED | Physical slips 327–1148 inspected; signed certificate |
| DEC-005 negative stock / stocktake | G7 | ACT-06 | Plant Head / Auditor | PENDING_REVIEW / BLOCKED | Certified Sheet D double-blind count |
| DEC-006 template dummy row 2 | G8 | ACT-07 | Systems Architect / QA | PENDING_REVIEW / BLOCKED | Signed Template Exclusion Directive (code change only after) |
| DEC-007 18 zero-charge heats | G9 | ACT-08 | Foundry Head | PENDING_REVIEW / BLOCKED | Paper melt sheets or signed Quarantine Order |
| DEC-008 legacy Store Inventory.xlsx | G10 | ACT-09 | IT Head | PENDING_REVIEW / BLOCKED | Signed retirement memo; ETL exclusion |
| — | G1 exec sign-off | ACT-10 (A) | MD / Plant Head | BLOCKED | Signed `MANAGEMENT_SIGNOFF_TEMPLATE.md` |
| — | G11 source hashes | — | Lead QA | **VERIFIED** | none |
| — | G12 PG16 non-prod (port 5439) | ACT-10 (B) | Lead DBA | BLOCKED | Container, 001–005 applied, suite on PG — only after G1 |
| — | G13 backup rehearsal | — | Lead DBA | BLOCKED | Dump + SHA-256 + restore, after G12 |

**Dependency chain:** ACT-01/DEC-002 (root) → ACT-06 stocktake; ACT-02 → ACT-04; ACT-02…ACT-09 → G1 (ACT-10 A) → G12 → G13 → Stage 3B decision. The Stage 3A.7/3A.8 intake register shows all ACT items `NOT_RECEIVED`/pending with no hashes.

**Items not previously surfaced that the human owners should see**
1. **Two cutoff dates are in circulation**: 12-Oct-2026 in code, config, README and opening-balance defaults; 18/19-Oct-2026 in the Stage 3A.4/3A.8 DEC-002 material. Management must state the governing date in the DEC-002 memorandum (BIZ-02/SW-10). I have not chosen one.
2. `docs/BUSINESS_RULES.md §6` lists four **costing policies** still pending (internal recovery rate, denominator, overhead apportionment, opening rate method) — these are not covered by DEC-001..008 (BIZ-09).
3. Stage 3A.1 verification snippets assert a revision id that does not exist (SW-14).

## 7. Prioritised backlog (compact view)

| Order | ID | Class | Title | Human approval? |
|---|---|---|---|---|
| 1 | SW-01/02/03 | Software defect | Authentication, authorization on all routes, UI identity | IDs of mechanism: yes |
| 2 | TST-01 | Test | RBAC route×role matrix | no |
| 3 | SW-04–SW-08 | Software defect/gap | SoD, ledger hardening, valuation versioning, reversal workflow, stocktake recheck | partly (policy) |
| 4 | BIZ-02 → BIZ-05, BIZ-01, BIZ-03/04/06/07/08 | Business evidence | Signatures and physical evidence for DEC-001..008 | yes, all |
| 5 | BIZ-10 | Governance | G1 executive sign-off | yes |
| 6 | INF-01/02, TST-02, SW-05 verification | Infrastructure | PG 16 on 5439, backup rehearsal, PG test mode | yes (DBA, after G1) |
| 7 | SW-09–SW-14, TST-03/04, INF-03/04, BIZ-09 | Hardening / Phase 8 | Remaining quality, CI, deployment, costing policies | mixed |

Counts: 32 items — P0 ×8, P1 ×13, P2 ×10, P3 ×1; SOFTWARE_DEFECT 10, SOFTWARE_GAP 4, TEST_GAP 4, BUSINESS_EVIDENCE 10, INFRASTRUCTURE 4. Software work (SW-01…SW-14, TST-*) can proceed **now** without any Phase 7 decision, except SW-10's date change and SW-06/SW-04 policy inputs.

## 8. Authorization statement

* Stage 3B is **not** authorized by this document. Resumption conditions remain those in `phase7_stage3a8/AUTHORIZATION_BOUNDARIES.md §5`.
* Historical migration, PostgreSQL provisioning, Docker operations and opening-balance posting remain prohibited until G1 and the downstream gates are closed by humans.
* No business rule, rate, date, quantity or approval was invented; where the repository is silent or inconsistent (cutoff date, reversal authority, SoD waiver) the item is recorded as a human decision.

## 9. Limitations of this audit

* Findings SW-02/SW-03/SW-05/SW-07/SW-08 come from reading code and grep; they were not reproduced by running the server. SW-03 in particular should be confirmed in a browser before fixing.
* ~100 routes and 21 views were sampled for authorization by route listing and targeted reads, not line-by-line review of every function. Costing math correctness was assessed via its test names, not independently recomputed.
* Alembic/model consistency checked by parsing `create_table`/`add_column` calls (columns by name); types, indexes, defaults and constraints were not compared.
* The reported "114 indexes" and PostgreSQL-specific behaviour are unverified.
