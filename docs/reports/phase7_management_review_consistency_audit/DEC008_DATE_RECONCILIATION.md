# VSPL Material Management & Costing System — DEC-008 Legacy Receipt Date Reconciliation

**Audit Scope:** Deep Source Verification of DEC-008 Legacy Store Inventory Date & Receipt Counts  
**Date:** 2026-10-13  
**Status:** **AUDIT VERIFIED — SOURCE CONTEXT DOCUMENTED**  

---

## 1. Executive Summary & Verification Findings

The management review documentation references:
> *"Old data Frm08 on Silicon and 113 physical receipts 2026-11-07."*

This deep audit independently inspected the frozen legacy workbook:
- **File:** `C:\VSPL_MM\_legacy_archive\Store Inventory.xlsx` (and frozen counterpart in freeze package)
- **Worksheet:** `Material Receipt`
- **Result:** **All 113 rows verified directly at the cell level.**

---

## 2. Source-Level Cell Coordinates & Data Representation

### 2.1 The Exact Cell Range:
- **Worksheet:** `Material Receipt`
- **Physical Rows:** Exactly **Row 9 through Row 121 (113 consecutive rows)**.
- **Date Column:** Column A (`Timestamp` / `Date`).
- **Exact Cell Range:** `A9` through `A121`.

### 2.2 Stored Value vs Displayed Value:
- **Underlying Python / openpyxl Stored Value:** `datetime.datetime(2026, 11, 7, 0, 0)`
- **Openpyxl Cell Data Type:** `'d'` (Date object)
- **Cell Number Format:** `mm/dd/yyyy`
- **Spreadsheet Displayed String:** `11/07/2026` (or `2026-11-07 00:00:00` depending on Excel regional locale).

---

## 3. The Date Ambiguity: 7 November 2026 vs 11 July 2026

### 3.1 Chronological Anomaly:
- The system live costing start date is **12 October 2026**.
- The current audit date is **13 October 2026**.
- If taken literally, `2026-11-07` represents **7 November 2026** — a date nearly **one month in the future** relative to the operational audit date!

### 3.2 Contextual Evidence for Transposition (Day/Month Swap):
1. **Preceding Operational Dates:**
   - Rows 2 through 8 in the same sheet contain explicit timestamps spanning **08-Jul-2026 to 14-Jul-2026**:
     - Row 2: `2026-07-08 10:11:55.517000` (Physical stock Crc)
     - Row 3: `2026-07-09 09:26:35.274000` (Pre Coated Sand)
     - Row 4: `2026-07-09 13:44:55.875000` (Cement empty)
     - Row 5: `2026-07-11 17:07:51.328000` (Grinding Wheel 7 Inch)
     - Row 6: `2026-07-13 16:41:44.682000` (Hand gloves)
     - Row 7: `2026-07-13 17:11:29.762000` (Cast innoculant)
     - Row 8: `2026-07-14 09:33:52.014000` (Holcoat 100)
2. **The 11-Jul-2026 Insertion:**
   - On 11-Jul-2026, store keepers entered Row 5 (`Grinding Wheel 7 Inch`).
   - If an Indian date format (`DD/MM/YYYY`) was typed as `11/07/2026` into an Excel sheet formatted with US locale (`MM/DD/YYYY`), Excel silently parses it as **November 7, 2026**.
   - Chronologically, taking physical stock on **11-Jul-2026 (Saturday)** fits the plant's weekend stocktake schedule.
3. **Audit Stance:**
   - While `11-Jul-2026` is a compelling metallurgical and operational hypothesis, **it is an interpretation, not an established fact**.
   - The literal stored byte value is `2026-11-07`. Under strict audit standards, the date must remain classified as **AMBIGUOUS / FUTURE DATE** pending written IT/Stores sign-off.

---

## 4. Verification of the "113 Physical Receipts" Count

### 4.1 Row Breakdown in Worksheet `Material Receipt`:
- **Total Rows in Sheet:** 123 rows (Row 1 header + 122 data rows).
- **Vendor Name for Rows 9 to 121:** Exactly **100% of these 113 rows contain the string `'Physical stock'` in Column B (`Supplier Name`)**.
- **Nature of the Records:** These are **NOT vendor purchase deliveries**. They are plant-wide physical stock audit entries keyed into the receipt sheet to establish initial balances in the legacy workbook.
- **The Remaining 9 Rows in `Material Receipt`:**
  - Row 2: Physical stock `Crc` (Qty `None`, Date `2026-07-08`)
  - Row 3: Physical stock `Pre Coated Sand` (Qty `10300.0`, Date `2026-07-09`)
  - Rows 4–8: Actual vendor receipts from `s.srinivas`, `MM Tools`, `Kiran hand gloves`, `Shreenathji`, and `Aldan industries` (5 vendor deliveries).
  - Rows 122–123: `Magnesium` (550 kg) and `Manganese` (20 kg) with **completely blank dates and blank vendors**.

### 4.2 Exact Reproducibility:
- $121 - 9 + 1 = \mathbf{113\text{ rows}}$.
- All 113 rows share:
  - Date = `2026-11-07 00:00:00`
  - Supplier = `Physical stock`
  - Valid item code and positive physical quantity.
- The 113-receipt count is **100% verified and reproducible**.

---

## 5. Audit Conclusion & Wording Recommendation for DEC-008

1. **Clarification in Executive Narrative:**
   - In DEC-008, the phrase *"113 physical receipts dated 2026-11-07"* should be clarified as *"113 legacy physical stock count entries recorded in the receipt sheet dated 2026-11-07"*.
2. **Exclusion Recommendation Reaffirmed:**
   - Ingesting these 113 rows into the live system would post inventory receipts dated November 2026 (in the future), directly corrupting live balances as of October 2026.
   - The recommendation to **permanently exclude `Store Inventory.xlsx` from operational migration** remains 100% sound.
