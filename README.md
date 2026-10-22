<div align="center">

<!-- Hero Banner with Dynamic Gradient Animation -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=1,2,9,20&height=220&section=header&text=VSPL%20Material%20Cost%20%26%20AI%20System&fontSize=38&animation=fadeIn&fontAlignY=38&desc=Enterprise%20SG%20Iron%20Foundry%20Material%20Management%20%26%20Costing%20Platform&descAlignY=58&descAlign=50" width="100%" alt="VSPL Material Costing Banner"/>

<!-- Dynamic Animated Typing Header -->
<a href="https://github.com/DarshanCat/material-cost-system-with-AI">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=22&duration=3000&pause=1000&color=2563EB&center=true&vCenter=true&width=850&lines=Industrial-Grade+SG+Iron+Foundry+ERP+%26+Costing+Engine;Arbitrary-Precision+Weighted-Average+Inventory+Valuation;Append-Only+Immutable+Stock+Ledger+with+Audit+Trails;Induction+Furnace+Melt+Log+Mass-Balance+Reconciliation;AI-Assisted+Anomaly+Detection+%26+Migration+Auditing;Strict+Zero-Stock+Restart+%26+Deterministic+Tie-Breaking" alt="Typing SVG" />
</a>

<p align="center">
  <a href="#-key-capabilities"><img src="https://img.shields.io/badge/Architecture-Clean%20Hexagonal-blue?style=for-the-badge&logo=codereview&logoColor=white" alt="Architecture"/></a>
  <a href="#-system-architecture"><img src="https://img.shields.io/badge/Database-PostgreSQL%2016-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL"/></a>
  <a href="#-technology-stack"><img src="https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.11+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/></a>
  <a href="#-technology-stack"><img src="https://img.shields.io/badge/Frontend-React%2019%20%7C%20Vite%20%7C%20TS-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React 19"/></a>
  <a href="#-testing--verification"><img src="https://img.shields.io/badge/Tests-68%2F68%20Passing%20(100%25)-success?style=for-the-badge&logo=pytest&logoColor=white" alt="Pytest"/></a>
  <a href="#-audit--evidence-governance"><img src="https://img.shields.io/badge/Data%20Integrity-100%25%20SHA--256%20Verified-purple?style=for-the-badge&logo=securityscorecard&logoColor=white" alt="Integrity"/></a>
</p>

---

### 🏭 Purpose-Built for Industrial Metallurgy & SG Iron Foundries
**Vijay Spheroidals Pvt. Ltd. (VSPL)** operates high-volume Induction Furnaces producing specialized Spheroidal Graphite (SG) and Ductile Iron castings. This system replaces fragmented spreadsheets with an immutable, auditable, high-precision ERP engine.

</div>

---

## ⚡ Key Capabilities & Technical Innovations

<table>
  <tr>
    <td width="50%">
      <h3>💎 Arbitrary-Precision Costing</h3>
      <ul>
        <li>Uses Python <code>Decimal</code> with <code>ROUND_HALF_UP</code> to 4 decimal places (<code>NUMERIC(14, 4)</code>).</li>
        <li>Eliminates IEEE 754 floating-point cumulative drift in multi-crore raw material runs.</li>
        <li><strong>Strict Costing Baseline:</strong> Configurable cutoff baseline (<code>COSTING_START_DATE = 2026-10-12</code>).</li>
      </ul>
    </td>
    <td width="50%">
      <h3>🔒 Append-Only Immutable Ledger</h3>
      <ul>
        <li>Double-entry financial semantics for physical inventory (GRN, Issue, Waste, Adjustment).</li>
        <li><strong>Non-Negotiable:</strong> Stock ledger entries and quantities are strictly append-only; historical postings are never updated or deleted.</li>
        <li>Live closing balances dynamically derived via deterministic window aggregations.</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🔥 Furnace Heat Log & Mass-Balance</h3>
      <ul>
        <li>Reconciles induction furnace heat logs against material issue dockets.</li>
        <li>Tracks charge composition (Pig Iron, CRCA Scrap, Foundry Returns, Inoculants, FeSi, FeMn, Mg).</li>
        <li>Calculates liquid metal cost per kg tapped ($\text{Cost/kg}$) and individual cast part material cost.</li>
      </ul>
    </td>
    <td width="50%">
      <h3>🤖 AI-Assisted Migration & Anomaly Detection</h3>
      <ul>
        <li>Multi-pass reconciliation engine matching raw material names against canonical aliases.</li>
        <li>Automated detection of negative ledger balances, unpriced GRN receipts, and date anomalies.</li>
        <li>Cryptographic audit trail with SHA-256 evidence hashing across all historical migrations.</li>
      </ul>
    </td>
  </tr>
</table>

---

## 🏗 System Architecture

```mermaid
flowchart TD
    subgraph UI["Industrial Frontend (React 19 + TypeScript + Vite)"]
        DASH["Live Inventory & Costing Dashboard"]
        GRN_VIEW["GRN Management & Vendor Invoicing"]
        HEAT_VIEW["Induction Furnace Heat Log & Tapping"]
        VAL_VIEW["Weighted-Average Valuation & Journal"]
    end

    subgraph API["Backend Application Shell (FastAPI + Pydantic v2)"]
        AUTH["Role-Based Access Control (STORES | FOUNDRY | FINANCE | ADMIN)"]
        ROUTERS["API Endpoints (/api/v1)"]
        SERVICES["Core Business Engines"]
    end

    subgraph CORE_ENGINES["Deterministic Processing Engines"]
        LEDGER_ENG["Append-Only Stock Ledger Service"]
        COST_ENG["Weighted-Average Costing Service (Decimal 4-dec)"]
        RECON_ENG["3-Pass Furnace & Issue Reconciliation Engine"]
        AUDIT_ENG["Physical Stocktake Arbitration & Audit Service"]
    end

    subgraph DB["PostgreSQL 16 Industrial Schema"]
        direction TB
        M_TABLES[("Master Data (Items, Vendors, Departments, UOMs)")]
        L_TABLES[("Stock Ledger & Journal Entries (Immutable)")]
        H_TABLES[("Furnace Heat Logs & Charge Details")]
        C_TABLES[("Costing Runs & Snapshot Archives")]
    end

    UI -->|REST / JSON| API
    API --> CORE_ENGINES
    CORE_ENGINES -->|SQLAlchemy 2.x / psycopg 3| DB
```

---

## 📊 Phase-by-Phase Engineering Status

| Phase | Milestone | Scope & Deliverables | Status |
| :---: | :--- | :--- | :---: |
| **01** | **Foundation & Shell** | Clean Hexagonal Architecture, FastAPI, React 19, Docker setup | ![Complete](https://img.shields.io/badge/Phase%201-Completed-brightgreen?style=flat-square) |
| **02** | **Master Data & Workflows** | 741 Items taxonomy, Vendor masters, 4-eye Item Approval Workflow | ![Complete](https://img.shields.io/badge/Phase%202-Completed-brightgreen?style=flat-square) |
| **03** | **Material Transactions** | GRN receiving, Multi-line Issues, Waste Dispositions, GST validation | ![Complete](https://img.shields.io/badge/Phase%203-Completed-brightgreen?style=flat-square) |
| **04** | **Append-Only Ledger** | Double-entry journal, Physical audit arbitration, Blind stocktakes | ![Complete](https://img.shields.io/badge/Phase%204-Completed-brightgreen?style=flat-square) |
| **05** | **Furnace Heat Engine** | Induction furnace heat logging, Scrap aliases, 3-Pass issue reconciliation | ![Complete](https://img.shields.io/badge/Phase%205-Completed-brightgreen?style=flat-square) |
| **06** | **Weighted-Average Costing** | Arbitrary-precision costing, Zero-stock restart, Heat/Part cost modeling | ![Complete](https://img.shields.io/badge/Phase%206-Completed-brightgreen?style=flat-square) |
| **07** | **Migration & Audit Gate** | Stage 3A Evidence Intake, 82-Day Void governance, Cryptographic freeze | ![In Progress](https://img.shields.io/badge/Phase%207%20Stage%203A-Ready%20for%20Evidence-blue?style=flat-square) |

---

## 🧮 Costing Mathematical Formulations

<details>
<summary><b>Click to expand mathematical rules & tie-breaking hierarchy</b></summary>

### 1. Cumulative Weighted-Average Unit Cost (WAUC)
For any receipt transaction at timestamp $t$ with quantity $Q_{\text{recv}}$ and net ex-GST unit purchase rate $R_{\text{recv}}$:

$$\text{WAUC}_t = \frac{\left( Q_{\text{prior}} \times \text{WAUC}_{\text{prior}} \right) + \left( Q_{\text{recv}} \times R_{\text{recv}} \right)}{Q_{\text{prior}} + Q_{\text{recv}}}$$

### 2. Zero-Stock Rate Restart
If physical balance drops to zero ($Q_{\text{prior}} = 0$), the next inbound receipt restarts the effective rate without historical dilution:

$$\text{WAUC}_t = R_{\text{recv}} \quad \text{when } Q_{\text{prior}} = 0$$

### 3. Deterministic Same-Day Transaction Ordering
When multiple inventory transactions occur on the same calendar day, processing order is strictly guaranteed by:

$$\text{Sequence Priority} = \begin{cases} 
1 & \text{Opening Balance} \\ 
2 & \text{Goods Receipt Note (GRN)} \\ 
3 & \text{Material Issue (Stores $\rightarrow$ Foundry)} \\ 
4 & \text{Waste / Scrap Disposition} \\ 
5 & \text{Physical Audit Adjustment} 
\end{cases} \quad \longrightarrow \text{Tie-break by Primary Key ID ASC}$$

### 4. Liquid Metal & Part Costing
- **Liquid Metal Cost per kg Tapped:**
  $$\text{Cost/kg} = \frac{\sum_{i=1}^{n} \left( M_i \times \text{WAUC}_i \right)}{\text{Total Liquid Metal Tapped (kg)}}$$
- **Individual Cast Part Material Cost:**
  $$\text{Part Material Cost} = \text{Unit Cast Weight (kg)} \times \text{Cost/kg}$$

</details>

---

## 🛠 Technology Stack

```
Frontend:          React 19  •  TypeScript 5  •  Vite  •  Tailwind CSS  •  Lucide Icons
Backend:           Python 3.11+ / 3.14  •  FastAPI  •  Pydantic v2  •  Starlette
ORM & Migration:   SQLAlchemy 2.x  •  Alembic  •  psycopg 3 (PostgreSQL driver)
Database:          PostgreSQL 16  •  SQLite (In-Memory Fast Unit Testing)
DevOps & Tooling:  Docker  •  PowerShell Core  •  Pytest  •  Git Cryptographic Tagging
```

---

## 🚀 Quick Start Guide

### 1. Clone Repository & Setup Prerequisites
```powershell
# Clone the repository
git clone https://github.com/DarshanCat/material-cost-system-with-AI.git
cd "material-cost-system-with-AI"

# Prerequisites check:
# Python 3.11+ (python --version)
# Node.js 18+  (node --version)
# PostgreSQL 15+ (psql --version)
```

### 2. Automated Environment Initialization
```powershell
# Run the automated environment setup script
.\scripts\setup-env.ps1
```

### 3. Start Backend Development Server
```powershell
# Starts FastAPI server on http://127.0.0.1:8000
.\scripts\run-backend.ps1
```
* **Interactive OpenAPI Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **System Health Endpoint:** [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

### 4. Start Industrial Frontend Application
```powershell
# In a separate PowerShell terminal
.\scripts\run-frontend.ps1
```
* **Frontend Web Application:** [http://localhost:5173](http://localhost:5173)

---

## 🧪 Testing & Verification

The suite incorporates strict regression assertions across unit models, decimal costing precision, and multi-line reconciliation:

```powershell
# Run full automated test suite
pytest
```
```text
============================= test session starts =============================
collected 68 items
backend/tests/test_config.py ...                                         [  4%]
backend/tests/test_costing_audit.py ...                                  [  8%]
backend/tests/test_excel_import.py ...                                   [ 13%]
backend/tests/test_grn.py ...                                            [ 17%]
backend/tests/test_health.py .....                                       [ 25%]
backend/tests/test_heat_costing.py ....                                  [ 30%]
backend/tests/test_heat_import.py .                                      [ 32%]
backend/tests/test_heats.py ...                                          [ 36%]
backend/tests/test_inventory_valuation.py .....                          [ 44%]
backend/tests/test_issues.py ..                                          [ 47%]
backend/tests/test_item_requests_workflow.py .....                       [ 54%]
backend/tests/test_ledger_issues.py ..                                   [ 57%]
backend/tests/test_ledger_posting.py ..                                  [ 60%]
backend/tests/test_master_data.py ....                                   [ 66%]
backend/tests/test_material_aliases.py ...                               [ 70%]
backend/tests/test_opening_balances.py .                                 [ 72%]
backend/tests/test_part_costing.py ...                                   [ 76%]
backend/tests/test_physical_audits.py .                                  [ 77%]
backend/tests/test_reconciliation.py ...                                 [ 82%]
backend/tests/test_reconciliation_isolation.py .                         [ 83%]
backend/tests/test_vendors.py ...                                        [ 88%]
backend/tests/test_waste.py .                                            [ 89%]
backend/tests/test_weighted_average_costing.py .......                   [100%]
============================== 68 passed in 7.28s ==============================
```

---

## 📜 Regulatory Audit & Evidence Governance

All historical migrations adhere to strict ISO/Indian Accounting Standard (Ind AS 2) requirements:
- **Zero Synthetic Data Rule:** No simulated records are ever inserted into unrecorded periods.
- **Double-Blind Stocktaking:** Physical counts require two independent tally sheets before system reconciliation.
- **Cryptographic Evidence Sealing:** Every source spreadsheet digest is cataloged under SHA-256 in [`docs/reports/`](file:///c:/VSPL_MM/Material%20managment%20system/docs/reports/).

---

<div align="center">

<!-- Footer Banner -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=1,2,9,20&height=100&section=footer" width="100%" alt="Footer Banner"/>

<p align="center">
  <b>VSPL Material Management & Costing System</b> • Vijay Spheroidals Pvt. Ltd.<br>
  <i>Designed for Mission-Critical Metallurgy & Manufacturing Cost Control</i>
</p>

</div>
