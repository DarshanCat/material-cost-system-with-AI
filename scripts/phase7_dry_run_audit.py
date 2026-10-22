"""
VSPL Material Management & Costing System — Phase 7 Stage 1 Dry-Run Analysis Engine
STRICTLY READ-ONLY: ZERO DATABASE WRITES, ZERO DATA MUTATIONS.
Audits all discoverable historical Excel workbooks, reconciles stocks, and generates
durable CSV review manifests.
"""

import os
import sys
import hashlib
import csv
import datetime
from decimal import Decimal, InvalidOperation
from collections import Counter, defaultdict
import openpyxl

# Output directory
OUT_DIR = r"c:\VSPL_MM\Material managment system\docs\reports\phase7_dry_run"
os.makedirs(OUT_DIR, exist_ok=True)

# 1. Discover Workbooks
WORKBOOKS = [
    {
        "id": "ITEM_MASTER",
        "category": "Item Master & Reference Catalogs",
        "path": r"c:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Item_Master.xlsx",
    },
    {
        "id": "MATERIAL_ENTRY",
        "category": "Transaction Entry (GRN, Issue, Waste, New Items, Vendors)",
        "path": r"c:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Material_Entry.xlsx",
    },
    {
        "id": "HEAT_LOG",
        "category": "Furnace Production Log (Heats, Charges, Cast Parts)",
        "path": r"c:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Foundry_Heat_Log.xlsx",
    },
    {
        "id": "MASTER_LEDGER",
        "category": "Interim Material Balance Ledger",
        "path": r"c:\VSPL_MM\VSPL_MM_Data\ledger\VSPL_Master_Ledger.xlsx",
    },
    {
        "id": "LEGACY_STORE",
        "category": "Legacy Archive Store Inventory (July 2026 Raw Spreadsheets)",
        "path": r"c:\VSPL_MM\_legacy_archive\Store Inventory.xlsx",
    },
]

print("Stage 1 Dry-Run: Auditing workbooks...")

workbook_inventory = []
for wb_meta in WORKBOOKS:
    p = wb_meta["path"]
    sz = os.path.getsize(p)
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(p), tz=datetime.timezone.utc).isoformat()
    with open(p, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    
    wb = openpyxl.load_workbook(p, data_only=True)
    sheets_info = []
    for sname in wb.sheetnames:
        ws = wb[sname]
        non_empty = 0
        total_rows = ws.max_row or 0
        total_cols = ws.max_column or 0
        first_row = []
        for r_idx, row in enumerate(ws.iter_rows(values_only=True)):
            if r_idx == 0:
                first_row = [str(c) if c is not None else "" for c in row]
            if any(cell is not None and str(cell).strip() != "" for cell in row):
                non_empty += 1
        sheets_info.append({
            "sheet_name": sname,
            "max_row": total_rows,
            "max_col": total_cols,
            "non_empty_rows": non_empty,
            "headers": first_row[:15]
        })
    wb.close()
    
    workbook_inventory.append({
        "id": wb_meta["id"],
        "category": wb_meta["category"],
        "path": p,
        "size_bytes": sz,
        "mtime": mtime,
        "sha256": sha256,
        "sheets": sheets_info,
    })

# Write workbook inventory CSV
with open(os.path.join(OUT_DIR, "source_workbooks_inventory.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Workbook ID", "Category", "File Path", "Size (Bytes)", "Last Modified (UTC)", "SHA256 Fingerprint", "Sheet Name", "Max Rows", "Max Cols", "Non-Empty Rows", "Headers"])
    for wb_info in workbook_inventory:
        for s in wb_info["sheets"]:
            writer.writerow([
                wb_info["id"], wb_info["category"], wb_info["path"], wb_info["size_bytes"],
                wb_info["mtime"], wb_info["sha256"], s["sheet_name"], s["max_row"], s["max_col"],
                s["non_empty_rows"], " | ".join(s["headers"])
            ])

# 2. Detailed Sheet Analysis & Classification
# Load Item Master
wb_item = openpyxl.load_workbook(r"c:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Item_Master.xlsx", data_only=True)
ws_item = wb_item["Item Master"]
canonical_items = {}
legacy_to_canonical = {}
for r in ws_item.iter_rows(min_row=2, values_only=True):
    if r[0]:
        code = str(r[0]).strip()
        canonical_items[code] = {
            "code": code, "desc": r[1], "category": r[2], "dept": r[4],
            "uom": r[5], "reorder": r[6], "legacy": r[11], "orig_desc": r[12]
        }
        if r[11]:
            legacy_to_canonical[str(r[11]).strip().upper()] = code
wb_item.close()

# Evaluate Issues in VSPL_Material_Entry.xlsx
wb_entry = openpyxl.load_workbook(r"c:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Material_Entry.xlsx", data_only=True)
ws_iss = wb_entry["4. Issue"]
iss_records = []
for idx, r in enumerate(ws_iss.iter_rows(min_row=2, values_only=True), start=2):
    if not any(c is not None and str(c).strip() != "" for c in r):
        continue
    dt, slip, desc, code, uom, qty, section, unit, wo, dept, by, rem = r
    code_str = str(code).strip() if code else ""
    
    # Classify
    status = "VALID_NEW_CANDIDATE"
    reasons = []
    
    # Check date
    if not dt or not (isinstance(dt, (datetime.datetime, datetime.date))):
        status = "INVALID_SOURCE"
        reasons.append("Invalid or unparseable transaction date")
    
    # Check item code
    if not code_str or code_str in ("NOT FOUND", "None", "Na", "NA"):
        status = "UNMAPPED"
        reasons.append("Missing or unmapped item code")
    elif code_str not in canonical_items:
        status = "UNMAPPED"
        reasons.append(f"Item code '{code_str}' not in canonical Item Master")
        
    # Check quantity
    try:
        q_dec = Decimal(str(qty))
        if q_dec <= 0:
            status = "INVALID_SOURCE"
            reasons.append(f"Non-positive quantity: {qty}")
    except (InvalidOperation, TypeError):
        status = "INVALID_SOURCE"
        reasons.append(f"Malformed quantity: {qty}")
        
    iss_records.append({
        "source_row": idx,
        "date": str(dt) if dt else "",
        "issue_slip_number": str(slip) if slip else "",
        "item_description": str(desc) if desc else "",
        "item_code": code_str,
        "canonical_item_code": canonical_items.get(code_str, {}).get("code", ""),
        "uom": str(uom) if uom else "",
        "quantity": str(qty) if qty is not None else "",
        "consuming_section": str(section) if section else "",
        "work_order": str(wo) if wo else "",
        "department": str(dept) if dept else "",
        "status": status,
        "reasons": "; ".join(reasons) if reasons else "Conforms to issue schema"
    })

# Write Issues Audit CSV
with open(os.path.join(OUT_DIR, "issues_dry_run_audit.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Row #", "Date", "Issue Slip No", "Item Description", "Item Code", "Canonical Item Code", "UOM", "Quantity", "Consuming Section", "Work Order", "Department", "Classification Status", "Audit Notes"])
    for ir in iss_records:
        writer.writerow([
            ir["source_row"], ir["date"], ir["issue_slip_number"], ir["item_description"],
            ir["item_code"], ir["canonical_item_code"], ir["uom"], ir["quantity"],
            ir["consuming_section"], ir["work_order"], ir["department"], ir["status"], ir["reasons"]
        ])

# Evaluate GRN Receipts in VSPL_Material_Entry.xlsx
ws_grn = wb_entry["3. Receipt GRN"]
grn_records = []
for idx, r in enumerate(ws_grn.iter_rows(min_row=2, values_only=True), start=2):
    if not any(c is not None and str(c).strip() != "" for c in r):
        continue
    dt, grn_no, vname, inv_no, po_no, desc, code, cat, uom, qty, rem, by = r
    code_str = str(code).strip() if code else ""
    status = "VALID_NEW_CANDIDATE"
    reasons = []
    
    if not dt:
        status = "INVALID_SOURCE"
        reasons.append("Missing receipt date")
    if not grn_no:
        status = "INVALID_SOURCE"
        reasons.append("Missing GRN document number")
    if not code_str or code_str in ("NOT FOUND", "None", "Na", "NA") or code_str not in canonical_items:
        status = "UNMAPPED"
        reasons.append(f"Unmapped item code '{code_str}'")
        
    # Costing check: commercial receipt rate missing in source spreadsheet!
    reasons.append("RATE_MISSING: Sheet has no rate_ex_gst column (costing blocker)")
    
    grn_records.append({
        "source_row": idx,
        "date": str(dt) if dt else "",
        "grn_number": str(grn_no) if grn_no else "",
        "vendor_name": str(vname) if vname else "",
        "supplier_invoice_no": str(inv_no) if inv_no else "",
        "po_no": str(po_no) if po_no else "",
        "item_description": str(desc) if desc else "",
        "item_code": code_str,
        "uom": str(uom) if uom else "",
        "quantity": str(qty) if qty is not None else "",
        "status": status,
        "reasons": "; ".join(reasons)
    })

with open(os.path.join(OUT_DIR, "grn_receipts_dry_run_audit.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Row #", "Date", "GRN No", "Vendor Name", "Supplier Invoice No", "PO No", "Item Description", "Item Code", "UOM", "Quantity", "Classification Status", "Audit Notes"])
    for gr in grn_records:
        writer.writerow([
            gr["source_row"], gr["date"], gr["grn_number"], gr["vendor_name"],
            gr["supplier_invoice_no"], gr["po_no"], gr["item_description"], gr["item_code"],
            gr["uom"], gr["quantity"], gr["status"], gr["reasons"]
        ])

# Evaluate Waste Disposition in VSPL_Material_Entry.xlsx
ws_wst = wb_entry["5. Waste Disposition"]
wst_records = []
for idx, r in enumerate(ws_wst.iter_rows(min_row=2, values_only=True), start=2):
    if not any(c is not None and str(c).strip() != "" for c in r):
        continue
    dt, note_no, desc, code, uom, qty, w_type, reason, sec, disp_to, app_by, rem = r
    code_str = str(code).strip() if code else ""
    status = "VALID_NEW_CANDIDATE"
    reasons = []
    
    if not dt:
        status = "MANUAL_REVIEW"
        reasons.append("Missing disposition date")
    if not note_no:
        status = "MANUAL_REVIEW"
        reasons.append("Missing disposal note number")
    if not code_str or code_str not in canonical_items:
        status = "UNMAPPED"
        reasons.append(f"Unmapped item code '{code_str}'")
    if qty is None:
        status = "INVALID_SOURCE"
        reasons.append("Missing quantity")
        
    wst_records.append({
        "source_row": idx,
        "date": str(dt) if dt else "",
        "note_no": str(note_no) if note_no else "",
        "item_description": str(desc) if desc else "",
        "item_code": code_str,
        "uom": str(uom) if uom else "",
        "quantity": str(qty) if qty is not None else "",
        "waste_type": str(w_type) if w_type else "",
        "status": status,
        "reasons": "; ".join(reasons) if reasons else "Valid waste record"
    })

with open(os.path.join(OUT_DIR, "waste_disposition_dry_run_audit.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Row #", "Date", "Disposal Note No", "Item Description", "Item Code", "UOM", "Quantity", "Waste Type", "Classification Status", "Audit Notes"])
    for wr in wst_records:
        writer.writerow([
            wr["source_row"], wr["date"], wr["note_no"], wr["item_description"],
            wr["item_code"], wr["uom"], wr["quantity"], wr["waste_type"],
            wr["status"], wr["reasons"]
        ])
wb_entry.close()

# 3. Legacy Store Inventory (Stock Details) Reconciliation vs VSPL_Master_Ledger
wb_store = openpyxl.load_workbook(r"c:\VSPL_MM\_legacy_archive\Store Inventory.xlsx", data_only=True)
ws_sd = wb_store["Stock Details"]
sd_dict = {}
for idx, r in enumerate(ws_sd.iter_rows(min_row=3, values_only=True), start=3):
    if r[0]:
        leg_code = str(r[0]).strip().upper()
        sd_dict[leg_code] = {
            "row": idx, "legacy_code": leg_code, "name": r[1], "dept": r[2],
            "unit": r[3], "rate": r[4], "reorder": r[5], "rcpt": r[6], "iss": r[7], "stock": r[8], "val": r[9]
        }

wb_ledger = openpyxl.load_workbook(r"c:\VSPL_MM\VSPL_MM_Data\ledger\VSPL_Master_Ledger.xlsx", data_only=True)
ws_led = wb_ledger["Ledger"]
reconciliation_records = []

for idx, r in enumerate(ws_led.iter_rows(min_row=2, values_only=True), start=2):
    if not r[0]:
        continue
    code = str(r[0]).strip()
    name = r[1]
    dept = r[4]
    uom = r[5]
    open_stock = r[6]
    rcpt = r[7]
    iss = r[8]
    wst = r[9]
    close_stock = r[10]
    
    # Lookup legacy code from canonical item master
    item_info = canonical_items.get(code, {})
    leg_code = str(item_info.get("legacy", "")).strip().upper() if item_info.get("legacy") else ""
    
    sd_info = sd_dict.get(leg_code)
    legacy_stock = sd_info["stock"] if sd_info else None
    legacy_rcpt = sd_info["rcpt"] if sd_info else None
    legacy_iss = sd_info["iss"] if sd_info else None
    
    # Compare
    has_variance = False
    variance_desc = []
    
    if legacy_stock is not None:
        try:
            ls_dec = Decimal(str(legacy_stock))
            cs_dec = Decimal(str(close_stock or 0))
            if ls_dec != cs_dec:
                has_variance = True
                variance_desc.append(f"Stock mismatch: Legacy Stock={ls_dec} vs Master Ledger Closing={cs_dec}")
        except:
            has_variance = True
            variance_desc.append(f"Unparseable stock: legacy={legacy_stock}, ledger={close_stock}")
    else:
        variance_desc.append("No matching legacy Stock Details record")
        
    reconciliation_records.append({
        "item_code": code,
        "item_name": name,
        "legacy_code": leg_code,
        "uom": uom,
        "master_ledger_opening": open_stock,
        "master_ledger_received": rcpt,
        "master_ledger_issued": iss,
        "master_ledger_waste": wst,
        "master_ledger_closing": close_stock,
        "legacy_receipt": legacy_rcpt,
        "legacy_issue": legacy_iss,
        "legacy_stock": legacy_stock,
        "variance_flag": "VARIANCE" if has_variance else "MATCH",
        "notes": "; ".join(variance_desc) if variance_desc else "Balances align"
    })

wb_store.close()
wb_ledger.close()

with open(os.path.join(OUT_DIR, "stock_reconciliation_audit.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Item Code", "Item Name", "Legacy Code", "UOM",
        "Master Ledger Opening", "Master Ledger Received", "Master Ledger Issued", "Master Ledger Waste", "Master Ledger Closing",
        "Legacy Stock Details Receipt", "Legacy Stock Details Issue", "Legacy Stock Details Stock",
        "Reconciliation Status", "Reconciliation Notes"
    ])
    for rr in reconciliation_records:
        writer.writerow([
            rr["item_code"], rr["item_name"], rr["legacy_code"], rr["uom"],
            rr["master_ledger_opening"], rr["master_ledger_received"], rr["master_ledger_issued"],
            rr["master_ledger_waste"], rr["master_ledger_closing"], rr["legacy_receipt"],
            rr["legacy_issue"], rr["legacy_stock"], rr["variance_flag"], rr["notes"]
        ])

print("Stage 1 Dry-Run Analysis complete. Audit CSV files successfully generated in:", OUT_DIR)
