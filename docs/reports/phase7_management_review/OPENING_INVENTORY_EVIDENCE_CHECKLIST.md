# VSPL Material Management & Costing System — Opening Inventory Evidence Checklist

**Document ID:** `DOC-P7-OPENING-INV-CHECKLIST`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd. (SG Iron Foundry & Machine Shop, Peenya, Bangalore)  
**Governance Scope:** Mandatory Physical Stocktake & Opening Valuation Audit Protocols  
**Date:** 2026-10-13  
**Status:** **AUDIT STANDARD FOR OPENING BALANCE CERTIFICATION**  

---

## 1. Executive Context & The Invariant of Opening Stock

Under Phase 4 (Append-Only Live Inventory Ledger) and Phase 6 (Weighted-Average Costing & Valuation), opening inventory is **not a casual estimate or mathematical residual**. It is the authoritative anchor of the entire material management and costing system.

### Core Ledger Invariant:
```
Closing Balance = Opening Balance + Total Receipts - Total Issues - Total Waste +/- Certified Audit Adjustments
```
If the Opening Balance is incorrect, every downstream stock balance, reorder alert, furnace charge reconciliation, weighted-average rate, and part cost calculation will be permanently skewed.

---

## 2. Mandatory Physical Count Protocols

A complete, plant-wide physical inventory count must be executed to certify Opening Stock as of the approved cutoff date (e.g., 12-Oct-2026).

### 2.1 Physical Count Scope & Segregation of Yards:
1. **Raw Material Scrap Yard (Peenya Foundry Yard):**
   - Heavy melting scrap, CRC Scrap-Low MN (`FDY-RM-008`), CRC Scrap-Low High MN (`FDY-RM-007`), MS Scrap (`FDY-RM-018`).
   - *Protocol:* Weighbridge gross/tare measurement or volumetric survey certified by Foundry Supervisor.
2. **Foundry Returns & Gatings Yard:**
   - Internal foundry returns, gating heads, runner risers, sprue scrap (`FDY-RM-009` to `012`).
   - *Protocol:* Bin-level tared weighing.
3. **Pig Iron & Ferrous Alloys Store:**
   - Pig Iron (`FDY-RM-019`), Silicon (`FDY-RM-020`), Manganese (`FDY-RM-017`), Magnesium (`FDY-RM-016`), Inoculants (`FDY-RM-014`, `015`), Carburizers (`FDY-RM-013`).
   - *Protocol:* Piece/bag count and bag weight verification.
4. **Foundry & Machine Shop Consumables Store:**
   - Grinding wheels, cutting blades, pattern wax, paints, tempo brushes, safety gloves, cotton waste.
   - *Protocol:* Exact physical count per storage bin/rack.
5. **Machine Shop Tooling & Bearings Store:**
   - Turning tools, boring tools, tool posts, bearings, V-belts.
   - *Protocol:* Exact piece count against rack locations.
6. **Cast Parts & Work-in-Progress (Fettling / Inspection):**
   - SG Iron raw castings, fettled castings, machined castings awaiting dispatch.
   - *Protocol:* Piece count by part number / pattern and grade.

---

## 3. Physical Count Evidence Schedule (Template)

Every counted item must be recorded on signed, serialized physical count tags and transcribed into the Opening Stock Evidence Register:

| Item Code | Canonical Description | Category | Cost Head | Department | Canonical UOM | Physical Tag # | Physical Count Qty | Unit Valuation Rate (ex-GST INR) | Total Opening Valuation (INR) | Counted By (Name/Role) | Verified By (Auditor) | Variance vs Interim Ledger | Notes / Bin Location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `FDY-RM-007` | CRC Scrap-Low High MN | Raw Material | Foundry Raw Material | Foundry | Kg | TAG-RM-001 | *[Fill]* | *[Fill]* | *[Computed]* | *[Signature]* | *[Signature]* | *[Computed]* | Scrap Yard Bay 1 |
| `FDY-RM-008` | CRC Scrap-Low MN | Raw Material | Foundry Raw Material | Foundry | Kg | TAG-RM-002 | *[Fill]* | *[Fill]* | *[Computed]* | *[Signature]* | *[Signature]* | *[Computed]* | Scrap Yard Bay 2 |
| `FDY-RM-011` | Gattings-500 | Raw Material | Foundry Raw Material | Foundry | Kg | TAG-RM-003 | *[Fill]* | *[Fill]* | *[Computed]* | *[Signature]* | *[Signature]* | *[Computed]* | Returns Bin R1 |
| `FDY-RM-014` | Inoculant 15 | Raw Material | Foundry Raw Material | Foundry | Kg | TAG-RM-004 | *[Fill]* | *[Fill]* | *[Computed]* | *[Signature]* | *[Signature]* | *[Computed]* | Alloy Room Bin A4 |
| `FDY-RM-016` | Magnesium | Raw Material | Foundry Raw Material | Foundry | Kg | TAG-RM-005 | *[Fill]* | *[Fill]* | *[Computed]* | *[Signature]* | *[Signature]* | *[Computed]* | Alloy Room Bin A2 |
| `FDY-RM-017` | Manganese | Raw Material | Foundry Raw Material | Foundry | Kg | TAG-RM-006 | *[Fill]* | *[Fill]* | *[Computed]* | *[Signature]* | *[Signature]* | *[Computed]* | Alloy Room Bin A3 |
| `FDY-RM-019` | Pig Iron | Raw Material | Foundry Raw Material | Foundry | Kg | TAG-RM-007 | *[Fill]* | *[Fill]* | *[Computed]* | *[Signature]* | *[Signature]* | *[Computed]* | Pig Iron Stacks |
| `FDY-RM-020` | Silicon | Raw Material | Foundry Raw Material | Foundry | Kg | TAG-RM-008 | *[Fill]* | *[Fill]* | *[Computed]* | *[Signature]* | *[Signature]* | *[Computed]* | Alloy Room Bin A1 |
| `MNT-CN-001` | 3306PMKT-Generator | Consumables | Maintenance Consumables| Maintenance | Set | TAG-MN-001 | *[Fill]* | *[Fill]* | *[Computed]* | *[Signature]* | *[Signature]* | *[Computed]* | Maint Rack M1 |
| `MCS-CN-002` | Tool Post | Consumables | Machine Shop Consumables| Machine Shop| Nos | TAG-MS-001 | *[Fill]* | *[Fill]* | *[Computed]* | *[Signature]* | *[Signature]* | *[Computed]* | Tool Crib Bin T2 |

---

## 4. Supporting Rate & Valuation Requirements

In accordance with cost accounting standards and Phase 6 rules:
1. **Ex-GST Unit Rates:** Every opening stock quantity must be paired with an approved commercial unit rate excluding GST.
2. **Valuation Source Documents:**
   - Most recent approved purchase tax invoice from the authorized vendor.
   - For internal foundry returns / gatings: Metallurgist / Cost Accountant certified valuation rate (e.g. scrap equivalent market price).
   - For work-in-progress cast parts: Accumulated raw material melting cost per kg + fettling charge.
3. **Prohibited Valuation Methods:**
   - Standard rates copied from competitors.
   - Inflated tax-inclusive rates (GST input tax credits must be segregated).
   - Arbitrary round-number guesses.

---

## 5. Variance Investigation & Reconciliations

Any variance between the certified physical count and previous electronic records (e.g. Master Ledger closing figures) must be categorized and documented:

### Variance Categories:
1. **Unrecorded Inward Receipts:** Material delivered to the foundry but never entered into the system.
2. **Unrecorded Stores Issues:** Material drawn by the foundry or machine shop on informal paper slips without electronic entry.
3. **Melting / Scrap Losses:** Unrecorded furnace slag, oxidization, spillages, or machining turnings.
4. **Clerical Measurement Discrepancies:** Moisture weight loss, scale calibration variance, or bulk scrap density estimation errors.

---

## 6. Audit Trail & Certification Sign-Off

The final Opening Stock Evidence Package must be signed by three independent authorities before technical entry into the live database:

```
====================================================================================================
                       OPENING INVENTORY CERTIFICATION SIGN-OFF
====================================================================================================

Count Date: ____________________       Effective Opening Date: ____________________

1. PHYSICAL COUNT VERIFICATION:
   I certify that the physical inventory quantities enumerated above represent an accurate,
   independent, physical count of all inventory located at the VSPL Peenya facility.
   
   Stores Manager Signature: ___________________________    Date: ______________
   Plant Head Signature: _______________________________    Date: ______________

2. VALUATION & COMMERCIAL RATE CERTIFICATION:
   I certify that the unit valuation rates applied above exclude GST and reflect certified
   vendor purchase invoices or approved cost-accounting valuation schedules.
   
   Finance Head Signature: _____________________________    Date: ______________

3. AUDIT & INTERNAL CONTROLS INDEPENDENCE:
   I certify that the count procedures conformed to standard inventory control protocols
   and that variances have been formally investigated and documented.
   
   Inventory Control Auditor Signature: _______________    Date: ______________

====================================================================================================
```
