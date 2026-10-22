# VSPL Material Management & Costing System — PostgreSQL Pre-Provisioning Verification Checklist

**Document ID:** `DOC-P7-S3A2-POSTGRES-CHECKLIST`  
**System:** VSPL Material Management & Costing System  
**Date:** 2026-10-17  
**Governance Scope:** Pre-Flight Verification Criteria for Future PostgreSQL Non-Production Deployment  
**Execution Status:** **READ-ONLY VERIFICATION CHECKLIST — ZERO INFRASTRUCTURE MUTATIONS EXECUTED**  

---

## 1. Executive Purpose & Governance Invariants

This checklist establishes the pre-flight verification requirements that must be confirmed by the Lead Database Administrator (DBA) and Systems Architect before an isolated, non-production PostgreSQL instance can be provisioned for Vijay Spheroidals Pvt. Ltd. (VSPL).

### Fundamental Safety Constraints:
> [!IMPORTANT]
> **Strict Non-Execution Rule:**  
> This checklist evaluates technical prerequisites without executing deployment. No Docker containers have been launched, no ports have been opened, no databases have been created, and no system services have been altered during this stage.

---

## 2. Infrastructure Status: Planned Configuration vs Verified Reality

To maintain complete transparency and avoid premature claims of readiness, every architectural dimension is explicitly categorized below:

| Architectural Component | Planned Specification (`POSTGRESQL_NONPROD_SETUP_PLAN.md`) | Verified Reality on Host Workstation | Readiness Status |
| :--- | :--- | :--- | :--- |
| **Host Port Assignment** | Port `5439` (isolated dedicated non-production port) | Port `5432` occupied by OMS container `backend-db-1`; Port `5439` verified unallocated | **PLANNED & VERIFIED UNALLOCATED** |
| **Network Interface** | Loopback binding strictly to `127.0.0.1` | No container running; compose spec declares `127.0.0.1:5439:5432` | **PLANNED SPECIFICATION ONLY** |
| **Persistent Volume** | Dedicated named volume `vspl_mm_pg16_nonprod_data` | Volume does not exist on host Docker engine | **PLANNED SPECIFICATION ONLY** |
| **Database Engine** | PostgreSQL 16 Alpine (`postgres:16-alpine`) | Image not pulled; container not instantiated | **PLANNED SPECIFICATION ONLY** |
| **Database Credentials** | Application user `vspl_app` owning `vspl_material_management` | Database and role do not exist | **PLANNED SPECIFICATION ONLY** |
| **Schema Migration State**| Alembic revisions 001–005 (`005_cost_history`) | Python migration scripts verified on disk; zero tables created in PostgreSQL | **SCRIPTS VERIFIED; UNMIGRATED** |
| **Test Suite Execution** | 68 regression tests passing against live PostgreSQL | 68/68 tests verified passing in **SQLite StaticPool in-memory only** | **SQLITE VERIFIED; PG UNTESTED** |
| **Pre-Migration Backup** | Binary baseline dump via `pg_dump -Fc` | No PostgreSQL database exists to back up | **BLOCKED ON DEPLOYMENT** |
| **Restore Rehearsal** | Rehearsal restoration into `vspl_mm_restore_test` | Scratch database does not exist | **BLOCKED ON BACKUP** |

---

## 3. Pre-Provisioning Verification Checklist

When formal executive approval to provision the non-production test environment is received, the Lead DBA must complete and sign every item in this checklist:

### 3.1 Network & Port Isolation Verification
- [ ] **Socket Availability Test:** Confirm port `5439` has zero listening sockets on TCP:
  ```powershell
  $check = Test-NetConnection -ComputerName 127.0.0.1 -Port 5439 -WarningAction SilentlyContinue
  if ($check.TcpTestSucceeded) { throw "PORT 5439 CONFLICT" }
  ```
- [ ] **Port 5432 Isolation:** Confirm that existing container `backend-db-1` (running for OMS at `C:\VSPL`) is completely unaffected and remains untouched on port `5432`.
- [ ] **External Interface Prohibition:** Confirm that `docker-compose.nonprod.yml` binds exclusively to `127.0.0.1:5439` and does not bind to `0.0.0.0` or any physical LAN adapter.

### 3.2 Storage Volume & Data Isolation Verification
- [ ] **Volume Namespace Check:** Confirm named volume `vspl_mm_pg16_nonprod_data` is isolated from other Docker volumes:
  ```powershell
  docker volume inspect vspl_mm_pg16_nonprod_data 2>$null
  ```
- [ ] **Host Filesystem Integrity:** Confirm zero database files or transaction logs bleed into host application repositories or user desktop directories.

### 3.3 Security & Role Separation Verification
- [ ] **Role Isolation:** Confirm `vspl_app` is provisioned as the database owner, with separate credentials from the PostgreSQL superuser.
- [ ] **Least Privilege:** Confirm `vspl_app` has zero privileges on the `postgres` system database or template databases.
- [ ] **Environment Variable Isolation:** Confirm that production credentials or secrets are not committed to Git or embedded in compose files.

### 3.4 Schema Realization & Migration Verification
- [ ] **Sequential Migration Execution:** Apply revisions 001 through 005 via Alembic:
  ```powershell
  $env:DATABASE_URL = "postgresql://vspl_app:VsplSecureNonProd2026!@127.0.0.1:5439/vspl_material_management"
  .venv\Scripts\python.exe -m alembic upgrade head
  ```
- [ ] **Table Count Assertion:** Programmatically verify public table count equals exactly **36 tables**:
  ```sql
  SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';
  -- Must assert: 36
  ```
- [ ] **Index Count Assertion:** Programmatically verify index count equals at least **114 indexes**:
  ```sql
  SELECT count(*) FROM pg_indexes WHERE schemaname = 'public';
  -- Must assert: >= 114
  ```
- [ ] **Alembic Revision Assertion:** Verify migration head matches revision 005:
  ```sql
  SELECT version_num FROM alembic_version;
  -- Must assert: '005_cost_history'
  ```
- [ ] **Unique Constraint Assertion:** Verify that unique constraint `uq_source_doc_line_posting` is active on `stock_ledger_entries`:
  ```sql
  SELECT conname FROM pg_constraint WHERE conname = 'uq_source_doc_line_posting';
  -- Must assert: 'uq_source_doc_line_posting'
  ```

### 3.5 PostgreSQL Automated Test Suite Execution
- [ ] **Execute Regression Suite against PostgreSQL:** Run full backend test suite pointing `DATABASE_URL` to port `5439`:
  ```powershell
  $env:TEST_DATABASE_URL = "postgresql://vspl_app:VsplSecureNonProd2026!@127.0.0.1:5439/vspl_material_management"
  .venv\Scripts\python.exe -m pytest backend/tests/
  ```
- [ ] **Zero Failures Requirement:** Require 100% of tests to pass (68/68) with zero dialect errors, zero timestamp timezone mismatches, and zero UUID serialization errors.

### 3.6 Baseline Backup & Rehearsal Verification
- [ ] **Capture Baseline Snapshot:** Execute `pg_dump -Fc` and verify archive integrity:
  ```powershell
  pg_dump -h 127.0.0.1 -p 5439 -U vspl_app -d vspl_material_management -Fc -f vspl_mm_baseline_pre_migration.dump
  ```
- [ ] **Generate SHA-256 Digest:** Store checksum in `.sha256` sidecar file.
- [ ] **Rehearsal Restore Test:** Execute restore into `vspl_mm_restore_test` and confirm schema parity (36 tables / 114 indexes).
- [ ] **Issue Signed Certificate:** Execute and sign `RESTORE_REHEARSAL_CERTIFICATE.md`.

---

## 4. Verification Sign-Off Table

| Verification Domain | Verifying Authority | Required Sign-Off Date | Verification Status |
| :--- | :--- | :--- | :--- |
| **Port & Loopback Network Isolation** | Lead Systems Engineer | Prior to Container Launch | **UNVERIFIED (Awaiting Authorization)** |
| **Docker Volume & Storage Isolation** | Lead Systems Engineer | Prior to Container Launch | **UNVERIFIED (Awaiting Authorization)** |
| **Application Role & Least Privilege**| Lead DBA | Post-Launch / Pre-Migration | **UNVERIFIED (Awaiting Authorization)** |
| **Alembic 001–005 Schema Parity** | Systems Architect | Post-Migration Run | **UNVERIFIED (Awaiting Authorization)** |
| **PostgreSQL Regression Test Suite** | Lead QA Auditor | Post-Schema Realization | **UNVERIFIED (Awaiting Authorization)** |
| **Restore Rehearsal Certification** | Systems Architect | Pre-Migration Gate G13 | **UNVERIFIED (Awaiting Authorization)** |

---

## 5. Stop Condition Attestation

- **Status:** **PRE-PROVISIONING CHECKLIST COMPLETE.**
- **Attestation:** Zero host configuration changes, zero container runs, and zero database writes have been performed. All items remain in `UNVERIFIED` status until authorized execution in future project phases.
