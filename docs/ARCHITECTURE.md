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

### 2.2 System Responsibilities

```
+-----------------------------------------------------------------------------------+
|                                  PLANT LAN CLIENTS                                |
|   Stores Terminals  |  Foundry Floor Terminals  |  Purchase & Management Desks    |
+-----------------------------------------------------------------------------------+
                                          |
                                    HTTP / REST
                                          v
+-----------------------------------------------------------------------------------+
|                         FRONTEND (React + Vite + TypeScript)                      |
|  - Desktop-First Industrial UI                                                    |
|  - Zero Synthetic Data Representation (Empty state discipline)                    |
|  - Role-aware Navigation (Stores, Foundry, Purchase, Management, Admin)           |
+-----------------------------------------------------------------------------------+
                                          |
                              REST API (/api/v1/*) + JSON
                                          v
+-----------------------------------------------------------------------------------+
|                         BACKEND SERVICE (FastAPI + Python 3.11+)                  |
|  - Core Config & Settings Validation (pydantic-settings)                          |
|  - Role-Based Access Control (RBAC) Enforcement                                   |
|  - Append-Only Stock Movement Engine (Zero DELETE/UPDATE)                         |
|  - Strict Receipt & Issue Validation Gates                                        |
|  - Heat Log Reconciliation & Furnace Yield Engine                                 |
|  - Weighted-Average Costing Engine (Arbitrary Precision Decimal)                   |
+-----------------------------------------------------------------------------------+
                                          |
                               SQLAlchemy 2.x + psycopg 3
                                          v
+-----------------------------------------------------------------------------------+
|                      DATABASE LAYER (PostgreSQL 15+ / 16+)                        |
|  - ACID Transaction Guarantee                                                     |
|  - Schema Versioning via Alembic Migrations                                       |
|  - Decimal/Numeric Precision for Quantities & Currency                            |
|  - Immutable Transaction Log & Audit Journal                                      |
+-----------------------------------------------------------------------------------+
```

---

## 3. Backend Architecture & Design Principles

### 3.1 Layered Separation of Concerns
1. **API Routing Layer (`app/api/v1/`):**
   - HTTP request parsing, payload validation via Pydantic schemas.
   - Standardized JSON responses and HTTP status codes.
   - Authentication dependency gates and role checks.
2. **Service / Domain Layer (`app/services/`):**
   - Pure business logic isolated from HTTP concerns.
   - Costing calculation engine (`costing_service.py`).
   - Movement ledger processor (`ledger_service.py`).
   - Reconciliation logic (`reconciliation_service.py`).
3. **Repository Layer (`app/repositories/`):**
   - Isolated SQLAlchemy 2.x queries.
   - Encapsulation of complex joins, bulk insertions, and transactional units.
4. **Data Model Layer (`app/models/`):**
   - Declarative SQLAlchemy models.
   - Explicit constraint naming (`POSTGRES_NAMING_CONVENTION`).
   - Mandatory UTC timestamp tracking via `TimestampMixin`.

### 3.2 Database Access & Integrity
- **Engine Configuration:** Configured with `pool_pre_ping=True` and connection pooling.
- **Precision Integrity:** All monetary figures, unit prices, stock quantities, and heat charges utilize `DECIMAL(18, 4)` or `DECIMAL(18, 6)`. Floating-point types (`FLOAT`, `DOUBLE PRECISION`) are prohibited for financial calculations.
- **Transaction Safety:** Read-committed isolation with explicit transaction blocks.

---

## 4. Security & Role-Based Access Control (RBAC)

### 4.1 Golden Security Rule
> **Frontend route hiding is NOT authorization.**
> Every backend endpoint must strictly validate caller identity and required permissions.

### 4.2 Architectural Roles Matrix
| Role | Primary Plant Functions | Access Permissions |
| :--- | :--- | :--- |
| **Stores** | GRNs, material inward, issues to departments, scrap logs, physical audit | `receipt:*`, `issue:*`, `waste:log`, `ledger:read`, `stock:adjust` |
| **Foundry** | Induction heat logging, charge mixes, parts poured, reconciliation review | `heat_log:*`, `heat:reconcile`, `issue:read`, `ledger:read` |
| **Purchase** | Vendor master catalog, purchase orders, material rates excluding GST | `vendor:manage`, `item:create`, `receipt:read` |
| **Management** | Cost per kg analysis, heat cost variance, audit reviews, stock valuation | `costing:*`, `audit:read`, `ledger:read`, `heat_log:read` |
| **Admin** | User administration, master approval workflows, system configuration | All permissions (`*`) |

### 4.3 Separation of Duties
- **Foundry floor supervisors** cannot directly adjust warehouse inventory balances. Only authorized warehouse Issue slips move stock out.
- **Stores staff** cannot log furnace heat chemistries or modify metallurgist logs.
- Physical stock corrections require approval and generate distinct `ADJUSTMENT` journal entries.

---

## 5. Auditability & Traceability

1. **Immutable Historical Log:**
   - Transaction records are append-only.
   - `DELETE` and `UPDATE` queries on committed transaction or ledger records are structurally forbidden.
2. **Audit Attribution:**
   - Every operational entry captures: `created_by_user_id`, `created_at` (UTC), `department_id`, and `source_document_ref`.
3. **Reversal Entries:**
   - Clerical errors are corrected exclusively via compensating reversal transactions linked to the original reference ID.
