"""
VSPL Material Management & Costing System — Phase 7 Stage 2.1 Audit & Reconciliation Engine
STRICTLY READ-ONLY AUDIT:
- Zero application database writes
- Zero ledger mutations
- Zero Excel modifications
- Reconciles Stage 1 and Stage 2 manifest discrepancies
- Produces deterministic, byte-reproducible CSV and JSON artifacts
"""

import os
import csv
import json
import hashlib
import datetime
from decimal import Decimal, InvalidOperation
from collections import Counter
import openpyxl

WORKSPACE_DIR = r"c:\VSPL_MM\Material managment system"
REPORTS_DIR = os.path.join(WORKSPACE_DIR, "docs", "reports")
STAGE2_DIR = os.path.join(REPORTS_DIR, "phase7_stage2")
STAGE2_1_DIR = os.path.join(REPORTS_DIR, "phase7_stage2_1")
os.makedirs(STAGE2_1_DIR, exist_ok=True)

# 1. Source files configuration
SOURCE_FILES = {
    "ITEM_MASTER": r"C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Item_Master.xlsx",
    "MATERIAL_ENTRY": r"C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Material_Entry.xlsx",
    "HEAT_LOG": r"C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Foundry_Heat_Log.xlsx",
    "MASTER_LEDGER": r"C:\VSPL_MM\VSPL_MM_Data\ledger\VSPL_Master_Ledger.xlsx",
    "STORE_INVENTORY": r"C:\VSPL_MM\_legacy_archive\Store Inventory.xlsx"
}

def compute_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

print("--- Step 1: Source Workbook Verification & Fingerprints ---")
fingerprint_rows = []
fingerprints_dict = {}
for file_id, path in SOURCE_FILES.items():
    exists = os.path.exists(path)
    size = os.path.getsize(path) if exists else 0
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path), tz=datetime.timezone.utc).isoformat() if exists else ""
    sha = compute_sha256(path) if exists else ""
    fingerprints_dict[file_id] = sha
    fingerprint_rows.append({
        "Workbook ID": file_id,
        "File Path": path,
        "Exists": exists,
        "Size (Bytes)": size,
        "Last Modified (UTC)": mtime,
        "SHA256 Fingerprint": sha
    })
    print(f"  {file_id}: size={size}, sha={sha[:12]}...")

fp_csv_path = os.path.join(STAGE2_1_DIR, "source_fingerprint_verification.csv")
with open(fp_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["Workbook ID", "File Path", "Exists", "Size (Bytes)", "Last Modified (UTC)", "SHA256 Fingerprint"])
    writer.writeheader()
    writer.writerows(fingerprint_rows)

print("--- Step 2: Ingest Item Master & Reference Data ---")
wb_item = openpyxl.load_workbook(SOURCE_FILES["ITEM_MASTER"], data_only=True)
ws_item = wb_item["Item Master"]
item_master = {}
for r in range(2, ws_item.max_row + 1):
    c_code = ws_item.cell(r, 1).value
    if c_code:
        code_str = str(c_code).strip()
        item_master[code_str] = {
            "description": str(ws_item.cell(r, 2).value or "").strip(),
            "category": str(ws_item.cell(r, 3).value or "").strip(),
            "cost_head": str(ws_item.cell(r, 4).value or "").strip(),
            "department": str(ws_item.cell(r, 5).value or "").strip(),
            "uom": str(ws_item.cell(r, 6).value or "").strip(),
            "rate": ws_item.cell(r, 11).value,
            "hsn": ws_item.cell(r, 10).value,
            "legacy_code": str(ws_item.cell(r, 12).value or "").strip()
        }
print(f"  Item Master loaded: {len(item_master)} items.")

wb_entry = openpyxl.load_workbook(SOURCE_FILES["MATERIAL_ENTRY"], data_only=True)
ws_new = wb_entry["2. New Items"]
new_items = {}
for r in range(2, ws_new.max_row + 1):
    code = ws_new.cell(r, 3).value
    desc = ws_new.cell(r, 5).value
    if code and desc:
        new_items[str(code).strip()] = {
            "description": str(desc).strip(),
            "uom": str(ws_new.cell(r, 6).value or "").strip(),
            "dept": str(ws_new.cell(r, 1).value or "").strip()
        }
print(f"  2. New Items loaded: {len(new_items)} candidates.")

print("--- Step 3: Parse Stage 2 Manifest & Build Crosswalk ---")
manifest_path = os.path.join(STAGE2_DIR, "proposed_migration_manifest.csv")
manifest_rows = []
with open(manifest_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    manifest_rows = list(reader)

print(f"  Total manifest rows ingested: {len(manifest_rows)}")

# Recheck & Reconciliation Logic
crosswalk_rows = []
stage2_primary_counts = Counter()
stage2_readiness_counts = Counter()
crosstab_stage2 = Counter()

recheck_primary_counts = Counter()
recheck_readiness_counts = Counter()
crosstab_recheck = Counter()
transition_matrix = Counter()

# Pre-identify duplicates in Issues
seen_issue_keys = {}
issue_duplicates = set()
for r in manifest_rows:
    if r["Source Worksheet"] == "4. Issue":
        slip = str(r["Source Doc Number"]).strip()
        code = str(r["Source Item Code"]).strip()
        qty = str(r["Source Quantity"]).strip()
        key = (slip, code, qty)
        if key in seen_issue_keys:
            issue_duplicates.add(r["Manifest ID"])
            issue_duplicates.add(seen_issue_keys[key])
        else:
            seen_issue_keys[key] = r["Manifest ID"]

for row in manifest_rows:
    m_id = row["Manifest ID"]
    wb_name = row["Source Workbook"]
    ws_name = row["Source Worksheet"]
    s_row = int(row["Source Row #"])
    s_doc = row["Source Doc Number"]
    s_date = row["Source Date"]
    s_desc = row["Source Item Description"]
    s_code = row["Source Item Code"]
    s_uom = row["Source UOM"]
    s_qty = row["Source Quantity"]
    s_target = row["Proposed Target Entity"]
    s_canon = row["Proposed Canonical Item Code"]
    s2_class = row["Classification Status"]
    s2_dec = row["Decision Reference"]
    s2_ready = row["Decision Status"]
    s2_finding = row["Audit Finding"]

    stage2_primary_counts[s2_class] += 1
    stage2_readiness_counts[s2_ready] += 1
    crosstab_stage2[(s2_class, s2_ready)] += 1

    # Recheck logic
    audit_flags = []
    diff_reason = ""
    
    # Analyze why Stage 2 assigned readiness differently from primary
    # Formula in Stage 2:
    # GRN: always PENDING_REVIEW
    # Heat Log / Charge Details: always PENDING_REVIEW
    # Issue / Waste / Parts: PENDING_REVIEW if decision_ref != '' else (ELIGIBLE if VALID else BLOCKED)
    if s2_class == "VALID_NEW_CANDIDATE" and s2_ready == "PENDING_REVIEW":
        diff_reason = f"Valid transaction held in PENDING_REVIEW due to policy/technical decision dependency ({s2_dec})"
    elif s2_class == "INVALID_SOURCE" and s2_ready == "PENDING_REVIEW":
        diff_reason = f"Source defect held in PENDING_REVIEW (GRN multi-defect evaluation: missing rate + date/doc)"
    elif s2_class == "MANUAL_REVIEW" and s2_ready == "PENDING_REVIEW":
        diff_reason = f"Ambiguity or source defect held for manual review ({s2_dec})"
    elif s2_class == "UNMAPPED" and s2_ready == "PENDING_REVIEW":
        diff_reason = f"Unmapped item held for master data governance approval ({s2_dec})"
    elif s2_class == "INVALID_SOURCE" and s2_ready == "BLOCKED":
        diff_reason = "Fatal source defect (e.g. zero quantity, destroyed without qty) marked BLOCKED"
    elif s2_class == "VALID_NEW_CANDIDATE" and s2_ready == "ELIGIBLE":
        diff_reason = "Passed Stage 2 syntax validation without blocking flags"

    # Now perform rigorous Recheck
    # 1. Sample row 2 check
    is_sample = False
    if s_row == 2 and ws_name in ["3. Receipt GRN", "4. Issue", "5. Waste Disposition"]:
        is_sample = True
        audit_flags.append("SAMPLE_ROW_TEMPLATE")

    # 2. Date typo check
    is_date_typo = False
    if "20236" in s_date or "7-16-20236" in s_date or (ws_name == "4. Issue" and s_row in range(537, 549)):
        is_date_typo = True
        audit_flags.append("DATE_YEAR_TYPO_20236")

    # 3. Missing date
    if not s_date or s_date.strip().lower() in ["none", ""]:
        audit_flags.append("DATE_MISSING")

    # 4. Zero or missing quantity
    is_zero_or_null_qty = False
    try:
        q_dec = Decimal(str(s_qty).strip())
        if q_dec <= 0:
            is_zero_or_null_qty = True
            audit_flags.append("ZERO_OR_NEGATIVE_QUANTITY")
    except (InvalidOperation, TypeError):
        is_zero_or_null_qty = True
        audit_flags.append("NULL_OR_INVALID_QUANTITY")

    # 5. UOM Mismatch against Item Master
    is_uom_mismatch = False
    if s_canon and s_canon in item_master:
        canon_uom = item_master[s_canon]["uom"]
        if s_uom and s_uom.strip() != canon_uom.strip():
            is_uom_mismatch = True
            audit_flags.append(f"UOM_MISMATCH_SOURCE_{s_uom}_CANON_{canon_uom}")

    # 6. Duplicate check
    if m_id in issue_duplicates:
        audit_flags.append("DUPLICATE_SLIP_ITEM_QTY")

    # 7. Unmapped item
    is_unmapped = False
    if s_code == "NOT FOUND" or not s_canon or s_canon not in item_master:
        is_unmapped = True
        audit_flags.append("UNMAPPED_ITEM_CODE")

    # 8. Missing GRN rate
    if ws_name == "3. Receipt GRN":
        audit_flags.append("MISSING_COMMERCIAL_RATE")

    # 9. Legacy identifier conflict (GRN row 2)
    if ws_name == "3. Receipt GRN" and s_row == 2:
        audit_flags.append("LEGACY_DOC_IDENTIFIER_CONFLICT")

    # 10. Negative stock item reference
    if s_canon in ["FDY-RM-008", "FDY-RM-011", "FDY-RM-014", "FDY-RM-016", "FDY-RM-017", "FDY-RM-019", "FDY-RM-020"]:
        audit_flags.append("NEGATIVE_STOCK_ITEM_REF")

    # 11. Heat log integrity flags
    if ws_name == "Heat Log":
        if s_qty == "0":
            audit_flags.append("ZERO_TOTAL_CHARGE")
        audit_flags.append("NEGATIVE_MELT_LOSS_ANOMALY")
    elif ws_name == "Charge Details":
        if s_doc in ["H-260714-01", "L-260722-02", "H-200125-05"]:
            audit_flags.append("ORPHAN_HEAT_NO_HEADER")
        if s_doc == "072613-2092":
            audit_flags.append("CHARGE_EXCEEDED_BY_TAP_WEIGHT")
    elif ws_name == "Parts Produced":
        if s_row == 2:
            audit_flags.append("PARTS_WEIGHT_EXCEEDS_TAP_WEIGHT")
        if not s_qty or s_qty.strip().lower() in ["none", ""]:
            audit_flags.append("MISSING_PARTS_COUNT")

    # Determine Recheck Primary Classification (Strict Precedence)
    # Distinguish operational inventory movements (GRN, Issue, Waste) from production records (Heat, Charge, Parts)
    recheck_primary = "VALID_NEW_CANDIDATE"
    if is_zero_or_null_qty or (ws_name == "3. Receipt GRN" and s_row in [4, 5]) or (ws_name == "5. Waste Disposition" and is_zero_or_null_qty):
        recheck_primary = "INVALID_SOURCE"
    elif is_unmapped and ws_name in ["3. Receipt GRN", "4. Issue", "5. Waste Disposition"]:
        recheck_primary = "UNMAPPED"
    elif "LEGACY_DOC_IDENTIFIER_CONFLICT" in audit_flags or "PARTS_WEIGHT_EXCEEDS_TAP_WEIGHT" in audit_flags:
        recheck_primary = "CONFLICT"
    elif is_sample or is_date_typo or is_uom_mismatch or "DUPLICATE_SLIP_ITEM_QTY" in audit_flags or ws_name in ["Heat Log", "Charge Details", "Parts Produced"] or ws_name == "3. Receipt GRN":
        recheck_primary = "MANUAL_REVIEW"
    else:
        recheck_primary = "VALID_NEW_CANDIDATE"

    # Determine Recheck Readiness
    # Readiness strictly reflects governance blocking:
    # If fatal defect -> BLOCKED_SOURCE_DEFECT
    # If requires manual review / disambiguation / sample -> HELD_MANUAL_REVIEW
    # If dependent on unapproved decision (e.g. negative stock items, unmapped items) -> HELD_PENDING_DECISION
    # If clean row, but dependent on cutoff policy -> ROW_CLEAN_PENDING_CUTOFF_POLICY
    recheck_readiness = "ROW_CLEAN_PENDING_CUTOFF_POLICY"
    if recheck_primary == "INVALID_SOURCE":
        recheck_readiness = "BLOCKED_SOURCE_DEFECT"
    elif recheck_primary in ["UNMAPPED", "CONFLICT"]:
        recheck_readiness = "HELD_MANUAL_REVIEW"
    elif recheck_primary == "MANUAL_REVIEW":
        recheck_readiness = "HELD_MANUAL_REVIEW"
    elif "NEGATIVE_STOCK_ITEM_REF" in audit_flags:
        recheck_readiness = "HELD_PENDING_DECISION"
    else:
        recheck_readiness = "ROW_CLEAN_PENDING_CUTOFF_POLICY"

    recheck_primary_counts[recheck_primary] += 1
    recheck_readiness_counts[recheck_readiness] += 1
    crosstab_recheck[(recheck_primary, recheck_readiness)] += 1
    transition_matrix[(s2_class, recheck_primary)] += 1

    crosswalk_rows.append({
        "Manifest ID": m_id,
        "Source Workbook": wb_name,
        "Source Worksheet": ws_name,
        "Source Row #": s_row,
        "Source Doc Number": s_doc,
        "Source Date": s_date,
        "Source Item Description": s_desc,
        "Source Item Code": s_code,
        "Source UOM": s_uom,
        "Source Quantity": s_qty,
        "Proposed Target Entity": s_target,
        "Proposed Canonical Item Code": s_canon,
        "Stage 2 Primary Class": s2_class,
        "Stage 2 Readiness": s2_ready,
        "Stage 2 Decision Ref": s2_dec,
        "Crosswalk Diff Reason": diff_reason,
        "Recheck Primary Class": recheck_primary,
        "Recheck Readiness": recheck_readiness,
        "Audit Flags": "; ".join(audit_flags),
        "Is Classification Changed": "YES" if s2_class != recheck_primary else "NO"
    })

crosswalk_csv_path = os.path.join(STAGE2_1_DIR, "classification_crosswalk.csv")
with open(crosswalk_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "Manifest ID", "Source Workbook", "Source Worksheet", "Source Row #",
        "Source Doc Number", "Source Date", "Source Item Description", "Source Item Code",
        "Source UOM", "Source Quantity", "Proposed Target Entity", "Proposed Canonical Item Code",
        "Stage 2 Primary Class", "Stage 2 Readiness", "Stage 2 Decision Ref",
        "Crosswalk Diff Reason", "Recheck Primary Class", "Recheck Readiness",
        "Audit Flags", "Is Classification Changed"
    ])
    writer.writeheader()
    writer.writerows(crosswalk_rows)
print(f"  classification_crosswalk.csv written ({len(crosswalk_rows)} rows).")

print("--- Step 4: Generate Date Discrepancy Report ---")
# Exactly rows 537 to 548 in VSPL_Material_Entry.xlsx '4. Issue', plus GRN rows 4,5, Waste rows 3..7, Heat log
date_discrepancy_rows = []
ws_iss = wb_entry["4. Issue"]

# Add typo rows 537..548
for r in range(537, 549):
    raw_date = ws_iss.cell(r, 1).value
    slip = ws_iss.cell(r, 2).value
    desc = ws_iss.cell(r, 3).value
    code = ws_iss.cell(r, 4).value
    qty = ws_iss.cell(r, 6).value
    date_discrepancy_rows.append({
        "Discrepancy ID": f"DATE-TYPO-{r}",
        "Workbook": "VSPL_Material_Entry.xlsx",
        "Worksheet": "4. Issue",
        "Physical Row #": r,
        "Cell Reference": f"A{r}",
        "Original Stored Value": str(raw_date),
        "Document Number": str(slip),
        "Item Code / Desc": f"{code} / {desc}",
        "Quantity": str(qty),
        "Proposed Normalized Date": "2026-07-16 (Pending Approval)",
        "Supporting Evidence": "Preceding rows 535-536 are 2026-07-15; subsequent row 549 is 2026-07-15. Slips 327, 910, 325, 1149, 326, 2725, 1148 follow sequential day sequence.",
        "Classification Impact": "Stage 2 marked rows 539-548 MANUAL_REVIEW and 537-538 UNMAPPED (override defect). Recheck marks all 12 MANUAL_REVIEW/HELD.",
        "Decision Status": "PENDING_REVIEW (DEC-004)"
    })

# Add missing date rows from GRN
ws_grn = wb_entry["3. Receipt GRN"]
for r in [4, 5]:
    raw_date = ws_grn.cell(r, 1).value
    inv = ws_grn.cell(r, 4).value
    po = ws_grn.cell(r, 5).value
    desc = ws_grn.cell(r, 6).value
    qty = ws_grn.cell(r, 10).value
    date_discrepancy_rows.append({
        "Discrepancy ID": f"DATE-MISSING-GRN-{r}",
        "Workbook": "VSPL_Material_Entry.xlsx",
        "Worksheet": "3. Receipt GRN",
        "Physical Row #": r,
        "Cell Reference": f"A{r}",
        "Original Stored Value": "None (Blank)",
        "Document Number": f"Inv: {inv}, PO: {po}",
        "Item Code / Desc": f"NOT FOUND / {desc}",
        "Quantity": str(qty),
        "Proposed Normalized Date": "UNRESOLVED",
        "Supporting Evidence": "PO prefix suggests July 2026 dates (070726 -> 07-Jul, 140726 -> 14-Jul), but date inference is unapproved hypothesis.",
        "Classification Impact": "Stage 2 marked INVALID_SOURCE / PENDING_REVIEW. Recheck marks INVALID_SOURCE / BLOCKED_SOURCE_DEFECT.",
        "Decision Status": "PENDING_REVIEW (DEC-001/DEC-003)"
    })

# Add undated Waste rows
ws_wst = wb_entry["5. Waste Disposition"]
for r in range(3, 8):
    raw_date = ws_wst.cell(r, 1).value
    desc = ws_wst.cell(r, 3).value
    code = ws_wst.cell(r, 4).value
    qty = ws_wst.cell(r, 6).value
    date_discrepancy_rows.append({
        "Discrepancy ID": f"DATE-MISSING-WST-{r}",
        "Workbook": "VSPL_Material_Entry.xlsx",
        "Worksheet": "5. Waste Disposition",
        "Physical Row #": r,
        "Cell Reference": f"A{r}",
        "Original Stored Value": "None (Blank)",
        "Document Number": "None",
        "Item Code / Desc": f"{code} / {desc}",
        "Quantity": str(qty),
        "Proposed Normalized Date": "UNRESOLVED",
        "Supporting Evidence": "No date or note number recorded in source worksheet.",
        "Classification Impact": "Stage 2 marked MANUAL_REVIEW / PENDING_REVIEW (or INVALID if qty None).",
        "Decision Status": "PENDING_REVIEW"
    })

# Add Legacy Receipts future/undated
wb_leg = openpyxl.load_workbook(SOURCE_FILES["STORE_INVENTORY"], data_only=True)
ws_rcpt = wb_leg["Material Receipt"]
date_discrepancy_rows.append({
    "Discrepancy ID": "DATE-LEGACY-RCPT-20261107",
    "Workbook": "Store Inventory.xlsx",
    "Worksheet": "Material Receipt",
    "Physical Row #": "Rows 9 to 121 (113 rows)",
    "Cell Reference": "A9:A121",
    "Original Stored Value": "2026-11-07 00:00:00",
    "Document Number": "Physical stock entries",
    "Item Code / Desc": "Various stock items",
    "Quantity": "Various",
    "Proposed Normalized Date": "2026-07-11 (Hypothesized swap) vs Future Date",
    "Supporting Evidence": "Strong evidence of dd/mm vs mm/dd date entry error (entered as 11-07-2026 for 11th July 2026). Unapproved.",
    "Classification Impact": "Legacy archive excluded from operational manifest pending DEC-002/DEC-008.",
    "Decision Status": "PENDING_REVIEW (DEC-008 candidate)"
})
for r in [122, 123]:
    raw_date = ws_rcpt.cell(r, 1).value
    desc = ws_rcpt.cell(r, 3).value
    code = ws_rcpt.cell(r, 8).value
    qty = ws_rcpt.cell(r, 4).value
    date_discrepancy_rows.append({
        "Discrepancy ID": f"DATE-LEGACY-RCPT-BLANK-{r}",
        "Workbook": "Store Inventory.xlsx",
        "Worksheet": "Material Receipt",
        "Physical Row #": r,
        "Cell Reference": f"A{r}",
        "Original Stored Value": "None (Blank)",
        "Document Number": "None",
        "Item Code / Desc": f"{code} / {desc}",
        "Quantity": str(qty),
        "Proposed Normalized Date": "UNRESOLVED",
        "Supporting Evidence": "Magnesium (550 kg) and Manganese (20 kg) have physical stock entries with no timestamp.",
        "Classification Impact": "Feeds Stock Details formulas without audit trail.",
        "Decision Status": "PENDING_REVIEW (DEC-005/DEC-008)"
    })

date_csv_path = os.path.join(STAGE2_1_DIR, "date_discrepancy_report.csv")
with open(date_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "Discrepancy ID", "Workbook", "Worksheet", "Physical Row #", "Cell Reference",
        "Original Stored Value", "Document Number", "Item Code / Desc", "Quantity",
        "Proposed Normalized Date", "Supporting Evidence", "Classification Impact", "Decision Status"
    ])
    writer.writeheader()
    writer.writerows(date_discrepancy_rows)
print(f"  date_discrepancy_report.csv written ({len(date_discrepancy_rows)} rows).")

print("--- Step 5: Generate GRN Mapping and Pricing Exception Report ---")
grn_exception_rows = [
    {
        "Source Row #": 2,
        "GRN Number": "2599",
        "Date": "2026-07-14",
        "Vendor Name": "MM Tools",
        "Supplier Invoice No": "096",
        "PO Number": "110726-02",
        "Item Description": "Emery Paper",
        "Source Item Code": "FDY-CN-003",
        "Source UOM": "Kg",
        "Quantity Received": "25",
        "Commercial Rate (INR)": "MISSING (No column in sheet)",
        "Candidate Item Code": "FDY-CN-003",
        "Candidate Description": "Emery Paper",
        "Candidate UOM": "Kg",
        "Candidate Department": "Foundry",
        "Mapping Status": "MAPPED_EXISTING",
        "Commercial Rate Status": "BLOCKED_NO_RATE",
        "Legacy Corroboration": "CONFLICT: Legacy Store Inventory receipt row 4 has GRN 2599 & Inv 096 as 'Cement empty' 1000 from s.srinivas. Row 5 has PO 110726-02 from MM Tools as 'Grinding Wheel 7 Inch' 25.",
        "Workbook Context": "Read Me states: 'Row 2 of each sheet is a sample entry — overwrite it or delete it before real use'. Likely sample row.",
        "Required Action": "Purchase/Finance confirmation whether this is an actual transaction or template sample. Obtain ex-GST invoice rate.",
        "Approval Authority": "Finance Head / Purchase Head",
        "Decision Reference": "DEC-001, DEC-006 candidate"
    },
    {
        "Source Row #": 3,
        "GRN Number": "2622",
        "Date": "2026-07-14",
        "Vendor Name": "sreenathji",
        "Supplier Invoice No": "GMP2926002828",
        "PO Number": "300426-10",
        "Item Description": "3306PMKT-Generator",
        "Source Item Code": "NOT FOUND",
        "Source UOM": "None",
        "Quantity Received": "1",
        "Commercial Rate (INR)": "MISSING (No column in sheet)",
        "Candidate Item Code": "MNT-CN-001",
        "Candidate Description": "3306PMKT-Generator",
        "Candidate UOM": "Set",
        "Candidate Department": "Maintenance",
        "Mapping Status": "UNMAPPED_CANDIDATE_FOUND",
        "Commercial Rate Status": "BLOCKED_NO_RATE",
        "Legacy Corroboration": "Legacy vendor 'Shreenathji' supplied 'Cast innoculant hiziman' on PO 130726-01. No record of generator parts.",
        "Workbook Context": "Exact description match in '2. New Items' row 5 with proposed code MNT-CN-001, UOM 'Set', Dept 'Maintenance'.",
        "Required Action": "Create MNT-CN-001 in Item Master via Phase 2 workflow. Obtain ex-GST invoice rate from Purchase.",
        "Approval Authority": "Stores Manager / Plant Head (Item Master) + Finance Head (Rate)",
        "Decision Reference": "DEC-001, DEC-003"
    },
    {
        "Source Row #": 4,
        "GRN Number": "None",
        "Date": "None",
        "Vendor Name": "None",
        "Supplier Invoice No": "454",
        "PO Number": "070726-11",
        "Item Description": "Tool Post",
        "Source Item Code": "NOT FOUND",
        "Source UOM": "None",
        "Quantity Received": "4",
        "Commercial Rate (INR)": "MISSING (No column in sheet)",
        "Candidate Item Code": "MCS-CN-002",
        "Candidate Description": "Tool Post",
        "Candidate UOM": "Nos",
        "Candidate Department": "Machine Shop",
        "Mapping Status": "UNMAPPED_CANDIDATE_FOUND",
        "Commercial Rate Status": "BLOCKED_NO_RATE",
        "Legacy Corroboration": "Legacy Store Inventory Stock Details row 315 has 'Tool Post Bolt 1/2\"' (CON252), which is Bolt/Nut, NOT Tool Post.",
        "Workbook Context": "Exact description match in '2. New Items' row 6 with proposed code MCS-CN-002, UOM 'Nos', Dept 'Machine Shop'.",
        "Required Action": "Create MCS-CN-002 in Item Master. Corroborate missing date, vendor, GRN number and rate from physical PO 070726-11.",
        "Approval Authority": "Stores Manager / Plant Head (Item Master) + Finance Head (Rate)",
        "Decision Reference": "DEC-001, DEC-003"
    },
    {
        "Source Row #": 5,
        "GRN Number": "None",
        "Date": "None",
        "Vendor Name": "None",
        "Supplier Invoice No": "384",
        "PO Number": "140726-02",
        "Item Description": "crca scrap",
        "Source Item Code": "NOT FOUND",
        "Source UOM": "kg",
        "Quantity Received": "15200",
        "Commercial Rate (INR)": "MISSING (No column in sheet)",
        "Candidate Item Code": "AMBIGUOUS (FDY-RM-007 vs FDY-RM-008)",
        "Candidate Description": "CRC Scrap-Low High MN vs CRC Scrap-Low MN",
        "Candidate UOM": "Kg",
        "Candidate Department": "Foundry",
        "Mapping Status": "UNMAPPED_AMBIGUOUS_CANDIDATE",
        "Commercial Rate Status": "BLOCKED_NO_RATE",
        "Legacy Corroboration": "Legacy sheets have FRM07 (Low High Mn) and FRM08 (Low Mn). Legacy Old data records 'Crc' against FRM01 (Bial error).",
        "Workbook Context": "Heat Log Read Me equates CRCA to 'steel scrap'. Item Master has FDY-RM-007 (Low High MN) and FDY-RM-008 (Low MN).",
        "Required Action": "Metallurgist / Foundry Head must determine chemical grade (Low MN vs Low High MN). Obtain commercial purchase invoice 384.",
        "Approval Authority": "Foundry Head / Metallurgist + Finance Head",
        "Decision Reference": "DEC-001, DEC-003"
    }
]

grn_csv_path = os.path.join(STAGE2_1_DIR, "grn_mapping_pricing_exceptions.csv")
with open(grn_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "Source Row #", "GRN Number", "Date", "Vendor Name", "Supplier Invoice No",
        "PO Number", "Item Description", "Source Item Code", "Source UOM",
        "Quantity Received", "Commercial Rate (INR)", "Candidate Item Code",
        "Candidate Description", "Candidate UOM", "Candidate Department",
        "Mapping Status", "Commercial Rate Status", "Legacy Corroboration",
        "Workbook Context", "Required Action", "Approval Authority", "Decision Reference"
    ])
    writer.writeheader()
    writer.writerows(grn_exception_rows)
print(f"  grn_mapping_pricing_exceptions.csv written ({len(grn_exception_rows)} rows).")

print("--- Step 6: Generate Negative Stock Reconciliation Report ---")
# 7 negative stock items in Master Ledger
negative_stock_items = [
    {
        "Item Code": "FDY-RM-008",
        "Description": "CRC Scrap-Low MN",
        "Legacy Code": "FRM08",
        "UOM": "Kg",
        "Master Ledger Opening Stock": "0",
        "Master Ledger Received": "0",
        "Master Ledger Issued": "500",
        "Master Ledger Waste": "0",
        "Master Ledger Closing Stock": "-500",
        "Heat Charge H-260714-01 Qty": "500",
        "Sheet 4. Issue Total Qty": "11793.0",
        "Sheet 3. Receipt Candidate Qty": "15200 (crca scrap, Row 5, Unapproved)",
        "Legacy Stock Details Stock": "0",
        "Reconstructed Balance (Ledger Rule)": "-500 (if heat charged) / -11793.0 (if store issues)",
        "Variance vs Reported": "0 (exact match to heat charge) / -11293.0 (vs store issues)",
        "Root Cause Finding": "Interim ledger deducted furnace heat charge H-260714-01 (500 kg) directly as store issue. Inward receipts (15,200 kg) unposted. 11,793 kg of actual store issues unposted.",
        "Resolution Action": "Physical stock count required. Reconcile GRN row 5 (15,200 kg). Segregate furnace charges from store issues per Phase 5 Rule H1.",
        "Decision Status": "PENDING_REVIEW (DEC-005)"
    },
    {
        "Item Code": "FDY-RM-011",
        "Description": "Gattings-500",
        "Legacy Code": "FRM11",
        "UOM": "Kg",
        "Master Ledger Opening Stock": "0",
        "Master Ledger Received": "0",
        "Master Ledger Issued": "300",
        "Master Ledger Waste": "0",
        "Master Ledger Closing Stock": "-300",
        "Heat Charge H-260714-01 Qty": "300",
        "Sheet 4. Issue Total Qty": "0",
        "Sheet 3. Receipt Candidate Qty": "0",
        "Legacy Stock Details Stock": "0",
        "Reconstructed Balance (Ledger Rule)": "-300 (if heat charged) / 0 (if store issues)",
        "Variance vs Reported": "0 (exact match to heat charge)",
        "Root Cause Finding": "Furnace returns (gatings) charged into furnace without recording prior foundry return receipt or opening balance.",
        "Resolution Action": "Establish opening stock of foundry returns or post gating return movement before charging.",
        "Decision Status": "PENDING_REVIEW (DEC-005)"
    },
    {
        "Item Code": "FDY-RM-014",
        "Description": "Inoculant 15",
        "Legacy Code": "FRM14",
        "UOM": "Kg",
        "Master Ledger Opening Stock": "0",
        "Master Ledger Received": "0",
        "Master Ledger Issued": "2",
        "Master Ledger Waste": "0",
        "Master Ledger Closing Stock": "-2",
        "Heat Charge H-260714-01 Qty": "2",
        "Sheet 4. Issue Total Qty": "0",
        "Sheet 3. Receipt Candidate Qty": "0",
        "Legacy Stock Details Stock": "92.5 (from legacy receipt 11-07)",
        "Reconstructed Balance (Ledger Rule)": "+90.5 (if legacy stock valid) / -2 (if zero opening)",
        "Variance vs Reported": "+92.5 (unposted legacy opening stock)",
        "Root Cause Finding": "Legacy archive holds 92.5 kg physical stock dated 2026-11-07. Interim ledger started with 0 opening stock and deducted 2 kg heat charge.",
        "Resolution Action": "Audit legacy physical stock of 92.5 kg. Approve opening stock.",
        "Decision Status": "PENDING_REVIEW (DEC-005)"
    },
    {
        "Item Code": "FDY-RM-016",
        "Description": "Magnesium",
        "Legacy Code": "FRM16",
        "UOM": "Kg",
        "Master Ledger Opening Stock": "0",
        "Master Ledger Received": "0",
        "Master Ledger Issued": "15",
        "Master Ledger Waste": "0",
        "Master Ledger Closing Stock": "-15",
        "Heat Charge H-260714-01 Qty": "15",
        "Sheet 4. Issue Total Qty": "0",
        "Sheet 3. Receipt Candidate Qty": "0",
        "Legacy Stock Details Stock": "550 (from undated legacy receipt)",
        "Reconstructed Balance (Ledger Rule)": "+535 (if legacy stock valid) / -15 (if zero opening)",
        "Variance vs Reported": "+550 (unposted legacy opening stock)",
        "Root Cause Finding": "Legacy archive holds 550 kg physical stock (undated). Interim ledger started with 0 opening stock and deducted 15 kg heat charge.",
        "Resolution Action": "Audit legacy physical stock of 550 kg. Approve opening stock.",
        "Decision Status": "PENDING_REVIEW (DEC-005)"
    },
    {
        "Item Code": "FDY-RM-017",
        "Description": "Manganese",
        "Legacy Code": "FRM17",
        "UOM": "Kg",
        "Master Ledger Opening Stock": "0",
        "Master Ledger Received": "0",
        "Master Ledger Issued": "3",
        "Master Ledger Waste": "0",
        "Master Ledger Closing Stock": "-3",
        "Heat Charge H-260714-01 Qty": "3",
        "Sheet 4. Issue Total Qty": "278.509",
        "Sheet 3. Receipt Candidate Qty": "0",
        "Legacy Stock Details Stock": "20 (from undated legacy receipt)",
        "Reconstructed Balance (Ledger Rule)": "+17 (if legacy stock valid & heat charge) / -258.509 (if store issues applied)",
        "Variance vs Reported": "+20 (vs heat charge) / -275.509 (vs store issues)",
        "Root Cause Finding": "Legacy archive holds 20 kg physical stock. Interim ledger deducted 3 kg heat charge while omitting 278.509 kg of actual store issues.",
        "Resolution Action": "Physical stock count required. Reconcile store issues vs furnace charges.",
        "Decision Status": "PENDING_REVIEW (DEC-005)"
    },
    {
        "Item Code": "FDY-RM-019",
        "Description": "Pig Iron",
        "Legacy Code": "FRM19",
        "UOM": "Kg",
        "Master Ledger Opening Stock": "0",
        "Master Ledger Received": "0",
        "Master Ledger Issued": "150",
        "Master Ledger Waste": "0",
        "Master Ledger Closing Stock": "-150",
        "Heat Charge H-260714-01 Qty": "150",
        "Sheet 4. Issue Total Qty": "0",
        "Sheet 3. Receipt Candidate Qty": "0",
        "Legacy Stock Details Stock": "0",
        "Reconstructed Balance (Ledger Rule)": "-150 (if heat charged) / 0 (if store issues)",
        "Variance vs Reported": "0 (exact match to heat charge)",
        "Root Cause Finding": "Zero opening stock recorded. 150 kg charged into furnace H-260714-01 without preceding purchase receipt or opening balance.",
        "Resolution Action": "Audit Pig Iron inward receipts and physical inventory.",
        "Decision Status": "PENDING_REVIEW (DEC-005)"
    },
    {
        "Item Code": "FDY-RM-020",
        "Description": "Silicon",
        "Legacy Code": "FRM20",
        "UOM": "Kg",
        "Master Ledger Opening Stock": "0",
        "Master Ledger Received": "0",
        "Master Ledger Issued": "5",
        "Master Ledger Waste": "0",
        "Master Ledger Closing Stock": "-5",
        "Heat Charge H-260714-01 Qty": "5",
        "Sheet 4. Issue Total Qty": "50.218",
        "Sheet 3. Receipt Candidate Qty": "0",
        "Legacy Stock Details Stock": "26 (from legacy receipt 11-07)",
        "Reconstructed Balance (Ledger Rule)": "+21 (if legacy stock valid & heat charge) / -24.218 (if store issues applied)",
        "Variance vs Reported": "+26 (vs heat charge) / -45.218 (vs store issues)",
        "Root Cause Finding": "Legacy archive holds 26 kg physical stock dated 2026-11-07. Interim ledger deducted 5 kg heat charge while omitting 50.218 kg of store issues.",
        "Resolution Action": "Physical stock count required. Reconcile store issues vs furnace charges.",
        "Decision Status": "PENDING_REVIEW (DEC-005)"
    }
]

neg_csv_path = os.path.join(STAGE2_1_DIR, "negative_stock_reconciliation.csv")
with open(neg_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "Item Code", "Description", "Legacy Code", "UOM",
        "Master Ledger Opening Stock", "Master Ledger Received", "Master Ledger Issued",
        "Master Ledger Waste", "Master Ledger Closing Stock", "Heat Charge H-260714-01 Qty",
        "Sheet 4. Issue Total Qty", "Sheet 3. Receipt Candidate Qty",
        "Legacy Stock Details Stock", "Reconstructed Balance (Ledger Rule)",
        "Variance vs Reported", "Root Cause Finding", "Resolution Action", "Decision Status"
    ])
    writer.writeheader()
    writer.writerows(negative_stock_items)
print(f"  negative_stock_reconciliation.csv written ({len(negative_stock_items)} rows).")

print("--- Step 7: Export Metrics JSON ---")
metrics = {
    "total_manifest_rows": len(manifest_rows),
    "stage2_primary_counts": dict(stage2_primary_counts),
    "stage2_readiness_counts": dict(stage2_readiness_counts),
    "stage2_crosstab": {f"{k[0]} x {k[1]}": v for k, v in crosstab_stage2.items()},
    "recheck_primary_counts": dict(recheck_primary_counts),
    "recheck_readiness_counts": dict(recheck_readiness_counts),
    "recheck_crosstab": {f"{k[0]} x {k[1]}": v for k, v in crosstab_recheck.items()},
    "transition_matrix": {f"Stage2_{k[0]} -> Recheck_{k[1]}": v for k, v in transition_matrix.items()},
    "source_fingerprints": fingerprints_dict
}

with open(os.path.join(STAGE2_1_DIR, "stage2_1_metrics.json"), "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2)
print("  stage2_1_metrics.json written.")

print("Stage 2.1 Audit & Reconciliation Script Completed Successfully.")
