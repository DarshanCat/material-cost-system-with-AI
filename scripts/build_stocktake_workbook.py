"""
VSPL Material Management & Costing System — Physical Stocktake Workbook Builder
Phase 7 Stocktake Preparation

Generates:
  docs/reports/phase7_stocktake_preparation/VSPL_Physical_Stocktake_Register.xlsx

Worksheets:
  A. Stocktake Register (391 canonical items + 16 candidate new items)
  B. Variance Investigation (20 pre-populated historical exception records)
  C. Valuation Register (Rule C1 compliance — explicitly unvalued)
  D. Opening Inventory Approval (Formal 3-way sign-off gate, all approvals blank)
"""

import os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Define paths
BASE_DIR = r"C:\VSPL_MM\Material managment system"
DATA_INPUTS = r"C:\VSPL_MM\VSPL_MM_Data\inputs"
DATA_LEDGER = r"C:\VSPL_MM\VSPL_MM_Data\ledger"
OUTPUT_DIR = os.path.join(BASE_DIR, r"docs\reports\phase7_stocktake_preparation")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "VSPL_Physical_Stocktake_Register.xlsx")

def load_canonical_items():
    item_master_path = os.path.join(DATA_INPUTS, "VSPL_Item_Master.xlsx")
    wb = openpyxl.load_workbook(item_master_path, data_only=True)
    ws = wb["Item Master"]
    
    items = []
    for r in range(2, ws.max_row + 1):
        code = ws.cell(r, 1).value
        if not code:
            continue
        code = str(code).strip()
        items.append({
            "code": code,
            "desc": ws.cell(r, 2).value or "",
            "category": ws.cell(r, 3).value or "",
            "dept": ws.cell(r, 5).value or "",
            "uom": ws.cell(r, 6).value or "",
            "bin": ws.cell(r, 8).value or "MAIN_STORE",
            "legacy": ws.cell(r, 12).value or "",
            "is_candidate": False
        })
    return items

def load_candidate_items():
    entry_path = os.path.join(DATA_INPUTS, "VSPL_Material_Entry.xlsx")
    wb = openpyxl.load_workbook(entry_path, data_only=True)
    if "2. New Items" not in wb.sheetnames:
        return []
    ws = wb["2. New Items"]
    
    candidates = []
    for r in range(2, ws.max_row + 1):
        code = ws.cell(r, 3).value
        if not code:
            continue
        code = str(code).strip()
        candidates.append({
            "code": code,
            "desc": ws.cell(r, 5).value or "",
            "category": ws.cell(r, 2).value or "Consumables",
            "dept": ws.cell(r, 1).value or "",
            "uom": ws.cell(r, 6).value or "Nos",
            "bin": ws.cell(r, 8).value or "STORE_NEW_ITEMS",
            "legacy": "NEW_PROPOSAL",
            "is_candidate": True
        })
    return candidates

def load_ledger_balances():
    ledger_path = os.path.join(DATA_LEDGER, "VSPL_Master_Ledger.xlsx")
    wb = openpyxl.load_workbook(ledger_path, data_only=True)
    ws = wb["Ledger"]
    
    balances = {}
    for r in range(2, ws.max_row + 1):
        code = ws.cell(r, 1).value
        if not code:
            continue
        code = str(code).strip()
        balances[code] = {
            "op": ws.cell(r, 7).value,
            "rec": ws.cell(r, 8).value,
            "iss": ws.cell(r, 9).value,
            "wst": ws.cell(r, 10).value,
            "cls": ws.cell(r, 11).value
        }
    return balances

def build_workbook():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    items = load_canonical_items()
    candidates = load_candidate_items()
    all_items = items + candidates
    ledger_balances = load_ledger_balances()
    
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)
    
    # Visual Styles
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="1F4E78")
    subtitle_font = Font(name="Calibri", size=10, italic=True, color="595959")
    warning_font = Font(name="Calibri", size=10, bold=True, color="C00000")
    bold_font = Font(name="Calibri", size=10, bold=True)
    regular_font = Font(name="Calibri", size=10)
    
    primary_header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    secondary_header_fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    accent_header_fill = PatternFill(start_color="333f48", end_color="333f48", fill_type="solid")
    candidate_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    exception_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
    
    thin_border_side = Side(border_style="thin", color="D9D9D9")
    cell_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    thick_bottom_side = Side(border_style="medium", color="1F4E78")
    header_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thick_bottom_side)

    known_exceptions = {
        "FDY-RM-008": "DEC-005: Interim Ledger Cls -500 kg; Heat H-260714-01 charge without opening; Omitted issues 11,793 kg; Receipt GRN Row 5 (15,200 kg) unposted",
        "FDY-RM-011": "DEC-005: Interim Ledger Cls -300 kg; Heat H-260714-01 gating returns charged without return movement",
        "FDY-RM-014": "DEC-005: Interim Ledger Cls -2 kg; Heat H-260714-01 charge without opening; Legacy receipt 92.5 kg dated 2026-11-07",
        "FDY-RM-016": "DEC-005: Interim Ledger Cls -15 kg; Heat H-260714-01 charge without opening; Legacy undated receipt 550 kg",
        "FDY-RM-017": "DEC-005: Interim Ledger Cls -3 kg; Heat H-260714-01 charge without opening; Omitted issues 278.509 kg; Legacy undated receipt 20 kg",
        "FDY-RM-019": "DEC-005: Interim Ledger Cls -150 kg; Heat H-260714-01 charge without opening; Purchase receipts unposted",
        "FDY-RM-020": "DEC-005: Interim Ledger Cls -5 kg; Heat H-260714-01 charge without opening; Omitted issues 50.218 kg; Legacy receipt 26 kg dated 2026-11-07",
        "FDY-CN-003": "DEC-006: Interim Ledger Cls 18 kg; Distorted by sample template row 2 in GRN (+25), Issue (-2), Waste (-5); Legacy conflict with cement bags"
    }

    # =========================================================================
    # WORKSHEET A: Stocktake Register
    # =========================================================================
    ws_a = wb.create_sheet(title="A. Stocktake Register")
    ws_a.views.sheetView[0].showGridLines = True
    
    ws_a["A1"] = "VIJAY SPHEROIDALS PVT. LTD. — PHYSICAL STOCKTAKE REGISTER"
    ws_a["A1"].font = title_font
    ws_a["A2"] = "CUTOFF DATE: 12-OCT-2026 23:59:59 | GOVERNANCE STATUS: CONTROLLED AUDIT PREPARATION — ZERO APPLICATION POSTINGS"
    ws_a["A2"].font = subtitle_font
    ws_a["A3"] = "CRITICAL INSTRUCTION: Enter Physical Counted Qty (Col F) during double-blind count. Never assume July interim balances represent October inventory."
    ws_a["A3"].font = warning_font
    
    headers_a = [
        ("Canonical Item Code", 22),
        ("Item Description", 38),
        ("Item Category", 20),
        ("Base UOM", 12),
        ("Source-Supported Book Qty", 26),
        ("Physical Counted Qty", 22),
        ("Count Date & Time", 20),
        ("Storage Location", 22),
        ("Counter Name & Sign", 22),
        ("Independent Verifier", 22),
        ("Quantity Variance", 20),
        ("Investigation Status", 28),
        ("Evidence Reference", 50),
        ("Approval Status", 18)
    ]
    
    row_idx = 5
    for col_idx, (header_text, col_width) in enumerate(headers_a, start=1):
        cell = ws_a.cell(row=row_idx, column=col_idx, value=header_text)
        cell.font = header_font
        cell.fill = primary_header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = header_border
        ws_a.column_dimensions[get_column_letter(col_idx)].width = col_width
    ws_a.row_dimensions[row_idx].height = 28
    
    data_start_row_a = 6
    for i, item in enumerate(all_items):
        r = data_start_row_a + i
        code = item["code"]
        
        ws_a.cell(row=r, column=1, value=code).alignment = Alignment(horizontal="center")
        ws_a.cell(row=r, column=2, value=item["desc"]).alignment = Alignment(horizontal="left")
        ws_a.cell(row=r, column=3, value=item["category"]).alignment = Alignment(horizontal="left")
        ws_a.cell(row=r, column=4, value=item["uom"]).alignment = Alignment(horizontal="center")
        
        # Source-supported book quantity:
        # Only populate if recorded in interim ledger, otherwise blank (82-day void makes 0 indefensible)
        book_qty = None
        evid_ref = ""
        inv_status = "PENDING_PHYSICAL_COUNT"
        
        if code in known_exceptions:
            led_info = ledger_balances.get(code, {})
            book_qty = led_info.get("cls")
            evid_ref = known_exceptions[code]
            inv_status = "PENDING_INVESTIGATION (EXCEPTION)"
        elif item["is_candidate"]:
            evid_ref = f"DEC-003: Candidate new item from '2. New Items'; UOM={item['uom']}; Requires Item Master creation"
            inv_status = "PENDING_MASTER_CREATION"
        else:
            evid_ref = "UNKNOWN (82-DAY OPERATIONAL VOID: 22-Jul to 12-Oct-2026; Physical count mandatory)"
            
        cell_book = ws_a.cell(row=r, column=5, value=book_qty)
        if book_qty is not None:
            cell_book.number_format = "#,##0.000" if item["uom"] == "Kg" else "#,##0"
            cell_book.alignment = Alignment(horizontal="right")
        else:
            cell_book.alignment = Alignment(horizontal="center")
            
        # Physical counted qty (Col F) - Blank
        cell_count = ws_a.cell(row=r, column=6, value=None)
        cell_count.number_format = "#,##0.000" if item["uom"] == "Kg" else "#,##0"
        cell_count.alignment = Alignment(horizontal="right")
        
        # Count Date & Time (Col G) - Blank
        ws_a.cell(row=r, column=7, value=None).alignment = Alignment(horizontal="center")
        
        # Storage Location (Col H)
        ws_a.cell(row=r, column=8, value=item["bin"]).alignment = Alignment(horizontal="center")
        
        # Counter (Col I) & Verifier (Col J) - Blank
        ws_a.cell(row=r, column=9, value=None).alignment = Alignment(horizontal="center")
        ws_a.cell(row=r, column=10, value=None).alignment = Alignment(horizontal="center")
        
        # Variance Formula (Col K): Counted Qty (F) - Book Qty (E)
        cell_var = ws_a.cell(row=r, column=11)
        cell_var.value = f'=IF(ISBLANK(F{r}),"",IF(ISNUMBER(E{r}),F{r}-E{r},"PENDING_BOOK_QTY"))'
        cell_var.alignment = Alignment(horizontal="right")
        cell_var.number_format = "#,##0.000" if item["uom"] == "Kg" else "#,##0"
        
        # Status (Col L) & Evidence (Col M)
        cell_status = ws_a.cell(row=r, column=12, value=inv_status)
        cell_status.alignment = Alignment(horizontal="center")
        
        cell_evid = ws_a.cell(row=r, column=13, value=evid_ref)
        cell_evid.alignment = Alignment(horizontal="left")
        
        # Approval Status (Col N) - Blank
        ws_a.cell(row=r, column=14, value=None).alignment = Alignment(horizontal="center")
        
        # Cell borders & row fills
        for c in range(1, 15):
            ws_a.cell(row=r, column=c).font = regular_font
            ws_a.cell(row=r, column=c).border = cell_border
            if item["is_candidate"]:
                ws_a.cell(row=r, column=c).fill = candidate_fill
            elif code in known_exceptions:
                ws_a.cell(row=r, column=c).fill = exception_fill

    ws_a.freeze_panes = "A6"

    # =========================================================================
    # WORKSHEET B: Variance Investigation
    # =========================================================================
    ws_b = wb.create_sheet(title="B. Variance Investigation")
    ws_b.views.sheetView[0].showGridLines = True
    
    ws_b["A1"] = "VIJAY SPHEROIDALS PVT. LTD. — STOCK VARIANCE & HISTORICAL EXCEPTION INVESTIGATION"
    ws_b["A1"].font = title_font
    ws_b["A2"] = "OBJECTIVE: FORMAL ROOT CAUSE ANALYSIS & PROPOSED CORRECTIVE ACTIONS — AUTOMATED RESOLUTION STRICTLY PROHIBITED"
    ws_b["A2"].font = subtitle_font
    ws_b["A3"] = "MANDATE: Every variance exceeding ±1% or involving negative balances, unmapped codes, or missing rates requires an approved corrective proposal."
    ws_b["A3"].font = warning_font
    
    headers_b = [
        ("Exception ID / Item Code", 25),
        ("Book Qty", 16),
        ("Counted Qty", 16),
        ("Variance", 16),
        ("Possible Cause (Clearly Marked Hypothesis)", 48),
        ("Supporting Evidence", 48),
        ("Investigation Owner", 24),
        ("Corrective Action Proposal", 45),
        ("Approval Status", 18)
    ]
    
    row_idx = 5
    for col_idx, (header_text, col_width) in enumerate(headers_b, start=1):
        cell = ws_b.cell(row=row_idx, column=col_idx, value=header_text)
        cell.font = header_font
        cell.fill = secondary_header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = header_border
        ws_b.column_dimensions[get_column_letter(col_idx)].width = col_width
    ws_b.row_dimensions[row_idx].height = 28

    exceptions_list = [
        {
            "code": "FDY-RM-008",
            "book": -500.0,
            "cause": "HYPOTHESIS: Furnace heat charge H-260714-01 (500 kg) deducted directly as store issue with zero opening balance recorded in interim ledger. Furthermore, 15,200 kg inward delivery on GRN Row 5 unposted, and 11,793 kg store issues omitted.",
            "evidence": "VSPL_Master_Ledger.xlsx (Row 9, Cls=-500); VSPL_Foundry_Heat_Log.xlsx (Charge H-260714-01); VSPL_Material_Entry.xlsx (Issue total=11,793 kg; GRN row 5=15,200 kg)",
            "owner": "Plant Head & Stores Manager",
            "action": "Conduct weighbridge physical stock count on cutoff date. Audit commercial invoice 384. Resolve metallurgical grade (Low MN vs Low High MN)."
        },
        {
            "code": "FDY-RM-011",
            "book": -300.0,
            "cause": "HYPOTHESIS: 300 kg foundry return runners/risers (gatings) charged into furnace H-260714-01 without recording prior foundry return receipt or establishing opening balance.",
            "evidence": "VSPL_Master_Ledger.xlsx (Row 12, Cls=-300); VSPL_Foundry_Heat_Log.xlsx (Charge Details Row 3)",
            "owner": "Foundry Head & Metallurgist",
            "action": "Physical stock count of foundry return gating yard. Establish opening balance of gating returns; configure foundry return movement workflow in live ERP."
        },
        {
            "code": "FDY-RM-014",
            "book": -2.0,
            "cause": "HYPOTHESIS: Inoculant 15 (2 kg) charged into furnace H-260714-01 with zero recorded opening balance. Legacy archive holds 92.5 kg physical stock dated 2026-11-07.",
            "evidence": "VSPL_Master_Ledger.xlsx (Row 15, Cls=-2); Store Inventory.xlsx (Material Receipt Row 26, 92.5 kg)",
            "owner": "Stores Manager & Inventory Auditor",
            "action": "Physical count of inoculant drums in alloy room. Certify physical count as of 12-Oct-2026 cutoff; discard future-dated legacy receipt timestamp."
        },
        {
            "code": "FDY-RM-016",
            "book": -15.0,
            "cause": "HYPOTHESIS: Pure Magnesium (15 kg) charged into treatment ladle for heat H-260714-01 with zero opening balance. Legacy archive records 550 kg undated physical stock.",
            "evidence": "VSPL_Master_Ledger.xlsx (Row 17, Cls=-15); Store Inventory.xlsx (Material Receipt Row 122, 550 kg)",
            "owner": "Plant Head & Stores Manager",
            "action": "Physical weighment of pure magnesium ingots under strict security protocol. Reconcile against physical count on cutoff date."
        },
        {
            "code": "FDY-RM-017",
            "book": -3.0,
            "cause": "HYPOTHESIS: FeMn alloy (3 kg) charged into furnace H-260714-01 with zero opening balance. Interim ledger also omitted 278.509 kg of actual store issues. Legacy archive holds 20 kg undated stock.",
            "evidence": "VSPL_Master_Ledger.xlsx (Row 18, Cls=-3); VSPL_Material_Entry.xlsx (Issue sheet total=278.509 kg); Store Inventory.xlsx (Material Receipt Row 123)",
            "owner": "Stores Manager & Cost Accountant",
            "action": "Physical count of manganese alloy stock. Reconcile store issues vs furnace charges under Phase 5 Rule H1; establish certified cutoff balance."
        },
        {
            "code": "FDY-RM-019",
            "book": -150.0,
            "cause": "HYPOTHESIS: Foundry Pig Iron (150 kg) charged into furnace H-260714-01 without preceding purchase receipt or opening balance recorded.",
            "evidence": "VSPL_Master_Ledger.xlsx (Row 20, Cls=-150); VSPL_Foundry_Heat_Log.xlsx (Charge Details Row 2)",
            "owner": "Plant Head & Purchase Manager",
            "action": "Weighbridge physical stock count of pig iron raw material yard. Verify inward purchase invoices and certify true cutoff opening stock."
        },
        {
            "code": "FDY-RM-020",
            "book": -5.0,
            "cause": "HYPOTHESIS: FeSi alloy (5 kg) charged into furnace H-260714-01 with zero opening balance. Interim ledger omitted 50.218 kg of actual store issues. Legacy archive holds 26 kg dated 2026-11-07.",
            "evidence": "VSPL_Master_Ledger.xlsx (Row 21, Cls=-5); VSPL_Material_Entry.xlsx (Issue sheet total=50.218 kg); Store Inventory.xlsx (Material Receipt Row 27)",
            "owner": "Stores Manager & Inventory Auditor",
            "action": "Physical weighment of silicon alloy stock. Establish certified physical count as opening balance."
        },
        {
            "code": "FDY-CN-003",
            "book": 18.0,
            "cause": "HYPOTHESIS: Interim ledger closing stock of 18 kg is contaminated by template sample row 2 in GRN (+25), Issue (-2), and Waste (-5). Legacy conflict with cement bags.",
            "evidence": "VSPL_Master_Ledger.xlsx (Row 33, Cls=18); VSPL_Material_Entry.xlsx (Row 2 in sheets 3, 4, 5); DEC-006 register",
            "owner": "Stores Manager & QA Lead",
            "action": "Purge dummy template sample row 2 transactions from operational migration manifest per DEC-006. Perform physical count of Emery Paper."
        },
        {
            "code": "FDY-RM-008-OMISS",
            "book": 11793.0,
            "cause": "HYPOTHESIS: Interim master ledger omitted 11,793 kg of actual store issues recorded in VSPL_Material_Entry.xlsx sheet '4. Issue'. Omission occurred during manual spreadsheet collation.",
            "evidence": "VSPL_Material_Entry.xlsx ('4. Issue' sum=11,793 kg); VSPL_Master_Ledger.xlsx (Issued=0 kg); Frozen report negative_stock_reconciliation.csv",
            "owner": "Plant Head & Inventory Auditor",
            "action": "DO NOT repost omitted issues into live ledger. Replace corrupted historical ledger with 12-Oct-2026 certified physical stocktake per Scenario A (DEC-002/DEC-005)."
        },
        {
            "code": "FDY-RM-017-OMISS",
            "book": 278.509,
            "cause": "HYPOTHESIS: Interim master ledger omitted 278.509 kg of Manganese store issues from sheet '4. Issue'.",
            "evidence": "VSPL_Material_Entry.xlsx ('4. Issue' Manganese sum=278.509 kg); VSPL_Master_Ledger.xlsx (Issued=0 kg)",
            "owner": "Stores Manager & Cost Accountant",
            "action": "Include Manganese in physical stocktake protocol. Disregard interim ledger balance in favor of physical count."
        },
        {
            "code": "FDY-RM-020-OMISS",
            "book": 50.218,
            "cause": "HYPOTHESIS: Interim master ledger omitted 50.218 kg of Silicon store issues from sheet '4. Issue'.",
            "evidence": "VSPL_Material_Entry.xlsx ('4. Issue' Silicon sum=50.218 kg); VSPL_Master_Ledger.xlsx (Issued=0 kg)",
            "owner": "Stores Manager & Cost Accountant",
            "action": "Include Silicon in physical stocktake protocol. Reconcile verified physical count as 12-Oct-2026 cutoff opening balance."
        },
        {
            "code": "MNT-CN-001",
            "book": 1.0,
            "cause": "HYPOTHESIS: Receipt GRN row 3 records 1 Set of '3306PMKT-Generator' received from sreenathji on PO 300426-10, Inv GMP2926002828. Code missing from canonical Item Master.",
            "evidence": "VSPL_Material_Entry.xlsx ('3. Receipt GRN' Row 3; '2. New Items' Row 5); DEC-001/DEC-003 registers",
            "owner": "Stores Manager & Maintenance Head",
            "action": "Conduct physical count in Maintenance generator store. Create MNT-CN-001 in Item Master via Phase 2 workflow. Audit commercial purchase invoice for ex-GST rate."
        },
        {
            "code": "MCS-CN-002",
            "book": 4.0,
            "cause": "HYPOTHESIS: Receipt GRN row 4 records 4 Nos of 'Tool Post' received on PO 070726-11, Inv 454. Missing date, vendor, and rate. Code missing from canonical Item Master.",
            "evidence": "VSPL_Material_Entry.xlsx ('3. Receipt GRN' Row 4; '2. New Items' Row 6); DEC-001/DEC-003 registers",
            "owner": "Machine Shop Head & Stores Manager",
            "action": "Physical count in Machine Shop tooling crib. Create MCS-CN-002 in Item Master. Corroborate physical PO 070726-11 and supplier invoice for rate and vendor."
        },
        {
            "code": "FDY-RM-007 / 008",
            "book": 15200.0,
            "cause": "HYPOTHESIS: Receipt GRN row 5 records 15,200 kg of 'crca scrap' on PO 140726-02, Inv 384. Missing date, vendor, and rate. Chemically ambiguous between Low MN (008) and Low High MN (007).",
            "evidence": "VSPL_Material_Entry.xlsx ('3. Receipt GRN' Row 5); Item Master rows 8 & 9; DEC-001/DEC-003 registers",
            "owner": "Foundry Head & Metallurgist",
            "action": "Take metallurgical sample from scrap yard for spectrometer analysis to determine manganese grade. Obtain commercial invoice 384 from Finance for rate."
        },
        {
            "code": "DATE-TYPO-537-548",
            "book": None,
            "cause": "HYPOTHESIS: Stored date '7-16-20236' across Issue rows 537-548 represents a manual typing error for 2026-07-16. Slips follow sequential numbering.",
            "evidence": "VSPL_Material_Entry.xlsx ('4. Issue' cells A537:A548); DEC-004 register; frozen date_discrepancy_report.csv",
            "owner": "Stores Manager & QA Lead",
            "action": "Audit physical hardcopy issue slips (Slips 327, 910, 325, 1149, 326, 2725, 1148). Sign off formal date normalization prior to historical staging."
        },
        {
            "code": "SAMPLE-ROW-2-ALL",
            "book": None,
            "cause": "HYPOTHESIS: Row 2 across Receipt GRN, Issue, and Waste sheets contains template demo/sample data. Read Me instructs deleting before real use.",
            "evidence": "VSPL_Material_Entry.xlsx (Read Me note; Row 2 across all transaction sheets); DEC-006 register",
            "owner": "Stores Manager & Systems Architect",
            "action": "Formally purge sample template row 2 records from operational migration manifest per DEC-006 sign-off."
        },
        {
            "code": "FURNACE-CHARGE-DEFICIT",
            "book": None,
            "cause": "HYPOTHESIS: 18 of 19 heats logged on 22-Jul-2026 in VSPL_Foundry_Heat_Log.xlsx record Total Charge = 0 kg yet report tapped metal 504-524 kg (-100% to -125% melt loss).",
            "evidence": "VSPL_Foundry_Heat_Log.xlsx ('Heat Log' rows 2-20; 'Charge Details' only 10 rows); DEC-007 register",
            "owner": "Foundry Head & Metallurgist",
            "action": "Retrieve physical paper furnace charge log sheets for 22-Jul-2026. Quarantine heat log records in staging preview pending physical log audit."
        },
        {
            "code": "LEGACY-RECEIPTS-20261107",
            "book": None,
            "cause": "HYPOTHESIS: 113 rows in Store Inventory.xlsx with stored date 2026-11-07 represent internal physical stock counts (entered as 11-07-2026), NOT vendor receipts. Occurs nearly one month in the future.",
            "evidence": "Store Inventory.xlsx ('Material Receipt' rows 9-121, Supplier='Physical stock'); DEC-008 register",
            "owner": "IT Head & Inventory Auditor",
            "action": "Formally retire Store Inventory.xlsx from operational migration. Retain strictly as read-only historical evidence. Do not import future-dated rows."
        },
        {
            "code": "LEGACY-UNDATED-STOCK",
            "book": None,
            "cause": "HYPOTHESIS: 550 kg Magnesium and 20 kg Manganese in Store Inventory.xlsx have blank timestamps and blank suppliers, feeding Stock Details formulas without audit trail.",
            "evidence": "Store Inventory.xlsx ('Material Receipt' rows 122 & 123); DEC-005/DEC-008 registers",
            "owner": "Stores Manager & Plant Head",
            "action": "Do not post legacy stock details into live ERP. Require certified physical count as of 12-Oct-2026 cutoff."
        },
        {
            "code": "GENERAL-RATE-DEFICIT",
            "book": None,
            "cause": "HYPOTHESIS: Zero items (0 of 391) in VSPL_Item_Master.xlsx have commercial purchase rates. GRN rows 2-5 lack commercial rates. Costing engine cannot calculate moving averages without commercial rates.",
            "evidence": "VSPL_Item_Master.xlsx (Col K Rate=None across all 391 rows); VSPL_Material_Entry.xlsx (Col H Commercial Rate absent); DEC-001 register",
            "owner": "Finance Head & Purchase Head",
            "action": "Audit physical purchase invoices and approved vendor POs to establish verified ex-GST purchase rates. Mark all items EXPLICITLY_UNVALUED until Finance signs off."
        }
    ]

    data_start_row_b = 6
    for i, exc in enumerate(exceptions_list):
        r = data_start_row_b + i
        code = exc["code"]
        book_val = exc["book"]
        
        ws_b.cell(row=r, column=1, value=code).alignment = Alignment(horizontal="center")
        
        cell_book = ws_b.cell(row=r, column=2, value=book_val)
        if book_val is not None:
            cell_book.number_format = "#,##0.000" if "kg" in exc["evidence"].lower() else "#,##0.00"
            cell_book.alignment = Alignment(horizontal="right")
        else:
            cell_book.value = "N/A (ANOMALY)"
            cell_book.alignment = Alignment(horizontal="center")
            
        # Counted Qty (Col C) - Blank
        cell_count = ws_b.cell(row=r, column=3, value=None)
        cell_count.alignment = Alignment(horizontal="right")
        cell_count.number_format = "#,##0.000"
        
        # Variance Formula (Col D)
        cell_var = ws_b.cell(row=r, column=4)
        cell_var.value = f'=IF(ISBLANK(C{r}),"",IF(ISNUMBER(B{r}),C{r}-B{r},""))'
        cell_var.alignment = Alignment(horizontal="right")
        cell_var.number_format = "#,##0.000"
        
        ws_b.cell(row=r, column=5, value=exc["cause"]).alignment = Alignment(horizontal="left", wrap_text=True)
        ws_b.cell(row=r, column=6, value=exc["evidence"]).alignment = Alignment(horizontal="left", wrap_text=True)
        ws_b.cell(row=r, column=7, value=exc["owner"]).alignment = Alignment(horizontal="center", wrap_text=True)
        ws_b.cell(row=r, column=8, value=exc["action"]).alignment = Alignment(horizontal="left", wrap_text=True)
        
        # Approval Status (Col I) - Blank
        ws_b.cell(row=r, column=9, value=None).alignment = Alignment(horizontal="center")
        
        for c in range(1, 10):
            ws_b.cell(row=r, column=c).font = regular_font
            ws_b.cell(row=r, column=c).border = cell_border
            ws_b.cell(row=r, column=c).fill = exception_fill

    ws_b.freeze_panes = "A6"

    # =========================================================================
    # WORKSHEET C: Valuation Register
    # =========================================================================
    ws_c = wb.create_sheet(title="C. Valuation Register")
    ws_c.views.sheetView[0].showGridLines = True
    
    ws_c["A1"] = "VIJAY SPHEROIDALS PVT. LTD. — INVENTORY VALUATION REGISTER"
    ws_c["A1"].font = title_font
    ws_c["A2"] = "COSTING BASIS: MOVING WEIGHTED AVERAGE (RULE C1) | STATUS: EXPLICITLY UNVALUED PENDING COMMERCIAL INVOICE AUDIT"
    ws_c["A2"].font = subtitle_font
    ws_c["A3"] = "MANDATORY FINANCIAL CONTROL: Unapproved or missing purchase rates must remain EXPLICITLY UNVALUED. Never estimate or guess rates."
    ws_c["A3"].font = warning_font
    
    headers_c = [
        ("Canonical Item Code", 22),
        ("Item Description", 38),
        ("Base UOM", 12),
        ("Approved Valuation Basis", 28),
        ("Verified Rate (INR)", 20),
        ("Rate Source", 36),
        ("Effective Date", 16),
        ("Extended Value (INR)", 22),
        ("Approval Reference", 24),
        ("Valuation Status", 24)
    ]
    
    row_idx = 5
    for col_idx, (header_text, col_width) in enumerate(headers_c, start=1):
        cell = ws_c.cell(row=row_idx, column=col_idx, value=header_text)
        cell.font = header_font
        cell.fill = accent_header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = header_border
        ws_c.column_dimensions[get_column_letter(col_idx)].width = col_width
    ws_c.row_dimensions[row_idx].height = 28

    data_start_row_c = 6
    for i, item in enumerate(all_items):
        r = data_start_row_c + i
        code = item["code"]
        
        ws_c.cell(row=r, column=1, value=code).alignment = Alignment(horizontal="center")
        ws_c.cell(row=r, column=2, value=item["desc"]).alignment = Alignment(horizontal="left")
        ws_c.cell(row=r, column=3, value=item["uom"]).alignment = Alignment(horizontal="center")
        
        # Valuation basis
        ws_c.cell(row=r, column=4, value="EXPLICITLY_UNVALUED").alignment = Alignment(horizontal="center")
        
        # Verified Rate (Col E) - Blank!
        cell_rate = ws_c.cell(row=r, column=5, value=None)
        cell_rate.alignment = Alignment(horizontal="right")
        cell_rate.number_format = "₹#,##0.00"
        
        # Rate Source (Col F)
        ws_c.cell(row=r, column=6, value="PENDING_COMMERCIAL_INVOICE_AUDIT").alignment = Alignment(horizontal="left")
        
        # Effective Date (Col G) - Blank!
        ws_c.cell(row=r, column=7, value=None).alignment = Alignment(horizontal="center")
        
        # Extended Value (Col H): Physical Counted Qty (Sheet A Col F) * Verified Rate (Col E)
        cell_ext = ws_c.cell(row=r, column=8)
        cell_ext.value = f'=IF(OR(ISBLANK(E{r}),ISBLANK(\'A. Stocktake Register\'!F{r})),"",\'A. Stocktake Register\'!F{r}*E{r})'
        cell_ext.alignment = Alignment(horizontal="right")
        cell_ext.number_format = "₹#,##0.00"
        
        # Approval Reference (Col I) - Blank!
        ws_c.cell(row=r, column=9, value=None).alignment = Alignment(horizontal="center")
        
        # Valuation Status (Col J)
        ws_c.cell(row=r, column=10, value="EXPLICITLY_UNVALUED").alignment = Alignment(horizontal="center")
        
        for c in range(1, 11):
            ws_c.cell(row=r, column=c).font = regular_font
            ws_c.cell(row=r, column=c).border = cell_border
            if item["is_candidate"]:
                ws_c.cell(row=r, column=c).fill = candidate_fill

    ws_c.freeze_panes = "A6"

    # =========================================================================
    # WORKSHEET D: Opening Inventory Approval
    # =========================================================================
    ws_d = wb.create_sheet(title="D. Opening Inventory Approval")
    ws_d.views.sheetView[0].showGridLines = True
    
    ws_d["A1"] = "VIJAY SPHEROIDALS PVT. LTD. — OPENING INVENTORY AUTHORIZATION & SIGN-OFF GATE"
    ws_d["A1"].font = title_font
    ws_d["A2"] = "GOVERNANCE GATE: THREE-WAY SIGN-OFF (STORES, PLANT HEAD, FINANCE HEAD) MANDATORY BEFORE APPLICATION POSTING"
    ws_d["A2"].font = subtitle_font
    ws_d["A3"] = "STRICT PROHIBITION: ALL APPROVAL FIELDS MUST REMAIN BLANK UNTIL THE PHYSICAL STOCKTAKE IS COMPLETED AND VALUED."
    ws_d["A3"].font = warning_font
    
    headers_d = [
        ("Canonical Item Code", 22),
        ("Item Description", 38),
        ("Base UOM", 12),
        ("Proposed Opening Qty", 22),
        ("Proposed Valuation (INR)", 24),
        ("Reconciliation Evidence", 40),
        ("Physical Count Reference", 26),
        ("Outstanding Exceptions", 35),
        ("Stores Approval (Sign & Date)", 28),
        ("Plant Head Approval (Sign & Date)", 28),
        ("Finance Approval (Sign & Date)", 28),
        ("Final Authorization Status", 25)
    ]
    
    row_idx = 5
    for col_idx, (header_text, col_width) in enumerate(headers_d, start=1):
        cell = ws_d.cell(row=row_idx, column=col_idx, value=header_text)
        cell.font = header_font
        cell.fill = primary_header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = header_border
        ws_d.column_dimensions[get_column_letter(col_idx)].width = col_width
    ws_d.row_dimensions[row_idx].height = 28

    data_start_row_d = 6
    for i, item in enumerate(all_items):
        r = data_start_row_d + i
        code = item["code"]
        
        ws_d.cell(row=r, column=1, value=code).alignment = Alignment(horizontal="center")
        ws_d.cell(row=r, column=2, value=item["desc"]).alignment = Alignment(horizontal="left")
        ws_d.cell(row=r, column=3, value=item["uom"]).alignment = Alignment(horizontal="center")
        
        # Proposed Opening Qty: links to Sheet A Physical Counted Qty
        cell_prop_qty = ws_d.cell(row=r, column=4)
        cell_prop_qty.value = f'=IF(ISBLANK(\'A. Stocktake Register\'!F{r}),"",\'A. Stocktake Register\'!F{r})'
        cell_prop_qty.alignment = Alignment(horizontal="right")
        cell_prop_qty.number_format = "#,##0.000" if item["uom"] == "Kg" else "#,##0"
        
        # Proposed Valuation: links to Sheet C Extended Value
        cell_prop_val = ws_d.cell(row=r, column=5)
        cell_prop_val.value = f'=IF(ISBLANK(\'C. Valuation Register\'!H{r}),"",\'C. Valuation Register\'!H{r})'
        cell_prop_val.alignment = Alignment(horizontal="right")
        cell_prop_val.number_format = "₹#,##0.00"
        
        # Reconciliation Evidence
        evid_text = "Physical stock count as of 12-Oct-2026 cutoff; independent count sheets attached"
        if code in known_exceptions:
            evid_text = f"EXCEPTION AUDIT REQUIRED ({code}): See Sheet B Variance Investigation"
        elif item["is_candidate"]:
            evid_text = f"CANDIDATE NEW ITEM: Requires master approval before opening balance entry"
        ws_d.cell(row=r, column=6, value=evid_text).alignment = Alignment(horizontal="left")
        
        # Physical Count Reference - Blank
        ws_d.cell(row=r, column=7, value=None).alignment = Alignment(horizontal="center")
        
        # Outstanding Exceptions
        exc_text = "NONE (STANDARD ITEM)"
        if code in known_exceptions:
            exc_text = f"BLOCKED BY EXCEPTION ({code})"
        elif item["is_candidate"]:
            exc_text = "PENDING MASTER CREATION"
        ws_d.cell(row=r, column=8, value=exc_text).alignment = Alignment(horizontal="center")
        
        # Approvals: Stores (Col 9), Plant Head (Col 10), Finance (Col 11), Authorization Status (Col 12)
        # ALL APPROVAL FIELDS REMAIN STRICTLY BLANK PER SPECIFICATION
        for c in range(9, 13):
            ws_d.cell(row=r, column=c, value=None).alignment = Alignment(horizontal="center")
            
        for c in range(1, 13):
            ws_d.cell(row=r, column=c).font = regular_font
            ws_d.cell(row=r, column=c).border = cell_border
            if item["is_candidate"]:
                ws_d.cell(row=r, column=c).fill = candidate_fill
            elif code in known_exceptions:
                ws_d.cell(row=r, column=c).fill = exception_fill

    ws_d.freeze_panes = "A6"

    # Save workbook
    wb.save(OUTPUT_FILE)
    print(f"Successfully generated stocktake workbook: {OUTPUT_FILE}")
    print(f"Total items in Register: {len(all_items)} (391 canonical + {len(candidates)} candidate new items)")
    print(f"Total pre-populated exception records: {len(exceptions_list)}")

if __name__ == "__main__":
    build_workbook()
