# Sprint 2 — Transaction integrity: maker-checker, append-only ledger, reversal design

Baseline: `94de903` (Sprint 1), 679 backend tests passing. Date: 2026-10-22. Backlog items addressed: SW-04 (partly), SW-05 (partly), SW-07 (design only), TST-02 (not addressed).

## 1. Inventory of ledger write paths (verified by code search, enforced by `test_ledger_immutability.py`)

| Path | File | Effect |
|---|---|---|
| GRN approval → `post_grn_to_ledger` | `ledger_service.py` | INSERT INWARD_RECEIPT / INTERNAL_INWARD |
| Issue approval → `post_issue_to_ledger` | `ledger_service.py` | INSERT OUTWARD_ISSUE (stock checks) |
| Waste approval → `post_waste_to_ledger` | `ledger_service.py` | INSERT SCRAP_OUTWARD / INTERNAL_RECOVERY |
| Physical-audit approval → `post_audit_adjustment_to_ledger` | `ledger_service.py` | INSERT PHYSICAL_AUDIT_ADJUSTMENT |
| Manual reversal → `reverse_stock_ledger_entry` | `ledger_service.py` | INSERT REVERSAL (compensating) |
| Opening balance post → `post_approved_opening_balances` | `opening_balance_service.py` | INSERT OPENING_BALANCE |

No application code updates or deletes ledger rows; no API route exposes PUT/PATCH/DELETE on the ledger. Costing, heat and reconciliation code only read it. All five posting paths run in one transaction with the document status change and audit log.

## 2. Maker-checker (implemented, provisional policy)

* **Established rule:** only Rule M2 (item requests) is written down, and it was already enforced. Rule T5 (DRAFT → SUBMITTED "verification" → APPROVED) and Rule L8 (physical audits approved by Management or Admin) do not say whether the creator may also approve.
* **Implemented:** `services/maker_checker.py`. Approving a **GRN, issue slip, waste disposition or physical audit** is refused (HTTP 403, nothing changed) when the approver is the document's `created_by`. The check lives in the domain services, uses the authenticated actor from Sprint 1, ignores any body/query user id, and compares case/whitespace-insensitively.
* **Configurable, not hard-coded:** `MAKER_CHECKER_DOCUMENTS` (default `GRN,ISSUE,WASTE,PHYSICAL_AUDIT`; also supports `ALIAS`). Management can relax or extend it by configuration.
* **No new role assignments.** Who may approve each type remains the Sprint 1 provisional matrix (Management, Admin). Admin holds every permission, so an Admin creating a document still cannot approve it.
* **Approval concurrency:** approval reads the document with `SELECT … FOR UPDATE` (PostgreSQL only; ignored by SQLite) and runs inside `ledger_write_guard`, which rolls back everything on any failure and turns a database integrity conflict (duplicate posting, duplicate entry number) into HTTP 409 with nothing posted.

### Decisions required (not guessed)
1. **Is creator ≠ approver the intended rule for each document type?** The default enforces it for the four ledger-posting documents. A single-person shift would be blocked; the alternative (waive per type) needs a written policy.
2. **Who approves GRN, issue, waste and physical audit?** Not defined in the repository. The matrix is provisional.
3. **Should the submitter also differ from the approver?** Only creator ≠ approver is enforced.
4. **Opening valuations** (`POST /costing/opening-valuations`) are proposed and approved in one call by one user with no `created_by`; maker-checker cannot be applied without a model change and policy (SW-06).
5. **Material aliases:** supported but off by default. Separately, `POST /material-aliases` accepts `status` from the request body, so any caller with `alias:create` can create an already-APPROVED alias and bypass approval. This is existing behaviour that tests rely on; it was left unchanged and needs a decision.
6. **Opening-balance posting, excel import, reversal and reconciliation confirmation** have no creator/approver pair; whether they need a second person is a policy question.

## 3. Append-only ledger protection (three layers)

1. **ORM guard** (`app/db/ledger_guard.py`, installed from `app/models/__init__.py`): mapper `before_update`/`before_delete` and a session `do_orm_execute` hook refuse updating/deleting `StockLedgerEntry`, including bulk `update()`/`delete()`. Raises `LedgerImmutableError`.
2. **SQLite triggers** created with the table (`create_all`): any UPDATE/DELETE, even raw SQL, aborts. This only makes the test database behave like the intended production control.
3. **PostgreSQL triggers — Alembic revision `006_sprint2_ledger_immutability`** (down_revision `005_phase6_costing_valuation`): row triggers BEFORE UPDATE/DELETE and a statement trigger BEFORE TRUNCATE raise `restrict_violation`. Additive only: no data touched, revisions 001–005 untouched. SQL is frozen inside the migration and a test asserts it equals the module constants.

### Limitations
* **Revision 006 has not been executed anywhere** and the PostgreSQL DDL has not been run against a PostgreSQL server (none exists; gate G12). Run it only on the isolated non-production instance (port 5439) after G12, then repeat the immutability and concurrency tests there. SQLite results are not PostgreSQL evidence.
* Triggers do not stop a table owner or superuser from dropping them. A DBA should also `REVOKE UPDATE, DELETE, TRUNCATE ON stock_ledger_entries` from the application role and keep ownership in a separate role.
* `ledger_write_guard` row locks and the 409 mapping are tested by simulation only; real concurrent sessions were not exercised (SQLite, single connection).
* Entry numbers are still generated as `COUNT+1` (SW-05). Two concurrent postings on the same date can collide; the unique constraint prevents a duplicate number and the guard converts it to a safe 409, but a DB sequence is still recommended.

## 4. Reversal workflow — current behaviour and design for the remainder

### Current behaviour (Rule L5), verified by tests
Management/Admin (`ledger:reverse`, provisional) can `POST /ledger/entries/{id}/reverse` with a reason (min 5 chars). The service appends a `REVERSAL` entry with the opposite quantity, links `reversal_of_entry_id`, records the authenticated actor, refuses reversal of a reversal (400), refuses a second reversal (409; also guaranteed by `UNIQUE(source_document_type, source_line_id)`), and refuses a reversal of an inward entry that would drive stock negative (409, unless `ALLOW_NEGATIVE_STOCK`). The original row is never changed. New in Sprint 2: row lock + conflict-to-409 mapping for concurrent duplicates, and tests that every rejected reversal leaves all ledger rows and balances identical.

### Design for the remaining work (NOT implemented: policy missing)
| Aspect | Proposed design | Policy needed first |
|---|---|---|
| Eligible sources | Entries from APPROVED GRN / issue / waste; reversal of an OPENING_BALANCE or PHYSICAL_AUDIT_ADJUSTMENT entry is currently *possible* | Which movement types may be reversed; whether opening/audit entries are reversible |
| Document level | New `REVERSED` status; reversing a document posts compensating entries for **all** its lines in one transaction and links them to one reversal record | Whether whole-document reversal is wanted; allowed time window |
| Required data | Reason (exists), reference to a corrective document or ticket, authenticated actor (exists) | Whether a reference is mandatory |
| Duplicate / concurrent | One reversal per source line (DB unique constraint) + `FOR UPDATE` + 409 (done) | None |
| Authorization | Separate permission (exists: `ledger:reverse`); optionally require a second approver (reverser ≠ original poster, or two-step REQUEST → APPROVE) | Who may reverse; maker-checker for reversals |
| Audit trail | Reversal request/approval log table (actor, reason, reference, timestamps) in addition to the ledger row | Retention/reporting needs |
| Stock effect | Balance changes only by the appended entry; negative-stock rule applies to inward reversals (done) | Negative-stock exceptions |
| Dating | Today it uses today's date, not the original date. Back-dating changes historical valuation and costing runs | Which date applies (and period-close rules) |
| Costing | Costing already treats REVERSAL movements; no test yet runs a reversal through a costing run | Expected costing treatment |

## 5. Verification (this sprint)
New tests: `test_maker_checker.py` (27), `test_ledger_immutability.py` (27). Full backend suite: **733 passed** (679 before). No frontend source changed.

## 6. Remaining risks
* PostgreSQL behaviour of revision 006, locking and concurrent approval is unverified.
* Provisional approver roles and the creator ≠ approver default await management sign-off.
* Alias creation can self-approve via the request body (decision needed).
* Reversal has no UI, no document-level workflow, no second approver, no reference field, and dates at "today".
* Production authentication still does not exist (Sprint 1 limitation).
* Raw-SQL changes by a database superuser/owner remain possible until DBA revocations are applied.
