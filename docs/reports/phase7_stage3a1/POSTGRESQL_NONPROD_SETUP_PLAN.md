# VSPL Material Management & Costing System — Isolated Non-Production PostgreSQL Setup Plan

**Document ID:** `DOC-P7-S3A1-POSTGRES-PLAN`  
**System:** VSPL Material Management & Costing System  
**Date:** 2026-10-17  
**Governance Scope:** Standard Operating Procedure for Isolated Non-Production Database Provisioning  
**Execution Status:** **PLANNING SPECIFICATION ONLY — NO DOCKER CONTAINERS OR SYSTEM CHANGES EXECUTED**  

---

## 1. Executive Purpose & Governance Principles

This document specifies the architecture, containerization parameters, network bindings, and step-by-step verification standard operating procedures (SOP) for provisioning an isolated, non-production PostgreSQL 16 database instance for Vijay Spheroidals Pvt. Ltd. (VSPL).

### Fundamental Constraints:
1. **Zero Host Collision:** The setup must avoid any conflict with existing production, staging, or sister-project containers running on the development workstation.
2. **Local Loopback Isolation:** Database ports must bind strictly to `127.0.0.1` and never expose ports on `0.0.0.0` or external network adapters.
3. **Execution Prohibition:** In accordance with the Phase 7 Stage 3A.1 safety protocol, this document is a planning specification. No Docker commands, container launches, or database writes are performed during this stage.

---

## 2. Port Conflict Analysis & Telemetry

### 2.1 Host Environment Discovery
During Phase 7 Stage 3A pre-flight verification, an attempt to connect to default PostgreSQL port `5432` failed with authentication errors:
```
psql: error: connection to server at "localhost" (127.0.0.1), port 5432 failed: 
FATAL: password authentication failed for user "postgres"
```
Process and container inspection revealed that port `5432` is actively claimed by a pre-existing container:
- **Container Name:** `backend-db-1`
- **Host Project Root:** `C:\VSPL` (Order Management System / OMS project)
- **Status:** Running on host port `5432:5432`

Further port telemetry identified additional active PostgreSQL/database containers on the host machine:
- Port `5433`: Active container (`vspl-oms-staging`)
- Port `5435`: Active container (`vspl-analytics-db`)
- Port `5438`: Active container (`vspl-legacy-mirror`)

### 2.2 Dedicated Target Port Selection
Port availability testing confirmed that **Port `5439`** is completely unallocated, free of listening sockets, and isolated from all other project containers:
- **Allocated Non-Production Port:** `5439`
- **Target Connection URI:** `postgresql://vspl_app:<secure_password>@127.0.0.1:5439/vspl_material_management`

---

## 3. Containerization Architecture & Specification

### 3.1 Docker Compose Specification (`docker-compose.nonprod.yml`)
To ensure complete isolation and reproducible deployments, the non-production instance is declared as an isolated Docker service:

```yaml
version: '3.8'

services:
  vspl-mm-postgres-nonprod:
    image: postgres:16-alpine
    container_name: vspl_mm_postgres_nonprod
    restart: "no"
    ports:
      - "127.0.0.1:5439:5432"
    environment:
      POSTGRES_DB: vspl_material_management
      POSTGRES_USER: vspl_app
      POSTGRES_PASSWORD: ${VSPL_NONPROD_DB_PASSWORD:-VsplSecureNonProd2026!}
      PGDATA: /var/lib/postgresql/data/pgdata
      TZ: Asia/Kolkata
    volumes:
      - vspl_mm_pg16_nonprod_data:/var/lib/postgresql/data
    command: >
      postgres
        -c shared_buffers=256MB
        -c work_mem=16MB
        -c maintenance_work_mem=64MB
        -c effective_cache_size=512MB
        -c log_connections=on
        -c log_disconnections=on
        -c log_line_prefix='%m [%p] %u@%d '
        -c timezone=Asia/Kolkata
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vspl_app -d vspl_material_management"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  vspl_mm_pg16_nonprod_data:
    name: vspl_mm_pg16_nonprod_data
```

### 3.2 Security & Least Privilege Configuration
1. **Dedicated Application Role:** The application connects exclusively as `vspl_app`, an unprivileged user owning only the `vspl_material_management` database.
2. **Strict Loopback Binding:** Exposing `127.0.0.1:5439:5432` ensures the database cannot be queried or scanned across the local area network.
3. **Dedicated Volume Isolation:** Volume `vspl_mm_pg16_nonprod_data` is strictly namespaced to prevent cross-project volume mounting or data bleed.

---

## 4. Step-by-Step Provisioning & Verification SOP

When formal authorization to deploy the non-production test environment is granted, the following standard operating procedure must be executed in sequence:

### Step 1: Pre-Launch Port Verification
Confirm port 5439 remains completely unallocated:
```powershell
$portCheck = Test-NetConnection -ComputerName 127.0.0.1 -Port 5439 -WarningAction SilentlyContinue
if ($portCheck.TcpTestSucceeded) {
    throw "ABORT: Port 5439 is unexpectedly occupied. Inspect active services before continuing."
} else {
    Write-Host "Port 5439 is verified available."
}
```

### Step 2: Container Launch (Isolated Non-Production Mode)
Launch the container from the project root using the dedicated compose file:
```powershell
docker compose -f docker-compose.nonprod.yml up -d
```

### Step 3: Engine Health Check
Verify the database engine is accepting connections:
```powershell
docker exec vspl_mm_postgres_nonprod pg_isready -U vspl_app -d vspl_material_management
```

### Step 4: Environment Variable Configuration
Configure the application environment for non-production execution:
```powershell
$env:DATABASE_URL = "postgresql://vspl_app:VsplSecureNonProd2026!@127.0.0.1:5439/vspl_material_management"
$env:ENVIRONMENT = "development"
```

### Step 5: Execute Alembic Migration Chain (Revisions 001–005)
Apply the complete linear migration sequence to the fresh PostgreSQL instance:
```powershell
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
```

### Step 6: Schema Topology & Index Verification
Run verification queries to certify complete schema realization:
```powershell
.venv\Scripts\python.exe -c "
import psycopg2
conn = psycopg2.connect('postgresql://vspl_app:VsplSecureNonProd2026!@127.0.0.1:5439/vspl_material_management')
cur = conn.cursor()
cur.execute(\"SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';\")
tables = cur.fetchone()[0]
cur.execute(\"SELECT count(*) FROM pg_indexes WHERE schemaname = 'public';\")
indexes = cur.fetchone()[0]
cur.execute(\"SELECT version_num FROM alembic_version;\")
version = cur.fetchone()[0]
print(f'Verification Results: Tables={tables} (Expected 36), Indexes={indexes} (Expected 114), Alembic={version} (Expected 005_cost_history)')
assert tables == 36, f'Table mismatch: got {tables}, expected 36'
assert version == '005_cost_history', f'Alembic head mismatch: got {version}'
conn.close()
"
```

### Step 7: Regression Test Suite Execution against PostgreSQL
Execute the full 68-test backend suite targeting the live PostgreSQL instance:
```powershell
$env:TEST_DATABASE_URL = "postgresql://vspl_app:VsplSecureNonProd2026!@127.0.0.1:5439/vspl_material_management"
.venv\Scripts\python.exe -m pytest tests/
```

---

## 5. Teardown, Cleanup & Reset Procedures

### 5.1 Non-Destructive Stop
To pause the non-production instance between testing sessions without losing staged state:
```powershell
docker compose -f docker-compose.nonprod.yml stop
```

### 5.2 Complete Clean Teardown (Scratch Reset)
To completely remove the container and erase the scratch database volume prior to fresh rehearsals:
```powershell
docker compose -f docker-compose.nonprod.yml down -v
```

---

## 6. Stop Condition & Implementation Integrity

- **Status:** **PROCEDURAL SPECIFICATION COMPLETE.**
- **Enforcement:** No Docker containers have been launched, no ports have been opened, and no configuration files have been altered during this planning stage.
