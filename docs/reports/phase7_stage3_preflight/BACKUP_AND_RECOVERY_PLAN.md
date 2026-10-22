# VSPL Material Management & Costing System — Backup and Recovery Plan

**Document ID:** `DOC-P7-S3A-BACKUP-RECOVERY`  
**System:** VSPL Material Management & Costing System  
**Date:** 2026-10-17  
**Governance Scope:** Standard Operating Procedure for Migration Backups, Rehearsals & Rollbacks  
**Status:** **PROCEDURAL SPECIFICATION ONLY — ZERO MUTATING OPERATIONS EXECUTED**  

---

## 1. Executive Purpose & Governance Principles

This document specifies the standard operating procedures (SOP) for database backup, integrity verification, restore rehearsals, and emergency rollback required before any write-enabled migration can occur.

### Mandatory Principles:
1. **Pre-Migration Baseline:** An immutable physical backup of the target database must be taken and verified immediately prior to any migration execution.
2. **Restore Rehearsal Prerequisite:** A backup is not considered valid until it has been successfully restored into a scratch environment and programmatically validated against schema baselines.
3. **Zero Production Risk:** No backup, restore, or database management command may be executed against a production host without written authorization from the Managing Director.

---

## 2. Database Backup Procedure (PostgreSQL)

### 2.1 Backup Execution Standard
All database snapshots must be created using PostgreSQL's native custom archive format (`-Fc`), which incorporates internal compression, bloat prevention, and support for selective table restoration.

```powershell
# Standard Non-Production Backup Command (Example Specification)
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = "C:\VSPL_MM\backups\vspl_mm_pre_migration_${Timestamp}.dump"

pg_dump -h localhost -p 5432 -U postgres -d vspl_material_management `
        -Fc -b -v -f $BackupFile
```

### 2.2 Backup Integrity & Digest Verification
Immediately following backup completion, a cryptographic checksum must be generated and recorded:
```powershell
Get-FileHash -Path $BackupFile -Algorithm SHA256 | `
  Export-Csv -Path "${BackupFile}.sha256.csv" -NoTypeInformation
```

---

## 3. Restore Rehearsal & Validation Standard

Before any write-enabled migration job is scheduled, the backup archive must undergo a mandatory **Restore Rehearsal**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   MANDATORY RESTORE REHEARSAL FLOW                     │
├────────────────────────────────────────────────────────────────────────┤
│ 1. CREATE SCRATCH TARGET:                                              │
│    createdb -h localhost -U postgres vspl_mm_restore_test              │
│                                                                        │
│ 2. EXECUTE RESTORE:                                                    │
│    pg_restore -h localhost -U postgres -d vspl_mm_restore_test         │
│               -v -c $BackupFile                                        │
│                                                                        │
│ 3. PROGRAMMATIC SCHEMA VERIFICATION:                                   │
│    SELECT count(*) FROM information_schema.tables                      │
│    WHERE table_schema = 'public'; -- Must equal exactly 36 tables      │
│                                                                        │
│ 4. DISCARD SCRATCH TARGET:                                             │
│    dropdb -h localhost -U postgres vspl_mm_restore_test                │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Preservation of Source Workbooks and Audit Registers

In addition to relational database backups, all primary migration evidence must be preserved across immutable storage tiers:

1. **Source Excel Workbooks (`inputs/`, `ledger/`, `legacy_archive/`):**
   - Filesystem permissions set to `Read-Only` (`attrib +r`).
   - SHA-256 hashes verified before every script run against `source_fingerprint_verification.csv`.
2. **Frozen Audit Archives:**
   - Permanent archive `VSPL_Phase7_Stage2_1_Evidence_Freeze_20261013.zip` preserved on secondary storage.
   - Hash `033684d8b26dc65e9c67b569e48991b07c0d0909c2cc37717b5d3485d922c5c5` verified before and after operations.
3. **Decision & Manifest Registers:**
   - Tagged and committed in Git repository under master commit hashes.

---

## 5. Rollback Criteria & Emergency Abort Protocols

An active migration must be aborted immediately and rolled back to the pre-migration baseline upon triggering any of the following **Hard Rollback Criteria**:

| Trigger Code | Rollback Condition | Action Required |
| :--- | :--- | :--- |
| **RB-01** | Any unhandled database exception or schema constraint violation | Terminate process; issue `ROLLBACK`; inspect error trace |
| **RB-02** | Any duplicate posting detected in `stock_ledger_entries` | Immediate abort; verify unique constraint index |
| **RB-03** | Any discrepancy between manifest quantity and posted quantity | Immediate abort; halt subsequent batches |
| **RB-04** | Negative inventory balance generated on any canonical item | Immediate abort; quarantine batch |
| **RB-05** | Moving weighted-average unit rate calculates as negative or zero | Immediate abort; check ex-GST invoice rate |

### Rollback Execution Flow:
1. Terminate migration runner process.
2. Disconnect all application pool connections.
3. Restore database from pre-migration snapshot `$BackupFile`.
4. Run regression test suite (`pytest backend/tests`) to certify system baseline restoration.
5. Notify Managing Director and Plant Head with a formal Incident & Rollback Report.
