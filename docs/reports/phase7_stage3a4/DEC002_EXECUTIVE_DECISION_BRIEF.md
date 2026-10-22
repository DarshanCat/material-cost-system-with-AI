# VSPL Material Management & Costing System — Executive Decision Brief: DEC-002

**Document ID:** `DOC-P7-S3A4-DEC002-BRIEF`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd., Peenya Industrial Area, Bangalore  
**Target Executive Audience:** Managing Director, Plant Head, Finance Head  
**Decision Under Review:** `DEC-002` — Historical Data vs 12-Oct-2026 Costing Cutoff (Cutoff Policy & 82-Day Void Treatment)  
**Current Governance Status:** **PENDING_REVIEW — AWAITING FORMAL EXECUTIVE DETERMINATION**  
**Execution Authority:** **READ-ONLY BRIEFING & DECISION TEMPLATE — ZERO OPERATIONAL MUTATIONS**  

---

## 1. Executive Summary & Context

This executive brief provides Vijay Spheroidals Pvt. Ltd. (VSPL) leadership—specifically the **Managing Director** and **Plant Head**—with the objective evidentiary analysis required to formally resolve **Decision DEC-002**. 

### 1.1 The Fundamental Challenge
VSPL is transitioning its material management, inventory ledger, and foundry melt costing from fragmented, unverified spreadsheets to an authoritative, append-only ERP database. 

However, two chronological realities collide:
1. **Source Spreadsheet Cutoff:** Primary digital records in `VSPL_Material_Entry.xlsx` and `VSPL_Foundry_Heat_Log.xlsx` terminate abruptly on **22 July 2026**.
2. **ERP Go-Live & Costing Target:** The intended live system startup and costing baseline date is **12 October 2026**.

Between these two dates lies an **82-day operational void** (23 July 2026 through 11 October 2026) during which the foundry operated continuously, melted heats, consumed raw materials, and received scrap without electronic ledger logging. 

Furthermore, the interim spreadsheet ledger (`VSPL_Master_Ledger.xlsx`) subtracted furnace charges directly from an uninitialized (zero) opening balance, generating **seven negative raw material balances** while simultaneously omitting **11,793 kg of scrap issues** recorded on physical store dockets.

### 1.2 Purpose of this Brief
This document defines the policy alternatives, evaluates statutory and financial risks, clarifies the necessity of an independent physical stocktake, outlines the cross-functional impacts on inventory valuation under Phase 6 Rule C1, and provides a formal, unexecuted **Decision Record Template** for executive determination.

> [!IMPORTANT]
> **No Presumed Approval:**  
> This package does **not** assume approval of any scenario. Approval fields are intentionally blank and must remain unexecuted until authorized leadership convenes, deliberates, and signs the physical decision record. Stage 3B live migration remains **STRICTLY UNAUTHORIZED**.

---

## 2. Source-Data Realities & Evidence Analysis

### 2.1 The 82-Day Operational Void (23-Jul-2026 to 11-Oct-2026)
- **Verified Source Cutoff Date:** Cell `A601` of `VSPL_Material_Entry.xlsx` ('4. Issue') records the final digital issue transaction on **22-Jul-2026**. Similarly, row 20 of `VSPL_Foundry_Heat_Log.xlsx` ('Heat Log') records heat `072622-2110` on **22-Jul-2026**.
- **The Gap:** Exactly **82 calendar days** elapsed between the source cutoff and the target costing go-live date of **12-Oct-2026**.
- **Plant Activity During the Gap:** Physical operations did not stop. Raw materials were consumed across three daily foundry shifts, shop supplies were issued, customer castings were poured, and scrap was generated. These transactions exist solely as physical paper slips, weighbridge tickets, and furnace deck logs, or were unlogged.

### 2.2 Seven Negative Balances in the Interim Ledger
In `VSPL_Master_Ledger.xlsx` ('Daily Ledger'), the maintainer recorded furnace charges for heat `H-260714-01` by directly subtracting charged quantities without recording an initial opening balance. This generated the following mathematically indefensible negative book stock:

| Item Code | Item Description | Reported Closing Balance | Underlying Cause | Impact on ERP Database |
| :--- | :--- | :--- | :--- | :--- |
| `RM-SC-001` | Mild Steel Scrap | **-500.00 kg** | Heat `H-260714-01` charge subtracted from 0 opening stock | Violates non-negative stock invariant; rejects subsequent issues |
| `RM-SC-003` | Foundry Returns / Gatings | **-300.00 kg** | Heat `H-260714-01` charge subtracted from 0 opening stock | Violates non-negative stock invariant; rejects subsequent issues |
| `RM-SC-005` | Cast Iron Scrap | **-100.00 kg** | Heat `H-260714-01` charge subtracted from 0 opening stock | Violates non-negative stock invariant; rejects subsequent issues |
| `RM-FA-001` | Ferro Silicon | **-10.00 kg** | Heat `H-260714-01` charge subtracted from 0 opening stock | Rejects alloy allocations to melt batches |
| `RM-FA-002` | Ferro Manganese | **-4.00 kg** | Heat `H-260714-01` charge subtracted from 0 opening stock | Rejects alloy allocations to melt batches |
| `RM-FA-003` | Ferro Chrome | **-4.00 kg** | Heat `H-260714-01` charge subtracted from 0 opening stock | Rejects alloy allocations to melt batches |
| `RM-TR-002` | Inoculant | **-2.00 kg** | Heat `H-260714-01` charge subtracted from 0 opening stock | Rejects ladle treatment records |

### 2.3 The 11,793 kg Omitted Scrap Issues
During Phase 7 Stage 2.1 cross-reconciliation, audit scripts identified that physical store issue slips 315, 316, 317, 318, 319, and 320 recorded **11,793.00 kg** of scrap issued to the furnace yard. These transactions were recorded in `VSPL_Material_Entry.xlsx` ('4. Issue') but were **completely omitted** from `VSPL_Master_Ledger.xlsx` ('Issue' sheet).

Carrying the interim ledger balances into the live ERP would mean carrying forward a spreadsheet that is missing nearly 12 tonnes of raw material consumption.

---

## 3. Why a Certified Physical Stocktake is Mandatory

The new application database enforces strict, non-negotiable operational invariants at the software and database layer:

1. **Non-Negative Balance Constraint (`HTTP 409 Conflict`):** As demonstrated by automated regression tests in `backend/tests/test_ledger_issues.py`, the system actively blocks any material issue or scrap disposition if available book stock is insufficient or uninitialized.
2. **Moving Weighted-Average Recalculation (Rule C1):** Under Phase 6 Rule C1 (`costing_service.py`), every material receipt recalculates the weighted-average unit price:
   $$\text{New Average Rate} = \frac{(\text{Current Qty} \times \text{Current Rate}) + (\text{Incoming Qty} \times \text{Incoming Rate})}{\text{Current Qty} + \text{Incoming Qty}}$$
   If current quantity is negative (e.g. $-500\text{ kg}$), the denominator collapses or yields an absurd, inverted valuation, corrupting casting cost sheets.
3. **Statutory & Audit Defensibility:** Carrying unverified July balances forward across an 82-day void violates Indian Accounting Standard (Ind AS 2) and statutory cost audit standards. It creates "phantom inventory" (material recorded on books that physically departed months ago) or "false stockouts" (raw materials physically present in the yard that the computer reports as zero or negative).

**Conclusion:** Authoritative opening stock **cannot be derived mathematically from historical spreadsheets**. It can only be established through an independent, certified physical count.

---

## 4. Cross-Functional Dependencies: Inventory, Scrap, and Costing

Executive Decision DEC-002 does not exist in isolation. It anchors four other critical migration workstreams:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   DEC-002 GOVERNANCE ANCHOR MATRIX                     │
├────────────────────────────────────────────────────────────────────────┤
│ DEC-002: Executive Cutoff Policy Mandate                               │
│ │                                                                      │
│ ├──> DEC-001 (Commercial Invoice Rates)                                │
│ │    • Purchase invoices establish ex-GST base cost.                   │
│ │    • Combined with physical stocktake quantities to initialize       │
│ │      Rule C1 opening valuations in item_cost_journal_entries.        │
│ │                                                                      │
│ ├──> DEC-003 & DEC-005 (Scrap Chemistry & Yard Reconciliation)         │
│ │    • Spectrometer test certifies CRCA scrap chemistry (007 vs 008).  │
│ │    • Physical weighbridge count eliminates 7 negative balances.      │
│ │                                                                      │
│ └──> Rule H1 Isolation (Furnace Production vs Stores Ledger)           │
│      • Confirms heat charges are melt costing records, NOT store issue │
│        documents. Prevents double-counting of furnace charges.         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Policy Alternatives & Evaluation for Management

Executive management must choose between three fundamental policy pathways:

```
+-------------------------------------------------------------------------------------------------------------------+
| COMPARATIVE EVALUATION OF CUTOFF POLICY SCENARIOS                                                                 |
+------------------------------------+------------------------------------+-----------------------------------------+
| Policy Pathway                     | Operational & Financial Advantages | Risks, Costs & Audit Disadvantages      |
+------------------------------------+------------------------------------+-----------------------------------------+
| SCENARIO A:                        | 1. Clear, legally defensible audit | 1. Requires plant-wide physical count.  |
| Historical Audit Archive &         |    baseline as of 12-Oct-2026.    | 2. Historical transactions remain an    |
| Certified Physical Cutoff          | 2. Immediately purges 7 negative   |    archive, not in active ERP ledger.   |
| (RECOMMENDED BY IMPLEMENTATION)    |    balances and spreadsheet errors.| 3. Requires Finance sign-off on opening |
|                                    | 3. Enables clean Rule C1 costing.  |    inventory valuation write-offs.      |
+------------------------------------+------------------------------------+-----------------------------------------+
| SCENARIO B:                        | 1. Reconstructs unbroken history.  | 1. 6 to 8 week implementation delay.    |
| Full Retrospective Reconstruction  | 2. Ingests all paper slips across  | 2. Heavy labor and audit cost.          |
| of the 82-Day Operational Void     |    the July-October void.          | 3. Severe risk of missing/lost paper    |
| (NOT RECOMMENDED)                  |                                    |    dockets, yielding incomplete data.   |
+------------------------------------+------------------------------------+-----------------------------------------+
| SCENARIO C:                        | 1. Zero counting effort required.  | 1. Guarantees immediate audit rejection.|
| Direct Roll-Forward of July Data   | 2. Fast technical cutover.         | 2. Injects 7 negative stock balances.   |
| Without Physical Stocktake         |                                    | 3. Corrupts Rule C1 unit rates.         |
| (STRICTLY PROHIBITED BY AUDIT)     |                                    | 4. System rejects daily issues on Day 1.|
+------------------------------------+------------------------------------+-----------------------------------------+
```

---

## 6. The Six Executive Questions to Decide

The **Managing Director** and **Plant Head** must formally deliberate and record decisions on the following six specific policy items:

### Question 1: Operational Cutoff Date
> **Decision Point:** Does executive leadership formally designate **12 October 2026, 23:59:59 IST** as the definitive, plant-wide operational cutoff timestamp?

### Question 2: Historical Archive Policy (82-Day Void Treatment)
> **Decision Point:** Does management approve **Scenario A**, mandating that records prior to 23 July 2026 be treated strictly as a read-only historical archive, with no retrospective ledger reconstruction of the 82-day void?

### Question 3: Treatment of Scrap & Negative Interim Balances
> **Decision Point:** Does management mandate that the physical weighbridge stocktake of the raw material scrap yard supersedes all historical negative spreadsheet balances, writing off unverified spreadsheet discrepancies?

### Question 4: Legal Opening Inventory Authority
> **Decision Point:** Who holds the formal authority to sign off and legally certify the initial opening stock quantities and values—delegated jointly to the **Plant Head** and **Finance Head**, with final countersignature by the **Managing Director**?

### Question 5: Financial Valuation & Rule C1 Integration
> **Decision Point:** Does Finance authorize valuing opening stock quantities at verified ex-GST purchase rates from the latest vendor tax invoices, with unrated items valued under an approved commercial schedule, booking any net stocktake variance to an inventory adjustment reserve?

### Question 6: Execution of Sign-Off Mandate
> **Decision Point:** Does management authorize executing the physical sign-offs on the attached Decision Record Template and [`MANAGEMENT_SIGNOFF_TEMPLATE.md`](file:///C:/VSPL_MM/Material%20managment%20system/docs/reports/phase7_management_signoff/MANAGEMENT_SIGNOFF_TEMPLATE.md) to formally unblock Acceptance Gates G1 and G2?

---

## 7. Accountable Roles & Governance Matrix

| Lifecycle Stage | Governing Role | Designated Responsibility |
| :--- | :--- | :--- |
| **Policy Determination** | **Managing Director** | Final corporate approval; authorization of Cutoff Scenario A; signing of executive mandate. |
| **Operational Execution** | **Plant Head** | Plant-wide operations freeze; stocktake resource allocation; scrap yard weighbridge management. |
| **Financial Valuation** | **Finance Head** | Verification of ex-GST purchase rates; GST compliance; accounting for stocktake variances. |
| **Count Execution** | **Stores Manager** | Item master catalog freeze; count tag administration (`TAG-YYYYMMDD-XXXX`); physical counting. |
| **Metallurgical Control** | **Chief Metallurgist** | Spectrometer chemical testing of scrap; isolation of furnace melt logs from stores ledger (Rule H1). |
| **Independent Audit** | **Lead Inventory Auditor** | Supervision of double-blind counting; audit of Sheet B variances; certification of Sheet D. |
| **Technical Verification** | **Systems Architect** | Staging manifest generation; verification that no historical imports occur until gates clear. |

---

## 8. DEC-002 Formal Executive Decision Record Template

```
====================================================================================================
                        VIJAY SPHEROIDALS PVT. LTD. — EXECUTIVE DECISION RECORD
====================================================================================================

1. DECISION IDENTIFIER:
   Decision ID: DEC-002
   Title: Cutoff Policy Mandate & Treatment of 82-Day Operational Void (22-Jul-2026 to 12-Oct-2026)
   Related Acceptance Gates: G1 (Executive Sign-Off), G2 (Cutoff Policy), G7 (Physical Stocktake)

2. DECISION STATEMENT:
   Executive leadership of Vijay Spheroidals Pvt. Ltd. hereby deliberates on the cutoff policy governing
   the transition from legacy spreadsheets to the authoritative Material Management & Costing System.

3. SELECTED POLICY PATHWAY (Executive to check one):
   [ ] SCENARIO A (Approved): Adopt Historical Audit Archive & Certified Physical Cutoff.
       • Historical transactions up to 22-Jul-2026 are preserved as read-only historical archive.
       • The 82-day void is not reconstructed electronically.
       • Certified physical stocktake as of 12-Oct-2026 establishes opening ERP inventory.
   [ ] SCENARIO B: Mandate full retrospective reconstruction of all paper dockets (82-day delay).
   [ ] SCENARIO C: Rejected by Audit.

4. EFFECTIVE CUTOFF DATE & TIME:
   Designated Cutoff Timestamp: 12 October 2026, 23:59:59 IST

5. TREATMENT OF TRANSACTIONS DURING THE 82-DAY VOID:
   Policy Determination: __________________________________________________________________________
   ________________________________________________________________________________________________

6. TREATMENT OF HISTORICAL SCRAP & NEGATIVE INTERIM BALANCES:
   Policy Determination: __________________________________________________________________________
   ________________________________________________________________________________________________

7. OPENING BALANCE LEGAL AUTHORITY & VALUATION METHOD:
   Authorized Signatories: Plant Head and Finance Head (Countersigned by Managing Director)
   Valuation Method: Latest verified ex-GST vendor invoice rate under Phase 6 Rule C1.

8. REQUIRED SUPPORTING EVIDENCE ATTACHMENTS:
   Attachment 1: Certified Physical Stocktake Register (VSPL_Physical_Stocktake_Register.xlsx Sheet D)
   Attachment 2: Scrap Spectrometry Test Certificate (Quality Lab OES Report for 15,200 kg CRCA scrap)
   Attachment 3: Commercial Purchase Rates Staging Schedule (commercial_rates_staging.csv)
   Attachment 4: Stocktake Discrepancy & Variance Investigation Report (Sheet B)

9. CONDITIONS, EXCEPTIONS, AND OPEN QUESTIONS:
   • _____________________________________________________________________________________________
   • _____________________________________________________________________________________________

----------------------------------------------------------------------------------------------------
                                    FORMAL EXECUTIVE SIGN-OFF
----------------------------------------------------------------------------------------------------

MANAGING DIRECTOR APPROVAL:
Name:      ____________________________________________________
Signature: ____________________________________________________
Date:      ________________________ (DD/MM/YYYY)


PLANT HEAD APPROVAL:
Name:      ____________________________________________________
Signature: ____________________________________________________
Date:      ________________________ (DD/MM/YYYY)


FINANCE HEAD ACKNOWLEDGEMENT:
Name:      ____________________________________________________
Signature: ____________________________________________________
Date:      ________________________ (DD/MM/YYYY)


STORES MANAGER ACKNOWLEDGEMENT:
Name:      ____________________________________________________
Signature: ____________________________________________________
Date:      ________________________ (DD/MM/YYYY)

----------------------------------------------------------------------------------------------------
FINAL GOVERNANCE STATUS:
[X] PENDING_REVIEW (Current state — awaiting completed signatures above)
[ ] APPROVED       (Applicable only when signed physical/digital document is filed in project archive)
====================================================================================================
```

---

## 9. Stop Condition & Safety Attestation

### Operational Attestation:
- **Zero Database Operations:** No database records, stock ledger entries, or opening balance journals were posted.
- **Zero Configuration Changes:** No Docker containers were started, no network ports were modified, and no Alembic migrations were applied.
- **Documentation Only:** This executive brief provides the decision framework. DEC-002 remains in `PENDING_REVIEW` status until authorized executives physically sign the Decision Record.
- **Prohibition Enforced:** **Stage 3B live migration remains strictly unauthorized.**
