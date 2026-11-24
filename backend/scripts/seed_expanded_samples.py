"""
Expanded Realistic Sample Data Seeding for VSPL MMS.
Adds additional November 2026 operational sample data:
- 2 Approved GRNs with Stock Ledger Inwards
- 2 Approved Stores Material Issues to Foundry
- 2 High-Precision Induction Furnace Heat Logs (with liquid heel, mass-balance, and parts cast)
- 1 Waste & Scrap Fettling Recovery Disposition
"""

import sys
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.models.department import Department
from app.models.uom import UOM
from app.models.vendor import Vendor
from app.models.item import MaterialItem
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.models.grn import GRNHeader, GRNLineItem, GRNAuditLog, GRNStatus, GRNSourceType
from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueAuditLog, IssueStatus
from app.models.waste import WasteDispositionHeader, WasteDispositionLineItem, WasteAuditLog, WasteStatus, DispositionType
from app.models.heat import (
    HeatHeader,
    HeatChargeLine,
    HeatPartsProduced,
    ProductionStatus,
    HeelMeasurementMethod,
    HeelVerificationStatus,
    HeatChargeValidationStatus,
    CastingClassification,
)
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_expanded")


def run():
    db = SessionLocal()
    try:
        # Load references
        items = {it.item_code: it for it in db.query(MaterialItem).all()}
        vendors = {v.name: v for v in db.query(Vendor).all()}
        depts = {d.code: d for d in db.query(Department).all()}
        uoms = {u.code: u for u in db.query(UOM).all()}

        kg_uom = uoms.get("KG")
        nos_uom = uoms.get("NOS")

        v_tata = vendors.get("Tata Metaliks Ltd")
        v_sarda = vendors.get("Sarda Energy & Minerals Ltd")

        # ---------------------------------------------------------
        # 1. New GRN: GRN-20261102-0001 (Tata Metaliks Pig Iron)
        # ---------------------------------------------------------
        grn_num = "GRN-20261102-0001"
        if not db.scalar(select(GRNHeader).where(GRNHeader.grn_number == grn_num)):
            logger.info(f"Seeding {grn_num}...")
            grn1 = GRNHeader(
                grn_number=grn_num,
                receipt_date=date(2026, 11, 2),
                source_type=GRNSourceType.EXTERNAL_VENDOR.value,
                vendor_id=v_tata.id if v_tata else 1,
                vendor_invoice_no="TML-NOV-2601",
                invoice_date=date(2026, 11, 1),
                reference_document="PO-VSPL-2026-1101",
                notes="Weighbridge Gross 34,220 kg, Tare 19,220 kg. Clean lumps, no slag adhering.",
                status=GRNStatus.APPROVED.value,
                created_by="usr_stores_01",
                created_at=datetime(2026, 11, 2, 9, 30, tzinfo=timezone.utc),
            )
            db.add(grn1)
            db.flush()

            it_pig = items["FDY-RM-001"]
            line1 = GRNLineItem(
                grn_id=grn1.id,
                line_number=1,
                material_item_id=it_pig.id,
                uom_id=it_pig.base_uom_id,
                quantity=Decimal("15000.0000"),
                rate_ex_gst=Decimal("46.25"),
                gst_percent=Decimal("18.00"),
                remarks="Foundry Grade 1 Si 2.05% S 0.018%",
            )
            db.add(line1)
            db.flush()

            db.add(GRNAuditLog(grn_id=grn1.id, action="APPROVED", from_status="SUBMITTED", to_status="APPROVED", actor_id="usr_mgmt_01", comments="QC Lab spectrometer verified. Approved for melting."))
            db.add(StockLedgerEntry(
                entry_number="ENT-20261102-0001",
                posting_group_id=f"GRN-{grn1.id}",
                material_item_id=it_pig.id,
                uom_id=it_pig.base_uom_id,
                transaction_date=date(2026, 11, 2),
                posted_at=datetime(2026, 11, 2, 11, 0, tzinfo=timezone.utc),
                movement_type=MovementType.INWARD_RECEIPT.value,
                quantity_delta=Decimal("15000.0000"),
                source_document_type=SourceDocumentType.GRN.value,
                source_document_id=grn1.id,
                source_line_id=line1.id,
                source_document_number=grn1.grn_number,
                reference_number="PO-VSPL-2026-1101",
                reason="GRN Gate receipt from Tata Metaliks Ltd",
                posted_by="usr_mgmt_01",
            ))
            logger.info("  ✓ GRN 1 created & posted to ledger")

        # ---------------------------------------------------------
        # 2. New Material Issue: ISS-20261102-0001 (Issued to Foundry)
        # ---------------------------------------------------------
        iss_num = "ISS-20261102-0001"
        if not db.scalar(select(MaterialIssueHeader).where(MaterialIssueHeader.issue_slip_number == iss_num)):
            logger.info(f"Seeding {iss_num}...")
            iss1 = MaterialIssueHeader(
                issue_slip_number=iss_num,
                issue_date=date(2026, 11, 2),
                issuing_department_id=depts["GNS"].id if "GNS" in depts else 1,
                receiving_department_id=depts["FDY"].id if "FDY" in depts else 1,
                heat_reference_number="H-20261102-0001",
                notes="Furnace charge materials issued for Heat H-20261102-0001 (SG Hub 30kg casting run).",
                status=IssueStatus.APPROVED.value,
                created_by="usr_stores_01",
                created_at=datetime(2026, 11, 2, 13, 0, tzinfo=timezone.utc),
            )
            db.add(iss1)
            db.flush()

            it_pig = items["FDY-RM-001"]
            it_scrap = items["FDY-RM-002"]
            it_fesi = items["FDY-RM-004"]
            it_cpc = items["FDY-RM-007"]

            l1 = MaterialIssueLineItem(issue_id=iss1.id, line_number=1, material_item_id=it_pig.id, uom_id=it_pig.base_uom_id, quantity=Decimal("7000.0000"), remarks="Weighed in charging bucket 1 & 2")
            l2 = MaterialIssueLineItem(issue_id=iss1.id, line_number=2, material_item_id=it_scrap.id, uom_id=it_scrap.base_uom_id, quantity=Decimal("4500.0000"), remarks="Clean CRCA low-Mn bales")
            l3 = MaterialIssueLineItem(issue_id=iss1.id, line_number=3, material_item_id=it_fesi.id, uom_id=it_fesi.base_uom_id, quantity=Decimal("110.0000"), remarks="FeSi 75% furnace addition")
            l4 = MaterialIssueLineItem(issue_id=iss1.id, line_number=4, material_item_id=it_cpc.id, uom_id=it_cpc.base_uom_id, quantity=Decimal("65.0000"), remarks="Graphite CPC recarburizer")
            db.add_all([l1, l2, l3, l4])
            db.flush()

            db.add(IssueAuditLog(issue_id=iss1.id, action="APPROVED", from_status="SUBMITTED", to_status="APPROVED", actor_id="usr_mgmt_01", comments="Checker approval. Outward posted to Foundry WIP."))
            
            # Post outward stock movements to ledger
            for l_item, q_val in [(l1, Decimal("-7000.0000")), (l2, Decimal("-4500.0000")), (l3, Decimal("-110.0000")), (l4, Decimal("-65.0000"))]:
                db.add(StockLedgerEntry(
                    entry_number=f"ENT-20261102-ISS-{l_item.line_number}",
                    posting_group_id=f"ISS-{iss1.id}",
                    material_item_id=l_item.material_item_id,
                    uom_id=l_item.uom_id,
                    transaction_date=date(2026, 11, 2),
                    posted_at=datetime(2026, 11, 2, 13, 30, tzinfo=timezone.utc),
                    movement_type=MovementType.OUTWARD_ISSUE.value,
                    quantity_delta=q_val,
                    source_document_type=SourceDocumentType.ISSUE.value,
                    source_document_id=iss1.id,
                    source_line_id=l_item.id,
                    source_document_number=iss1.issue_slip_number,
                    reference_number="H-20261102-0001",
                    reason=f"Stores Issue to Foundry for Heat {iss1.heat_reference_number}",
                    posted_by="usr_mgmt_01",
                ))
            logger.info("  ✓ Issue 1 created & outward posted to ledger")

        # ---------------------------------------------------------
        # 3. New Heat Log: H-20261102-0001 (Induction Furnace Heat)
        # ---------------------------------------------------------
        heat_num = "H-20261102-0001"
        if not db.scalar(select(HeatHeader).where(HeatHeader.heat_number == heat_num)):
            logger.info(f"Seeding {heat_num}...")
            heat1 = HeatHeader(
                heat_number=heat_num,
                original_heat_number=heat_num,
                normalized_heat_number=heat_num,
                heat_date=date(2026, 11, 2),
                furnace_id="FURNACE-1",
                shift="SHIFT_A",
                metal_tapped_weight=Decimal("12350.0000"),
                metal_tapped_uom_id=kg_uom.id if kg_uom else 1,
                production_status=ProductionStatus.COMPLETED.value,
                notes="Heat completed smoothly. Bath temp 1480C. Crane scale ladle gross 17,850 kg, tare 5,500 kg.",
                opening_liquid_heel_kg=Decimal("320.0000"),
                closing_liquid_heel_kg=Decimal("280.0000"),
                heel_measurement_method=HeelMeasurementMethod.DIP_ROD.value,
                heel_verification_status=HeelVerificationStatus.VERIFIED.value,
                is_cold_start=False,
                is_furnace_empty=False,
                created_by="usr_foundry_01",
                created_at=datetime(2026, 11, 2, 14, 0, tzinfo=timezone.utc),
            )
            db.add(heat1)
            db.flush()

            # Charges
            c1 = HeatChargeLine(heat_id=heat1.id, line_number=1, original_material_description="Pig Iron (Foundry Grade 1)", charged_quantity=Decimal("7000.0000"), uom_id=kg_uom.id if kg_uom else 1, validation_status=HeatChargeValidationStatus.VALID.value, remarks="From Stores Issue #ISS-20261102-0001")
            c2 = HeatChargeLine(heat_id=heat1.id, line_number=2, original_material_description="CRCA Steel Scrap (Low Manganese)", charged_quantity=Decimal("4500.0000"), uom_id=kg_uom.id if kg_uom else 1, validation_status=HeatChargeValidationStatus.VALID.value, remarks="From Stores Issue #ISS-20261102-0001")
            c3 = HeatChargeLine(heat_id=heat1.id, line_number=3, original_material_description="Ferro Silicon 75% (FeSi)", charged_quantity=Decimal("110.0000"), uom_id=kg_uom.id if kg_uom else 1, validation_status=HeatChargeValidationStatus.VALID.value, remarks="Ladle addition")
            c4 = HeatChargeLine(heat_id=heat1.id, line_number=4, original_material_description="Carbon Raiser (CPC 98.5%)", charged_quantity=Decimal("65.0000"), uom_id=kg_uom.id if kg_uom else 1, validation_status=HeatChargeValidationStatus.VALID.value, remarks="Carbon adjustment")
            c5 = HeatChargeLine(heat_id=heat1.id, line_number=5, original_material_description="Foundry In-House Returns / Runners", charged_quantity=Decimal("1000.0000"), uom_id=kg_uom.id if kg_uom else 1, validation_status=HeatChargeValidationStatus.VALID.value, remarks="Internal runner/riser returns")
            db.add_all([c1, c2, c3, c4, c5])

            # Castings produced
            p1 = HeatPartsProduced(heat_id=heat1.id, line_number=1, original_part_description="Rear Wheel Hub SG 400/12 (Part #HUB-400-30)", quantity_produced=Decimal("280"), unit_cast_weight=Decimal("30.50"), weight_uom_id=kg_uom.id if kg_uom else 1, classification=CastingClassification.GOOD.value)
            p2 = HeatPartsProduced(heat_id=heat1.id, line_number=2, original_part_description="Brake Rotor Disc (Part #BRK-450-22)", quantity_produced=Decimal("95"), unit_cast_weight=Decimal("22.00"), weight_uom_id=kg_uom.id if kg_uom else 1, classification=CastingClassification.GOOD.value)
            p3 = HeatPartsProduced(heat_id=heat1.id, line_number=3, original_part_description="Runners, Risers & Gating Systems", quantity_produced=Decimal("1"), unit_cast_weight=Decimal("1550.00"), weight_uom_id=kg_uom.id if kg_uom else 1, classification=CastingClassification.REWORK.value)
            p4 = HeatPartsProduced(heat_id=heat1.id, line_number=4, original_part_description="Cold Shut Surface Defect Castings", quantity_produced=Decimal("4"), unit_cast_weight=Decimal("30.50"), weight_uom_id=kg_uom.id if kg_uom else 1, classification=CastingClassification.REJECTED.value)
            db.add_all([p1, p2, p3, p4])
            db.flush()
            logger.info("  ✓ Heat 1 (H-20261102-0001) logged with 5 charges & 4 casting part groups")

        # ---------------------------------------------------------
        # 4. New Heat Log: H-20261108-0001 (Induction Furnace Heat 2)
        # ---------------------------------------------------------
        heat_num2 = "H-20261108-0001"
        if not db.scalar(select(HeatHeader).where(HeatHeader.heat_number == heat_num2)):
            logger.info(f"Seeding {heat_num2}...")
            heat2 = HeatHeader(
                heat_number=heat_num2,
                original_heat_number=heat_num2,
                normalized_heat_number=heat_num2,
                heat_date=date(2026, 11, 8),
                furnace_id="FURNACE-1",
                shift="SHIFT_B",
                metal_tapped_weight=Decimal("11850.0000"),
                metal_tapped_uom_id=kg_uom.id if kg_uom else 1,
                production_status=ProductionStatus.COMPLETED.value,
                notes="Evening shift. Optical pyrometer reading 1475C at tap. Spectro sample within spec.",
                opening_liquid_heel_kg=Decimal("280.0000"),
                closing_liquid_heel_kg=Decimal("340.0000"),
                heel_measurement_method=HeelMeasurementMethod.DIP_ROD.value,
                heel_verification_status=HeelVerificationStatus.VERIFIED.value,
                is_cold_start=False,
                is_furnace_empty=False,
                created_by="usr_foundry_01",
                created_at=datetime(2026, 11, 8, 20, 30, tzinfo=timezone.utc),
            )
            db.add(heat2)
            db.flush()

            # Charges
            c2_1 = HeatChargeLine(heat_id=heat2.id, line_number=1, original_material_description="Pig Iron (Foundry Grade 1)", charged_quantity=Decimal("6800.0000"), uom_id=kg_uom.id if kg_uom else 1, validation_status=HeatChargeValidationStatus.VALID.value, remarks="Main bath charge")
            c2_2 = HeatChargeLine(heat_id=heat2.id, line_number=2, original_material_description="CRCA Steel Scrap (Low Manganese)", charged_quantity=Decimal("4200.0000"), uom_id=kg_uom.id if kg_uom else 1, validation_status=HeatChargeValidationStatus.VALID.value, remarks="Steel addition")
            c2_3 = HeatChargeLine(heat_id=heat2.id, line_number=3, original_material_description="Ferro Silicon 75% (FeSi)", charged_quantity=Decimal("95.0000"), uom_id=kg_uom.id if kg_uom else 1, validation_status=HeatChargeValidationStatus.VALID.value, remarks="Silicon trimming")
            c2_4 = HeatChargeLine(heat_id=heat2.id, line_number=4, original_material_description="Inoculant FeSi-Ba (SMZ)", charged_quantity=Decimal("25.0000"), uom_id=kg_uom.id if kg_uom else 1, validation_status=HeatChargeValidationStatus.VALID.value, remarks="Stream inoculation")
            c2_5 = HeatChargeLine(heat_id=heat2.id, line_number=5, original_material_description="Foundry In-House Returns / Runners", charged_quantity=Decimal("1200.0000"), uom_id=kg_uom.id if kg_uom else 1, validation_status=HeatChargeValidationStatus.VALID.value, remarks="Clean heavy runners")
            db.add_all([c2_1, c2_2, c2_3, c2_4, c2_5])

            # Castings produced
            p2_1 = HeatPartsProduced(heat_id=heat2.id, line_number=1, original_part_description="Differential Case Flange (Part #DIF-500-38)", quantity_produced=Decimal("200"), unit_cast_weight=Decimal("38.00"), weight_uom_id=kg_uom.id if kg_uom else 1, classification=CastingClassification.GOOD.value)
            p2_2 = HeatPartsProduced(heat_id=heat2.id, line_number=2, original_part_description="Hydraulic Cylinder End Cap (Part #HYD-350-18)", quantity_produced=Decimal("110"), unit_cast_weight=Decimal("18.50"), weight_uom_id=kg_uom.id if kg_uom else 1, classification=CastingClassification.GOOD.value)
            p2_3 = HeatPartsProduced(heat_id=heat2.id, line_number=3, original_part_description="Runners, Gates & Risers", quantity_produced=Decimal("1"), unit_cast_weight=Decimal("1950.00"), weight_uom_id=kg_uom.id if kg_uom else 1, classification=CastingClassification.REWORK.value)
            db.add_all([p2_1, p2_2, p2_3])
            db.flush()
            logger.info("  ✓ Heat 2 (H-20261108-0001) logged with 5 charges & 3 casting part groups")

        # ---------------------------------------------------------
        # 5. New Waste / Internal Scrap Recovery: WST-20261104-0001
        # ---------------------------------------------------------
        wst_num = "WST-20261104-0001"
        if not db.scalar(select(WasteDispositionHeader).where(WasteDispositionHeader.waste_number == wst_num)):
            logger.info(f"Seeding {wst_num}...")
            wst1 = WasteDispositionHeader(
                waste_number=wst_num,
                disposition_date=date(2026, 11, 4),
                waste_type="RUNNERS_RISERS",
                disposition_type=DispositionType.INTERNAL_RECOVERY.value,
                source_department_id=depts["FDY"].id if "FDY" in depts else 1,
                destination_notes="Foundry Melting WIP",
                notes="Shot-blasted and cleaned runner/riser scrap recovered from fettling shop. Added back to FDY-RM-003 inventory.",
                status=WasteStatus.APPROVED.value,
                created_by="usr_stores_01",
                created_at=datetime(2026, 11, 4, 16, 0, tzinfo=timezone.utc),
            )
            db.add(wst1)
            db.flush()

            it_ret = items["FDY-RM-003"]
            w_line1 = WasteDispositionLineItem(
                waste_id=wst1.id,
                line_number=1,
                material_item_id=it_ret.id,
                uom_id=it_ret.base_uom_id,
                quantity=Decimal("3250.0000"),
                reason="Shot-blasted fettling returns",
                remarks="Clean fettling SG iron returns (runner/risers)",
            )
            db.add(w_line1)
            db.flush()

            db.add(WasteAuditLog(waste_id=wst1.id, action="APPROVED", from_status="SUBMITTED", to_status="APPROVED", actor_id="usr_mgmt_01", comments="Fettling count verified by Plant Supervisor. Posted."))
            db.add(StockLedgerEntry(
                entry_number="ENT-20261104-WST-1",
                posting_group_id=f"WST-{wst1.id}",
                material_item_id=it_ret.id,
                uom_id=it_ret.base_uom_id,
                transaction_date=date(2026, 11, 4),
                posted_at=datetime(2026, 11, 4, 17, 0, tzinfo=timezone.utc),
                movement_type=MovementType.INWARD_RECEIPT.value,
                quantity_delta=Decimal("3250.0000"),
                source_document_type=SourceDocumentType.WASTE.value,
                source_document_id=wst1.id,
                source_line_id=w_line1.id,
                source_document_number=wst1.waste_number,
                reference_number="FETTLING-REC-NOV-01",
                reason="Internal recovery of cleaned runners/risers into stock",
                posted_by="usr_mgmt_01",
            ))
            logger.info("  ✓ Waste Recovery WST-20261104-0001 created & posted to ledger")

        db.commit()
        logger.info("All expanded sample data successfully committed to database!")

    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding expanded samples: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
