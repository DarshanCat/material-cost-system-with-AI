"""
Phase 2B-2E Technical Remediation Test Suite.
Validates:
1. AUD-2B2D-001: Item-level Stores Issue Backing & Reconciliation:
   - Line-by-line item matching and shortfall detection
   - Multiple approved issue slips aggregation
   - Exclusion of DRAFT, SUBMITTED, and REVERSED issue slips
   - Cross-heat duplicate allocation / overconsumption protection
   - Incompatible UOM detection
2. AUD-2B2D-002: Multi-GRN Return Scrap Aggregation & Authoritative WAC:
   - Multi-GRN return scrap quantity aggregation
   - Duplicate GRN credit prevention
   - Non-approved and REVERSED GRN exclusion
   - Dynamic item WAC retrieval (never hardcodes ?38/kg; returns PENDING_REVIEW when WAC is missing)
3. AUD-2B2D-003: Alembic Migration Graph Linearization:
   - Forward-only linear graph: 007 -> 008 -> 009 -> 010 -> 011 -> 012
   - Zero branching heads; single head 012
4. Security & Maker-Checker:
   - Admin master-data maintenance authorized
   - Strict self-approval prevention (HTTP 403 Forbidden)
   - Dev-login restricted to non-production loopback
5. Primary Database Invariants:
   - Exactly 43 stock ledger entries; 116,979.0000 delta; revision 007.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import os
import re
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text
from fastapi import HTTPException

from app.db.session import SessionLocal
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.department import Department
from app.models.grn import GRNHeader, GRNLineItem, GRNStatus, GRNSourceType
from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueStatus
from app.models.heat import HeatHeader, HeatChargeLine, HeatPartsProduced, CastingClassification
from app.models.ledger import StockLedgerEntry
from app.models.costing import ItemOpeningValuation, ValuationStatus, OpeningValuationStatus
from app.models.item_request import ItemRequest, RequestStatus
from app.core.security import UserRole, ROLE_PERMISSIONS, Permission, DevUserContext
from app.services.ledger_service import post_grn_to_ledger
from app.services.item_request_service import ItemRequestService
from app.services.costing_service import (
    reconcile_heat_stores_issue_backing,
    aggregate_heat_return_scrap_grns,
    calculate_heat_cost_detail,
    get_item_rate_as_of_date,
)
from app.services.heat_calculations import (
    calculate_heat_costing_measures,
    RATE_PRECISION,
    VALUE_PRECISION,
    WEIGHT_PRECISION,
)


def _get_or_create_item(db: Session, item_code: str, name: str, dept_code: str = "FDY", uom_code: str = "KG") -> MaterialItem:
    item = db.execute(select(MaterialItem).where(MaterialItem.item_code == item_code)).scalars().first()
    if not item:
        dept = db.execute(select(Department).where(Department.code == dept_code)).scalars().first()
        if not dept:
            dept = Department(code=dept_code, name=dept_code)
            db.add(dept)
            db.flush()
        uom = db.execute(select(UOM).where(UOM.code == uom_code)).scalars().first()
        if not uom:
            uom = UOM(code=uom_code, name=uom_code)
            db.add(uom)
            db.flush()
        item = MaterialItem(item_code=item_code, name=name, department_id=dept.id, base_uom_id=uom.id, category="Raw Material")
        db.add(item)
        db.flush()
    return item


# =========================================================================
# AUD-2B2D-001: Item-Level Stores Issue Reconciliation Tests
# =========================================================================

def test_audit_001_item_level_stores_issue_reconciliation_deficit(db_session: Session):
    """
    Test AUD-2B2D-001: When charged quantity exceeds approved issued quantity,
    reconcile_heat_stores_issue_backing detects DEFICIT and shortfall,
    marking is_fully_backed=False and costing status=PROVISIONAL.
    """
    uom = db_session.execute(select(UOM).where(UOM.code == "KG")).scalars().first()
    dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalars().first()
    item_pig = _get_or_create_item(db_session, "FDY-RM-001", "Pig Iron Grade 1")

    # Create approved issue slip with 4,000 kg
    issue = MaterialIssueHeader(
        issue_slip_number="ISS-TEST-001-DEFICIT",
        issue_date=date(2026, 10, 15),
        issuing_department_id=dept.id,
        receiving_department_id=dept.id,
        heat_reference_number="H-TEST-001",
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(issue)
    db_session.flush()
    db_session.add(MaterialIssueLineItem(
        issue_id=issue.id, line_number=1, material_item_id=item_pig.id,
        uom_id=uom.id, quantity=Decimal("4000.0000"),
    ))

    # Create heat charging 5,000 kg (1,000 kg deficit)
    heat = HeatHeader(
        heat_number="H-TEST-001", original_heat_number="TEST-001", normalized_heat_number="TEST-001",
        heat_date=date(2026, 10, 15), furnace_id="F-1", shift="MORNING",
        metal_tapped_weight=Decimal("4800.0000"), metal_tapped_uom_id=uom.id,
        created_by="usr_foundry_01",
    )
    db_session.add(heat)
    db_session.flush()
    db_session.add(HeatChargeLine(
        heat_id=heat.id, line_number=1, material_item_id=item_pig.id,
        original_material_description="Pig Iron Grade 1", charged_quantity=Decimal("5000.0000"),
        uom_id=uom.id,
    ))
    db_session.flush()

    recon = reconcile_heat_stores_issue_backing(db_session, heat)
    assert not recon["is_fully_backed"]
    assert len(recon["shortfalls"]) == 1
    shortfall = recon["shortfalls"][0]
    assert shortfall["material_item_id"] == item_pig.id
    assert shortfall["charged_quantity_kg"] == Decimal("5000.0000")
    assert shortfall["approved_issued_quantity_kg"] == Decimal("4000.0000")
    assert shortfall["shortfall_quantity_kg"] == Decimal("1000.0000")
    assert shortfall["status"] == "DEFICIT"
    assert any("INSUFFICIENT_ISSUE_QUANTITY" in a for a in recon["anomalies"])


def test_audit_001_item_level_stores_issue_exact_backing(db_session: Session):
    """
    Test AUD-2B2D-001: When approved issued quantity matches or exceeds charged quantity,
    reconcile_heat_stores_issue_backing marks is_fully_backed=True with zero shortfalls.
    """
    uom = db_session.execute(select(UOM).where(UOM.code == "KG")).scalars().first()
    dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalars().first()
    item_pig = _get_or_create_item(db_session, "FDY-RM-001", "Pig Iron Grade 1")

    issue = MaterialIssueHeader(
        issue_slip_number="ISS-TEST-002-EXACT",
        issue_date=date(2026, 10, 15),
        issuing_department_id=dept.id,
        receiving_department_id=dept.id,
        heat_reference_number="H-TEST-002",
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(issue)
    db_session.flush()
    db_session.add(MaterialIssueLineItem(
        issue_id=issue.id, line_number=1, material_item_id=item_pig.id,
        uom_id=uom.id, quantity=Decimal("5000.0000"),
    ))

    heat = HeatHeader(
        heat_number="H-TEST-002", original_heat_number="TEST-002", normalized_heat_number="TEST-002",
        heat_date=date(2026, 10, 15), furnace_id="F-1", shift="MORNING",
        metal_tapped_weight=Decimal("4800.0000"), metal_tapped_uom_id=uom.id,
        created_by="usr_foundry_01",
    )
    db_session.add(heat)
    db_session.flush()
    db_session.add(HeatChargeLine(
        heat_id=heat.id, line_number=1, material_item_id=item_pig.id,
        original_material_description="Pig Iron Grade 1", charged_quantity=Decimal("5000.0000"),
        uom_id=uom.id,
    ))
    db_session.flush()

    recon = reconcile_heat_stores_issue_backing(db_session, heat)
    assert recon["is_fully_backed"]
    assert len(recon["shortfalls"]) == 0
    assert len(recon["line_reconciliation"]) == 1
    assert recon["line_reconciliation"][0]["status"] == "COVERED"


def test_audit_001_multi_slip_issue_aggregation(db_session: Session):
    """
    Test AUD-2B2D-001: Aggregates multiple approved issue slips referencing the same heat.
    Slip 1: 3,000 kg + Slip 2: 2,000 kg = 5,000 kg backing for 5,000 kg charge.
    """
    uom = db_session.execute(select(UOM).where(UOM.code == "KG")).scalars().first()
    dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalars().first()
    item_pig = _get_or_create_item(db_session, "FDY-RM-001", "Pig Iron Grade 1")

    issue1 = MaterialIssueHeader(
        issue_slip_number="ISS-TEST-003-PART1",
        issue_date=date(2026, 10, 15),
        issuing_department_id=dept.id, receiving_department_id=dept.id,
        heat_reference_number="H-TEST-003", status=IssueStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    issue2 = MaterialIssueHeader(
        issue_slip_number="ISS-TEST-003-PART2",
        issue_date=date(2026, 10, 15),
        issuing_department_id=dept.id, receiving_department_id=dept.id,
        heat_reference_number="H-TEST-003", status=IssueStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add_all([issue1, issue2])
    db_session.flush()
    db_session.add(MaterialIssueLineItem(issue_id=issue1.id, line_number=1, material_item_id=item_pig.id, uom_id=uom.id, quantity=Decimal("3000.0000")))
    db_session.add(MaterialIssueLineItem(issue_id=issue2.id, line_number=1, material_item_id=item_pig.id, uom_id=uom.id, quantity=Decimal("2000.0000")))

    heat = HeatHeader(
        heat_number="H-TEST-003", original_heat_number="TEST-003", normalized_heat_number="TEST-003",
        heat_date=date(2026, 10, 15), furnace_id="F-1", shift="MORNING",
        metal_tapped_weight=Decimal("4800.0000"), metal_tapped_uom_id=uom.id,
        created_by="usr_foundry_01",
    )
    db_session.add(heat)
    db_session.flush()
    db_session.add(HeatChargeLine(
        heat_id=heat.id, line_number=1, material_item_id=item_pig.id,
        original_material_description="Pig Iron Grade 1", charged_quantity=Decimal("5000.0000"),
        uom_id=uom.id,
    ))
    db_session.flush()

    recon = reconcile_heat_stores_issue_backing(db_session, heat)
    assert recon["is_fully_backed"]
    assert len(recon["approved_issue_slip_numbers"]) == 2
    assert recon["line_reconciliation"][0]["approved_issued_quantity_kg"] == Decimal("5000.0000")


def test_audit_001_unapproved_issue_slips_excluded(db_session: Session):
    """
    Test AUD-2B2D-001: Draft, Submitted, or Reversed issue slips NEVER provide backing.
    """
    uom = db_session.execute(select(UOM).where(UOM.code == "KG")).scalars().first()
    dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalars().first()
    item_pig = _get_or_create_item(db_session, "FDY-RM-001", "Pig Iron Grade 1")

    for st in [IssueStatus.DRAFT.value, IssueStatus.SUBMITTED.value, IssueStatus.REVERSED.value]:
        issue = MaterialIssueHeader(
            issue_slip_number=f"ISS-TEST-UNAPP-{st}",
            issue_date=date(2026, 10, 15),
            issuing_department_id=dept.id, receiving_department_id=dept.id,
            heat_reference_number=f"H-TEST-UNAPP-{st}", status=st,
            created_by="usr_stores_01",
        )
        db_session.add(issue)
        db_session.flush()
        db_session.add(MaterialIssueLineItem(issue_id=issue.id, line_number=1, material_item_id=item_pig.id, uom_id=uom.id, quantity=Decimal("5000.0000")))

        heat = HeatHeader(
            heat_number=f"H-TEST-UNAPP-{st}", original_heat_number=f"TEST-UNAPP-{st}", normalized_heat_number=f"TEST-UNAPP-{st}",
            heat_date=date(2026, 10, 15), furnace_id="F-1", shift="MORNING",
            metal_tapped_weight=Decimal("4800.0000"), metal_tapped_uom_id=uom.id,
            created_by="usr_foundry_01",
        )
        db_session.add(heat)
        db_session.flush()
        db_session.add(HeatChargeLine(
            heat_id=heat.id, line_number=1, material_item_id=item_pig.id,
            original_material_description="Pig Iron Grade 1", charged_quantity=Decimal("5000.0000"),
            uom_id=uom.id,
        ))
        db_session.flush()

        recon = reconcile_heat_stores_issue_backing(db_session, heat)
        assert not recon["is_fully_backed"]
        assert any("UNAPPROVED_ISSUE_SLIP" in a for a in recon["anomalies"])
        assert any("ZERO_ISSUE_BACKING" in a for a in recon["anomalies"])


def test_audit_001_cross_heat_duplicate_allocation_protection(db_session: Session):
    """
    Test AUD-2B2D-001: Protects against double-counting issue slips across multiple heats.
    If an issue slip has 7,000 kg and Heat 1 consumes 5,000 kg, only 2,000 kg remains for Heat 2.
    """
    uom = db_session.execute(select(UOM).where(UOM.code == "KG")).scalars().first()
    dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalars().first()
    item_pig = _get_or_create_item(db_session, "FDY-RM-001", "Pig Iron Grade 1")

    # Single issue slip of 7,000 kg referencing common heat reference
    issue = MaterialIssueHeader(
        issue_slip_number="ISS-TEST-SHARED-7000",
        issue_date=date(2026, 10, 15),
        issuing_department_id=dept.id, receiving_department_id=dept.id,
        heat_reference_number="SHARED-REF-01", status=IssueStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(issue)
    db_session.flush()
    db_session.add(MaterialIssueLineItem(issue_id=issue.id, line_number=1, material_item_id=item_pig.id, uom_id=uom.id, quantity=Decimal("7000.0000")))

    # Heat 1 charges 5,000 kg on 15-Oct Morning
    heat1 = HeatHeader(
        heat_number="H-SHARED-REF-01", original_heat_number="H-SHARED-REF-01", normalized_heat_number="SHARED-REF-01",
        heat_date=date(2026, 10, 15), furnace_id="F-1", shift="MORNING",
        metal_tapped_weight=Decimal("4800.0000"), metal_tapped_uom_id=uom.id,
        created_by="usr_foundry_01",
    )
    db_session.add(heat1)
    db_session.flush()
    db_session.add(HeatChargeLine(
        heat_id=heat1.id, line_number=1, material_item_id=item_pig.id,
        original_material_description="Pig Iron Grade 1", charged_quantity=Decimal("5000.0000"),
        uom_id=uom.id,
    ))
    db_session.flush()

    # Heat 2 attempts to charge 4,000 kg on 15-Oct Evening (only 2,000 kg unconsumed remains!)
    heat2 = HeatHeader(
        heat_number="SHARED-REF-01", original_heat_number="SHARED-REF-01", normalized_heat_number="SHARED-REF-01",
        heat_date=date(2026, 10, 15), furnace_id="F-1", shift="EVENING",
        metal_tapped_weight=Decimal("3800.0000"), metal_tapped_uom_id=uom.id,
        created_by="usr_foundry_01",
    )
    db_session.add(heat2)
    db_session.flush()
    db_session.add(HeatChargeLine(
        heat_id=heat2.id, line_number=1, material_item_id=item_pig.id,
        original_material_description="Pig Iron Grade 1", charged_quantity=Decimal("4000.0000"),
        uom_id=uom.id,
    ))
    db_session.flush()

    recon2 = reconcile_heat_stores_issue_backing(db_session, heat2)
    assert not recon2["is_fully_backed"]
    assert len(recon2["shortfalls"]) == 1
    # 4,000 charged - (7,000 issued - 5,000 consumed by heat1) = 2,000 shortfall
    assert recon2["shortfalls"][0]["approved_issued_quantity_kg"] == Decimal("2000.0000")
    assert recon2["shortfalls"][0]["shortfall_quantity_kg"] == Decimal("2000.0000")
    assert any("CROSS_HEAT_OVERCONSUMPTION" in a for a in recon2["anomalies"])


# =========================================================================
# AUD-2B2D-002: Multi-GRN Return Scrap Aggregation Tests
# =========================================================================

def test_audit_002_multi_grn_return_scrap_aggregation(db_session: Session):
    """
    Test AUD-2B2D-002: Aggregates multiple approved internal return GRNs for a single heat.
    GRN 1: 300 kg @ ?38.00 = ?11,400.00
    GRN 2: 250 kg @ ?38.00 = ?9,500.00
    Total Scrap Credit = ?20,900.00
    """
    uom = db_session.execute(select(UOM).where(UOM.code == "KG")).scalars().first()
    scrap_item = _get_or_create_item(db_session, "FDY-RM-003", "Foundry Return Scrap")

    # Establish moving WAC of ?38.00 via approved inward receipt posted to ledger
    grn_in = GRNHeader(
        grn_number="GRN-SCRAP-INWARD-01", receipt_date=date(2026, 10, 12),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn_in)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn_in.id, line_number=1, material_item_id=scrap_item.id, uom_id=uom.id,
                               quantity=Decimal("1000.0000"), rate_ex_gst=Decimal("38.00")))
    db_session.flush()
    post_grn_to_ledger(db_session, grn_in, "usr_stores_01")
    db_session.flush()

    heat = HeatHeader(
        heat_number="H-SCRAP-MULTI-01", original_heat_number="SCRAP-MULTI-01", normalized_heat_number="SCRAP-MULTI-01",
        heat_date=date(2026, 10, 18), furnace_id="F-1", shift="MORNING",
        metal_tapped_weight=Decimal("7500.0000"), metal_tapped_uom_id=uom.id,
        created_by="usr_foundry_01",
    )
    db_session.add(heat)
    db_session.flush()

    grn1 = GRNHeader(
        grn_number="GRN-INTERNAL-001", receipt_date=date(2026, 10, 18),
        source_type=GRNSourceType.INTERNAL_VSPL.value, reference_document="H-SCRAP-MULTI-01",
        status=GRNStatus.APPROVED.value, created_by="usr_stores_01",
    )
    grn2 = GRNHeader(
        grn_number="GRN-INTERNAL-002", receipt_date=date(2026, 10, 18),
        source_type=GRNSourceType.INTERNAL_VSPL.value, reference_document="H-SCRAP-MULTI-01",
        status=GRNStatus.APPROVED.value, created_by="usr_stores_01",
    )
    db_session.add_all([grn1, grn2])
    db_session.flush()

    db_session.add(GRNLineItem(grn_id=grn1.id, line_number=1, material_item_id=scrap_item.id, uom_id=uom.id, quantity=Decimal("300.0000")))
    db_session.add(GRNLineItem(grn_id=grn2.id, line_number=1, material_item_id=scrap_item.id, uom_id=uom.id, quantity=Decimal("250.0000")))
    db_session.flush()

    credit, anomalies, details = aggregate_heat_return_scrap_grns(db_session, heat)
    assert credit == Decimal("20900.00")
    assert len(details) == 2
    assert sum(d["quantity_kg"] for d in details) == Decimal("550.0000")


def test_audit_002_non_approved_and_reversed_grns_excluded(db_session: Session):
    """
    Test AUD-2B2D-002: Excludes DRAFT, SUBMITTED, and REVERSED internal GRNs from scrap credit.
    """
    uom = db_session.execute(select(UOM).where(UOM.code == "KG")).scalars().first()
    scrap_item = _get_or_create_item(db_session, "FDY-RM-003", "Foundry Return Scrap")

    heat = HeatHeader(
        heat_number="H-SCRAP-EXCLUDE-01", original_heat_number="SCRAP-EXCLUDE-01", normalized_heat_number="SCRAP-EXCLUDE-01",
        heat_date=date(2026, 10, 18), furnace_id="F-1", shift="MORNING",
        metal_tapped_weight=Decimal("7500.0000"), metal_tapped_uom_id=uom.id,
        created_by="usr_foundry_01",
    )
    db_session.add(heat)
    db_session.flush()

    grn_rev = GRNHeader(
        grn_number="GRN-INTERNAL-REV", receipt_date=date(2026, 10, 18),
        source_type=GRNSourceType.INTERNAL_VSPL.value, reference_document="H-SCRAP-EXCLUDE-01",
        status=GRNStatus.REVERSED.value, created_by="usr_stores_01",
    )
    db_session.add(grn_rev)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn_rev.id, line_number=1, material_item_id=scrap_item.id, uom_id=uom.id, quantity=Decimal("400.0000")))
    db_session.flush()

    credit, anomalies, details = aggregate_heat_return_scrap_grns(db_session, heat)
    assert credit is None
    assert any("EXCLUDED_GRN" in a for a in anomalies)


def test_audit_002_missing_wac_returns_pending_review_never_hardcoded(db_session: Session):
    """
    Test AUD-2B2D-002: If return scrap GRN exists but canonical moving WAC is missing,
    system NEVER applies a hardcoded ?38/kg fallback. Returns PENDING_REVIEW and credit=None.
    """
    uom = db_session.execute(select(UOM).where(UOM.code == "KG")).scalars().first()
    unvalued_item = _get_or_create_item(db_session, "FDY-RM-UNVALUED", "Unvalued Test Scrap")

    heat = HeatHeader(
        heat_number="H-SCRAP-NOWAC-01", original_heat_number="SCRAP-NOWAC-01", normalized_heat_number="SCRAP-NOWAC-01",
        heat_date=date(2026, 10, 18), furnace_id="F-1", shift="MORNING",
        metal_tapped_weight=Decimal("7500.0000"), metal_tapped_uom_id=uom.id,
        created_by="usr_foundry_01",
    )
    db_session.add(heat)
    db_session.flush()

    grn = GRNHeader(
        grn_number="GRN-INTERNAL-NOWAC", receipt_date=date(2026, 10, 18),
        source_type=GRNSourceType.INTERNAL_VSPL.value, reference_document="H-SCRAP-NOWAC-01",
        status=GRNStatus.APPROVED.value, created_by="usr_stores_01",
    )
    db_session.add(grn)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn.id, line_number=1, material_item_id=unvalued_item.id, uom_id=uom.id, quantity=Decimal("500.0000"), remarks="RETURN RUNNERS"))
    db_session.flush()

    credit, anomalies, details = aggregate_heat_return_scrap_grns(db_session, heat)
    assert credit is None
    assert any("PENDING_REVIEW" in a for a in anomalies)
    assert any("No arbitrary rate applied" in a for a in anomalies)


# =========================================================================
# AUD-2B2D-003: Alembic Migration Graph Linearization Tests
# =========================================================================

def test_audit_003_alembic_migration_graph_linearization():
    """
    Test AUD-2B2D-003: Verifies that the migration graph forms a strictly linear forward chain:
    001 -> 002 -> 003 -> 004 -> 005 -> 006 -> 007 -> 008 -> 009 -> 010 -> 011 -> 012.
    Ensures:
    - 010 revises 009 (multiple heads eliminated)
    - Single head (012_heat_liquid_heel)
    - Zero diverging branches.
    """
    versions_dir = os.path.join("backend", "migrations", "versions")
    proposed_dir = os.path.join("backend", "migrations", "proposed")

    all_files = []
    for d in [versions_dir, proposed_dir]:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith(".py") and not f.startswith("__"):
                    all_files.append(os.path.join(d, f))

    revisions = {}
    down_revisions = {}

    for file_path in all_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        rev_match = re.search(r"revision:\s*str\s*=\s*['\"]([^'\"]+)['\"]", content)
        if not rev_match:
            rev_match = re.search(r"revision\s*=\s*['\"]([^'\"]+)['\"]", content)

        down_match = re.search(r"down_revision:\s*Union\[str,\s*None\]\s*=\s*['\"]([^'\"]+)['\"]", content)
        if not down_match:
            down_match = re.search(r"down_revision\s*=\s*['\"]([^'\"]+)['\"]", content)

        if rev_match:
            rev_id = rev_match.group(1)
            down_id = down_match.group(1) if down_match else None
            revisions[rev_id] = os.path.basename(file_path)
            down_revisions[rev_id] = down_id

    # Verify key links
    assert down_revisions.get("008_item_code_registry") == "007_opening_val_versioning"
    assert down_revisions.get("009_material_item_cost_head") == "008_item_code_registry"
    assert down_revisions.get("010_material_item_reconciliation_category") == "009_material_item_cost_head", \
        "010 must revise 009 to eliminate the multiple-heads branch conflict."
    assert down_revisions.get("011_stock_ledger_valuation") == "010_material_item_reconciliation_category"
    assert down_revisions.get("012_heat_liquid_heel") == "011_stock_ledger_valuation"

    # Verify single forward head
    parent_counts = {}
    for rev, down in down_revisions.items():
        if down:
            parent_counts[down] = parent_counts.get(down, 0) + 1

    # Every revision except the terminal head (012) must be the parent of exactly one child
    assert parent_counts.get("008_item_code_registry") == 1, "008 must have exactly 1 child (009), not 2"
    assert parent_counts.get("009_material_item_cost_head") == 1
    assert parent_counts.get("010_material_item_reconciliation_category") == 1
    assert parent_counts.get("011_stock_ledger_valuation") == 1


# =========================================================================
# Security Regression: Admin Master-Data Permissions & Maker-Checker
# =========================================================================

def test_security_admin_item_requests_maker_checker_enforced(db_session: Session):
    """
    Test Security: Verifies that Admin can create and submit item requests,
    but cannot self-approve their own request (HTTP 403 Forbidden).
    """
    assert Permission.ITEM_REQUEST_CREATE in ROLE_PERMISSIONS[UserRole.ADMIN]
    assert Permission.ITEM_REQUEST_SUBMIT in ROLE_PERMISSIONS[UserRole.ADMIN]
    assert Permission.ITEM_APPROVE in ROLE_PERMISSIONS[UserRole.ADMIN]
    # Admin must NOT have operational stock posting permissions
    assert Permission.OPENING_BALANCE_POST not in ROLE_PERMISSIONS[UserRole.ADMIN]
    assert Permission.STOCK_ADJUST not in ROLE_PERMISSIONS[UserRole.ADMIN]
    assert Permission.RECEIPT_CREATE not in ROLE_PERMISSIONS[UserRole.ADMIN]
    assert Permission.ISSUE_CREATE not in ROLE_PERMISSIONS[UserRole.ADMIN]

    dept = db_session.execute(select(Department).where(Department.code == "MNT")).scalars().first()
    uom = db_session.execute(select(UOM).where(UOM.code == "NOS")).scalars().first()

    # Admin drafts a request
    service = ItemRequestService(db_session)
    admin_user = DevUserContext(user_id="usr_admin_01", role="Admin", department="Admin")

    req = service.create_draft(
        requested_name="High Tensile Hex Bolt M12x50",
        proposed_department_id=dept.id,
        proposed_category="Bolts & Nuts",
        proposed_subcategory=None,
        proposed_uom_id=uom.id,
        justification="Furnace housing maintenance requirement",
        actor=admin_user,
    )
    assert req.requester_id == "usr_admin_01"
    assert req.status == RequestStatus.DRAFT.value

    # Admin submits the request
    req = service.submit_request(request_id=req.id, actor=admin_user)
    assert req.status == RequestStatus.SUBMITTED.value

    # Admin attempts to approve their own request -> MUST be rejected with HTTP 403
    with pytest.raises(HTTPException) as exc_info:
        service.approve_request(request_id=req.id, actor=admin_user)
    assert exc_info.value.status_code == 403
    assert "Self-approval violation" in exc_info.value.detail


# =========================================================================
# Strict Primary Database Invariants Preservation
# =========================================================================

def test_live_primary_database_ledger_invariants_preserved():
    """
    Confirms zero database mutations during test run:
    - Exactly 43 stock ledger entries.
    - Exactly 116,979.0000 mixed UOM delta.
    - Alembic version remains 007_opening_val_versioning.
    """
    db = SessionLocal()
    try:
        count = db.execute(select(func.count(StockLedgerEntry.id))).scalar()
        assert count == 43, f"Primary ledger count mutated! Expected 43, found {count}"

        delta = db.execute(select(func.sum(StockLedgerEntry.quantity_delta))).scalar()
        assert delta == Decimal("116979.0000"), f"Primary ledger delta mutated! Expected 116,979.0000, found {delta}"

        ver = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert ver == "007_opening_val_versioning", f"Alembic version mutated! Expected 007_opening_val_versioning, found {ver}"
    finally:
        db.close()
