# VSPL Material Management & Costing System — Architecture Specification

## 1. Executive Summary & Purpose

The **VSPL Material Management & Costing System** is an enterprise-grade ERP subsystem engineered for **Vijay Spheroidals Pvt. Ltd. (VSPL)**, an SG (Spheroidal Graphite) iron foundry manufacturing critical cast components.

The system enforces strict accounting discipline, an append-only inventory movement ledger across **741 material items**, reconciliation between induction furnace heat charges and warehouse issue slips, and weighted-average costing starting from **12 October 2026**.

---

## 2. System Boundaries & Deployment Context

### 2.1 Plant LAN Boundary
- **Deployment Target:** On-premise industrial plant Local Area Network (LAN).
- **Network Isolation:** The application is not exposed to the public Internet. It operates within the foundry's internal subnets connecting Stores, Foundry floor supervisors, Purchase, Quality, and Management workstations.
- **Client Endpoints:** Modern desktop web browsers (Chrome, Edge) on industrial and office PC terminals.

### 2.2 System Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                                  PLANT LAN CLIENTS                                |
|   Stores Terminals  |  Foundry Floor Terminals  |  Purchase & Management Desks    |
+-----------------------------------------------------------------------------------+
                                          |
                                    HTTP / REST
                                          v
+-----------------------------------------------------------------------------------+
|                         FRONTEND (React 19 + Vite + TypeScript)                   |
|  - Desktop-First Industrial ERP UI Shell                                          |
|  - Material Item Master View & Detail Drawer                                      |
|  - Vendor Master Management & Creation Form                                       |
|  - Item Creation Requisition Workflow, Pending Queue, Decision Interface         |
|  - Department & UOM Reference Precision Architecture Views                        |
|  - Role-aware Navigation (Stores, Foundry, Purchase, Management, Admin)           |
+-----------------------------------------------------------------------------------+
                                          |
                              REST API (/api/v1/*) + JSON
                                          v
+-----------------------------------------------------------------------------------+
|                         BACKEND SERVICE (FastAPI + Python 3.11+)                  |
|  - Core Config & Settings Validation (pydantic-settings)                          |
|  - Role-Based Access Control (RBAC) Enforcement via require_permission            |
|  - Item Request Workflow State Machine (DRAFT -> SUBMITTED -> APPROVED/REJECTED)  |
|  - Separation of Duties (No Self-Approval Enforcement)                            |
|  - Vendor Name Normalization & GSTIN Syntax Validation Gate                       |
|  - Append-Only Stock Movement Engine (Zero DELETE/UPDATE)                         |
|  - Weighted-Average Costing Engine (Arbitrary Precision Decimal)                   |
+-----------------------------------------------------------------------------------+
                                          |
                               SQLAlchemy 2.x + psycopg 3
                                          v
+-----------------------------------------------------------------------------------+
|                      DATABASE LAYER (PostgreSQL 15+ / 16+)                        |
|  - ACID Transaction Guarantee with Explicit Constraint Naming                     |
|  - Schema Versioning via Alembic Migrations (001_phase2_master_data)              |
|  - Decimal/Numeric Precision for Quantities & Currency                            |
|  - Immutable Transaction Log & Audit Journal (item_request_audit_logs)            |
+-----------------------------------------------------------------------------------+
```

---

## 3. Backend Architecture & Design Principles

### 3.1 Layered Separation of Concerns
1. **API Routing Layer (`app/api/v1/endpoints/`):**
   - HTTP request parsing, payload validation via Pydantic schemas.
   - Standardized JSON responses and HTTP status codes.
   - Granular RBAC permission checks via `Depends(require_permission(...))`.
2. **Service / Domain Layer (`app/services/`):**
   - Pure domain business logic isolated from HTTP routing.
   - `ItemRequestService`: State machine controller, conflict detection, item code generator (`DEPT-CATEGORY-SERIAL`), atomic transaction management.
   - `validators.py`: Vendor name normalization and GSTIN syntax validation.
3. **Data Model Layer (`app/models/`):**
   - Declarative SQLAlchemy models (`Department`, `UOM`, `MaterialItem`, `Vendor`, `ItemRequest`, `ItemRequestAuditLog`).
   - Explicit constraint naming (`POSTGRES_NAMING_CONVENTION`).
   - Mandatory UTC timestamp tracking via `TimestampMixin`.

### 3.2 Database Access & Precision Integrity
- **Engine Configuration:** Configured with `pool_pre_ping=True` and connection pooling.
- **Precision Integrity:** All monetary figures, unit prices, stock quantities, and heat charges utilize `DECIMAL(18, 4)` or `DECIMAL(18, 6)`. Binary floating-point types (`FLOAT`, `DOUBLE PRECISION`) are prohibited.
- **Transaction Safety:** Read-committed isolation with explicit database transaction rollbacks upon validation failures.

---

## 4. Security & Role-Based Access Control (RBAC)

### 4.1 Golden Security Rule
> **Frontend route hiding is NOT authorization.**
> Every backend endpoint strictly validates caller identity and required permissions.

### 4.2 Role-to-Permission Mapping Matrix (Phase 2 Implemented)

| Permission Scope | Stores | Foundry | Purchase | Management | Admin |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `department:read`, `uom:read` | Yes | Yes | Yes | Yes | Yes |
| `item:read` | Yes | Yes | Yes | Yes | Yes |
| `item_request:create` | Yes | Yes | Yes | Yes | Yes |
| `item_request:submit` | Yes | Yes | Yes | Yes | Yes |
| `item_request:cancel` | Yes | Yes | Yes | Yes | Yes |
| `item_request:read` | Yes | Yes | Yes | Yes | Yes |
| `item:approve`, `item:reject` | No | No | No | **Yes** | **Yes** |
| `vendor:read` | Yes | No | Yes | Yes | Yes |
| `vendor:manage` | No | No | **Yes** | No | **Yes** |

### 4.3 Separation of Duties & Self-Approval Prevention
- A manager or administrator who initiates an item requisition cannot approve their own requisition (`reviewer_id != requester_id`).
- Foundry and Stores roles cannot approve item master entries.
- Purchase role manages vendor records.

### 4.4 Authentication Status & Limitations
- **Current State:** For Phase 2 development and testing, an explicit Development User Context (`DevUserContext`) is extracted from request headers (`X-User-Id`, `X-User-Role`, `X-User-Department`).
- **Limitation Warning:** This development mechanism is **NOT production-secure**. Production authentication (JWT / SSO / LDAP) is scheduled for Phase 8.

---

## 5. Auditability & State Transitions

1. **State Machine (`ItemRequest`):**
   - `DRAFT`: Editable by requester.
   - `SUBMITTED`: Locked; pending review by Management/Admin.
   - `APPROVED`: Terminal state; atomically generates `MaterialItem`.
   - `REJECTED`: Terminal state; requires mandatory reason; no item generated.
   - `CANCELLED`: Terminal state; cancelled by requester before approval.
2. **Audit Attribution (`ItemRequestAuditLog`):**
   - Every state transition records: `action`, `from_status`, `to_status`, `actor_id`, `actor_role`, `comments`, and `timestamp` (UTC).
   - Modification or purging of audit log entries is structurally prohibited.
