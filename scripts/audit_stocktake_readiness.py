"""
VSPL Material Management & Costing System — Stocktake Readiness QA Audit Script
Executes deep read-only inspection of:
  - docs/reports/phase7_stocktake_preparation/VSPL_Physical_Stocktake_Register.xlsx
  - Companion protocol and exception registers
  - Source data files and management decision status
"""

import os
import csv
import openpyxl
from collections import Counter

BASE_DIR = r"C:\VSPL_MM\Material managment system"
WB_PATH = os.path.join(BASE_DIR, r"docs\reports\phase7_stocktake_preparation\VSPL_Physical_Stocktake_Register.xlsx")
DATA_INPUTS = r"C:\VSPL_MM\VSPL_MM_Data\inputs"
DATA_LEDGER = r"C:\VSPL_MM\VSPL_MM_Data\ledger"
LEGACY_DIR = r"C:\VSPL_MM\_legacy_archive"

def run_audit():
    print("="*70)
    print("VSPL PHYSICAL STOCKTAKE READINESS QA AUDIT")
    print("="*70)
    
    assert os.path.exists(WB_PATH), "Workbook does not exist!"
    wb = openpyxl.load_workbook(WB_PATH, data_only=False)
    
    # 1. Sheets and Protection
    print("\n[CHECK 1] Sheet Structure & Protection")
    for name in wb.sheetnames:
        ws = wb[name]
        is_protected = ws.protection.sheet if ws.protection else False
        print(f"  Sheet: '{name}' | Protection: {is_protected} | Dimensions: {ws.dimensions} | Max Row: {ws.max_row}")
        
    # 2. Double-Blind Analysis on Sheet A
    ws_a = wb['A. Stocktake Register']
    print("\n[CHECK 2] Double-Blind Counting Feasibility on Sheet A")
    book_col_dim = ws_a.column_dimensions['E']
    print(f"  Col E (Book Qty) Width: {book_col_dim.width}, Hidden: {book_col_dim.hidden}")
    print(f"  Col F (Counted Qty) Width: {ws_a.column_dimensions['F'].width}, Hidden: {ws_a.column_dimensions['F'].hidden}")
    populated_book_cells = [(r, ws_a.cell(r, 1).value, ws_a.cell(r, 5).value) 
                            for r in range(6, ws_a.max_row + 1) if ws_a.cell(r, 5).value is not None]
    print(f"  Total items with visible Book Qty: {len(populated_book_cells)}")
    for r, code, val in populated_book_cells:
        print(f"    Row {r}: {code} -> Book Qty = {val}")

    # 3. Formula Integrity
    print("\n[CHECK 3] Formula Integrity & Syntax")
    formula_errors_a = []
    for r in range(6, ws_a.max_row + 1):
        f = ws_a.cell(r, 11).value
        expected = f'=IF(ISBLANK(F{r}),"",IF(ISNUMBER(E{r}),F{r}-E{r},"PENDING_BOOK_QTY"))'
        if f != expected:
            formula_errors_a.append((r, f, expected))
    print(f"  Sheet A Col K (Variance): {ws_a.max_row - 5} rows, {len(formula_errors_a)} formula discrepancies")
    
    ws_b = wb['B. Variance Investigation']
    formula_errors_b = []
    for r in range(6, ws_b.max_row + 1):
        f = ws_b.cell(r, 4).value
        expected = f'=IF(ISBLANK(C{r}),"",IF(ISNUMBER(B{r}),C{r}-B{r},""))'
        if f != expected:
            formula_errors_b.append((r, f, expected))
    print(f"  Sheet B Col D (Variance): {ws_b.max_row - 5} rows, {len(formula_errors_b)} formula discrepancies")
    
    col_c_b_vals = [ws_b.cell(r, 3).value for r in range(6, ws_b.max_row + 1)]
    print(f"  Sheet B Col C (Counted Qty): Values present: {[v for v in col_c_b_vals if v is not None]}")
    
    ws_c = wb['C. Valuation Register']
    formula_errors_c = []
    for r in range(6, ws_c.max_row + 1):
        f = ws_c.cell(r, 8).value
        expected = f'=IF(OR(ISBLANK(E{r}),ISBLANK(\'A. Stocktake Register\'!F{r})),"",\'A. Stocktake Register\'!F{r}*E{r})'
        if f != expected:
            formula_errors_c.append((r, f, expected))
    print(f"  Sheet C Col H (Extended Value): {ws_c.max_row - 5} rows, {len(formula_errors_c)} formula discrepancies")

    ws_d = wb['D. Opening Inventory Approval']
    formula_errors_d = []
    for r in range(6, ws_d.max_row + 1):
        f_d = ws_d.cell(r, 4).value
        f_e = ws_d.cell(r, 5).value
        exp_d = f'=IF(ISBLANK(\'A. Stocktake Register\'!F{r}),"",\'A. Stocktake Register\'!F{r})'
        exp_e = f'=IF(ISBLANK(\'C. Valuation Register\'!H{r}),"",\'C. Valuation Register\'!H{r})'
        if f_d != exp_d:
            formula_errors_d.append((r, 'Col D', f_d, exp_d))
        if f_e != exp_e:
            formula_errors_d.append((r, 'Col E', f_e, exp_e))
    print(f"  Sheet D Col D/E: {ws_d.max_row - 5} rows, {len(formula_errors_d)} formula discrepancies")

    # 4. Item Segregation & Candidate Items
    print("\n[CHECK 4] Item Segregation & Canonical vs Candidate Identification")
    candidate_items = []
    for r in range(6, ws_a.max_row + 1):
        status = ws_a.cell(r, 12).value
        code = ws_a.cell(r, 1).value
        desc = ws_a.cell(r, 2).value
        uom = ws_a.cell(r, 4).value
        if status == 'PENDING_MASTER_CREATION':
            candidate_items.append((r, code, desc, uom))
    print(f"  Total candidate items in Sheet A: {len(candidate_items)} (Rows 397 to 412)")

    # 5. Duplicate Analysis
    print("\n[CHECK 5] Duplicate Codes, Descriptions, and Candidate Clashes")
    codes = [ws_a.cell(r, 1).value for r in range(6, ws_a.max_row + 1)]
    code_dups = [item for item, count in Counter(codes).items() if count > 1]
    print(f"  Duplicate Item Codes: {code_dups}")
    
    descs = [str(ws_a.cell(r, 2).value).strip().lower() for r in range(6, ws_a.max_row + 1)]
    desc_dups = {item: count for item, count in Counter(descs).items() if count > 1}
    print(f"  Duplicate Descriptions count: {len(desc_dups)}")
    for d, c in sorted(desc_dups.items(), key=lambda x: -x[1]):
        matches = [ws_a.cell(r, 1).value for r in range(6, ws_a.max_row + 1) if str(ws_a.cell(r, 2).value).strip().lower() == d]
        print(f"    '{d}' ({c}x): {matches}")

    # 6. UOM Integrity
    print("\n[CHECK 6] UOM Integrity & Non-standard Units")
    uoms = [ws_a.cell(r, 4).value for r in range(6, ws_a.max_row + 1)]
    uom_dist = Counter(uoms)
    print(f"  UOM Distribution: {dict(uom_dist)}")
    canonical_uoms = {'Kg', 'Nos', 'Ltr', 'Pack'}
    non_canonical = {u: c for u, c in uom_dist.items() if u not in canonical_uoms}
    print(f"  Non-canonical UOMs detected: {non_canonical}")

    # 7. Approvals & Audit Trail
    print("\n[CHECK 7] Approval Columns & Audit Trail Verification")
    populated_approvals_a = sum(1 for r in range(6, ws_a.max_row + 1) if ws_a.cell(r, 14).value is not None)
    populated_approvals_b = sum(1 for r in range(6, ws_b.max_row + 1) if ws_b.cell(r, 9).value is not None)
    populated_approvals_c = sum(1 for r in range(6, ws_c.max_row + 1) if ws_c.cell(r, 9).value is not None)
    populated_approvals_d = sum(1 for r in range(6, ws_d.max_row + 1) for col in [9, 10, 11, 12] if ws_d.cell(r, col).value is not None)
    print(f"  Sheet A Approvals Populated: {populated_approvals_a}")
    print(f"  Sheet B Approvals Populated: {populated_approvals_b}")
    print(f"  Sheet C Approvals Populated: {populated_approvals_c}")
    print(f"  Sheet D Approvals Populated: {populated_approvals_d} (Cols 9, 10, 11, 12 across 407 rows)")

    # 8. Legacy Store Inventory Check
    print("\n[CHECK 8] Legacy Archive Check: Store Inventory.xlsx")
    legacy_receipt_path = os.path.join(LEGACY_DIR, "Store Inventory.xlsx")
    if os.path.exists(legacy_receipt_path):
        wb_leg = openpyxl.load_workbook(legacy_receipt_path, data_only=True)
        ws_mr = wb_leg['Material Receipt']
        future_dated_count = 0
        phys_stock_count = 0
        for r in range(2, ws_mr.max_row + 1):
            dt = ws_mr.cell(r, 1).value
            sup = str(ws_mr.cell(r, 2).value).strip()
            if sup.lower() == 'physical stock':
                phys_stock_count += 1
            if str(dt).startswith('2026-11-07'):
                future_dated_count += 1
        print(f"  Material Receipt: {phys_stock_count} rows with Supplier='Physical stock'")
        print(f"  Material Receipt: {future_dated_count} rows with Timestamp=2026-11-07")

    # 9. Governance & Management Approvals Check
    print("\n[CHECK 9] Governance Check: Decision Status for DEC-001 through DEC-008")
    signoff_csv = os.path.join(BASE_DIR, r"docs\reports\phase7_management_signoff\MANAGEMENT_DECISION_REGISTER.csv")
    if os.path.exists(signoff_csv):
        with open(signoff_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                print(f"  {row['Issue ID']}: Current Status = '{row['Current Status']}' | Approval Status = '{row['Approval Status']}' | Approver = '{row['Approver']}'")

if __name__ == "__main__":
    run_audit()
