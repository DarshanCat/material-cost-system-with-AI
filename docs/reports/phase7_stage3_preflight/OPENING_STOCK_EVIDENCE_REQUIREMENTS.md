# VSPL Material Management & Costing System — Opening Stock Evidence Requirements

**Document ID:** `DOC-P7-S3A-OPENING-STOCK-EVIDENCE`  
**System:** VSPL Material Management & Costing System  
**Date:** 2026-10-17  
**Governance Scope:** Cutoff Policy Analysis & Opening Stock Certification Standards  
**Status:** **POLICY PENDING EXECUTIVE SELECTION — ZERO OPENING BALANCES POSTED**  

---

## 1. Executive Cutoff Context & The 82-Day Operational Void

The live application configuration establishes the official costing baseline start date as:
```python
COSTING_START_DATE = date(2026, 10, 12)
```
Historical digital transaction records in `VSPL_Material_Entry.xlsx` terminate on **22 July 2026**. Between 23-Jul-2026 and 11-Oct-2026, the foundry and machine shop operated continuously for **82 days without electronic inventory logging**.

### Mandatory Auditing Principle:
> [!CAUTION]
> **No Silent Carrying Forward:**  
> A manufacturing plant running continuous melting, casting, machining, and dispatch operations consumes dozens of tonnes of raw materials and hundreds of tooling inserts weekly. July 2026 spreadsheet balances **cannot and must not** be assumed to represent inventory as of 12 October 2026.

---

## 2. Comparative Analysis of Cutoff Scenarios

Management must formally review and authorize one of three distinct cutoff scenarios under **DEC-002**:

```
                                  CUTOFF SCENARIO ARCHITECTURE
  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
  │ SCENARIO A: HISTORICAL AUDIT ARCHIVE (READ-ONLY INGESTION) — [TECHNICALLY RECOMMENDED]     │
  │ • July 2026 data ingested into read-only historical archive tables (not live stock ledger).│
  │ • Live inventory ledger begins on 12-Oct-2026 with an audited, certified physical count.   │
  │ • Pros: 100% compliant with statutory audit standards; avoids 82-day void; 0 negative stock.│
  │ • Cons: Requires formal plant-wide physical stocktake before live transactions begin.       │
  ├─────────────────────────────────────────────────────────────────────────────────────────────┤
  │ SCENARIO B: RECONSTRUCTED INVENTORY POSITION (FULL PAPER AUDIT)                             │
  │ • Attempt to reconstruct all movements between 23-Jul and 11-Oct from physical paper dockets.│
  │ • Pros: Provides a theoretical continuous chronological ledger from July onward.             │
  │ • Cons: Extreme operational overhead; missing paper slips will cause statutory audit defects.│
  ├─────────────────────────────────────────────────────────────────────────────────────────────┤
  │ SCENARIO C: FULL HISTORICAL MOVEMENT IMPORT (ASSUMED CONTINUITY) — [STRICTLY UNACCEPTABLE]   │
  │ • Post July transactions directly into live ledger, assuming July balances equal October.    │
  │ • Fatal Defects: Violates ledger non-negative invariants; zero rates corrupt casting costs.  │
  └─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Segregated Evidence Requirements: Quantity versus Valuation

To maintain strict accounting separation under Phase 6 Rule C1, opening stock requires two independent, corroborated streams of evidence before any opening balance can be initialized:

### 3.1 Stream 1: Physical Opening Quantities
Opening quantities must be proven through primary physical measurement, **never** derived from ledger arithmetic or furnace heat charges:

| Material Category | Primary Physical Evidence Required | Verification Protocol | Responsible Authority |
| :--- | :--- | :--- | :--- |
| **Bulk Raw Materials** *(Scrap, Pig Iron, Gatings)* | Certified weighbridge tickets (gross - tare) or geometric stockpile survey with core density checks | Two-part count tags; weighbridge calibration stamp | Plant Head & Weighbridge Operator |
| **Ferro-Alloys & Inoculants** *(FeSi, FeMn, Mg, Inoculants)* | Digital platform scale weighment tickets (tared container) in locked alloy crib | Sealed drum count + loose container weighment | Foundry Metallurgist & Stores Manager |
| **Consumables & Moulding** *(Bentonite, Refractory, Core Binders)* | Physical bag and pallet count; dipstick fluid level measurement on coating drums | Standard bag count + partial bag scale check | Stores Manager |
| **Cutting Tools & Inserts** *(Blades, Tool Posts, Inserts)* | 100% discrete physical piece count across all crib drawers and CNC machine carousels | Reground/dull tools physically segregated from new stock | Machine Shop Head & Tool Crib In-charge |

### 3.2 Stream 2: Commercial Opening Valuation
Opening valuations must be derived from verified commercial purchase documents, **never** estimated, standard-costed, or guessed:

| Valuation Element | Mandatory Primary Evidence | Verification Standard | Responsible Authority |
| :--- | :--- | :--- | :--- |
| **Unit Purchase Rate** | Original supplier Tax Invoice (Form GST INV-01) or approved Purchase Order | Commercial rate strictly **excluding GST** (ex-GST base rate) | Finance Head & Purchase Head |
| **Freight & Incidental Cost** | Inward freight lorry receipts (LR) or approved transportation billing | Attributed per kilogram where applicable | Cost Accountant |
| **Missing Rates** | Any material without an audited supplier invoice must remain **`EXPLICITLY_UNVALUED`** | System assigns zero rate to value; inventory quantity remains active | Finance Head |

---

## 4. Specific Evidence Standards for the Seven Negative-Stock Items

The seven raw materials exhibiting negative closing balances in `VSPL_Master_Ledger.xlsx` require specific forensic resolution prior to opening balance creation:

```
+------------+--------------------+---------------------+---------------------------------------------------------------+
| Item Code  | Description        | Interim Ledger Cls  | Mandatory Opening Evidence Standard                           |
+------------+--------------------+---------------------+---------------------------------------------------------------+
| FDY-RM-008 | CRC Scrap-Low MN   | -500.000 kg         | 1. Weighbridge certificate for low-manganese scrap yard.      |
|            |                    |                     | 2. Reconcile unposted 15,200 kg GRN row 5 (Invoice 384).      |
|            |                    |                     | 3. Spectrometry report proving Mn content (0.15–0.25%).       |
+------------+--------------------+---------------------+---------------------------------------------------------------+
| FDY-RM-011 | Gattings-500       | -300.000 kg         | 1. Physical weighbridge survey of foundry return gating yard. |
|            |                    |                     | 2. Implement internal foundry return movement workflow.       |
+------------+--------------------+---------------------+---------------------------------------------------------------+
| FDY-RM-014 | Inoculant 15       | -2.000 kg           | 1. Scale weighment of alloy crib drums on cutoff date.        |
|            |                    |                     | 2. Discard future-dated 2026-11-07 legacy receipt timestamp.  |
+------------+--------------------+---------------------+---------------------------------------------------------------+
| FDY-RM-016 | Magnesium          | -15.000 kg          | 1. Physical ingot weighment under security supervisor log.    |
|            |                    |                     | 2. Corroborate against 550 kg undated legacy physical stock.  |
+------------+--------------------+---------------------+---------------------------------------------------------------+
| FDY-RM-017 | Manganese          | -3.000 kg           | 1. Scale weighment of FeMn containers in alloy room.          |
|            |                    |                     | 2. Reconcile store issues vs furnace charges (Rule H1).       |
+------------+--------------------+---------------------+---------------------------------------------------------------+
| FDY-RM-019 | Pig Iron           | -150.000 kg         | 1. Weighbridge survey of pig iron raw material yard.          |
|            |                    |                     | 2. Audit supplier purchase invoices for ex-GST rate.          |
+------------+--------------------+---------------------+---------------------------------------------------------------+
| FDY-RM-020 | Silicon            | -5.000 kg           | 1. Scale weighment of FeSi containers in alloy room.          |
|            |                    |                     | 2. Corroborate against 26 kg legacy receipt on 12-Oct cutoff. |
+------------+--------------------+---------------------+---------------------------------------------------------------+
```

### Governing Restraint:
Under no circumstances may an algorithm calculate opening stock by adding furnace charges back into ledger balances. All seven items remain **BLOCKED** until physical stocktake certificates are executed.
