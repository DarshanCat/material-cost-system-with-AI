# VSPL Material Management & Costing System — PostgreSQL Readiness Assessment

**Document ID:** `DOC-P7-S3A-POSTGRESQL-READINESS`  
**System:** VSPL Material Management & Costing System  
**Date:** 2026-10-17  
**Governance Scope:** Read-Only Environment Inspection & Readiness Evaluation  
**Status:** **POSTGRESQL UNVERIFIED / UNAVAILABLE — PRODUCTION READINESS WITHHELD**  

---

## 1. Executive Summary

A comprehensive read-only audit of the development workstation environment was conducted to evaluate the operational readiness of the target PostgreSQL database system.

### Core Verdict:
> [!WARNING]
> **PostgreSQL Integration Unverified:**  
> The development test suite (68/68 passed in 4.65s) operates entirely within an isolated in-memory SQLite database utilizing SQLAlchemy's `StaticPool`.  
> While a Docker engine is running on the workstation, the PostgreSQL instance bound to port `5432` (`backend-db-1`) belongs to a separate enterprise application (`C:\VSPL`), and connection attempts fail with authentication errors. No dedicated, verified PostgreSQL database exists for `vspl_material_management`.  
> **Passing SQLite unit tests must never be cited as proof of PostgreSQL production readiness.**

---

## 2. Workstation Environment Inspection

The following empirical inspections were performed without installing software, altering services, or mutating system configurations:

| Component | Inspection Method | Verified Result | Assessment |
| :--- | :--- | :--- | :--- |
| **Windows Native Service** | `Get-Service -Name "*postgres*"` | None found (Exit code 1) | No native Windows PostgreSQL service installed |
| **Command-Line Client** | `Get-Command psql` | None found in system PATH | `psql` utility not available in CLI |
| **Docker Engine** | `Get-Command docker`, `docker ps` | Docker 20.x running; 6 containers present | Docker available; hosting multiple projects |
| **Port 5432 Listener** | `Get-NetTCPConnection -LocalPort 5432` | Container `backend-db-1` listening | Port 5432 occupied by legacy OMS application |
| **Target Database Status** | `app.db.session.check_database_connection()` | `OperationalError: password authentication failed` | No accessible `vspl_material_management` database |

---

## 3. Application Database Configuration

Inspection of [`backend/app/core/config.py`](file:///C:/VSPL_MM/Material%20managment%20system/backend/app/core/config.py) and runtime settings confirms:

- **Target Engine Driver:** `postgresql+psycopg://` (Psycopg 3.x modern async/sync driver)
- **Target Host:** `localhost` (IPv4: `127.0.0.1`, IPv6: `::1`)
- **Target Port:** `5432`
- **Target Database Name:** `vspl_material_management`
- **Target User:** `postgres`
- **Password Configuration:** Configured in environment file (sanitized from logs)
- **Connection Timeout:** 3 seconds (`connect_timeout=3`)
- **Pool Verification:** `pool_pre_ping=True` (proactive heartbeat check enabled)

### Error Telemetry:
When the application attempts to verify connectivity to `localhost:5432`, PostgreSQL returns:
```
Database connectivity failed: OperationalError - (psycopg.OperationalError) 
connection failed: connection to server at "127.0.0.1", port 5432 failed: 
FATAL: password authentication failed for user "postgres"
```
This confirms that port 5432 is receiving requests, but the running container (`backend-db-1`) belongs to another project with different credentials.

---

## 4. PostgreSQL Version & Behavioral Requirements

### 4.1 Required PostgreSQL Version
- **Target Version:** **PostgreSQL 16.x or higher** (e.g. `postgres:16-alpine`).
- **Rationale:** The application relies on modern SQL features, ISO timestamp parsing with microsecond precision, subquery scalar CTEs, and strict decimal arithmetic consistent with Python's `Decimal(ROUND_HALF_UP)`.

### 4.2 Schema Types & Portability
Review of the Alembic migration files (`001` through `005`) reveals that the schema design is highly disciplined:
- **Numeric Precision:** Explicit `sa.Numeric(15, 4)` for all stock quantities and unit rates; `sa.Numeric(15, 2)` for currency values. PostgreSQL implements `NUMERIC` with exact arbitrary precision, matching the Python Decimal layer.
- **Timestamp Types:** Explicit `sa.DateTime(timezone=True)`. PostgreSQL maps this to `TIMESTAMPTZ`, preserving UTC normalization.
- **Boolean Defaults:** `sa.Boolean()` with `server_default=sa.text('true')`.
- **Constraint Naming:** Alembic naming conventions (`pk_`, `fk_`, `uq_`, `ix_`) are explicitly defined on all constraints.
- **Portability Benefit:** No dialect-specific proprietary types (`postgresql.ENUM`, `postgresql.UUID`, `postgresql.JSONB`) are used in the core ledger or costing tables, ensuring clean DDL execution once a proper instance is connected.

---

## 5. Isolated Non-Production Verification Plan

Before Phase 7 Stage 3 live migration can be proposed, a dedicated, isolated non-production PostgreSQL environment must be established.

```
┌────────────────────────────────────────────────────────────────────────┐
│             ISOLATED NON-PRODUCTION POSTGRESQL ENVIRONMENT             │
├────────────────────────────────────────────────────────────────────────┤
│ 1. PORT ALLOCATION:                                                    │
│    - Avoid port 5432 collision with other VSPL containers.             │
│    - Allocate dedicated port 5439 for Material Management.             │
│                                                                        │
│ 2. DOCKER PROVISIONING (NON-MUTATING COMMAND):                          │
│    docker run -d --name vspl_mm_postgres \                             │
│      -e POSTGRES_DB=vspl_material_management \                        │
│      -e POSTGRES_USER=postgres \                                       │
│      -e POSTGRES_PASSWORD=<secure_dev_password> \                      │
│      -p 5439:5432 postgres:16-alpine                                  │
│                                                                        │
│ 3. ENVIRONMENT ISOLATION (.env):                                       │
│    POSTGRES_PORT=5439                                                  │
│    POSTGRES_DB=vspl_material_management                                │
│                                                                        │
│ 4. PRE-FLIGHT VERIFICATION GATES:                                      │
│    Gate 1: alembic upgrade head (Verify all 5 revisions on PG)         │
│    Gate 2: pytest backend/tests (Run test suite against real PG)       │
│    Gate 3: alembic downgrade base && alembic upgrade head (Reversibility│
└────────────────────────────────────────────────────────────────────────┘
```

### Mandatory Governance Constraint:
No automated tool or agent may spin up this container, mutate `.env`, or execute migrations against PostgreSQL until **explicit written authorization** is granted by management.
