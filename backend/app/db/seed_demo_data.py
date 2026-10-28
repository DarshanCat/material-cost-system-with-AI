"""
Comprehensive Idempotent Dummy Data Seeding for VSPL Material Management & Costing System.

Seeds realistic production-style data for Vijay Spheroidals Pvt. Ltd. (SG Iron Foundry):
1. Foundational Reference Data (8 Departments, 7 UOMs)
2. Vendors (12 realistic Indian industrial suppliers with GSTINs)
3. Material Items (24 items across raw materials, lining, moulding, tooling, maintenance, safety)
4. Material Description Aliases (linking foundry heat-log charge strings to official items)
5. Baseline Opening Stock Balances & Approved Opening Valuations (as of 12 October 2026)
6. Goods Receipt Notes (GRNs) in DRAFT, SUBMITTED, and APPROVED states (with stock postings)
7. Material Issues in DRAFT, SUBMITTED, and APPROVED states (with outward stock postings)
8. Induction Furnace Heat Logs with charge lines, tapped metal, and parts produced
9. Waste Dispositions (internal recovery & scrap outward)
10. Physical Stock Audits (variance calculations)
11. Item Requests (approval workflow)
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, Any

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_reference_data
from app.models.department import Department
from app.models.uom import UOM
from app.models.vendor import Vendor
from app.models.item import MaterialItem
from app.models.material_alias import MaterialAlias, AliasApprovalStatus
from app.models.ledger import (
    StockLedgerEntry,
    MovementType,
    SourceDocumentType,
)
from app.models.costing import (
    ItemOpeningValuation,
    OpeningValuationStatus,
    ItemOpeningValuationAuditLog,
)
from app.models.grn import (
    GRNHeader,
    GRNLineItem,
    GRNAuditLog,
    GRNStatus,
    GRNSourceType,
)
from app.models.issue import (
    MaterialIssueHeader,
    MaterialIssueLineItem,
    IssueAuditLog,
    IssueStatus,
)
from app.models.heat import (
    HeatHeader,
    HeatChargeLine,
    HeatPartsProduced,
    ProductionStatus,
    HeatChargeValidationStatus,
    CastingClassification,
)
from app.models.waste import (
    WasteDispositionHeader,
    WasteDispositionLineItem,
    WasteAuditLog,
    WasteStatus,
    WasteType,
    DispositionType,
)
from app.models.physical_audit import (
    PhysicalAuditHeader,
    PhysicalAuditLine,
    PhysicalAuditAuditLog,
    AuditStatus,
)
from app.models.item_request import (
    ItemRequest,
    ItemRequestAuditLog,
    RequestStatus,
)
from app.services.validators import normalize_vendor_name, normalize_alias_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("vspl.db.seed_demo")


def run_seed(db: Session) -> Dict[str, Any]:
    stats = {}
    
    # -------------------------------------------------------------------------
    # 1. Master Reference Data (Departments & UOMs)
    # -------------------------------------------------------------------------
    logger.info("Step 1: Checking reference data...")
    ref_res = seed_reference_data(db)
    stats["reference"] = ref_res

    dept_map = {d.code: d for d in db.execute(select(Department)).scalars().all()}
    uom_map = {u.code: u for u in db.execute(select(UOM)).scalars().all()}

    # -------------------------------------------------------------------------
    # 2. Vendors (Suppliers for SG Iron Foundry operations)
    # -------------------------------------------------------------------------
    logger.info("Step 2: Seeding vendors...")
    vendors_data = [
        {
            "name": "Tata Metaliks Limited",
            "gstin": "19AAACT2727Q1ZU",
            "address": "Tata Centre, 43 Jawaharlal Nehru Road, Kolkata, WB - 700071",
            "contact_person": "Ramesh Sen (Key Accounts)",
            "phone": "+91 33 6613 4200",
            "email": "pigiron.sales@tatametaliks.co.in",
        },
        {
            "name": "Steel Authority of India Ltd (SAIL)",
            "gstin": "03AAACS2625M1ZQ",
            "address": "Bokaro Steel City, Bokaro, Jharkhand - 827001",
            "contact_person": "Amitabh Roy",
            "phone": "+91 6542 240333",
            "email": "commercial.bsp@sail.in",
        },
        {
            "name": "Sarda Energy & Minerals Ltd",
            "gstin": "22AAACS2337E1ZZ",
            "address": "Industrial Growth Centre, Siltara, Raipur, CG - 493111",
            "contact_person": "Virendra Agrawal",
            "phone": "+91 771 221 6200",
            "email": "alloys@seml.co.in",
        },
        {
            "name": "Vesuvius India Limited",
            "gstin": "19AAACV0508N1Z4",
            "address": "P-104 Taratala Road, Kolkata, WB - 700088",
            "contact_person": "Dipankar Ghosh",
            "phone": "+91 33 3041 0600",
            "email": "orders.india@vesuvius.com",
        },
        {
            "name": "Saint-Gobain India Pvt Ltd",
            "gstin": "33AAACS7308D1ZT",
            "address": "Sigapi Achi Building, 18/3 Rukmani Lakshmipathy Road, Egmore, Chennai, TN - 600008",
            "contact_person": "K. Venkatesh",
            "phone": "+91 44 4593 6000",
            "email": "ceramics.refractories@saint-gobain.com",
        },
        {
            "name": "Ashapura Minechem Ltd",
            "gstin": "27AAACA0896C1Z9",
            "address": "Jeevan Udyog Bldg, 278 DN Road, Fort, Mumbai, MH - 400001",
            "contact_person": "Sanjay Parekh",
            "phone": "+91 22 6665 1700",
            "email": "bentonite.industrial@ashapura.com",
        },
        {
            "name": "Sandvik Coromant India",
            "gstin": "27AAACS1815H1ZW",
            "address": "Mumbai-Pune Road, Dapodi, Pune, MH - 411012",
            "contact_person": "Nitin Kulkarni",
            "phone": "+91 20 2710 4800",
            "email": "coromant.in@sandvik.com",
        },
        {
            "name": "SKF India Limited",
            "gstin": "27AAACS0645B1ZG",
            "address": "Chinchwad, Pune, MH - 411033",
            "contact_person": "Rahul Deshmukh",
            "phone": "+91 20 6611 2500",
            "email": "industrial.orders@skf.com",
        },
        {
            "name": "Castrol India Limited",
            "gstin": "27AAACC2029B1Z0",
            "address": "Technopolis Knowledge Park, Mahakali Caves Road, Andheri East, Mumbai, MH - 400093",
            "contact_person": "Sunil Nair",
            "phone": "+91 22 6698 4100",
            "email": "industrial.lubricants@castrol.com",
        },
        {
            "name": "Unbrako Fasteners",
            "gstin": "03AAACU1234D1ZF",
            "address": "Dhandari Kalan, G.T. Road, Ludhiana, PB - 141010",
            "contact_person": "Jaswant Singh",
            "phone": "+91 161 503 8000",
            "email": "sales.ht@unbrako.com",
        },
        {
            "name": "Superon Schweisstechnik India",
            "gstin": "06AAACS5678E1ZK",
            "address": "Plot 552, Phase V, Udyog Vihar, Gurugram, HR - 122016",
            "contact_person": "Rajesh Chadha",
            "phone": "+91 124 499 8700",
            "email": "blades.welding@superonindia.com",
        },
        {
            "name": "Mallcom Safety India",
            "gstin": "19AAACM4567F1ZL",
            "address": "EN-12, Sector V, Salt Lake City, Kolkata, WB - 700091",
            "contact_person": "Debasish Mukherjee",
            "phone": "+91 33 4016 1000",
            "email": "ppe.sales@mallcom.in",
        },
    ]

    vendors_added = 0
    vendor_by_name = {}
    for vd in vendors_data:
        norm = normalize_vendor_name(vd["name"])
        existing = db.execute(select(Vendor).where(Vendor.normalized_name == norm)).scalar_one_or_none()
        if not existing:
            v = Vendor(
                name=vd["name"],
                normalized_name=norm,
                gstin=vd["gstin"],
                address=vd["address"],
                contact_person=vd["contact_person"],
                phone=vd["phone"],
                email=vd["email"],
                is_active=True,
            )
            db.add(v)
            db.flush()
            vendor_by_name[vd["name"]] = v
            vendors_added += 1
        else:
            vendor_by_name[vd["name"]] = existing
    stats["vendors_added"] = vendors_added

    # -------------------------------------------------------------------------
    # 3. Material Items (Foundry raw materials, tooling, maintenance, safety)
    # -------------------------------------------------------------------------
    logger.info("Step 3: Seeding material items...")
    items_data = [
        # Raw Materials (FDY-RM)
        ("FDY-RM-001", "Pig Iron (Foundry Grade 1)", "FDY", "Raw Material", "Ferrous Raw Material", "KG", "High purity SG iron foundry pig iron (Si 1.8-2.2%, Mn < 0.2%)"),
        ("FDY-RM-002", "CRCA Steel Scrap (Low Manganese)", "FDY", "Raw Material", "Ferrous Scrap", "KG", "Clean cold rolled close annealed sheet punchings/clippings (Mn < 0.3%)"),
        ("FDY-RM-003", "Foundry In-House Returns / Runners", "FDY", "Raw Material", "Foundry Returns", "KG", "Internal SG iron clean gating, runner, riser and pig returns"),
        ("FDY-RM-004", "Ferro Silicon 75% (FeSi)", "FDY", "Raw Material", "Ferro Alloys", "KG", "Ferro Silicon 70-75% lump size 10-50mm for furnace additions"),
        ("FDY-RM-005", "Ferro Manganese HC (FeMn)", "FDY", "Raw Material", "Ferro Alloys", "KG", "High Carbon Ferro Manganese (Mn 70-75%, C 6-8%)"),
        ("FDY-RM-006", "Inoculant FeSi-Ba (SMZ)", "FDY", "Raw Material", "Inoculants", "KG", "Barium containing ladle inoculant grain size 0.2-2.0mm"),
        ("FDY-RM-007", "Carbon Raiser (CPC 98.5%)", "FDY", "Raw Material", "Carbon Additives", "KG", "Calcined Petroleum Coke C > 98.5%, S < 0.05%, N < 0.03%"),
        ("FDY-RM-008", "Pure Magnesium Granules (Nodulizer)", "FDY", "Raw Material", "Treatment Alloys", "KG", "Magnesium treatment alloy granules for sandwich nodulization"),
        # Lining Material (FDY-LN)
        ("FDY-LN-001", "Silica Ramming Mass (SVLHTC Premix)", "FDY", "Lining Material", "Refractory Linings", "KG", "Pre-mixed acidic silica ramming mass with boric acid binder for 3T induction furnace"),
        # Moulding Material (FDY-MD)
        ("FDY-MD-001", "Silica Sand AFS 45-50 (Washed & Dried)", "FDY", "Moulding Material", "Foundry Sand", "KG", "High purity washed silica sand AFS fineness 45-50 for green sand plant"),
        ("FDY-MD-002", "Foundry Bentonite Powder (Active Clay)", "FDY", "Moulding Material", "Binders", "KG", "High swelling sodium bentonite binder for green sand casting"),
        # Consumables (FDY-CN)
        ("FDY-CN-001", "Ceramic Pouring Cup 70mm", "FDY", "Consumables", "Foundry Ceramic", "NOS", "Refractory ceramic pouring cup 70mm diameter for runner gating system"),
        ("FDY-CN-002", "Ceramic Foam Filter 10 PPI (50x50x22)", "FDY", "Consumables", "Filtration", "NOS", "Silicon carbide ceramic foam molten metal filter 10 PPI"),
        # Paints & Coatings (FDY-PT)
        ("FDY-PT-001", "Zircon Alcohol-Based Mould Coating Wash", "FDY", "Paints & Coatings", "Refractory Coatings", "KG", "Zircon based refractory coating wash for sand moulds and cores"),
        # Cutting Blades (MCS-CB)
        ("MCS-CB-001", "Bi-Metal Band Saw Blade 34x1.1x3505", "MSP", "Cutting Blades", "Sawing Blades", "NOS", "M42 Cobalt bi-metal band saw blade for casting gating cut-off"),
        # Inserts & Tools (MCS-IT)
        ("MCS-IT-001", "CNMG 120408 Turning Carbide Insert", "MSP", "Inserts & Tools", "CNC Inserts", "NOS", "CVD coated carbide insert for heavy rough turning of SG iron castings"),
        ("MCS-IT-002", "WNMG 080408 Roughing Insert", "MSP", "Inserts & Tools", "CNC Inserts", "NOS", "Trigon double-sided insert for CNC facing and turning"),
        # Oils & Lubricants (MNT-OL)
        ("MNT-OL-001", "Hydraulic Oil ISO VG 68", "MNT", "Oils & Lubricants", "Hydraulic Fluids", "LTR", "Anti-wear industrial hydraulic oil for moulding line presses & power packs"),
        # Bearings (MNT-BR)
        ("MNT-BR-001", "Deep Groove Ball Bearing 6210 2Z C3", "MNT", "Bearings", "Rolling Bearings", "NOS", "Deep groove ball bearing shielded with C3 radial clearance"),
        # Bolts & Nuts (MNT-BN)
        ("MNT-BN-001", "Hex Bolt M12x50 High Tensile 8.8", "MNT", "Bolts & Nuts", "Fasteners", "NOS", "Grade 8.8 high tensile hex head bolt fully threaded"),
        # Quality Material (QLY-QC)
        ("QLY-QC-001", "Thermal Analysis Tellurium Coated Sample Cup", "QLT", "Quality Material", "Lab Consumables", "NOS", "Quick-cup tellurium coated for carbon equivalent liquid metal analysis"),
        # Packing Material (PKD-PK)
        ("PKD-PK-001", "Export Quality Wooden Pallet 1200x1000mm", "PKG", "Packing Material", "Pallets", "NOS", "Heat-treated ISPM-15 compliant four-way wooden export pallet"),
        # Fuel (UTL-FU)
        ("UTL-FU-001", "High Speed Diesel (HSD)", "GNS", "Fuel", "Plant Fuel", "LTR", "Commercial grade diesel for backup DG set and ladle preheater"),
        # Safety Material (GEN-SF)
        ("GEN-SF-001", "Split Leather Heat Resistant Foundry Gloves", "GNS", "Safety Material", "Foundry PPE", "SET", "16-inch heavy split leather heat and molten metal splash resistant gloves"),
    ]

    items_added = 0
    item_by_code = {}
    for code, name, dept_code, category, subcat, uom_code, desc in items_data:
        existing = db.execute(select(MaterialItem).where(MaterialItem.item_code == code)).scalar_one_or_none()
        dept = dept_map[dept_code]
        uom = uom_map[uom_code]
        if not existing:
            item = MaterialItem(
                item_code=code,
                name=name,
                department_id=dept.id,
                category=category,
                subcategory=subcat,
                base_uom_id=uom.id,
                description=desc,
                is_active=True,
            )
            db.add(item)
            db.flush()
            item_by_code[code] = item
            items_added += 1
        else:
            item_by_code[code] = existing
    stats["items_added"] = items_added

    # -------------------------------------------------------------------------
    # 4. Material Description Aliases
    # -------------------------------------------------------------------------
    logger.info("Step 4: Seeding material aliases...")
    aliases_data = [
        ("CRC Scrap", "FDY-RM-002"),
        ("Pig Iron Gr1", "FDY-RM-001"),
        ("FeSi 75%", "FDY-RM-004"),
        ("FeMn HC", "FDY-RM-005"),
        ("Foundry Returns", "FDY-RM-003"),
        ("CPC Carbon Raiser", "FDY-RM-007"),
    ]
    aliases_added = 0
    for alias_text, item_code in aliases_data:
        norm_key = normalize_alias_key(alias_text)
        existing = db.execute(select(MaterialAlias).where(MaterialAlias.normalized_alias_key == norm_key)).scalar_one_or_none()
        if not existing and item_code in item_by_code:
            target_item = item_by_code[item_code]
            alias = MaterialAlias(
                alias_text=alias_text,
                normalized_alias_key=norm_key,
                material_item_id=target_item.id,
                is_active=True,
                status=AliasApprovalStatus.APPROVED.value,
                reviewer_id="usr_mgmt_01",
                reviewed_at=datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc),
                decision_notes="Approved alias mapping for furnace heat log charges.",
                created_by="usr_foundry_01",
            )
            db.add(alias)
            aliases_added += 1
    stats["aliases_added"] = aliases_added

    # -------------------------------------------------------------------------
    # 5. Baseline Opening Stock Balances & Approved Opening Valuations (12 Oct 2026)
    # -------------------------------------------------------------------------
    logger.info("Step 5: Seeding opening stock balances & valuations...")
    baseline_date = date(2026, 10, 12)
    opening_balances_data = [
        # (item_code, opening_qty, rate_ex_gst)
        ("FDY-RM-001", Decimal("25000.0000"), Decimal("45.50")),  # Pig Iron
        ("FDY-RM-002", Decimal("35000.0000"), Decimal("36.20")),  # Steel Scrap
        ("FDY-RM-003", Decimal("12000.0000"), Decimal("38.00")),  # Returns
        ("FDY-RM-004", Decimal("2500.0000"), Decimal("110.00")),  # FeSi
        ("FDY-RM-005", Decimal("1800.0000"), Decimal("86.50")),   # FeMn
        ("FDY-RM-006", Decimal("450.0000"), Decimal("145.00")),   # Inoculant
        ("FDY-RM-007", Decimal("1200.0000"), Decimal("62.00")),   # Carbon Raiser
        ("FDY-RM-008", Decimal("300.0000"), Decimal("320.00")),   # Magnesium
        ("FDY-LN-001", Decimal("8000.0000"), Decimal("18.00")),   # Ramming Mass
        ("FDY-MD-001", Decimal("20000.0000"), Decimal("3.80")),   # Silica Sand
        ("FDY-MD-002", Decimal("5000.0000"), Decimal("9.20")),    # Bentonite
        ("FDY-CN-001", Decimal("500.0000"), Decimal("42.00")),    # Pouring Cup
        ("FDY-CN-002", Decimal("300.0000"), Decimal("125.00")),   # Ceramic Filter
        ("FDY-PT-001", Decimal("400.0000"), Decimal("180.00")),   # Zircon Wash
        ("MCS-CB-001", Decimal("25.0000"), Decimal("1850.00")),   # Band Saw Blade
        ("MCS-IT-001", Decimal("120.0000"), Decimal("375.00")),   # CNMG Insert
        ("MCS-IT-002", Decimal("80.0000"), Decimal("390.00")),    # WNMG Insert
        ("MNT-OL-001", Decimal("630.0000"), Decimal("160.00")),   # Hydraulic Oil
        ("MNT-BR-001", Decimal("36.0000"), Decimal("850.00")),    # Ball Bearing
        ("MNT-BN-001", Decimal("250.0000"), Decimal("18.50")),    # Hex Bolt
        ("QLY-QC-001", Decimal("400.0000"), Decimal("65.00")),    # Tellurium Cup
        ("PKD-PK-001", Decimal("150.0000"), Decimal("750.00")),   # Pallet
        ("UTL-FU-001", Decimal("1500.0000"), Decimal("88.00")),   # Diesel
        ("GEN-SF-001", Decimal("80.0000"), Decimal("450.00")),    # Foundry Gloves
    ]

    ob_ledger_added = 0
    ob_val_added = 0
    for idx, (code, qty, rate) in enumerate(opening_balances_data, start=1):
        item = item_by_code[code]
        # Check if ledger entry already exists
        existing_ledger = db.execute(
            select(StockLedgerEntry).where(
                StockLedgerEntry.source_document_type == SourceDocumentType.OPENING_BALANCE.value,
                StockLedgerEntry.source_line_id == item.id,
            )
        ).scalar_one_or_none()

        if not existing_ledger:
            entry = StockLedgerEntry(
                entry_number=f"ENT-20261012-{idx:04d}",
                posting_group_id="OB-20261012-INITIAL",
                material_item_id=item.id,
                uom_id=item.base_uom_id,
                transaction_date=baseline_date,
                posted_at=datetime(2026, 10, 12, 8, 0, 0, tzinfo=timezone.utc),
                movement_type=MovementType.OPENING_BALANCE.value,
                quantity_delta=qty,
                source_document_type=SourceDocumentType.OPENING_BALANCE.value,
                source_document_id=0,
                source_line_id=item.id,
                source_document_number="OB-20261012",
                reference_number="AUDIT-OB-2026-10-12",
                reason=f"Approved baseline physical inventory balance as of {baseline_date}.",
                posted_by="usr_admin_01",
            )
            db.add(entry)
            ob_ledger_added += 1

        # Check opening valuation
        existing_val = db.execute(
            select(ItemOpeningValuation).where(
                ItemOpeningValuation.material_item_id == item.id,
                ItemOpeningValuation.version == 1,
            )
        ).scalar_one_or_none()

        if not existing_val:
            val = ItemOpeningValuation(
                material_item_id=item.id,
                version=1,
                baseline_date=baseline_date,
                opening_rate_ex_gst=rate,
                status=OpeningValuationStatus.APPROVED.value,
                created_by="usr_stores_01",
                approved_by="usr_mgmt_01",
                approved_at=datetime(2026, 10, 12, 9, 30, 0, tzinfo=timezone.utc),
                notes="Management-authorized opening stock valuation rate per unit.",
            )
            db.add(val)
            db.flush()
            audit = ItemOpeningValuationAuditLog(
                valuation_id=val.id,
                action="APPROVED",
                from_status=OpeningValuationStatus.PROPOSED.value,
                to_status=OpeningValuationStatus.APPROVED.value,
                actor_id="usr_mgmt_01",
                comments="Initial baseline valuation signed off by Plant Finance.",
                timestamp=datetime(2026, 10, 12, 9, 30, 0, tzinfo=timezone.utc),
            )
            db.add(audit)
            ob_val_added += 1

    stats["ob_ledger_added"] = ob_ledger_added
    stats["ob_val_added"] = ob_val_added

    # -------------------------------------------------------------------------
    # 6. Goods Receipt Notes (GRNs)
    # -------------------------------------------------------------------------
    logger.info("Step 6: Seeding Goods Receipt Notes (GRNs)...")
    grns_added = 0
    grn_ledger_added = 0

    # GRN 1: Approved - Tata Metaliks Pig Iron
    grn1_num = "GRN-20261014-0001"
    existing_grn1 = db.execute(select(GRNHeader).where(GRNHeader.grn_number == grn1_num)).scalar_one_or_none()
    if not existing_grn1:
        v_tata = vendor_by_name["Tata Metaliks Limited"]
        grn1 = GRNHeader(
            grn_number=grn1_num,
            receipt_date=date(2026, 10, 14),
            source_type=GRNSourceType.EXTERNAL_VENDOR.value,
            vendor_id=v_tata.id,
            vendor_invoice_no="TM/INV/2026/4102",
            invoice_date=date(2026, 10, 13),
            reference_document="PO-VSPL-2026-0891",
            notes="Consignment received in weighbridge Bay 1. Weighment slip #WB-8812 verified.",
            status=GRNStatus.APPROVED.value,
            created_by="usr_stores_01",
            created_at=datetime(2026, 10, 14, 11, 0, 0, tzinfo=timezone.utc),
        )
        db.add(grn1)
        db.flush()

        it_pig = item_by_code["FDY-RM-001"]
        line1 = GRNLineItem(
            grn_id=grn1.id,
            line_number=1,
            material_item_id=it_pig.id,
            uom_id=it_pig.base_uom_id,
            quantity=Decimal("12000.0000"),
            rate_ex_gst=Decimal("46.00"),
            gst_percent=Decimal("18.00"),
            remarks="Visual inspection clear; slag-free pig iron bundles.",
        )
        db.add(line1)
        db.flush()

        # Audit logs (Submitted + Approved)
        db.add(GRNAuditLog(grn_id=grn1.id, action="SUBMITTED", from_status="DRAFT", to_status="SUBMITTED", actor_id="usr_stores_01", comments="Weighment complete, submitted for QA approval."))
        db.add(GRNAuditLog(grn_id=grn1.id, action="APPROVED", from_status="SUBMITTED", to_status="APPROVED", actor_id="usr_admin_01", comments="Spectro analysis chemistry verified. Approved."))

        # Post to append-only stock ledger
        db.add(StockLedgerEntry(
            entry_number="ENT-20261014-0001",
            posting_group_id=f"GRN-{grn1.id}",
            material_item_id=it_pig.id,
            uom_id=it_pig.base_uom_id,
            transaction_date=date(2026, 10, 14),
            posted_at=datetime(2026, 10, 14, 14, 30, 0, tzinfo=timezone.utc),
            movement_type=MovementType.INWARD_RECEIPT.value,
            quantity_delta=Decimal("12000.0000"),
            source_document_type=SourceDocumentType.GRN.value,
            source_document_id=grn1.id,
            source_line_id=line1.id,
            source_document_number=grn1.grn_number,
            reference_number="PO-VSPL-2026-0891",
            reason=f"GRN Inward receipt from Tata Metaliks Limited (Inv: TM/INV/2026/4102)",
            posted_by="usr_admin_01",
        ))
        grns_added += 1
        grn_ledger_added += 1

    # GRN 2: Approved - Sarda Energy Ferro Alloys
    grn2_num = "GRN-20261016-0001"
    existing_grn2 = db.execute(select(GRNHeader).where(GRNHeader.grn_number == grn2_num)).scalar_one_or_none()
    if not existing_grn2:
        v_sarda = vendor_by_name["Sarda Energy & Minerals Ltd"]
        grn2 = GRNHeader(
            grn_number=grn2_num,
            receipt_date=date(2026, 10, 16),
            source_type=GRNSourceType.EXTERNAL_VENDOR.value,
            vendor_id=v_sarda.id,
            vendor_invoice_no="SEML-OCT-0941",
            invoice_date=date(2026, 10, 15),
            reference_document="PO-VSPL-2026-0902",
            notes="Ferro alloy drums received intact with manufacturer test certificate.",
            status=GRNStatus.APPROVED.value,
            created_by="usr_stores_01",
            created_at=datetime(2026, 10, 16, 10, 15, 0, tzinfo=timezone.utc),
        )
        db.add(grn2)
        db.flush()

        it_fesi = item_by_code["FDY-RM-004"]
        it_femn = item_by_code["FDY-RM-005"]
        line2_1 = GRNLineItem(
            grn_id=grn2.id,
            line_number=1,
            material_item_id=it_fesi.id,
            uom_id=it_fesi.base_uom_id,
            quantity=Decimal("1500.0000"),
            rate_ex_gst=Decimal("112.50"),
            gst_percent=Decimal("18.00"),
            remarks="FeSi 75% batch SEML-75-901",
        )
        line2_2 = GRNLineItem(
            grn_id=grn2.id,
            line_number=2,
            material_item_id=it_femn.id,
            uom_id=it_femn.base_uom_id,
            quantity=Decimal("800.0000"),
            rate_ex_gst=Decimal("88.00"),
            gst_percent=Decimal("18.00"),
            remarks="FeMn HC batch SEML-HC-440",
        )
        db.add_all([line2_1, line2_2])
        db.flush()

        db.add(GRNAuditLog(grn_id=grn2.id, action="SUBMITTED", from_status="DRAFT", to_status="SUBMITTED", actor_id="usr_stores_01", comments="Unloaded and verified against packing list."))
        db.add(GRNAuditLog(grn_id=grn2.id, action="APPROVED", from_status="SUBMITTED", to_status="APPROVED", actor_id="usr_mgmt_01", comments="MTC verified by Metallurgist. Approved."))

        db.add(StockLedgerEntry(
            entry_number="ENT-20261016-0001",
            posting_group_id=f"GRN-{grn2.id}",
            material_item_id=it_fesi.id,
            uom_id=it_fesi.base_uom_id,
            transaction_date=date(2026, 10, 16),
            posted_at=datetime(2026, 10, 16, 14, 0, 0, tzinfo=timezone.utc),
            movement_type=MovementType.INWARD_RECEIPT.value,
            quantity_delta=Decimal("1500.0000"),
            source_document_type=SourceDocumentType.GRN.value,
            source_document_id=grn2.id,
            source_line_id=line2_1.id,
            source_document_number=grn2.grn_number,
            reference_number="PO-VSPL-2026-0902",
            reason="GRN Inward receipt from Sarda Energy & Minerals Ltd (FeSi)",
            posted_by="usr_mgmt_01",
        ))
        db.add(StockLedgerEntry(
            entry_number="ENT-20261016-0002",
            posting_group_id=f"GRN-{grn2.id}",
            material_item_id=it_femn.id,
            uom_id=it_femn.base_uom_id,
            transaction_date=date(2026, 10, 16),
            posted_at=datetime(2026, 10, 16, 14, 0, 0, tzinfo=timezone.utc),
            movement_type=MovementType.INWARD_RECEIPT.value,
            quantity_delta=Decimal("800.0000"),
            source_document_type=SourceDocumentType.GRN.value,
            source_document_id=grn2.id,
            source_line_id=line2_2.id,
            source_document_number=grn2.grn_number,
            reference_number="PO-VSPL-2026-0902",
            reason="GRN Inward receipt from Sarda Energy & Minerals Ltd (FeMn)",
            posted_by="usr_mgmt_01",
        ))
        grns_added += 1
        grn_ledger_added += 2

    # GRN 3: Approved - Sandvik Inserts
    grn3_num = "GRN-20261018-0001"
    existing_grn3 = db.execute(select(GRNHeader).where(GRNHeader.grn_number == grn3_num)).scalar_one_or_none()
    if not existing_grn3:
        v_sandvik = vendor_by_name["Sandvik Coromant India"]
        grn3 = GRNHeader(
            grn_number=grn3_num,
            receipt_date=date(2026, 10, 18),
            source_type=GRNSourceType.EXTERNAL_VENDOR.value,
            vendor_id=v_sandvik.id,
            vendor_invoice_no="SAN-PUN-8821",
            invoice_date=date(2026, 10, 17),
            reference_document="PO-VSPL-2026-0915",
            notes="Tooling consignment for machine shop.",
            status=GRNStatus.APPROVED.value,
            created_by="usr_stores_01",
            created_at=datetime(2026, 10, 18, 9, 30, 0, tzinfo=timezone.utc),
        )
        db.add(grn3)
        db.flush()

        it_cnmg = item_by_code["MCS-IT-001"]
        it_wnmg = item_by_code["MCS-IT-002"]
        line3_1 = GRNLineItem(grn_id=grn3.id, line_number=1, material_item_id=it_cnmg.id, uom_id=it_cnmg.base_uom_id, quantity=Decimal("50.0000"), rate_ex_gst=Decimal("380.00"), gst_percent=Decimal("18.00"))
        line3_2 = GRNLineItem(grn_id=grn3.id, line_number=2, material_item_id=it_wnmg.id, uom_id=it_wnmg.base_uom_id, quantity=Decimal("40.0000"), rate_ex_gst=Decimal("395.00"), gst_percent=Decimal("18.00"))
        db.add_all([line3_1, line3_2])
        db.flush()

        db.add(GRNAuditLog(grn_id=grn3.id, action="SUBMITTED", from_status="DRAFT", to_status="SUBMITTED", actor_id="usr_stores_01", comments="Tooling packet inspected."))
        db.add(GRNAuditLog(grn_id=grn3.id, action="APPROVED", from_status="SUBMITTED", to_status="APPROVED", actor_id="usr_admin_01", comments="Machining Lead approval received."))

        db.add(StockLedgerEntry(
            entry_number="ENT-20261018-0001",
            posting_group_id=f"GRN-{grn3.id}",
            material_item_id=it_cnmg.id,
            uom_id=it_cnmg.base_uom_id,
            transaction_date=date(2026, 10, 18),
            posted_at=datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc),
            movement_type=MovementType.INWARD_RECEIPT.value,
            quantity_delta=Decimal("50.0000"),
            source_document_type=SourceDocumentType.GRN.value,
            source_document_id=grn3.id,
            source_line_id=line3_1.id,
            source_document_number=grn3.grn_number,
            reference_number="PO-VSPL-2026-0915",
            reason="GRN Inward receipt from Sandvik Coromant India (CNMG)",
            posted_by="usr_admin_01",
        ))
        db.add(StockLedgerEntry(
            entry_number="ENT-20261018-0002",
            posting_group_id=f"GRN-{grn3.id}",
            material_item_id=it_wnmg.id,
            uom_id=it_wnmg.base_uom_id,
            transaction_date=date(2026, 10, 18),
            posted_at=datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc),
            movement_type=MovementType.INWARD_RECEIPT.value,
            quantity_delta=Decimal("40.0000"),
            source_document_type=SourceDocumentType.GRN.value,
            source_document_id=grn3.id,
            source_line_id=line3_2.id,
            source_document_number=grn3.grn_number,
            reference_number="PO-VSPL-2026-0915",
            reason="GRN Inward receipt from Sandvik Coromant India (WNMG)",
            posted_by="usr_admin_01",
        ))
        grns_added += 1
        grn_ledger_added += 2

    # GRN 4: SUBMITTED - Castrol Hydraulic Oil
    grn4_num = "GRN-20261021-0001"
    existing_grn4 = db.execute(select(GRNHeader).where(GRNHeader.grn_number == grn4_num)).scalar_one_or_none()
    if not existing_grn4:
        v_castrol = vendor_by_name["Castrol India Limited"]
        grn4 = GRNHeader(
            grn_number=grn4_num,
            receipt_date=date(2026, 10, 21),
            source_type=GRNSourceType.EXTERNAL_VENDOR.value,
            vendor_id=v_castrol.id,
            vendor_invoice_no="CAS-MUM-5412",
            invoice_date=date(2026, 10, 20),
            reference_document="PO-VSPL-2026-0932",
            notes="1 barrel (210 L) received in lubrication storage area.",
            status=GRNStatus.SUBMITTED.value,
            created_by="usr_stores_01",
            created_at=datetime(2026, 10, 21, 15, 0, 0, tzinfo=timezone.utc),
        )
        db.add(grn4)
        db.flush()

        it_oil = item_by_code["MNT-OL-001"]
        line4 = GRNLineItem(grn_id=grn4.id, line_number=1, material_item_id=it_oil.id, uom_id=it_oil.base_uom_id, quantity=Decimal("210.0000"), rate_ex_gst=Decimal("165.00"), gst_percent=Decimal("18.00"))
        db.add(line4)
        db.flush()

        db.add(GRNAuditLog(grn_id=grn4.id, action="SUBMITTED", from_status="DRAFT", to_status="SUBMITTED", actor_id="usr_stores_01", comments="Barrel seal intact; submitted for Maintenance Lead sign-off."))
        grns_added += 1

    # GRN 5: DRAFT - Ashapura Sand & Bentonite
    grn5_num = "GRN-20261025-0001"
    existing_grn5 = db.execute(select(GRNHeader).where(GRNHeader.grn_number == grn5_num)).scalar_one_or_none()
    if not existing_grn5:
        v_ash = vendor_by_name["Ashapura Minechem Ltd"]
        grn5 = GRNHeader(
            grn_number=grn5_num,
            receipt_date=date(2026, 10, 25),
            source_type=GRNSourceType.EXTERNAL_VENDOR.value,
            vendor_id=v_ash.id,
            vendor_invoice_no="ASH-26-8801",
            invoice_date=date(2026, 10, 25),
            reference_document="PO-VSPL-2026-0948",
            notes="Truck arrived at yard. Unloading in progress.",
            status=GRNStatus.DRAFT.value,
            created_by="usr_stores_01",
            created_at=datetime(2026, 10, 25, 14, 0, 0, tzinfo=timezone.utc),
        )
        db.add(grn5)
        db.flush()

        it_sand = item_by_code["FDY-MD-001"]
        it_bent = item_by_code["FDY-MD-002"]
        line5_1 = GRNLineItem(grn_id=grn5.id, line_number=1, material_item_id=it_sand.id, uom_id=it_sand.base_uom_id, quantity=Decimal("10000.0000"), rate_ex_gst=Decimal("4.10"), gst_percent=Decimal("5.00"))
        line5_2 = GRNLineItem(grn_id=grn5.id, line_number=2, material_item_id=it_bent.id, uom_id=it_bent.base_uom_id, quantity=Decimal("3000.0000"), rate_ex_gst=Decimal("9.50"), gst_percent=Decimal("5.00"))
        db.add_all([line5_1, line5_2])
        grns_added += 1

    stats["grns_added"] = grns_added
    stats["grn_ledger_added"] = grn_ledger_added

    # -------------------------------------------------------------------------
    # 7. Material Issues (Issue Slips)
    # -------------------------------------------------------------------------
    logger.info("Step 7: Seeding Material Issues...")
    issues_added = 0
    issue_ledger_added = 0

    dept_gns = dept_map["GNS"]
    dept_fdy = dept_map["FDY"]
    dept_msp = dept_map["MSP"]
    dept_mnt = dept_map["MNT"]

    # Issue 1: Approved - Stores to Foundry for Furnace Melting
    iss1_num = "ISS-20261015-0001"
    existing_iss1 = db.execute(select(MaterialIssueHeader).where(MaterialIssueHeader.issue_slip_number == iss1_num)).scalar_one_or_none()
    if not existing_iss1:
        iss1 = MaterialIssueHeader(
            issue_slip_number=iss1_num,
            issue_date=date(2026, 10, 15),
            issuing_department_id=dept_gns.id,
            receiving_department_id=dept_fdy.id,
            heat_reference_number="H-20261015-0001",
            notes="Raw material charge allocation for Shift A Induction Furnace F-01.",
            status=IssueStatus.APPROVED.value,
            created_by="usr_stores_01",
            created_at=datetime(2026, 10, 15, 7, 0, 0, tzinfo=timezone.utc),
        )
        db.add(iss1)
        db.flush()

        it_pig = item_by_code["FDY-RM-001"]
        it_scrap = item_by_code["FDY-RM-002"]
        it_fesi = item_by_code["FDY-RM-004"]
        it_femn = item_by_code["FDY-RM-005"]
        it_cpc = item_by_code["FDY-RM-007"]

        l1 = MaterialIssueLineItem(issue_id=iss1.id, line_number=1, material_item_id=it_pig.id, uom_id=it_pig.base_uom_id, quantity=Decimal("8500.0000"), remarks="Pig Iron charge")
        l2 = MaterialIssueLineItem(issue_id=iss1.id, line_number=2, material_item_id=it_scrap.id, uom_id=it_scrap.base_uom_id, quantity=Decimal("6000.0000"), remarks="CRCA Scrap charge")
        l3 = MaterialIssueLineItem(issue_id=iss1.id, line_number=3, material_item_id=it_fesi.id, uom_id=it_fesi.base_uom_id, quantity=Decimal("120.0000"), remarks="FeSi 75% addition")
        l4 = MaterialIssueLineItem(issue_id=iss1.id, line_number=4, material_item_id=it_femn.id, uom_id=it_femn.base_uom_id, quantity=Decimal("65.0000"), remarks="FeMn HC addition")
        l5 = MaterialIssueLineItem(issue_id=iss1.id, line_number=5, material_item_id=it_cpc.id, uom_id=it_cpc.base_uom_id, quantity=Decimal("80.0000"), remarks="Carbon correction")
        db.add_all([l1, l2, l3, l4, l5])
        db.flush()

        db.add(IssueAuditLog(issue_id=iss1.id, action="SUBMITTED", from_status="DRAFT", to_status="SUBMITTED", actor_id="usr_stores_01", comments="Weighed and issued to foundry floor."))
        db.add(IssueAuditLog(issue_id=iss1.id, action="APPROVED", from_status="SUBMITTED", to_status="APPROVED", actor_id="usr_foundry_01", comments="Received at furnace charge bay. Verified."))

        # Outward stock movements (negative quantity_delta)
        for idx, (line_obj, it_obj, qty_val) in enumerate([
            (l1, it_pig, Decimal("-8500.0000")),
            (l2, it_scrap, Decimal("-6000.0000")),
            (l3, it_fesi, Decimal("-120.0000")),
            (l4, it_femn, Decimal("-65.0000")),
            (l5, it_cpc, Decimal("-80.0000")),
        ], start=1):
            db.add(StockLedgerEntry(
                entry_number=f"ENT-20261015-{idx:04d}",
                posting_group_id=f"ISS-{iss1.id}",
                material_item_id=it_obj.id,
                uom_id=it_obj.base_uom_id,
                transaction_date=date(2026, 10, 15),
                posted_at=datetime(2026, 10, 15, 8, 30, 0, tzinfo=timezone.utc),
                movement_type=MovementType.OUTWARD_ISSUE.value,
                quantity_delta=qty_val,
                source_document_type=SourceDocumentType.ISSUE.value,
                source_document_id=iss1.id,
                source_line_id=line_obj.id,
                source_document_number=iss1.issue_slip_number,
                reference_number="H-20261015-0001",
                reason=f"Material Issue to Foundry for Heat H-20261015-0001",
                posted_by="usr_foundry_01",
            ))
            issue_ledger_added += 1
        issues_added += 1

    # Issue 2: Approved - Stores to Machine Shop (Tooling)
    iss2_num = "ISS-20261017-0001"
    existing_iss2 = db.execute(select(MaterialIssueHeader).where(MaterialIssueHeader.issue_slip_number == iss2_num)).scalar_one_or_none()
    if not existing_iss2:
        iss2 = MaterialIssueHeader(
            issue_slip_number=iss2_num,
            issue_date=date(2026, 10, 17),
            issuing_department_id=dept_gns.id,
            receiving_department_id=dept_msp.id,
            notes="CNC Machining Line 1 tooling replenishment.",
            status=IssueStatus.APPROVED.value,
            created_by="usr_stores_01",
            created_at=datetime(2026, 10, 17, 9, 0, 0, tzinfo=timezone.utc),
        )
        db.add(iss2)
        db.flush()

        it_cnmg = item_by_code["MCS-IT-001"]
        it_wnmg = item_by_code["MCS-IT-002"]
        it_blade = item_by_code["MCS-CB-001"]

        l2_1 = MaterialIssueLineItem(issue_id=iss2.id, line_number=1, material_item_id=it_cnmg.id, uom_id=it_cnmg.base_uom_id, quantity=Decimal("15.0000"), remarks="Turning inserts")
        l2_2 = MaterialIssueLineItem(issue_id=iss2.id, line_number=2, material_item_id=it_wnmg.id, uom_id=it_wnmg.base_uom_id, quantity=Decimal("10.0000"), remarks="Roughing inserts")
        l2_3 = MaterialIssueLineItem(issue_id=iss2.id, line_number=3, material_item_id=it_blade.id, uom_id=it_blade.base_uom_id, quantity=Decimal("2.0000"), remarks="Bandsaw blade")
        db.add_all([l2_1, l2_2, l2_3])
        db.flush()

        db.add(IssueAuditLog(issue_id=iss2.id, action="SUBMITTED", from_status="DRAFT", to_status="SUBMITTED", actor_id="usr_stores_01", comments="Issued against Machine Shop requisition #MS-REQ-104."))
        db.add(IssueAuditLog(issue_id=iss2.id, action="APPROVED", from_status="SUBMITTED", to_status="APPROVED", actor_id="usr_mgmt_01", comments="Approved."))

        for idx, (line_obj, it_obj, qty_val) in enumerate([
            (l2_1, it_cnmg, Decimal("-15.0000")),
            (l2_2, it_wnmg, Decimal("-10.0000")),
            (l2_3, it_blade, Decimal("-2.0000")),
        ], start=1):
            db.add(StockLedgerEntry(
                entry_number=f"ENT-20261017-{idx:04d}",
                posting_group_id=f"ISS-{iss2.id}",
                material_item_id=it_obj.id,
                uom_id=it_obj.base_uom_id,
                transaction_date=date(2026, 10, 17),
                posted_at=datetime(2026, 10, 17, 10, 30, 0, tzinfo=timezone.utc),
                movement_type=MovementType.OUTWARD_ISSUE.value,
                quantity_delta=qty_val,
                source_document_type=SourceDocumentType.ISSUE.value,
                source_document_id=iss2.id,
                source_line_id=line_obj.id,
                source_document_number=iss2.issue_slip_number,
                reference_number="MS-REQ-104",
                reason="Material Issue to Machine Shop for CNC Line 1",
                posted_by="usr_mgmt_01",
            ))
            issue_ledger_added += 1
        issues_added += 1

    # Issue 3: Approved - Stores to Maintenance
    iss3_num = "ISS-20261020-0001"
    existing_iss3 = db.execute(select(MaterialIssueHeader).where(MaterialIssueHeader.issue_slip_number == iss3_num)).scalar_one_or_none()
    if not existing_iss3:
        iss3 = MaterialIssueHeader(
            issue_slip_number=iss3_num,
            issue_date=date(2026, 10, 20),
            issuing_department_id=dept_gns.id,
            receiving_department_id=dept_mnt.id,
            notes="Hydraulic power pack preventative maintenance overhaul.",
            status=IssueStatus.APPROVED.value,
            created_by="usr_stores_01",
            created_at=datetime(2026, 10, 20, 8, 30, 0, tzinfo=timezone.utc),
        )
        db.add(iss3)
        db.flush()

        it_oil = item_by_code["MNT-OL-001"]
        it_brg = item_by_code["MNT-BR-001"]
        it_bolt = item_by_code["MNT-BN-001"]

        l3_1 = MaterialIssueLineItem(issue_id=iss3.id, line_number=1, material_item_id=it_oil.id, uom_id=it_oil.base_uom_id, quantity=Decimal("80.0000"), remarks="Hydraulic oil top-up")
        l3_2 = MaterialIssueLineItem(issue_id=iss3.id, line_number=2, material_item_id=it_brg.id, uom_id=it_brg.base_uom_id, quantity=Decimal("4.0000"), remarks="Motor bearing replacement")
        l3_3 = MaterialIssueLineItem(issue_id=iss3.id, line_number=3, material_item_id=it_bolt.id, uom_id=it_bolt.base_uom_id, quantity=Decimal("24.0000"), remarks="Mounting bolts")
        db.add_all([l3_1, l3_2, l3_3])
        db.flush()

        db.add(IssueAuditLog(issue_id=iss3.id, action="SUBMITTED", from_status="DRAFT", to_status="SUBMITTED", actor_id="usr_stores_01", comments="Maintenance job card #MNT-JC-302 verified."))
        db.add(IssueAuditLog(issue_id=iss3.id, action="APPROVED", from_status="SUBMITTED", to_status="APPROVED", actor_id="usr_admin_01", comments="Approved."))

        for idx, (line_obj, it_obj, qty_val) in enumerate([
            (l3_1, it_oil, Decimal("-80.0000")),
            (l3_2, it_brg, Decimal("-4.0000")),
            (l3_3, it_bolt, Decimal("-24.0000")),
        ], start=1):
            db.add(StockLedgerEntry(
                entry_number=f"ENT-20261020-{idx:04d}",
                posting_group_id=f"ISS-{iss3.id}",
                material_item_id=it_obj.id,
                uom_id=it_obj.base_uom_id,
                transaction_date=date(2026, 10, 20),
                posted_at=datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc),
                movement_type=MovementType.OUTWARD_ISSUE.value,
                quantity_delta=qty_val,
                source_document_type=SourceDocumentType.ISSUE.value,
                source_document_id=iss3.id,
                source_line_id=line_obj.id,
                source_document_number=iss3.issue_slip_number,
                reference_number="MNT-JC-302",
                reason="Material Issue to Maintenance for Hydraulic Overhaul",
                posted_by="usr_admin_01",
            ))
            issue_ledger_added += 1
        issues_added += 1

    # Issue 4: SUBMITTED - Stores to Foundry PPE & Sand
    iss4_num = "ISS-20261023-0001"
    existing_iss4 = db.execute(select(MaterialIssueHeader).where(MaterialIssueHeader.issue_slip_number == iss4_num)).scalar_one_or_none()
    if not existing_iss4:
        iss4 = MaterialIssueHeader(
            issue_slip_number=iss4_num,
            issue_date=date(2026, 10, 23),
            issuing_department_id=dept_gns.id,
            receiving_department_id=dept_fdy.id,
            notes="Weekly foundry floor PPE and moulding consumables issue.",
            status=IssueStatus.SUBMITTED.value,
            created_by="usr_stores_01",
            created_at=datetime(2026, 10, 23, 11, 0, 0, tzinfo=timezone.utc),
        )
        db.add(iss4)
        db.flush()

        it_glove = item_by_code["GEN-SF-001"]
        it_bent = item_by_code["FDY-MD-002"]
        it_cup = item_by_code["FDY-CN-001"]

        l4_1 = MaterialIssueLineItem(issue_id=iss4.id, line_number=1, material_item_id=it_glove.id, uom_id=it_glove.base_uom_id, quantity=Decimal("10.0000"), remarks="Leather gloves")
        l4_2 = MaterialIssueLineItem(issue_id=iss4.id, line_number=2, material_item_id=it_bent.id, uom_id=it_bent.base_uom_id, quantity=Decimal("500.0000"), remarks="Bentonite for moulding")
        l4_3 = MaterialIssueLineItem(issue_id=iss4.id, line_number=3, material_item_id=it_cup.id, uom_id=it_cup.base_uom_id, quantity=Decimal("60.0000"), remarks="Pouring cups")
        db.add_all([l4_1, l4_2, l4_3])
        db.flush()

        db.add(IssueAuditLog(issue_id=iss4.id, action="SUBMITTED", from_status="DRAFT", to_status="SUBMITTED", actor_id="usr_stores_01", comments="Awaiting Foundry Lead acceptance."))
        issues_added += 1

    # Issue 5: DRAFT - Stores to Foundry Lining Mass
    iss5_num = "ISS-20261026-0001"
    existing_iss5 = db.execute(select(MaterialIssueHeader).where(MaterialIssueHeader.issue_slip_number == iss5_num)).scalar_one_or_none()
    if not existing_iss5:
        iss5 = MaterialIssueHeader(
            issue_slip_number=iss5_num,
            issue_date=date(2026, 10, 26),
            issuing_department_id=dept_gns.id,
            receiving_department_id=dept_fdy.id,
            notes="Furnace F-02 lining replacement batch.",
            status=IssueStatus.DRAFT.value,
            created_by="usr_stores_01",
            created_at=datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc),
        )
        db.add(iss5)
        db.flush()

        it_ram = item_by_code["FDY-LN-001"]
        l5 = MaterialIssueLineItem(issue_id=iss5.id, line_number=1, material_item_id=it_ram.id, uom_id=it_ram.base_uom_id, quantity=Decimal("1500.0000"), remarks="Silica ramming mass")
        db.add(l5)
        issues_added += 1

    stats["issues_added"] = issues_added
    stats["issue_ledger_added"] = issue_ledger_added

    # -------------------------------------------------------------------------
    # 8. Induction Furnace Heat Logs
    # -------------------------------------------------------------------------
    logger.info("Step 8: Seeding Induction Furnace Heat Logs...")
    heats_added = 0
    uom_kg = uom_map["KG"]

    # Heat 1: Completed - Heat H-20261015-0001
    h1_num = "H-20261015-0001"
    existing_h1 = db.execute(select(HeatHeader).where(HeatHeader.heat_number == h1_num)).scalar_one_or_none()
    if not existing_h1:
        h1 = HeatHeader(
            heat_number=h1_num,
            original_heat_number=h1_num,
            normalized_heat_number=h1_num,
            heat_date=date(2026, 10, 15),
            furnace_id="F-01",
            shift="Shift A",
            metal_tapped_weight=Decimal("7420.0000"),
            metal_tapped_uom_id=uom_kg.id,
            production_status=ProductionStatus.COMPLETED.value,
            source_document_reference="LOG-F01-20261015",
            notes="Grade SG 450/10 melt. Good tapping temperature 1485°C. Inoculation carried out at stream.",
            created_by="usr_foundry_01",
        )
        db.add(h1)
        db.flush()

        c1 = HeatChargeLine(heat_id=h1.id, line_number=1, material_item_id=item_by_code["FDY-RM-001"].id, original_material_description="Pig Iron Gr1", charged_quantity=Decimal("4200.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        c2 = HeatChargeLine(heat_id=h1.id, line_number=2, material_item_id=item_by_code["FDY-RM-002"].id, original_material_description="CRC Scrap", charged_quantity=Decimal("2800.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        c3 = HeatChargeLine(heat_id=h1.id, line_number=3, material_item_id=item_by_code["FDY-RM-004"].id, original_material_description="FeSi 75%", charged_quantity=Decimal("60.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        c4 = HeatChargeLine(heat_id=h1.id, line_number=4, material_item_id=item_by_code["FDY-RM-005"].id, original_material_description="FeMn HC", charged_quantity=Decimal("35.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        c5 = HeatChargeLine(heat_id=h1.id, line_number=5, material_item_id=item_by_code["FDY-RM-007"].id, original_material_description="CPC Carbon Raiser", charged_quantity=Decimal("40.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        c6 = HeatChargeLine(heat_id=h1.id, line_number=6, material_item_id=item_by_code["FDY-RM-006"].id, original_material_description="SMZ Inoculant", charged_quantity=Decimal("15.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        db.add_all([c1, c2, c3, c4, c5, c6])

        p1 = HeatPartsProduced(heat_id=h1.id, line_number=1, original_part_description="VSPL-HUB-01 (SG Iron Wheel Hub)", quantity_produced=Decimal("116.0000"), unit_cast_weight=Decimal("30.0000"), weight_uom_id=uom_kg.id, classification=CastingClassification.GOOD.value, remarks="Good sound castings")
        p2 = HeatPartsProduced(heat_id=h1.id, line_number=2, original_part_description="VSPL-HUB-01 (SG Iron Wheel Hub)", quantity_produced=Decimal("4.0000"), unit_cast_weight=Decimal("30.0000"), weight_uom_id=uom_kg.id, classification=CastingClassification.REJECTED.value, remarks="Shrinkage cavity")
        p3 = HeatPartsProduced(heat_id=h1.id, line_number=3, original_part_description="VSPL-DIFF-02 (Differential Housing)", quantity_produced=Decimal("87.0000"), unit_cast_weight=Decimal("35.0000"), weight_uom_id=uom_kg.id, classification=CastingClassification.GOOD.value, remarks="Good sound castings")
        db.add_all([p1, p2, p3])
        heats_added += 1

    # Heat 2: Completed - Heat H-20261016-0001
    h2_num = "H-20261016-0001"
    existing_h2 = db.execute(select(HeatHeader).where(HeatHeader.heat_number == h2_num)).scalar_one_or_none()
    if not existing_h2:
        h2 = HeatHeader(
            heat_number=h2_num,
            original_heat_number=h2_num,
            normalized_heat_number=h2_num,
            heat_date=date(2026, 10, 16),
            furnace_id="F-01",
            shift="Shift B",
            metal_tapped_weight=Decimal("7380.0000"),
            metal_tapped_uom_id=uom_kg.id,
            production_status=ProductionStatus.COMPLETED.value,
            source_document_reference="LOG-F01-20261016",
            notes="Grade SG 500/7 melt. Nodulization magnesium recovery 78%.",
            created_by="usr_foundry_01",
        )
        db.add(h2)
        db.flush()

        h2_c1 = HeatChargeLine(heat_id=h2.id, line_number=1, material_item_id=item_by_code["FDY-RM-001"].id, original_material_description="Pig Iron Gr1", charged_quantity=Decimal("4000.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        h2_c2 = HeatChargeLine(heat_id=h2.id, line_number=2, material_item_id=item_by_code["FDY-RM-003"].id, original_material_description="Foundry Returns", charged_quantity=Decimal("3000.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        h2_c3 = HeatChargeLine(heat_id=h2.id, line_number=3, material_item_id=item_by_code["FDY-RM-004"].id, original_material_description="FeSi 75%", charged_quantity=Decimal("50.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        h2_c4 = HeatChargeLine(heat_id=h2.id, line_number=4, material_item_id=item_by_code["FDY-RM-005"].id, original_material_description="FeMn HC", charged_quantity=Decimal("30.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        h2_c5 = HeatChargeLine(heat_id=h2.id, line_number=5, material_item_id=item_by_code["FDY-RM-008"].id, original_material_description="Pure Magnesium", charged_quantity=Decimal("25.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        db.add_all([h2_c1, h2_c2, h2_c3, h2_c4, h2_c5])

        h2_p1 = HeatPartsProduced(heat_id=h2.id, line_number=1, original_part_description="VSPL-BRG-03 (Bearing Carrier Casting)", quantity_produced=Decimal("135.0000"), unit_cast_weight=Decimal("30.0000"), weight_uom_id=uom_kg.id, classification=CastingClassification.GOOD.value, remarks="Good sound castings")
        h2_p2 = HeatPartsProduced(heat_id=h2.id, line_number=2, original_part_description="VSPL-HUB-01 (SG Iron Wheel Hub)", quantity_produced=Decimal("78.0000"), unit_cast_weight=Decimal("30.0000"), weight_uom_id=uom_kg.id, classification=CastingClassification.GOOD.value, remarks="Good sound castings")
        db.add_all([h2_p1, h2_p2])
        heats_added += 1

    # Heat 3: Completed - Heat H-20261022-0001
    h3_num = "H-20261022-0001"
    existing_h3 = db.execute(select(HeatHeader).where(HeatHeader.heat_number == h3_num)).scalar_one_or_none()
    if not existing_h3:
        h3 = HeatHeader(
            heat_number=h3_num,
            original_heat_number=h3_num,
            normalized_heat_number=h3_num,
            heat_date=date(2026, 10, 22),
            furnace_id="F-02",
            shift="Shift A",
            metal_tapped_weight=Decimal("7500.0000"),
            metal_tapped_uom_id=uom_kg.id,
            production_status=ProductionStatus.COMPLETED.value,
            source_document_reference="LOG-F02-20261022",
            notes="Heavy flywheel casting production run.",
            created_by="usr_foundry_01",
        )
        db.add(h3)
        db.flush()

        h3_c1 = HeatChargeLine(heat_id=h3.id, line_number=1, material_item_id=item_by_code["FDY-RM-001"].id, original_material_description="Pig Iron Gr1", charged_quantity=Decimal("4500.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        h3_c2 = HeatChargeLine(heat_id=h3.id, line_number=2, material_item_id=item_by_code["FDY-RM-002"].id, original_material_description="CRC Scrap", charged_quantity=Decimal("2600.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        h3_c3 = HeatChargeLine(heat_id=h3.id, line_number=3, material_item_id=item_by_code["FDY-RM-004"].id, original_material_description="FeSi 75%", charged_quantity=Decimal("55.0000"), uom_id=uom_kg.id, validation_status=HeatChargeValidationStatus.VALID.value)
        db.add_all([h3_c1, h3_c2, h3_c3])

        h3_p1 = HeatPartsProduced(heat_id=h3.id, line_number=1, original_part_description="VSPL-FW-04 (Heavy Flywheel Casting)", quantity_produced=Decimal("64.0000"), unit_cast_weight=Decimal("105.0000"), weight_uom_id=uom_kg.id, classification=CastingClassification.GOOD.value, remarks="Good sound castings")
        db.add(h3_p1)
        heats_added += 1

    stats["heats_added"] = heats_added

    # -------------------------------------------------------------------------
    # 9. Waste Dispositions
    # -------------------------------------------------------------------------
    logger.info("Step 9: Seeding Waste Dispositions...")
    waste_added = 0
    w1_num = "WST-20261018-0001"
    existing_w1 = db.execute(select(WasteDispositionHeader).where(WasteDispositionHeader.waste_number == w1_num)).scalar_one_or_none()
    if not existing_w1:
        w1 = WasteDispositionHeader(
            waste_number=w1_num,
            disposition_date=date(2026, 10, 18),
            waste_type=WasteType.GATINGS_RUNNERS.value,
            disposition_type=DispositionType.INTERNAL_RECOVERY.value,
            source_department_id=dept_fdy.id,
            destination_notes="Remelting inside foundry charge mix.",
            status=WasteStatus.APPROVED.value,
            notes="Knockout and shot blasting line returns recovery.",
            created_by="usr_foundry_01",
            created_at=datetime(2026, 10, 18, 16, 0, 0, tzinfo=timezone.utc),
        )
        db.add(w1)
        db.flush()

        it_ret = item_by_code["FDY-RM-003"]
        w1_line = WasteDispositionLineItem(
            waste_id=w1.id,
            line_number=1,
            material_item_id=it_ret.id,
            uom_id=it_ret.base_uom_id,
            quantity=Decimal("1820.0000"),
            remarks="Returns segregated from heat H-20261015 & H-20261016",
        )
        db.add(w1_line)
        db.flush()

        db.add(WasteAuditLog(waste_id=w1.id, action="SUBMITTED", from_status="DRAFT", to_status="SUBMITTED", actor_id="usr_foundry_01", comments="Returns weighed and transferred to returns bin."))
        db.add(WasteAuditLog(waste_id=w1.id, action="APPROVED", from_status="SUBMITTED", to_status="APPROVED", actor_id="usr_mgmt_01", comments="Approved."))

        # Internal recovery in stock ledger
        db.add(StockLedgerEntry(
            entry_number="ENT-20261018-0010",
            posting_group_id=f"WST-{w1.id}",
            material_item_id=it_ret.id,
            uom_id=it_ret.base_uom_id,
            transaction_date=date(2026, 10, 18),
            posted_at=datetime(2026, 10, 18, 17, 0, 0, tzinfo=timezone.utc),
            movement_type=MovementType.INTERNAL_RECOVERY.value,
            quantity_delta=Decimal("1820.0000"),
            source_document_type=SourceDocumentType.WASTE.value,
            source_document_id=w1.id,
            source_line_id=w1_line.id,
            source_document_number=w1.waste_number,
            reference_number="KNOCKOUT-BAY-1",
            reason="Internal recovery of foundry runners & risers for remelting",
            posted_by="usr_mgmt_01",
        ))
        waste_added += 1

    w2_num = "WST-20261023-0001"
    existing_w2 = db.execute(select(WasteDispositionHeader).where(WasteDispositionHeader.waste_number == w2_num)).scalar_one_or_none()
    if not existing_w2:
        w2 = WasteDispositionHeader(
            waste_number=w2_num,
            disposition_date=date(2026, 10, 23),
            waste_type=WasteType.BORINGS.value,
            disposition_type=DispositionType.INSPECTION_HOLD.value,
            source_department_id=dept_msp.id,
            destination_notes="Awaiting QA inspection for briquetting compatibility.",
            status=WasteStatus.SUBMITTED.value,
            notes="Machining shop borings accumulated in scrap bins.",
            created_by="usr_stores_01",
            created_at=datetime(2026, 10, 23, 14, 0, 0, tzinfo=timezone.utc),
        )
        db.add(w2)
        db.flush()

        it_scrap = item_by_code["FDY-RM-002"]
        w2_line = WasteDispositionLineItem(
            waste_id=w2.id,
            line_number=1,
            material_item_id=it_scrap.id,
            uom_id=it_scrap.base_uom_id,
            quantity=Decimal("680.0000"),
            remarks="Machine shop SG iron dry borings",
        )
        db.add(w2_line)
        db.flush()
        db.add(WasteAuditLog(waste_id=w2.id, action="SUBMITTED", from_status="DRAFT", to_status="SUBMITTED", actor_id="usr_stores_01", comments="Submitted for briquetting approval."))
        waste_added += 1

    stats["waste_added"] = waste_added

    # -------------------------------------------------------------------------
    # 10. Physical Stock Audits
    # -------------------------------------------------------------------------
    logger.info("Step 10: Seeding Physical Stock Audits...")
    audits_added = 0
    aud1_num = "AUD-20261022-0001"
    existing_aud1 = db.execute(select(PhysicalAuditHeader).where(PhysicalAuditHeader.audit_number == aud1_num)).scalar_one_or_none()
    if not existing_aud1:
        aud1 = PhysicalAuditHeader(
            audit_number=aud1_num,
            audit_date=date(2026, 10, 22),
            department_id=dept_fdy.id,
            status=AuditStatus.APPROVED.value,
            notes="Fortnightly physical verification of raw materials and pouring consumables.",
            created_by="usr_stores_01",
            created_at=datetime(2026, 10, 22, 10, 0, 0, tzinfo=timezone.utc),
        )
        db.add(aud1)
        db.flush()

        it_pig = item_by_code["FDY-RM-001"]
        it_fesi = item_by_code["FDY-RM-004"]
        it_cup = item_by_code["FDY-CN-001"]

        # 28,500 book vs 28,450 physical -> -50 variance
        aud1_l1 = PhysicalAuditLine(audit_id=aud1.id, line_number=1, material_item_id=it_pig.id, uom_id=it_pig.base_uom_id, system_quantity=Decimal("28500.0000"), physical_quantity=Decimal("28450.0000"), variance=Decimal("-50.0000"), reason="Normal scale moisture evaporation / handling tolerance.")
        aud1_l2 = PhysicalAuditLine(audit_id=aud1.id, line_number=2, material_item_id=it_fesi.id, uom_id=it_fesi.base_uom_id, system_quantity=Decimal("3880.0000"), physical_quantity=Decimal("3880.0000"), variance=Decimal("0.0000"), reason="Full physical match.")
        aud1_l3 = PhysicalAuditLine(audit_id=aud1.id, line_number=3, material_item_id=it_cup.id, uom_id=it_cup.base_uom_id, system_quantity=Decimal("440.0000"), physical_quantity=Decimal("438.0000"), variance=Decimal("-2.0000"), reason="Handling transit breakage in storage.")
        db.add_all([aud1_l1, aud1_l2, aud1_l3])
        db.flush()

        db.add(PhysicalAuditAuditLog(audit_id=aud1.id, action="SUBMITTED", from_status="DRAFT", to_status="SUBMITTED", actor_id="usr_stores_01", comments="Physical count verified by stores supervisor and internal auditor."))
        db.add(PhysicalAuditAuditLog(audit_id=aud1.id, action="APPROVED", from_status="SUBMITTED", to_status="APPROVED", actor_id="usr_mgmt_01", comments="Variances within allowable foundry tolerance (0.17%). Approved."))

        # Post adjustment entries to stock ledger
        db.add(StockLedgerEntry(
            entry_number="ENT-20261022-0015",
            posting_group_id=f"AUD-{aud1.id}",
            material_item_id=it_pig.id,
            uom_id=it_pig.base_uom_id,
            transaction_date=date(2026, 10, 22),
            posted_at=datetime(2026, 10, 22, 17, 0, 0, tzinfo=timezone.utc),
            movement_type=MovementType.PHYSICAL_AUDIT_ADJUSTMENT.value,
            quantity_delta=Decimal("-50.0000"),
            source_document_type=SourceDocumentType.AUDIT_ADJUSTMENT.value,
            source_document_id=aud1.id,
            source_line_id=aud1_l1.id,
            source_document_number=aud1.audit_number,
            reason="Physical Audit adjustment: -50 KG Pig Iron",
            posted_by="usr_mgmt_01",
        ))
        db.add(StockLedgerEntry(
            entry_number="ENT-20261022-0016",
            posting_group_id=f"AUD-{aud1.id}",
            material_item_id=it_cup.id,
            uom_id=it_cup.base_uom_id,
            transaction_date=date(2026, 10, 22),
            posted_at=datetime(2026, 10, 22, 17, 0, 0, tzinfo=timezone.utc),
            movement_type=MovementType.PHYSICAL_AUDIT_ADJUSTMENT.value,
            quantity_delta=Decimal("-2.0000"),
            source_document_type=SourceDocumentType.AUDIT_ADJUSTMENT.value,
            source_document_id=aud1.id,
            source_line_id=aud1_l3.id,
            source_document_number=aud1.audit_number,
            reason="Physical Audit adjustment: -2 NOS Pouring Cup",
            posted_by="usr_mgmt_01",
        ))
        audits_added += 1

    aud2_num = "AUD-20261026-0001"
    existing_aud2 = db.execute(select(PhysicalAuditHeader).where(PhysicalAuditHeader.audit_number == aud2_num)).scalar_one_or_none()
    if not existing_aud2:
        aud2 = PhysicalAuditHeader(
            audit_number=aud2_num,
            audit_date=date(2026, 10, 26),
            department_id=dept_msp.id,
            status=AuditStatus.DRAFT.value,
            notes="Machine shop monthly tooling count in progress.",
            created_by="usr_stores_01",
            created_at=datetime(2026, 10, 26, 9, 0, 0, tzinfo=timezone.utc),
        )
        db.add(aud2)
        db.flush()

        it_cnmg = item_by_code["MCS-IT-001"]
        aud2_l1 = PhysicalAuditLine(audit_id=aud2.id, line_number=1, material_item_id=it_cnmg.id, uom_id=it_cnmg.base_uom_id, system_quantity=Decimal("155.0000"), physical_quantity=Decimal("155.0000"), variance=Decimal("0.0000"), reason="Count matched tool crib records.")
        db.add(aud2_l1)
        audits_added += 1

    stats["audits_added"] = audits_added

    # -------------------------------------------------------------------------
    # 11. Item Requests (Approval Workflow)
    # -------------------------------------------------------------------------
    logger.info("Step 11: Seeding Item Requests...")
    reqs_added = 0
    req1_num = "REQ-20261019-0001"
    existing_req1 = db.execute(select(ItemRequest).where(ItemRequest.request_number == req1_num)).scalar_one_or_none()
    if not existing_req1:
        it_fil = item_by_code["FDY-CN-002"]
        req1 = ItemRequest(
            request_number=req1_num,
            requested_name="Ceramic Foam Filter 10 PPI (50x50x22)",
            proposed_department_id=dept_fdy.id,
            proposed_category="Consumables",
            proposed_subcategory="Filtration",
            proposed_uom_id=uom_map["NOS"].id,
            justification="Required for high-integrity SG iron casting slag filtration to reduce scrap rate below 2%.",
            requester_id="usr_foundry_01",
            requester_role="Foundry Engineer",
            requester_department="Foundry",
            status=RequestStatus.APPROVED.value,
            submitted_at=datetime(2026, 10, 19, 10, 0, 0, tzinfo=timezone.utc),
            reviewer_id="usr_mgmt_01",
            decision_at=datetime(2026, 10, 19, 14, 0, 0, tzinfo=timezone.utc),
            decision_comments="Approved. Added to Master Item catalog as FDY-CN-002.",
            linked_item_id=it_fil.id,
        )
        db.add(req1)
        db.flush()
        db.add(ItemRequestAuditLog(request_id=req1.id, action="SUBMITTED", from_status="DRAFT", to_status="SUBMITTED", actor_id="usr_foundry_01", actor_role="Foundry Engineer", comments="Proposal submitted."))
        db.add(ItemRequestAuditLog(request_id=req1.id, action="APPROVED", from_status="SUBMITTED", to_status="APPROVED", actor_id="usr_mgmt_01", actor_role="Plant Management", comments="Approved and item created."))
        reqs_added += 1

    req2_num = "REQ-20261024-0001"
    existing_req2 = db.execute(select(ItemRequest).where(ItemRequest.request_number == req2_num)).scalar_one_or_none()
    if not existing_req2:
        req2 = ItemRequest(
            request_number=req2_num,
            requested_name="Solid Carbide Gundrill 6.5mm x 250mm",
            proposed_department_id=dept_msp.id,
            proposed_category="Inserts & Tools",
            proposed_subcategory="Drilling Tools",
            proposed_uom_id=uom_map["NOS"].id,
            justification="Deep hole oil gallery drilling in new differential case casting program.",
            requester_id="usr_stores_01",
            requester_role="Stores Supervisor",
            requester_department="General/Stores",
            status=RequestStatus.SUBMITTED.value,
            submitted_at=datetime(2026, 10, 24, 11, 30, 0, tzinfo=timezone.utc),
        )
        db.add(req2)
        db.flush()
        db.add(ItemRequestAuditLog(request_id=req2.id, action="SUBMITTED", from_status="DRAFT", to_status="SUBMITTED", actor_id="usr_stores_01", actor_role="Stores Supervisor", comments="Submitted for Engineering and Management review."))
        reqs_added += 1

    req3_num = "REQ-20261025-0001"
    existing_req3 = db.execute(select(ItemRequest).where(ItemRequest.request_number == req3_num)).scalar_one_or_none()
    if not existing_req3:
        req3 = ItemRequest(
            request_number=req3_num,
            requested_name="Laser Non-Contact Infrared Thermometer 1600C",
            proposed_department_id=dept_map["QLT"].id,
            proposed_category="Quality Material",
            proposed_subcategory="Pyrometry",
            proposed_uom_id=uom_map["NOS"].id,
            justification="Backup optical pyrometric verification for ladle pouring temperature audits.",
            requester_id="usr_mgmt_01",
            requester_role="Quality Lead",
            requester_department="Quality",
            status=RequestStatus.DRAFT.value,
        )
        db.add(req3)
        reqs_added += 1

    stats["reqs_added"] = reqs_added

    # Commit all transaction units
    db.commit()
    logger.info("Demo data seeding completed successfully.")
    return stats


if __name__ == "__main__":
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        results = run_seed(db)
        print("SEEDING SUMMARY:")
        for k, v in results.items():
            print(f"  {k}: {v}")
    finally:
        db.close()
