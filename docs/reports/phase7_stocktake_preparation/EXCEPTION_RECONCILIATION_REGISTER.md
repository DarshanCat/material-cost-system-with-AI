# VSPL Material Management & Costing System — Historical Exception Reconciliation Register

**Document ID:** `REG-P7-EXCEPTION-RECONCILIATION`  
**System:** VSPL Material Management & Costing System  
**Company:** Vijay Spheroidals Pvt. Ltd., Peenya Industrial Area, Bangalore  
**Scope:** Deep Forensic Investigation & Governance Paths for Historical Data Anomalies  
**Date:** 13 October 2026  
**Governance Status:** **AUDIT EVIDENCE COMPLIANT — AUTOMATED RESOLUTION STRICTLY PROHIBITED**  

---

## 1. Executive Summary & Prohibition on Auto-Resolution

During Phase 7 audit reconciliation (Stages 1, 2, and 2.1), seven major classes of data integrity exceptions were discovered across legacy spreadsheets and historical staging workbooks.

### Mandatory Auditor Rule:
> [!CAUTION]
> **Zero Automated Reconciliation:** No database migration script, staging loader, or spreadsheet macro may automatically zero-out, offset, normalize, or guess values for these exceptions. Every anomaly represents either physical inventory risk, metallurgical non-conformance, or financial statement distortion. Each must follow a strict, documented governance path.

---

## 2. Detailed Exception Analysis & Governance Paths

### 2.1 Exception Class 1: The Seven Negative Raw Material Closing Balances

#### Summary Table:
| Canonical Code | Material Description | Legacy Code | Interim Ledger Closing Stock | Furnace Heat Charge `H-260714-01` | Sheet 4 Actual Store Issues | Legacy Physical Stock | Decision Ref |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FDY-RM-008** | CRC Scrap-Low MN | FRM08 | **-500.000 kg** | 500.000 kg | 11,793.000 kg | 0.000 kg | DEC-005 |
| **FDY-RM-011** | Gattings-500 | FRM11 | **-300.000 kg** | 300.000 kg | 0.000 kg | 0.000 kg | DEC-005 |
| **FDY-RM-014** | Inoculant 15 | FRM14 | **-2.000 kg** | 2.000 kg | 0.000 kg | 92.500 kg (11-07) | DEC-005 |
| **FDY-RM-016** | Magnesium | FRM16 | **-15.000 kg** | 15.000 kg | 0.000 kg | 550.000 kg (undated) | DEC-005 |
| **FDY-RM-017** | Manganese | FRM17 | **-3.000 kg** | 3.000 kg | 278.509 kg | 20.000 kg (undated) | DEC-005 |
| **FDY-RM-019** | Pig Iron | FRM19 | **-150.000 kg** | 150.000 kg | 0.000 kg | 0.000 kg | DEC-005 |
| **FDY-RM-020** | Silicon | FRM20 | **-5.000 kg** | 5.000 kg | 50.218 kg | 26.000 kg (11-07) | DEC-005 |

#### Forensic Root-Cause Findings:
1. **Direct Deduction of Furnace Heat Charges:** The interim Master Ledger (`VSPL_Master_Ledger.xlsx`) recorded zero opening stock for all raw materials. When furnace heat `H-260714-01` was charged on 14-Jul-2026, the charges (500 kg scrap, 300 kg gatings, 2 kg inoculant, 15 kg magnesium, 3 kg manganese, 150 kg pig iron, 5 kg silicon) were subtracted directly as "Store Issues", plunging closing balances into negative territory.
2. **Gross Disconnect from Store Issue Logs:** The interim ledger completely ignored the actual Store Issue log (`VSPL_Material_Entry.xlsx` sheet `4. Issue`), which recorded:
   - **11,793 kg of CRC Scrap** issued across July 2026.
   - **278.509 kg of Manganese** issued across July 2026.
   - **50.218 kg of Silicon** issued across July 2026.
3. **Unposted Inward Deliveries:** An inward delivery of **15,200 kg of `crca scrap`** on GRN Row 5 was never posted to the interim ledger.
4. **Why Automated Clearing is Blocked:** If an algorithm simply "resets" these balances to zero, or posts the 11,793 kg of issues again, the live inventory ledger will immediately crash into negative balance constraint errors or duplicate physical usage.
5. **Governance Resolution Path:** Under **DEC-002 Scenario A**, the corrupted July ledger is retired. A certified physical stocktake is conducted as of 12-Oct-2026. True weighbridge quantities become the opening balance, while furnace charges are segregated from store issues under Phase 5 Rule H1.

---

### 2.2 Exception Class 2: Missing Commercial Purchase Rates & Zero Rates

#### Forensic Root-Cause Findings:
1. **Total Absence of Unit Rates in Item Master:** In `VSPL_Item_Master.xlsx`, Column K (`Rate (INR)`) is `None` across **all 391 canonical items**.
2. **Missing Rate Columns in Historical GRNs:** In `VSPL_Material_Entry.xlsx` sheet `3. Receipt GRN`, rows 2, 3, 4, and 5 have no commercial rate column or recorded purchase prices.
3. **Violation of Costing Engine Prerequisites:** Under Phase 6 Rule C1, inventory valuation and melting costs are computed on a **Moving Weighted Average** basis:
   $$\text{New Average Rate} = \frac{(\text{Current Qty} \times \text{Current Rate}) + (\text{Received Qty} \times \text{Invoice Unit Rate})}{\text{Current Qty} + \text{Received Qty}}$$
   Without invoice rates, the denominator updates while the numerator gains zero value, resulting in zero-valued inventory and zero-cost castings.
4. **Governance Resolution Path:** Finance Head and Purchase Head must audit original supplier tax invoices and approved purchase orders. All 407 items in Worksheet C (`C. Valuation Register`) are set to `EXPLICITLY_UNVALUED` until verified invoice rates are physically entered and signed off.

---

### 2.3 Exception Class 3: Candidate Unmapped Items & Chemical Ambiguity

#### Forensic Root-Cause Findings:
1. **MNT-CN-001 (3306PMKT-Generator):**
   - Source: Receipt GRN Row 3 records 1 Set received from vendor *sreenathji* on PO `300426-10`, Invoice `GMP2926002828`.
   - Issue: Item does not exist in canonical `VSPL_Item_Master.xlsx`. Exists only in `2. New Items` Row 5.
   - Path: Authorize creation of `MNT-CN-001` in Item Master via Phase 2 workflow; verify ex-GST invoice rate from Purchase.
2. **MCS-CN-002 (Tool Post):**
   - Source: Receipt GRN Row 4 records 4 Nos received on PO `070726-11`, Invoice `454`.
   - Issue: Missing date, vendor, rate. Item missing from Item Master; exists in `2. New Items` Row 6. Legacy code CON252 was a bolt, not a tool post.
   - Path: Authorize creation of `MCS-CN-002`; corroborate physical PO hardcopy; audit tooling crib stock.
3. **Chemical Ambiguity of `crca scrap` (15,200 kg):**
   - Source: Receipt GRN Row 5 records 15,200 kg received on PO `140726-02`, Invoice `384`. Missing date, vendor, rate.
   - Issue: Item Master distinguishes between `FDY-RM-007` (CRC Scrap-Low High MN, Mn 0.35–0.50%) and `FDY-RM-008` (CRC Scrap-Low MN, Mn 0.15–0.25%).
   - Risk: Manganese is a critical pearlitic stabilizer in ductile iron. Misclassifying scrap causes erratic magnesium recovery, carbide formation, or elongation failures.
   - Path: Foundry Metallurgist takes spectrometer coupons from scrap yard to classify true chemical grade before opening balance creation.

---

### 2.4 Exception Class 4: Issue Date Typo (`7-16-20236` across Rows 537–548)

#### Forensic Root-Cause Findings:
1. **The Typo:** In `VSPL_Material_Entry.xlsx` sheet `4. Issue`, twelve rows (rows 537 through 548) contain the string date value `'7-16-20236'`.
2. **Sequential Context:** Preceding rows 535–536 are dated `2026-07-15`. Subsequent row 549 is dated `2026-07-15`. The twelve rows cover physical store issue slips 327, 910, 325, 1149, 326, 2725, and 1148.
3. **Hypothesis vs Verified Fact:** While the contextual evidence that this was a typo for `2026-07-16` is overwhelming, the immutable audit rule states that source files must never be silently edited.
4. **Governance Resolution Path:** Stores Manager must inspect the hardcopy issue slips in the physical store archives, confirm the slip dates, and formally sign off on the date normalization register under **DEC-004**.

---

### 2.5 Exception Class 5: Template Sample Rows (Row 2 Contamination)

#### Forensic Root-Cause Findings:
1. **The Contamination:** In `VSPL_Material_Entry.xlsx`, row 2 across Receipt GRN, Issue, and Waste sheets contains test/sample data for `FDY-CN-003` (Emery Paper):
   - Receipt: +25 kg (GRN 2599, MM Tools, PO 110726-02).
   - Issue: -2 kg (Slip 999).
   - Waste: -5 kg (Note 999).
   - Net closing balance in Master Ledger: **18 kg**.
2. **Evidence in Read Me:** The workbook `Read Me` sheet explicitly warns: *"Row 2 of each sheet is a sample entry — overwrite it or delete it before real use."*
3. **Legacy Collision:** Legacy `Store Inventory.xlsx` row 4 lists GRN 2599 as "Cement empty 1000 bags from s.srinivas", proving the entry was synthetic test data.
4. **Governance Resolution Path:** Formally approve purging Row 2 records from the operational migration manifest under **DEC-006**. Conduct a clean physical count of Emery Paper during the stocktake.

---

### 2.6 Exception Class 6: Furnace Heat Log Integrity Deficit (18 Heats with 0 Charge)

#### Forensic Root-Cause Findings:
1. **Zero Charge Deficit:** In `VSPL_Foundry_Heat_Log.xlsx`, 18 of the 19 heats logged on `2026-07-22` (`072613-2092` to `2110`) record **Total Charge = 0 kg**.
2. **Physical Impossibility:** These 18 heats report liquid metal tapped between 504 kg and 524 kg, generating an impossible negative melt loss (-100% to -125%).
3. **Charge Details Sheet Missing:** `Charge Details` contains only 10 rows across the entire workbook. Only 1 row belongs to a logged heat.
4. **Governance Resolution Path:** Under **DEC-007**, all furnace heat log records are quarantined in staging preview. Live production tables will not be populated until the Foundry Head retrieves physical paper heat sheets from the melt deck.

---

### 2.7 Exception Class 7: Future-Dated Legacy Receipts (2026-11-07)

#### Forensic Root-Cause Findings:
1. **The Future Timestamp:** In `Store Inventory.xlsx` sheet `Material Receipt`, 113 rows (rows 9 through 121) contain the stored date `datetime(2026, 11, 7, 0, 0)`—nearly one month in the future relative to the October cutoff.
2. **Physical Stock Nature:** All 113 rows list `Supplier Name = 'Physical stock'`. They represent internal count estimates, not vendor delivery dockets.
3. **Hypothesis vs Strict Audit:** While the date is likely an Indian date entry inversion (`11-Jul-2026` entered into US-formatted Excel), treating them as vendor receipts would corrupt both ledger chronology and vendor AP balances.
4. **Governance Resolution Path:** Formally retire `Store Inventory.xlsx` from operational data migration under **DEC-008**. The workbook remains an immutable read-only historical archive.

---

## 3. Governance Resolution Matrix

```
+--------------------------------+----------------------------+-----------------------------+-------------------------------+
| Exception Category             | Accountable Lead           | Required Primary Evidence   | Target Live Action            |
+--------------------------------+----------------------------+-----------------------------+-------------------------------+
| 7 Negative Raw Materials       | Plant Head / Auditor       | Cutoff Physical Stock Count | Opening Balance via Sheet D   |
| Missing Commercial Rates       | Finance Head               | Audited Vendor Tax Invoices | Moving Avg Base in Sheet C    |
| Unmapped Items & Scrap Grade   | Metallurgist / Stores Mgr  | Lab Spectrometry Analysis   | Item Master Creation (Phase 2)|
| Issue Date Typo (Rows 537-548) | Stores Manager             | Physical Hardcopy Slips     | Certified Date Normalization  |
| Sample Template Row 2          | Lead Systems Architect     | Read Me Explicit Directive  | Staging Manifest Purge        |
| Incomplete Furnace Heats       | Foundry Head               | Paper Heat Deck Log Sheets  | Staging Quarantine            |
| Future-Dated Legacy Receipts   | IT Head / Inventory Auditor| Forensic Date Audit         | Permanent Archive Exclusion   |
+--------------------------------+----------------------------+-----------------------------+-------------------------------+
```

### Authorization Boundary:
No transaction or balance derived from these exceptions may be entered into the PostgreSQL database until formal sign-off on `VSPL_Physical_Stocktake_Register.xlsx` is completed and approved by the Managing Director.
