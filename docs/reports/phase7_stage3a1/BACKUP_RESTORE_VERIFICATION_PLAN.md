# VSPL Material Management & Costing System — Backup & Restore Verification Plan

**Document ID:** `DOC-P7-S3A1-BACKUP-PLAN`  
**System:** VSPL Material Management & Costing System  
**Date:** 2026-10-17  
**Governance Scope:** Standard Operating Procedure for Pre-Migration Baseline Backups, Restore Rehearsals & Rollbacks  
**Execution Status:** **PROCEDURAL SPECIFICATION ONLY — ZERO MUTATING OPERATIONS EXECUTED**  

---

## 1. Executive Purpose & Governance Invariants

This document specifies the standard operating procedure (SOP) for capturing pre-migration database baselines, verifying backup integrity, executing end-to-end restore rehearsals, and executing emergency rollbacks for the VSPL Material Management & Costing System.

### Non-Negotiable Governance Principles:
1. **Unverified Backups Are Worthless:** A database backup archive cannot be relied upon for migration safety until it has undergone a programmatic **Restore Rehearsal** into an isolated scratch database.
2. **Immutable Pre-Migration Baseline:** Immediately prior to executing any write-enabled migration script, an atomic binary snapshot of the target database must be captured and cryptographically locked.
3. **Hard Rollback Mandate:** If any data migration batch violates ledger invariants, triggers constraint errors, or generates unapproved negative balances, migration must halt immediately and roll back to the verified baseline.

---

## 2. Database Backup Standard Operating Procedure

### 2.1 Backup Archive Format & Flags
All PostgreSQL database backups must be generated using PostgreSQL's native custom format (`-Fc`). This format provides:
- Built-in zlib compression (reducing disk footprint while accelerating I/O).
- Embedded schema metadata enabling table-level selective restoration.
- Consistent, point-in-time ACID snapshot capture.

### 2.2 Standard Backup Execution Command
Targeting the dedicated non-production instance on port `5439`:

```powershell
# Define execution parameters and timestamp
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = "C:\VSPL_MM\backups"
if (-not (Test-Path -Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir -Force }

$BackupFile = Join-Path $BackupDir "vspl_mm_baseline_${Timestamp}.dump"
$HostPort = 5439
$DbUser = "vspl_app"
$DbName = "vspl_material_management"

Write-Host "Capturing pre-migration baseline: $BackupFile"

# Execute pg_dump inside the isolated container
docker exec -e PGPASSWORD="VsplSecureNonProd2026!" vspl_mm_postgres_nonprod `
    pg_dump -U $DbUser -d $DbName -Fc -b -v -Z 6 -f "/var/lib/postgresql/data/vspl_mm_baseline_${Timestamp}.dump"

# Copy archive to persistent host filesystem
docker cp "vspl_mm_postgres_nonprod:/var/lib/postgresql/data/vspl_mm_baseline_${Timestamp}.dump" $BackupFile

# Clean up temporary dump inside container
docker exec vspl_mm_postgres_nonprod rm -f "/var/lib/postgresql/data/vspl_mm_baseline_${Timestamp}.dump"
```

### 2.3 Cryptographic Checksum Generation
Immediately upon archive generation, compute and persist the SHA-256 digest:
```powershell
$Hash = (Get-FileHash -Path $BackupFile -Algorithm SHA256).Hash
$ChecksumFile = "${BackupFile}.sha256"
"$Hash  $([System.IO.Path]::GetFileName($BackupFile))" | Out-File -FilePath $ChecksumFile -Encoding utf8

Write-Host "Cryptographic Hash: $Hash"
Write-Host "Checksum stored in: $ChecksumFile"
```

---

## 3. Restore Rehearsal & Verification Protocol

Before any migration execution can be authorized (Gate G13), the captured backup archive must be validated through a **Rehearsal Restoration**:

```mermaid
flowchart TD
    A["Pre-Migration Backup (.dump)"] --> B["Compute & Verify SHA-256 Digest"]
    B --> C["Create Isolated Scratch DB<br>(vspl_mm_restore_test)"]
    C --> D["Execute pg_restore (-Fc)"]
    D --> E{"Programmatic Audit"}
    E -->|"Table Count != 36"| F["FAIL REHEARSAL<br>Log Discrepancy & Halt"]
    E -->|"Index Count != 114"| F
    E -->|"Alembic Head != 005"| F
    E -->|"Pass All Checks"| G["Drop Scratch DB<br>(vspl_mm_restore_test)"]
    G --> H["Issue Signed Certificate<br>(RESTORE_REHEARSAL_CERTIFICATE.md)"]
    H --> I["Satisfy Acceptance Gate G13"]
```

### 3.1 Step-by-Step Rehearsal Script

```powershell
# Step 1: Provision isolated scratch target
docker exec -e PGPASSWORD="VsplSecureNonProd2026!" vspl_mm_postgres_nonprod `
    psql -U vspl_app -d postgres -c "DROP DATABASE IF EXISTS vspl_mm_restore_test;"
docker exec -e PGPASSWORD="VsplSecureNonProd2026!" vspl_mm_postgres_nonprod `
    psql -U vspl_app -d postgres -c "CREATE DATABASE vspl_mm_restore_test OWNER vspl_app;"

# Step 2: Copy backup archive into container scratch area
docker cp $BackupFile "vspl_mm_postgres_nonprod:/tmp/restore_rehearsal.dump"

# Step 3: Execute pg_restore
docker exec -e PGPASSWORD="VsplSecureNonProd2026!" vspl_mm_postgres_nonprod `
    pg_restore -U vspl_app -d vspl_mm_restore_test -v -c "/tmp/restore_rehearsal.dump"

# Step 4: Run Programmatic Schema & Integrity Audit
$auditScript = @"
import psycopg2

conn = psycopg2.connect("postgresql://vspl_app:VsplSecureNonProd2026!@127.0.0.1:5439/vspl_mm_restore_test")
cur = conn.cursor()

# Verify table count
cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
tables = cur.fetchone()[0]

# Verify index count
cur.execute("SELECT count(*) FROM pg_indexes WHERE schemaname = 'public';")
indexes = cur.fetchone()[0]

# Verify Alembic version
cur.execute("SELECT version_num FROM alembic_version;")
alembic_head = cur.fetchone()[0]

print(f"Restore Audit: Tables={tables}/36, Indexes={indexes}/114, Alembic={alembic_head}")

assert tables == 36, f"Table count mismatch: {tables} found, expected 36"
assert indexes >= 114, f"Index count mismatch: {indexes} found, expected at least 114"
assert alembic_head == "005_cost_history", f"Alembic revision mismatch: {alembic_head}"

conn.close()
print("RESTORE REHEARSAL PASSED: All structural invariants certified.")
"@

.venv\Scripts\python.exe -c $auditScript

# Step 5: Clean up scratch artifacts
docker exec vspl_mm_postgres_nonprod rm -f "/tmp/restore_rehearsal.dump"
docker exec -e PGPASSWORD="VsplSecureNonProd2026!" vspl_mm_postgres_nonprod `
    psql -U vspl_app -d postgres -c "DROP DATABASE vspl_mm_restore_test;"
```

---

## 4. Hard Rollback Criteria & Emergency Abort Protocols

If any of the following **Hard Rollback Triggers** are tripped during a future write-enabled migration run, the migration runner must immediately terminate, issue a database `ROLLBACK`, and restore the pre-migration baseline:

| Trigger Code | Rollback Condition | Detection Mechanism | Immediate Action |
| :--- | :--- | :--- | :--- |
| **RB-01** | Unhandled database exception or foreign key constraint violation | Python `try/except` block catching `psycopg2.Error` or `IntegrityError` | Abort active batch; issue transaction `ROLLBACK`; generate error dump |
| **RB-02** | Duplicate posting detected in `stock_ledger_entries` | Index violation on `ix_stock_ledger_entries_source_ref` | Abort immediately; verify source coordinate uniqueness |
| **RB-03** | Manifest vs posted quantity discrepancy | Reconciliation check comparing manifest quantity with ledger `movement_quantity` | Halt pipeline; verify UOM conversion factor |
| **RB-04** | Negative inventory balance generated on any canonical item | Audit query against `current_balance` on `stock_ledger_entries` | Abort batch; quarantine affected item code |
| **RB-05** | Moving weighted-average rate calculates as negative or zero | Valuation trigger check under Phase 6 Rule C1 | Abort batch; verify ex-GST invoice rate |

### 4.1 Rollback Execution Flow

```powershell
# Standard Emergency Rollback Procedure:
Write-Warning "EMERGENCY ROLLBACK TRIGGERED: Restoring baseline..."

# Step 1: Disconnect all active client connections
docker exec -e PGPASSWORD="VsplSecureNonProd2026!" vspl_mm_postgres_nonprod `
    psql -U vspl_app -d postgres -c @"
    SELECT pg_terminate_backend(pid) 
    FROM pg_stat_activity 
    WHERE datname = 'vspl_material_management' AND pid <> pg_backend_pid();
"@

# Step 2: Drop corrupted database and recreate clean target
docker exec -e PGPASSWORD="VsplSecureNonProd2026!" vspl_mm_postgres_nonprod `
    psql -U vspl_app -d postgres -c "DROP DATABASE vspl_material_management;"
docker exec -e PGPASSWORD="VsplSecureNonProd2026!" vspl_mm_postgres_nonprod `
    psql -U vspl_app -d postgres -c "CREATE DATABASE vspl_material_management OWNER vspl_app;"

# Step 3: Restore pristine pre-migration baseline snapshot
docker cp $BackupFile "vspl_mm_postgres_nonprod:/tmp/rollback_baseline.dump"
docker exec -e PGPASSWORD="VsplSecureNonProd2026!" vspl_mm_postgres_nonprod `
    pg_restore -U vspl_app -d vspl_material_management -v "/tmp/rollback_baseline.dump"
docker exec vspl_mm_postgres_nonprod rm -f "/tmp/rollback_baseline.dump"

# Step 4: Execute regression suite to certify recovery
.venv\Scripts\python.exe -m pytest backend/tests/
```

---

## 5. Stop Condition & Implementation Integrity

- **Status:** **PROCEDURAL SPECIFICATION COMPLETE.**
- **Enforcement:** Zero database mutations, zero backup dump files created, and zero system alterations executed during Phase 7 Stage 3A.1.
