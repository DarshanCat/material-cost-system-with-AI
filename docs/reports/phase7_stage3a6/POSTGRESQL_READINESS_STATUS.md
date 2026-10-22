# VSPL Material Management & Costing System — PostgreSQL Non-Production Readiness Status

**Document ID:** `DOC-P7-S3A6-POSTGRES-STATUS`  
**System:** VSPL Material Management & Costing System  
**Date:** 2026-10-22  
**Governance Scope:** Authoritative Technical Status of Target Relational Database Infrastructure  
**Execution Authority:** **READ-ONLY AUDIT REPORT — ZERO INFRASTRUCTURE MUTATIONS EXECUTED**  

---

## 1. Executive Purpose & Governance Invariants

This document establishes the verified technical state of the PostgreSQL database environment for Vijay Spheroidals Pvt. Ltd. (VSPL). It strictly separates **documented architectural specifications** from **actual verified workstation reality**, ensuring that no premature claims of database readiness are made prior to authorized execution.

### Governing Invariant:
> [!IMPORTANT]
> **No Phantom Readiness:**  
> The existence of a Docker Compose specification (`docker-compose.nonprod.yml`) or a written setup plan does **not** constitute database readiness. Until a container is instantiated, migrations applied, schemas audited, and test suites executed against live PostgreSQL 16, Gates `G12` and `G13` remain **BLOCKED**.

---

## 2. Host Port Conflict & Availability Analysis

During Phase 7 Stage 3A pre-flight verification, an attempt to connect to the standard PostgreSQL port `5432` failed:
```
psql: error: connection to server at "localhost" (127.0.0.1), port 5432 failed: 
FATAL: password authentication failed for user "postgres"
```

### 2.1 Active Host Listener Telemetry
Inspection of host processes and network sockets revealed that multiple database containers are actively running on the development workstation for other projects:
- **Port `5432`:** Actively occupied by container `backend-db-1` belonging to `C:\VSPL` (Order Management System / OMS project). Attempting to use this port risks cross-project data corruption or credential locking.
- **Port `5433`:** Active database socket (`vspl-oms-staging`).
- **Port `5435`:** Active database socket (`vspl-analytics-db`).
- **Port `5438`:** Active database socket (`vspl-legacy-mirror`).

### 2.2 Target Port Verification (`5439`)
TCP socket availability testing confirmed that **Port `5439`** is completely unallocated:
- **Binding Address:** Strictly bound to loopback `127.0.0.1:5439:5432`.
- **Conflict Status:** Zero active processes or listening sockets on port `5439`.
- **Target URI:** `postgresql://vspl_app:<password>@127.0.0.1:5439/vspl_material_management`

---

## 3. Planned Architecture vs Verified Host Reality

The following matrix contrasts what has been designed versus what physically exists in the workstation environment:

| Architectural Dimension | Planned Design Specification (`POSTGRESQL_NONPROD_SETUP_PLAN.md`) | Verified Reality on Host Workstation | Current Readiness Status |
| :--- | :--- | :--- | :--- |
| **Host Network Port** | Dedicated port `5439` on `127.0.0.1` | Port `5432` claimed by OMS; Port `5439` verified unallocated | **UNALLOCATED & AVAILABLE (Unbound)** |
| **Container Engine** | Service `vspl_mm_postgres_nonprod` running `postgres:16-alpine` | Container does not exist; image not instantiated | **PLANNED SPECIFICATION ONLY** |
| **Storage Isolation** | Isolated named Docker volume `vspl_mm_pg16_nonprod_data` | Volume does not exist on host Docker engine | **PLANNED SPECIFICATION ONLY** |
| **Database & User Role**| Database `vspl_material_management` owned by `vspl_app` | Role and database do not exist | **PLANNED SPECIFICATION ONLY** |
| **Alembic Schema Chain**| 5 revisions (001–005) applied to head `005_cost_history` (36 tables, 114 indexes) | Migration Python scripts verified on disk; **zero tables created in PostgreSQL** | **SCRIPTS VERIFIED; UNMIGRATED** |
| **Automated Test Suite**| 68 regression tests passing against live PostgreSQL 16 dialect | 68/68 tests passing **strictly in in-memory SQLite (`StaticPool`)** | **SQLITE VERIFIED; PG UNTESTED** |
| **Pre-Migration Backup**| Custom binary dump (`pg_dump -Fc`) with SHA-256 sidecar checksum | No PostgreSQL database exists to snapshot | **BLOCKED ON DEPLOYMENT** |
| **Restore Rehearsal** | Automated test restore into scratch database `vspl_mm_restore_test` | Scratch database does not exist | **BLOCKED ON BACKUP** |

---

## 4. The Critical SQLite vs PostgreSQL Dialect Invariant

A central finding of this readiness review is the fundamental distinction between passing SQLite unit tests and certifying PostgreSQL production readiness:

### 4.1 What Passing 68/68 SQLite Tests Proves:
1. Application domain logic contracts execute correctly (e.g., non-negative stock balance enforcement, Rule H1 isolation of furnace charges from stores ledger, and Rule C1 weighted-average rate calculations).
2. Pydantic request and response schemas validate field types and precisions.
3. Fast-feedback local test execution functions smoothly without external database dependencies (5.62s total test duration).

### 4.2 What Passing SQLite Tests DOES NOT Prove:
1. **PostgreSQL Dialect Compatibility:** SQLite ignores column length constraints (`String(50)`), treats UUIDs as raw strings, and handles boolean columns as integers (0/1). PostgreSQL strictly enforces character bounds, native UUID representations, and boolean datatypes.
2. **PostgreSQL Unique Constraints & Indexes:** SQLite in-memory tables do not fully evaluate PostgreSQL index structures under heavy concurrent writes. In particular, composite unique index `uq_source_doc_line_posting` on table `stock_ledger_entries` must be verified against PostgreSQL's transaction manager.
3. **Timezone & Timestamp Precision:** SQLite stores datetimes as naive text strings. PostgreSQL with `DateTime(timezone=True)` enforces UTC offsets and microsecond precision, which directly affects chronological transaction sequencing in `ledger_service.py`.
4. **Concurrency & Locking:** SQLite `StaticPool` executes in a single-threaded in-memory lock. Real PostgreSQL transactions involve row-level MVCC locking, foreign key integrity checks, and connection pooling that must be validated live.

---

## 5. Sequential Execution Protocol to Satisfy Gate G12 & G13

PostgreSQL provisioning and validation can only be initiated **after** Executive Decision Sign-Off (Gate G1) is formally granted. When authorized, the Lead DBA and Systems Architect must execute the following sequential protocol:

```
┌────────────────────────────────────────────────────────────────────────┐
│               POSTGRESQL VERIFICATION PROTOCOL (POST-G1)               │
├────────────────────────────────────────────────────────────────────────┤
│ STEP 1: PORT AVAILABILITY CONFIRMATION                                 │
│ • Re-verify port 5439 has zero listening sockets on 127.0.0.1.          │
│                                                                        │
│ STEP 2: CONTAINER LAUNCH (ISOLATED NON-PROD MODE)                      │
│ • docker compose -f docker-compose.nonprod.yml up -d                  │
│ • docker exec vspl_mm_postgres_nonprod pg_isready -U vspl_app          │
│                                                                        │
│ STEP 3: EXECUTE ALEMBIC MIGRATIONS                                     │
│ • .venv\Scripts\python.exe -m alembic upgrade head                     │
│                                                                        │
│ STEP 4: PROGRAMMATIC SCHEMA & INDEX ASSERTIONS                         │
│ • Assert public table count == 36.                                     │
│ • Assert pg_indexes count >= 114.                                      │
│ • Assert alembic_version == '005_cost_history'.                        │
│ • Assert constraint 'uq_source_doc_line_posting' active.               │
│                                                                        │
│ STEP 5: REGRESSION TEST SUITE EXECUTION ON LIVE POSTGRESQL             │
│ • Run pytest backend/tests targeting DATABASE_URL on port 5439.        │
│ • Assert 68/68 tests pass with ZERO dialect errors.                    │
│                                                                        │
│ STEP 6: CAPTURE PRE-MIGRATION BASELINE (GATE G13)                      │
│ • pg_dump -U vspl_app -d vspl_material_management -Fc -f baseline.dump │
│ • Compute and record SHA-256 digest in sidecar file.                   │
│                                                                        │
│ STEP 7: RESTORE REHEARSAL CERTIFICATION                                │
│ • pg_restore -U vspl_app -d vspl_mm_restore_test baseline.dump         │
│ • Assert 36 tables and 114 indexes restored intact.                    │
│ • Drop vspl_mm_restore_test; sign RESTORE_REHEARSAL_CERTIFICATE.md.   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Operational Safety Affirmation

- **Zero Container Launches:** No Docker containers were started, created, or modified during Stage 3A.6.
- **Zero Database Writes:** No SQL tables, schemas, or records were created or altered.
- **Status:** **Gates G12 and G13 remain strictly BLOCKED.** Stage 3B live migration remains unauthorized.
