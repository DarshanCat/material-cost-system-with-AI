"""
VSPL Material Management & Costing System — Phase 7 Stage 2 Decision Register & Migration Manifest Generator
STRICTLY READ-ONLY & ISOLATED STAGING ARTIFACT GENERATOR:
- ZERO database writes
- ZERO data mutations
- Generates decision register CSV & Markdown
- Generates full proposed migration manifest CSV for all source entities
- Classifies records strictly according to evidence
"""

import os
import hashlib
import csv
import datetime
from decimal import Decimal, InvalidOperation
from collections import Counter
import openpyxl

OUT_DIR = r"c:\VSPL_MM\Material managment system\docs\reports\phase7_stage2"
os.makedirs(OUT_DIR, exist_ok=True)

print("Starting Phase 7 Stage 2 Staging Manifest & Decision Register Generation...")

# ==============================================================================
# 1. GENERATE DECISION REGISTER (CSV & MD)
# ==============================================================================
DECISION_REGISTER = [
    {
        "issue_id": "DEC-001",
        "title": "Missing Commercial Ex-GST Rates on Historical Receipts",
        "workbook": "VSPL_Material_Entry.xlsx",
        "worksheet": "3. Receipt GRN",
        "source_rows": "Rows 2 to 5",
        "original_value": "No rate_ex_gst or unit rate column exists in sheet",
        "problem_nature": "External GRN receipts cannot establish weighted-average inventory valuation or cost journals without commercial purchase rates.",
        "proposed_resolution": "Stage GRN receipts with status 'DRAFT' and rate_ex_gst=NULL. Require Purchase/Finance to approve commercial rates via Purchase Order or Vendor Invoice audit before posting to live ledger.",
        "approver": "Finance Head / Purchase Head",
        "decision_status": "PENDING_REVIEW",
        "evidence_ref": "Rule C1 (ex-GST receipt rate mandatory for weighted-average cost calculation); VSPL_Material_Entry.xlsx sheet '3. Receipt GRN'",
        "qty_reconciliation_impact": "None (quantities can be staged and tracked in physical units).",
        "costing_impact": "BLOCKING: Costing engine cannot compute weighted-average rates or inventory value for receipted items.",
        "blocks_migration": "YES (for live costing); NO (for staging preview only)"
    },
    {
        "issue_id": "DEC-002",
        "title": "Treatment of July 2026 Transactions Relative to 12-Oct-2026 Cutoff",
        "workbook": "VSPL_Material_Entry.xlsx, Store Inventory.xlsx, VSPL_Foundry_Heat_Log.xlsx",
        "worksheet": "4. Issue, Old data, Material Receipt, Heat Log",
        "source_rows": "All transaction rows spanning 2026-07-08 to 2026-07-22",
        "original_value": "Dates in range 2026-07-08 to 2026-07-22",
        "problem_nature": "All historical source spreadsheets date from July 2026, whereas settings.COSTING_START_DATE is strictly 12 October 2026 (~3 months gap).",
        "proposed_resolution": "Designate July 2026 records as 'Historical Audit Archive'. Net closing stock as of July 2026 must be audited and rolled forward to form the authoritative 'Opening Stock' baseline on 12-Oct-2026.",
        "approver": "Managing Director / Systems Architect",
        "decision_status": "PENDING_REVIEW",
        "evidence_ref": "settings.COSTING_START_DATE = '2026-10-12'; Rule C3 (strict cutoff date governance)",
        "qty_reconciliation_impact": "Determines whether opening stock on 12-Oct-2026 is derived from July roll-forward or a new physical count.",
        "costing_impact": "BLOCKING: Without roll-forward or October physical audit, opening balances lack verified quantities and valuation.",
        "blocks_migration": "YES"
    },
    {
        "issue_id": "DEC-003",
        "title": "Unmatched Item Descriptions in GRN Receipts",
        "workbook": "VSPL_Material_Entry.xlsx",
        "worksheet": "3. Receipt GRN",
        "source_rows": "Rows 3, 4, 5",
        "original_value": "Item Code = 'NOT FOUND' for '3306PMKT-Generator' (Row 3), 'Tool Post' (Row 4), 'crca scrap' (Row 5)",
        "problem_nature": "Receipt lines carry 'NOT FOUND' as Item Code and do not match canonical items in VSPL_Item_Master.xlsx.",
        "proposed_resolution": "Approve new item codes from '2. New Items' sheet: map '3306PMKT-Generator' -> 'MNT-CN-001', 'Tool Post' -> 'MCS-CN-002', and map 'crca scrap' (15,200 kg) -> 'FDY-RM-008' (CRC Scrap-Low MN).",
        "approver": "Stores Manager / Plant Head",
        "decision_status": "PENDING_REVIEW",
        "evidence_ref": "VSPL_Material_Entry.xlsx sheet '2. New Items' defines MNT-CN-001 and MCS-CN-002; FDY-RM-008 is canonical CRCA scrap",
        "qty_reconciliation_impact": "Directly impacts stock ledger for Maintenance, Machine Shop, and Foundry raw materials (15,200 kg scrap).",
        "costing_impact": "HIGH: 15,200 kg CRCA scrap receipt would dramatically impact weighted-average melt rate.",
        "blocks_migration": "YES (until item codes are formally approved)"
    },
    {
        "issue_id": "DEC-004",
        "title": "Corrupted Date Typo '7-16-20236' in Issue Slips",
        "workbook": "VSPL_Material_Entry.xlsx",
        "worksheet": "4. Issue",
        "source_rows": "Rows 537 to 548 (12 rows)",
        "original_value": "Date = '7-16-20236'",
        "problem_nature": "Year 20236 is a human typographical error for 2026-07-16 occurring on slips 325, 326, 327, 910, 1148, 1149, 2725.",
        "proposed_resolution": "Approve transformation rule: Parse string '7-16-20236' as date '2026-07-16'. Preserve original string in audit remarks.",
        "approver": "Stores Supervisor / QA Lead",
        "decision_status": "PENDING_REVIEW",
        "evidence_ref": "Sequential context: row 536 is 2026-07-15, row 549 is 2026-07-15; slips match July 2026 serial numbers",
        "qty_reconciliation_impact": "Enables 12 issue transactions (slips for paint, rope, grinding wheels, belts) to be dated and sequenced correctly.",
        "costing_impact": "LOW (consumables and packing; does not affect furnace melt rate directly).",
        "blocks_migration": "NO (if approved prior to migration)"
    },
    {
        "issue_id": "DEC-005",
        "title": "Negative Closing Stock Balances in Interim Master Ledger",
        "workbook": "VSPL_Master_Ledger.xlsx & VSPL_Foundry_Heat_Log.xlsx",
        "worksheet": "Ledger & Charge Details",
        "source_rows": "Ledger rows 9, 12, 15, 17, 18, 20, 21 (FDY-RM-008, 011, 014, 016, 017, 019, 020)",
        "original_value": "Closing stock: -500 kg, -300 kg, -2 kg, -15 kg, -3 kg, -150 kg, -5 kg",
        "problem_nature": "Interim Master Ledger logged furnace heat issue quantities (from Heat H-260714-01) starting from zero opening stock without prior receipt, causing negative closing inventory.",
        "proposed_resolution": "Stock ledger rule enforcement: Do not post furnace charge lines as independent issues (Rule H1 / Rule C5). Establish verified opening balances from legacy 'Stock Details' (FRM14: 92.5 kg, FRM16: 550 kg, FRM17: 20 kg, FRM20: 26 kg) and record external GRN for CRCA scrap (15,200 kg) to maintain strictly positive stock.",
        "approver": "Plant Head / Senior Inventory Auditor",
        "decision_status": "PENDING_REVIEW",
        "evidence_ref": "VSPL_Foundry_Heat_Log.xlsx sheet 'Charge Details' Heat H-260714-01 exactly matches the 7 negative ledger quantities!",
        "qty_reconciliation_impact": "CRITICAL: Resolves false negative stock balances across all 7 foundry raw materials.",
        "costing_impact": "CRITICAL: Negative stock suspends costing under Rule C4. Establishing positive baseline allows continuous rate calculation.",
        "blocks_migration": "YES (negative stock must be resolved before write-enabled ledger posting)"
    }
]

# Write Decision Register CSV
dec_csv_path = os.path.join(OUT_DIR, "migration_decision_register.csv")
with open(dec_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Issue ID", "Title", "Workbook", "Worksheet", "Source Rows", "Original Value",
        "Problem Nature", "Proposed Resolution", "Approver Role", "Decision Status",
        "Approval Evidence / Reference", "Quantity Reconciliation Impact", "Costing Impact", "Blocks Migration"
    ])
    for d in DECISION_REGISTER:
        writer.writerow([
            d["issue_id"], d["title"], d["workbook"], d["worksheet"], d["source_rows"], d["original_value"],
            d["problem_nature"], d["proposed_resolution"], d["approver"], d["decision_status"],
            d["evidence_ref"], d["qty_reconciliation_impact"], d["costing_impact"], d["blocks_migration"]
        ])

# Write Decision Register Markdown
dec_md_path = os.path.join(OUT_DIR, "MIGRATION_DECISION_REGISTER.md")
with open(dec_md_path, "w", encoding="utf-8") as f:
    f.write("# VSPL Material Management & Costing System — Historical Migration Decision Register\n\n")
    f.write("**Status:** OFFICIAL MIGRATION GOVERNANCE ARTIFACT (STAGE 2)\n")
    f.write(f"**Generated:** {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n\n")
    f.write("This register governs the five critical blockers identified during Phase 7 Stage 1. Under hard safety requirements, **no pending decision may be treated as approved**.\n\n")
    f.write("---\n\n")
    for d in DECISION_REGISTER:
        f.write(f"### {d['issue_id']}: {d['title']}\n")
        f.write(f"- **Workbook & Sheet:** `{d['workbook']}` $\\rightarrow$ `{d['worksheet']}` ({d['source_rows']})\n")
        f.write(f"- **Original Source Value:** `{d['original_value']}`\n")
        f.write(f"- **Problem Nature:** {d['problem_nature']}\n")
        f.write(f"- **Proposed Resolution:** {d['proposed_resolution']}\n")
        f.write(f"- **Required Approver:** `{d['approver']}`\n")
        f.write(f"- **Decision Status:** `{d['decision_status']}`\n")
        f.write(f"- **Evidence / Reference:** {d['evidence_ref']}\n")
        f.write(f"- **Quantity Impact:** {d['qty_reconciliation_impact']}\n")
        f.write(f"- **Costing Impact:** {d['costing_impact']}\n")
        f.write(f"- **Blocks Migration:** **{d['blocks_migration']}**\n\n")
        f.write("---\n\n")

print(f"Decision Register created at: {dec_csv_path}")

# ==============================================================================
# 2. LOAD CANONICAL MASTERS & BUILD PROPOSED MIGRATION MANIFEST
# ==============================================================================
wb_item = openpyxl.load_workbook(r"c:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Item_Master.xlsx", data_only=True)
ws_item = wb_item["Item Master"]
canonical_items = {}
legacy_map = {}
for r in ws_item.iter_rows(min_row=2, values_only=True):
    if r[0]:
        code = str(r[0]).strip()
        canonical_items[code] = {
            "code": code, "desc": r[1], "category": r[2], "dept": r[4],
            "uom": r[5], "reorder": r[6], "legacy": r[11], "orig_desc": r[12]
        }
        if r[11]:
            legacy_map[str(r[11]).strip().upper()] = code
wb_item.close()

# Manifest Entries: List of dicts representing each evaluated source row across all transaction sheets
manifest = []

# A. Process VSPL_Material_Entry.xlsx -> 4. Issue (558 rows)
wb_entry = openpyxl.load_workbook(r"c:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Material_Entry.xlsx", data_only=True)
ws_iss = wb_entry["4. Issue"]

for r_idx, r in enumerate(ws_iss.iter_rows(min_row=2, values_only=True), start=2):
    if not any(c is not None and str(c).strip() != "" for c in r):
        continue
    dt, slip, desc, code, uom, qty, section, unit, wo, dept, by, rem = r
    code_str = str(code).strip() if code else ""
    
    # Classify
    classification = "VALID_NEW_CANDIDATE"
    decision_ref = None
    finding = "Valid issue transaction candidate"
    
    # Check date typo
    is_typo_date = str(dt).strip() == "7-16-20236"
    if is_typo_date:
        classification = "MANUAL_REVIEW"
        decision_ref = "DEC-004"
        finding = "Date string '7-16-20236' is a suspected typo for 2026-07-16"
    elif not dt or not isinstance(dt, (datetime.datetime, datetime.date)):
        classification = "INVALID_SOURCE"
        finding = f"Invalid date: {dt}"
        
    # Check item code
    if not code_str or code_str in ("NOT FOUND", "None", "Na", "NA"):
        classification = "UNMAPPED"
        finding = f"Missing or unmapped item code: '{code_str}'"
    elif code_str not in canonical_items:
        classification = "UNMAPPED"
        finding = f"Item code '{code_str}' not in canonical Item Master"
        
    # Check quantity
    try:
        q_dec = Decimal(str(qty))
        if q_dec <= 0:
            classification = "INVALID_SOURCE"
            finding = f"Non-positive quantity: {qty}"
    except:
        classification = "INVALID_SOURCE"
        finding = f"Malformed quantity: {qty}"
        
    manifest.append({
        "manifest_id": f"MAN-ISS-{r_idx:04d}",
        "source_workbook": "VSPL_Material_Entry.xlsx",
        "source_worksheet": "4. Issue",
        "source_row": r_idx,
        "source_doc_number": str(slip) if slip else "",
        "source_date": str(dt) if dt else "",
        "source_item_desc": str(desc) if desc else "",
        "source_item_code": code_str,
        "source_uom": str(uom) if uom else "",
        "source_quantity": str(qty) if qty is not None else "",
        "proposed_target_entity": "material_issue_headers / material_issue_line_items",
        "proposed_item_code": canonical_items.get(code_str, {}).get("code", "UNRESOLVED"),
        "classification": classification,
        "decision_ref": decision_ref or "",
        "decision_status": "PENDING_REVIEW" if decision_ref else ("ELIGIBLE" if classification == "VALID_NEW_CANDIDATE" else "BLOCKED"),
        "audit_finding": finding
    })

# B. Process VSPL_Material_Entry.xlsx -> 3. Receipt GRN (4 rows)
ws_grn = wb_entry["3. Receipt GRN"]
for r_idx, r in enumerate(ws_grn.iter_rows(min_row=2, values_only=True), start=2):
    if not any(c is not None and str(c).strip() != "" for c in r):
        continue
    dt, grn_no, vname, inv_no, po_no, desc, code, cat, uom, qty, rem, by = r
    code_str = str(code).strip() if code else ""
    
    classification = "VALID_NEW_CANDIDATE"
    decision_ref = "DEC-001"
    finding = "Receipt valid but lacks rate_ex_gst column in source spreadsheet (DEC-001)"
    
    if code_str == "NOT FOUND":
        classification = "UNMAPPED"
        decision_ref = "DEC-003"
        finding = f"Item code 'NOT FOUND' for '{desc}' (DEC-003) & Missing rate (DEC-001)"
    elif code_str not in canonical_items:
        classification = "UNMAPPED"
        finding = f"Unmapped item code '{code_str}'"
        
    if not dt or not grn_no:
        classification = "INVALID_SOURCE"
        finding = "Missing receipt date or GRN number"
        
    manifest.append({
        "manifest_id": f"MAN-GRN-{r_idx:04d}",
        "source_workbook": "VSPL_Material_Entry.xlsx",
        "source_worksheet": "3. Receipt GRN",
        "source_row": r_idx,
        "source_doc_number": str(grn_no) if grn_no else f"PO-{po_no}",
        "source_date": str(dt) if dt else "",
        "source_item_desc": str(desc) if desc else "",
        "source_item_code": code_str,
        "source_uom": str(uom) if uom else "",
        "source_quantity": str(qty) if qty is not None else "",
        "proposed_target_entity": "grn_headers / grn_line_items",
        "proposed_item_code": canonical_items.get(code_str, {}).get("code", "UNRESOLVED"),
        "classification": classification,
        "decision_ref": decision_ref,
        "decision_status": "PENDING_REVIEW",
        "audit_finding": finding
    })

# C. Process VSPL_Material_Entry.xlsx -> 5. Waste Disposition (6 rows)
ws_wst = wb_entry["5. Waste Disposition"]
for r_idx, r in enumerate(ws_wst.iter_rows(min_row=2, values_only=True), start=2):
    if not any(c is not None and str(c).strip() != "" for c in r):
        continue
    dt, note_no, desc, code, uom, qty, w_type, reason, sec, disp_to, app_by, rem = r
    code_str = str(code).strip() if code else ""
    
    classification = "VALID_NEW_CANDIDATE"
    decision_ref = None
    finding = "Valid waste disposition record"
    
    if not dt:
        classification = "MANUAL_REVIEW"
        finding = "Missing disposition date (requires manual assignment)"
    if not note_no:
        classification = "MANUAL_REVIEW"
        finding += "; Missing disposal note number"
    if not code_str or code_str not in canonical_items:
        classification = "UNMAPPED"
        finding = f"Unmapped item code '{code_str}'"
    if qty is None:
        classification = "INVALID_SOURCE"
        finding = "Missing disposal quantity"
        
    manifest.append({
        "manifest_id": f"MAN-WST-{r_idx:04d}",
        "source_workbook": "VSPL_Material_Entry.xlsx",
        "source_worksheet": "5. Waste Disposition",
        "source_row": r_idx,
        "source_doc_number": str(note_no) if note_no else "UNASSIGNED",
        "source_date": str(dt) if dt else "",
        "source_item_desc": str(desc) if desc else "",
        "source_item_code": code_str,
        "source_uom": str(uom) if uom else "",
        "source_quantity": str(qty) if qty is not None else "",
        "proposed_target_entity": "waste_disposition_headers / waste_disposition_line_items",
        "proposed_item_code": canonical_items.get(code_str, {}).get("code", "UNRESOLVED"),
        "classification": classification,
        "decision_ref": decision_ref or "",
        "decision_status": "PENDING_REVIEW" if classification == "MANUAL_REVIEW" else ("ELIGIBLE" if classification == "VALID_NEW_CANDIDATE" else "BLOCKED"),
        "audit_finding": finding
    })
wb_entry.close()

# D. Process VSPL_Foundry_Heat_Log.xlsx -> Heat Log & Charge Details & Parts Produced
wb_heat = openpyxl.load_workbook(r"c:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Foundry_Heat_Log.xlsx", data_only=True)
ws_hl = wb_heat["Heat Log"]
for r_idx, r in enumerate(ws_hl.iter_rows(min_row=2, values_only=True), start=2):
    if not r[0]:
        continue
    h_no, dt, furn, grade, shift, tot_chg, tapped, loss, loss_pct, good, ret, rej, parts, yield_pct, rm_good, op, rem = r
    manifest.append({
        "manifest_id": f"MAN-HEAT-{r_idx:04d}",
        "source_workbook": "VSPL_Foundry_Heat_Log.xlsx",
        "source_worksheet": "Heat Log",
        "source_row": r_idx,
        "source_doc_number": str(h_no),
        "source_date": str(dt) if dt else "",
        "source_item_desc": f"Furnace {furn} Grade {grade}",
        "source_item_code": "N/A",
        "source_uom": "Kg",
        "source_quantity": str(tapped) if tapped is not None else "",
        "proposed_target_entity": "heat_headers",
        "proposed_item_code": "N/A",
        "classification": "VALID_NEW_CANDIDATE",
        "decision_ref": "DEC-002",
        "decision_status": "PENDING_REVIEW",
        "audit_finding": "Valid heat log. Does NOT create stock movements (Rule H1)."
    })

ws_cd = wb_heat["Charge Details"]
for r_idx, r in enumerate(ws_cd.iter_rows(min_row=2, values_only=True), start=2):
    if not r[0]:
        continue
    h_no, desc, code, uom, qty, pct, rem = r
    code_str = str(code).strip() if code else ""
    manifest.append({
        "manifest_id": f"MAN-CHG-{r_idx:04d}",
        "source_workbook": "VSPL_Foundry_Heat_Log.xlsx",
        "source_worksheet": "Charge Details",
        "source_row": r_idx,
        "source_doc_number": str(h_no),
        "source_date": "",
        "source_item_desc": str(desc) if desc else "",
        "source_item_code": code_str,
        "source_uom": str(uom) if uom else "",
        "source_quantity": str(qty) if qty is not None else "",
        "proposed_target_entity": "heat_charge_lines",
        "proposed_item_code": canonical_items.get(code_str, {}).get("code", "UNRESOLVED"),
        "classification": "VALID_NEW_CANDIDATE" if code_str in canonical_items else "UNMAPPED",
        "decision_ref": "DEC-005",
        "decision_status": "PENDING_REVIEW",
        "audit_finding": "Heat charge line. Strictly isolated from stock ledger (Rule H1)."
    })

ws_pp = wb_heat["Parts Produced"]
for r_idx, r in enumerate(ws_pp.iter_rows(min_row=2, values_only=True), start=2):
    if not r[0]:
        continue
    h_no, prod, grade, no_parts, unit_wt, tot_wt, rm_alloc, rem = r
    has_wt = unit_wt is not None and no_parts is not None
    manifest.append({
        "manifest_id": f"MAN-PART-{r_idx:04d}",
        "source_workbook": "VSPL_Foundry_Heat_Log.xlsx",
        "source_worksheet": "Parts Produced",
        "source_row": r_idx,
        "source_doc_number": str(h_no),
        "source_date": "",
        "source_item_desc": str(prod) if prod else "",
        "source_item_code": "N/A",
        "source_uom": "Nos",
        "source_quantity": str(no_parts) if no_parts is not None else "",
        "proposed_target_entity": "heat_parts_produced",
        "proposed_item_code": "N/A",
        "classification": "VALID_NEW_CANDIDATE" if has_wt else "MANUAL_REVIEW",
        "decision_ref": "",
        "decision_status": "ELIGIBLE" if has_wt else "PENDING_REVIEW",
        "audit_finding": "Valid part produced record" if has_wt else "Missing unit cast weight or count; cannot calculate part cost (Rule C7)"
    })
wb_heat.close()

# Write Proposed Migration Manifest CSV
manifest_csv_path = os.path.join(OUT_DIR, "proposed_migration_manifest.csv")
with open(manifest_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Manifest ID", "Source Workbook", "Source Worksheet", "Source Row #",
        "Source Doc Number", "Source Date", "Source Item Description", "Source Item Code",
        "Source UOM", "Source Quantity", "Proposed Target Entity", "Proposed Canonical Item Code",
        "Classification Status", "Decision Reference", "Decision Status", "Audit Finding"
    ])
    for m in manifest:
        writer.writerow([
            m["manifest_id"], m["source_workbook"], m["source_worksheet"], m["source_row"],
            m["source_doc_number"], m["source_date"], m["source_item_desc"], m["source_item_code"],
            m["source_uom"], m["source_quantity"], m["proposed_target_entity"], m["proposed_item_code"],
            m["classification"], m["decision_ref"], m["decision_status"], m["audit_finding"]
        ])

print(f"Proposed Migration Manifest created with {len(manifest)} rows at: {manifest_csv_path}")

# ==============================================================================
# 3. STATISTICAL SUMMARY OF PROPOSED MANIFEST
# ==============================================================================
counts = Counter(m["classification"] for m in manifest)
print("\nManifest Classification Breakdown:")
for k, v in counts.items():
    print(f"  {k:25}: {v:5} rows ({v/len(manifest)*100:.1f}%)")

eligible_count = sum(1 for m in manifest if m["decision_status"] == "ELIGIBLE")
pending_count = sum(1 for m in manifest if m["decision_status"] == "PENDING_REVIEW")
blocked_count = sum(1 for m in manifest if m["decision_status"] == "BLOCKED")

print(f"\nMigration Readiness:")
print(f"  ELIGIBLE (Safe for staged import once approved): {eligible_count}")
print(f"  PENDING_REVIEW (Awaiting Decision Sign-off):     {pending_count}")
print(f"  BLOCKED (Invalid/corrupt data rows):              {blocked_count}")
