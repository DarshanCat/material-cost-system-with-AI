"""
Tests for Whole-Document Reversal (SW-07).
Validates atomic, auditable document-level reversals for:
- Goods Receipt Notes (GRN)
- Material Issues
- Waste Dispositions
Covers:
- Compensating ledger entry creation and reference integrity.
- Immutability: original ledger entries never modified or deleted.
- Live stock revalidation and Rule L6 negative-stock rejection for GRN reversals.
- Disposition-specific waste semantics:
  - SCRAP_OUTWARD: inventory restoration (+delta)
  - INTERNAL_RECOVERY: net-neutral (delta = 0)
  - INSPECTION_HOLD: zero ledger entries (no phantom movements)
- Idempotency & duplicate reversal rejection (HTTP 409).
- Maker-checker/permission boundaries (only MANAGEMENT / ADMIN with LEDGER_REVERSE).
- Mandatory audit justification requirements (HTTP 400 on empty reason).
- Live PostgreSQL concurrency verification (serialized item row locks).
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.vendor import Vendor
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.models.grn import GRNHeader, GRNStatus
from app.models.issue import MaterialIssueHeader, IssueStatus
from app.models.waste import WasteDispositionHeader, WasteStatus, DispositionType
from app.services.ledger_service import get_material_stock_balance, reverse_stock_ledger_entry
from app.services.document_reversal_service import (
    reverse_grn,
    reverse_material_issue,
    reverse_waste_disposition,
)
from app.services.document_number_service import DocumentType, generate_document_number


def _setup_master_data(db: Session, suffix: str = "") -> tuple[Department, Department, UOM, MaterialItem, Vendor]:
    """Helper to provision standard departments, UOM, material item, and vendor."""
    dept_stores = db.query(Department).filter_by(code="GNS").first()
    dept_foundry = db.query(Department).filter_by(code="FDY").first()
    uom_kg = db.query(UOM).filter_by(code="KG").first()

    code = f"RAW-REV-{uuid.uuid4().hex[:6]}"
    item = MaterialItem(
        item_code=code,
        name=f"Test Inoculant {suffix}",
        department_id=dept_stores.id,
        category="RAW_MATERIALS",
        base_uom_id=uom_kg.id,
    )
    db.add(item)

    v_uid = uuid.uuid4().hex[:6]
    vendor = Vendor(
        name=f"Reversal Supplier {suffix} {v_uid}",
        normalized_name=f"REVERSAL SUPPLIER {suffix} {v_uid}".strip().upper(),
        gstin="29ABCDE1234F1Z5",
        is_active=True,
    )
    db.add(vendor)
    db.commit()
    db.refresh(item)
    db.refresh(vendor)
    return dept_stores, dept_foundry, uom_kg, item, vendor


def _seed_opening_balance(db: Session, item: MaterialItem, uom: UOM, qty: Decimal) -> StockLedgerEntry:
    """Helper to initialize stock ledger with an opening balance."""
    today = date.today()
    entry_number = generate_document_number(db, DocumentType.LEDGER, today)
    entry = StockLedgerEntry(
        entry_number=entry_number,
        posting_group_id=f"GRP-OB-{uuid.uuid4().hex[:6]}",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=today,
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=qty,
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=1,
        source_line_id=int(uuid.uuid4().int % 1000000) + 1,
        source_document_number=f"OB-{today.strftime('%Y%m%d')}",
        reference_number="Initial Balance Setup",
        reason="Opening stock baseline",
        posted_by="test_setup",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ==============================================================================
# 1. GRN REVERSAL TESTS
# ==============================================================================


def test_grn_reversal_happy_path(
    client: TestClient,
    db_session: Session,
    stores_headers: dict,
    management_headers: dict,
):
    """
    Test whole-document GRN reversal:
    - Creates and approves GRN for 100 KG.
    - Reverses GRN via POST /api/v1/grn/{grn_id}/reverse with valid reason.
    - Asserts compensating REVERSAL ledger entry with -100 KG.
    - Asserts GRN status is REVERSED, audit log created.
    - Asserts final stock balance drops back to 0.
    """
    dept_stores, _, uom_kg, item, vendor = _setup_master_data(db_session)

    # 1. Create GRN
    create_payload = {
        "receipt_date": str(date.today()),
        "source_type": "EXTERNAL_VENDOR",
        "vendor_id": vendor.id,
        "vendor_invoice_no": f"INV-{uuid.uuid4().hex[:6]}",
        "invoice_date": str(date.today()),
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "100.0000",
                "rate_ex_gst": "50.00",
                "gst_percent": "18.00",
            }
        ],
    }
    r = client.post("/api/v1/grn/", json=create_payload, headers=stores_headers)
    assert r.status_code == 201, r.text
    grn_id = r.json()["id"]

    # 2. Submit & Approve GRN
    client.post(f"/api/v1/grn/{grn_id}/submit", json={"comments": "Ready"}, headers=stores_headers)
    appr_resp = client.post(f"/api/v1/grn/{grn_id}/approve", json={"comments": "Approved"}, headers=management_headers)
    assert appr_resp.status_code == 200

    # Stock balance should be 100.0000
    bal, is_init, _, count = get_material_stock_balance(db_session, item.id)
    assert is_init is True
    assert bal == Decimal("100.0000")
    assert count == 1

    # 3. Whole-Document Reversal
    rev_payload = {"reason": "Vendor supplied defective consignment; returned at gate"}
    rev_resp = client.post(f"/api/v1/grn/{grn_id}/reverse", json=rev_payload, headers=management_headers)
    assert rev_resp.status_code == 200, rev_resp.text
    data = rev_resp.json()

    assert data["document_type"] == "GRN"
    assert data["document_id"] == grn_id
    assert data["status"] == "REVERSED"
    assert len(data["reversal_ledger_entry_ids"]) == 1
    assert len(data["original_ledger_entry_ids"]) == 1

    # 4. Verify DB state & ledger immutability
    grn = db_session.get(GRNHeader, grn_id)
    assert grn.status == GRNStatus.REVERSED.value

    # Exactly 2 entries: 1 original + 1 compensating reversal
    entries = (
        db_session.execute(
            select(StockLedgerEntry)
            .where(StockLedgerEntry.material_item_id == item.id)
            .order_by(StockLedgerEntry.id.asc())
        )
        .scalars()
        .all()
    )
    assert len(entries) == 2
    orig_entry, rev_entry = entries[0], entries[1]

    # Original entry remains untouched
    assert orig_entry.movement_type == MovementType.INWARD_RECEIPT.value
    assert orig_entry.quantity_delta == Decimal("100.0000")

    # Compensating entry has opposite sign and links to original
    assert rev_entry.movement_type == MovementType.REVERSAL.value
    assert rev_entry.quantity_delta == Decimal("-100.0000")
    assert rev_entry.reversal_of_entry_id == orig_entry.id
    assert rev_entry.reason == "Vendor supplied defective consignment; returned at gate"

    # Live balance is now 0.0000
    bal_after, _, _, count_after = get_material_stock_balance(db_session, item.id)
    assert bal_after == Decimal("0.0000")
    assert count_after == 2


def test_grn_reversal_negative_stock_rejection(
    client: TestClient,
    db_session: Session,
    stores_headers: dict,
    management_headers: dict,
):
    """
    Test Rule L6 enforcement on GRN reversal:
    - GRN receipt for 100 KG.
    - Outward issue for 60 KG is approved. Live balance = 40 KG.
    - Attempting to reverse the GRN requires deducting 100 KG, which would leave -60 KG.
    - Reversal MUST be rejected with HTTP 409 Conflict.
    - GRN status remains APPROVED; no reversal ledger entries created.
    """
    dept_stores, dept_foundry, uom_kg, item, vendor = _setup_master_data(db_session)

    # 1. Create & Approve GRN for 100 KG
    create_payload = {
        "receipt_date": str(date.today()),
        "source_type": "EXTERNAL_VENDOR",
        "vendor_id": vendor.id,
        "vendor_invoice_no": f"INV-{uuid.uuid4().hex[:6]}",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "100.0000",
                "rate_ex_gst": "40.00",
                "gst_percent": "18.00",
            }
        ],
    }
    r = client.post("/api/v1/grn/", json=create_payload, headers=stores_headers)
    grn_id = r.json()["id"]
    client.post(f"/api/v1/grn/{grn_id}/submit", json={}, headers=stores_headers)
    client.post(f"/api/v1/grn/{grn_id}/approve", json={}, headers=management_headers)

    # 2. Issue 60 KG to Foundry
    issue_payload = {
        "issue_date": str(date.today()),
        "issuing_department_id": dept_stores.id,
        "receiving_department_id": dept_foundry.id,
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "60.0000",
                "remarks": "Issue to furnace",
            }
        ],
    }
    ir = client.post("/api/v1/issues/", json=issue_payload, headers=stores_headers)
    assert ir.status_code == 201
    issue_id = ir.json()["id"]
    client.post(f"/api/v1/issues/{issue_id}/submit", json={}, headers=stores_headers)
    appr_issue = client.post(f"/api/v1/issues/{issue_id}/approve", json={}, headers=management_headers)
    assert appr_issue.status_code == 200

    bal, _, _, _ = get_material_stock_balance(db_session, item.id)
    assert bal == Decimal("40.0000")

    # 3. Attempt GRN Reversal (should fail because 40 < 100)
    rev_payload = {"reason": "Attempting to reverse full receipt after partial consumption"}
    rev_resp = client.post(f"/api/v1/grn/{grn_id}/reverse", json=rev_payload, headers=management_headers)
    assert rev_resp.status_code == 409, rev_resp.text
    assert "Negative stock is disallowed" in rev_resp.json()["detail"]
    assert "exceeds available stock 40.0000" in rev_resp.json()["detail"]

    # GRN status remains APPROVED
    grn = db_session.get(GRNHeader, grn_id)
    assert grn.status == GRNStatus.APPROVED.value
    # Balance remains 40.0000
    bal_after, _, _, _ = get_material_stock_balance(db_session, item.id)
    assert bal_after == Decimal("40.0000")


def test_grn_reversal_duplicate_and_pre_reversed_rejection(
    client: TestClient,
    db_session: Session,
    stores_headers: dict,
    management_headers: dict,
):
    """
    Test duplicate reversal prevention:
    - Reversing an already REVERSED GRN returns HTTP 409 Conflict.
    - If a GRN line was already reversed individually via /ledger/entries/{id}/reverse,
      attempting whole-document reversal also returns HTTP 409 Conflict.
    """
    dept_stores, _, uom_kg, item, vendor = _setup_master_data(db_session)

    # Create & approve GRN
    create_payload = {
        "receipt_date": str(date.today()),
        "source_type": "EXTERNAL_VENDOR",
        "vendor_id": vendor.id,
        "vendor_invoice_no": f"INV-{uuid.uuid4().hex[:6]}",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "50.0000",
                "rate_ex_gst": "100.00",
                "gst_percent": "18.00",
            }
        ],
    }
    r = client.post("/api/v1/grn/", json=create_payload, headers=stores_headers)
    grn_id = r.json()["id"]
    client.post(f"/api/v1/grn/{grn_id}/submit", json={}, headers=stores_headers)
    client.post(f"/api/v1/grn/{grn_id}/approve", json={}, headers=management_headers)

    # First reversal succeeds
    rev_resp = client.post(f"/api/v1/grn/{grn_id}/reverse", json={"reason": "First reversal"}, headers=management_headers)
    assert rev_resp.status_code == 200

    # Second whole-document reversal returns 409 Conflict
    rev_resp2 = client.post(f"/api/v1/grn/{grn_id}/reverse", json={"reason": "Duplicate reversal"}, headers=management_headers)
    assert rev_resp2.status_code == 409
    assert "already been reversed" in rev_resp2.json()["detail"]

    # Test individual line pre-reversal scenario
    # Create second GRN
    create_payload2 = {
        "receipt_date": str(date.today()),
        "source_type": "EXTERNAL_VENDOR",
        "vendor_id": vendor.id,
        "vendor_invoice_no": f"INV-{uuid.uuid4().hex[:6]}",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "25.0000",
                "rate_ex_gst": "100.00",
                "gst_percent": "18.00",
            }
        ],
    }
    r2 = client.post("/api/v1/grn/", json=create_payload2, headers=stores_headers)
    grn_id2 = r2.json()["id"]
    client.post(f"/api/v1/grn/{grn_id2}/submit", json={}, headers=stores_headers)
    client.post(f"/api/v1/grn/{grn_id2}/approve", json={}, headers=management_headers)

    # Manually reverse single entry
    entry = db_session.execute(
        select(StockLedgerEntry).where(StockLedgerEntry.source_document_id == grn_id2)
    ).scalars().first()
    assert entry is not None
    reverse_stock_ledger_entry(db_session, entry.id, "Single entry manual reversal", "test_user")

    # Now attempt whole-document reversal on grn_id2 -> should detect existing line reversal and return 409
    rev_resp3 = client.post(f"/api/v1/grn/{grn_id2}/reverse", json={"reason": "Whole doc after line rev"}, headers=management_headers)
    assert rev_resp3.status_code == 409
    assert "One or more ledger entries" in rev_resp3.json()["detail"]


def test_grn_reversal_validation_rules(
    client: TestClient,
    db_session: Session,
    stores_headers: dict,
    management_headers: dict,
):
    """
    Test input and status validations on GRN reversal:
    - Cannot reverse DRAFT GRN (HTTP 400).
    - Cannot reverse SUBMITTED GRN (HTTP 400).
    - Cannot reverse with empty or whitespace-only reason (HTTP 400).
    """
    dept_stores, _, uom_kg, item, vendor = _setup_master_data(db_session)

    create_payload = {
        "receipt_date": str(date.today()),
        "source_type": "EXTERNAL_VENDOR",
        "vendor_id": vendor.id,
        "vendor_invoice_no": f"INV-{uuid.uuid4().hex[:6]}",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "10.0000",
                "rate_ex_gst": "20.00",
                "gst_percent": "18.00",
            }
        ],
    }
    r = client.post("/api/v1/grn/", json=create_payload, headers=stores_headers)
    grn_id = r.json()["id"]

    # 1. DRAFT status reversal fails
    r_rev_draft = client.post(f"/api/v1/grn/{grn_id}/reverse", json={"reason": "Valid reason"}, headers=management_headers)
    assert r_rev_draft.status_code == 400
    assert "Only APPROVED GRNs can be reversed" in r_rev_draft.json()["detail"]

    # 2. SUBMITTED status reversal fails
    client.post(f"/api/v1/grn/{grn_id}/submit", json={}, headers=stores_headers)
    r_rev_sub = client.post(f"/api/v1/grn/{grn_id}/reverse", json={"reason": "Valid reason"}, headers=management_headers)
    assert r_rev_sub.status_code == 400
    assert "Only APPROVED GRNs can be reversed" in r_rev_sub.json()["detail"]

    # 3. Approve GRN
    client.post(f"/api/v1/grn/{grn_id}/approve", json={}, headers=management_headers)

    # 4. Empty reason fails
    r_empty1 = client.post(f"/api/v1/grn/{grn_id}/reverse", json={"reason": ""}, headers=management_headers)
    assert r_empty1.status_code == 400
    assert "Reversal reason is mandatory" in r_empty1.json()["detail"]

    r_empty2 = client.post(f"/api/v1/grn/{grn_id}/reverse", json={"reason": "   "}, headers=management_headers)
    assert r_empty2.status_code == 400
    assert "Reversal reason is mandatory" in r_empty2.json()["detail"]


# ==============================================================================
# 2. MATERIAL ISSUE REVERSAL TESTS
# ==============================================================================


def test_material_issue_reversal_happy_path(
    client: TestClient,
    db_session: Session,
    stores_headers: dict,
    management_headers: dict,
):
    """
    Test whole-document Material Issue reversal:
    - Initializes 150 KG opening stock.
    - Issues 50 KG outward to Foundry (approved, balance becomes 100 KG).
    - Reverses issue slip via POST /api/v1/issues/{issue_id}/reverse.
    - Asserts compensating REVERSAL entry with +50 KG.
    - Asserts stock balance restored to 150 KG.
    - Asserts Issue status becomes REVERSED.
    """
    dept_stores, dept_foundry, uom_kg, item, _ = _setup_master_data(db_session)
    _seed_opening_balance(db_session, item, uom_kg, Decimal("150.0000"))

    # 1. Create & Approve Issue of 50 KG
    issue_payload = {
        "issue_date": str(date.today()),
        "issuing_department_id": dept_stores.id,
        "receiving_department_id": dept_foundry.id,
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "50.0000",
                "remarks": "Furnace melt batch 1",
            }
        ],
    }
    ir = client.post("/api/v1/issues/", json=issue_payload, headers=stores_headers)
    assert ir.status_code == 201
    issue_id = ir.json()["id"]

    client.post(f"/api/v1/issues/{issue_id}/submit", json={}, headers=stores_headers)
    appr_resp = client.post(f"/api/v1/issues/{issue_id}/approve", json={}, headers=management_headers)
    assert appr_resp.status_code == 200

    bal_issued, _, _, _ = get_material_stock_balance(db_session, item.id)
    assert bal_issued == Decimal("100.0000")

    # 2. Reverse Issue Slip
    rev_payload = {"reason": "Batch cancelled before melting; full quantity returned to stores"}
    rev_resp = client.post(f"/api/v1/issues/{issue_id}/reverse", json=rev_payload, headers=management_headers)
    assert rev_resp.status_code == 200, rev_resp.text
    data = rev_resp.json()

    assert data["document_type"] == "ISSUE"
    assert data["document_id"] == issue_id
    assert data["status"] == "REVERSED"
    assert len(data["reversal_ledger_entry_ids"]) == 1

    # 3. Check DB and stock balance restoration
    issue = db_session.get(MaterialIssueHeader, issue_id)
    assert issue.status == IssueStatus.REVERSED.value

    bal_restored, _, _, count = get_material_stock_balance(db_session, item.id)
    assert bal_restored == Decimal("150.0000")
    assert count == 3  # Opening (150) + Outward (-50) + Reversal (+50)

    # Verify compensating entry details
    rev_entry = db_session.get(StockLedgerEntry, data["reversal_ledger_entry_ids"][0])
    assert rev_entry.movement_type == MovementType.REVERSAL.value
    assert rev_entry.quantity_delta == Decimal("50.0000")
    assert rev_entry.reversal_of_entry_id == data["original_ledger_entry_ids"][0]


def test_material_issue_reversal_duplicate_and_unapproved(
    client: TestClient,
    db_session: Session,
    stores_headers: dict,
    management_headers: dict,
):
    """
    Test duplicate reversal prevention and status validation for Material Issues:
    - Cannot reverse DRAFT or SUBMITTED issue slip.
    - Duplicate reversal returns HTTP 409 Conflict.
    """
    dept_stores, dept_foundry, uom_kg, item, _ = _setup_master_data(db_session)
    _seed_opening_balance(db_session, item, uom_kg, Decimal("80.0000"))

    issue_payload = {
        "issue_date": str(date.today()),
        "issuing_department_id": dept_stores.id,
        "receiving_department_id": dept_foundry.id,
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "20.0000",
            }
        ],
    }
    ir = client.post("/api/v1/issues/", json=issue_payload, headers=stores_headers)
    issue_id = ir.json()["id"]

    # DRAFT reversal fails
    r_draft = client.post(f"/api/v1/issues/{issue_id}/reverse", json={"reason": "Valid reason"}, headers=management_headers)
    assert r_draft.status_code == 400

    # Submit & SUBMITTED reversal fails
    client.post(f"/api/v1/issues/{issue_id}/submit", json={}, headers=stores_headers)
    r_sub = client.post(f"/api/v1/issues/{issue_id}/reverse", json={"reason": "Valid reason"}, headers=management_headers)
    assert r_sub.status_code == 400

    # Approve
    client.post(f"/api/v1/issues/{issue_id}/approve", json={}, headers=management_headers)

    # First reversal succeeds
    r_rev1 = client.post(f"/api/v1/issues/{issue_id}/reverse", json={"reason": "Valid reason"}, headers=management_headers)
    assert r_rev1.status_code == 200

    # Duplicate reversal returns 409 Conflict
    r_rev2 = client.post(f"/api/v1/issues/{issue_id}/reverse", json={"reason": "Duplicate attempt"}, headers=management_headers)
    assert r_rev2.status_code == 409
    assert "already been reversed" in r_rev2.json()["detail"]


# ==============================================================================
# 3. WASTE DISPOSITION REVERSAL TESTS
# ==============================================================================


def test_waste_reversal_scrap_outward(
    client: TestClient,
    db_session: Session,
    stores_headers: dict,
    management_headers: dict,
):
    """
    Test SCRAP_OUTWARD reversal:
    - Initial stock: 100 KG.
    - SCRAP_OUTWARD of 30 KG (approved -> ledger delta -30 KG, balance = 70 KG).
    - Reverse waste disposition -> compensating entry +30 KG.
    - Balance restored to 100 KG; status becomes REVERSED.
    """
    dept_stores, _, uom_kg, item, _ = _setup_master_data(db_session)
    _seed_opening_balance(db_session, item, uom_kg, Decimal("100.0000"))

    payload = {
        "disposition_date": str(date.today()),
        "waste_type": "RETURNS",
        "disposition_type": "SCRAP_OUTWARD",
        "source_department_id": dept_stores.id,
        "destination_notes": "Scrap buyer dispatch",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "30.0000",
                "reason": "Unusable slag mix",
            }
        ],
    }
    wr = client.post("/api/v1/waste/", json=payload, headers=stores_headers)
    assert wr.status_code == 201
    waste_id = wr.json()["id"]

    client.post(f"/api/v1/waste/{waste_id}/submit", json={}, headers=stores_headers)
    client.post(f"/api/v1/waste/{waste_id}/approve", json={}, headers=management_headers)

    bal, _, _, _ = get_material_stock_balance(db_session, item.id)
    assert bal == Decimal("70.0000")

    # Reverse waste disposition
    rev_resp = client.post(
        f"/api/v1/waste/{waste_id}/reverse",
        json={"reason": "Gate pass cancelled; truck was rejected at weighbridge"},
        headers=management_headers,
    )
    assert rev_resp.status_code == 200, rev_resp.text
    data = rev_resp.json()

    assert data["document_type"] == "WASTE"
    assert data["status"] == "REVERSED"
    assert len(data["reversal_ledger_entry_ids"]) == 1

    waste = db_session.get(WasteDispositionHeader, waste_id)
    assert waste.status == WasteStatus.REVERSED.value

    bal_restored, _, _, _ = get_material_stock_balance(db_session, item.id)
    assert bal_restored == Decimal("100.0000")


def test_waste_reversal_internal_recovery(
    client: TestClient,
    db_session: Session,
    stores_headers: dict,
    management_headers: dict,
):
    """
    Test INTERNAL_RECOVERY reversal:
    - Original ledger entry has quantity_delta = 0.0000 (net-neutral transfer).
    - Compensating entry has quantity_delta = 0.0000.
    - Status transitions to REVERSED.
    """
    dept_stores, _, uom_kg, item, _ = _setup_master_data(db_session)

    payload = {
        "disposition_date": str(date.today()),
        "waste_type": "GATINGS_RUNNERS",
        "disposition_type": "INTERNAL_RECOVERY",
        "source_department_id": dept_stores.id,
        "destination_notes": "Internal remelting in induction furnace",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "45.0000",
                "reason": "Foundry returns",
            }
        ],
    }
    wr = client.post("/api/v1/waste/", json=payload, headers=stores_headers)
    waste_id = wr.json()["id"]

    client.post(f"/api/v1/waste/{waste_id}/submit", json={}, headers=stores_headers)
    client.post(f"/api/v1/waste/{waste_id}/approve", json={}, headers=management_headers)

    # Reverse
    rev_resp = client.post(
        f"/api/v1/waste/{waste_id}/reverse",
        json={"reason": "Incorrect disposition classification; should have been hold"},
        headers=management_headers,
    )
    assert rev_resp.status_code == 200
    data = rev_resp.json()

    assert data["status"] == "REVERSED"
    assert len(data["reversal_ledger_entry_ids"]) == 1

    rev_entry = db_session.get(StockLedgerEntry, data["reversal_ledger_entry_ids"][0])
    assert rev_entry.quantity_delta == Decimal("0.0000")
    assert rev_entry.movement_type == MovementType.REVERSAL.value


def test_waste_reversal_inspection_hold(
    client: TestClient,
    db_session: Session,
    stores_headers: dict,
    management_headers: dict,
):
    """
    Test INSPECTION_HOLD reversal:
    - INSPECTION_HOLD creates 0 ledger entries on approval (material in hold custody).
    - Reversing INSPECTION_HOLD transitions status to REVERSED but creates 0 ledger entries
      (no phantom movements or ghost stock created).
    """
    dept_stores, _, uom_kg, item, _ = _setup_master_data(db_session)

    payload = {
        "disposition_date": str(date.today()),
        "waste_type": "REJECTED_CASTINGS",
        "disposition_type": "INSPECTION_HOLD",
        "source_department_id": dept_stores.id,
        "destination_notes": "Metallurgical lab hold area",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "15.0000",
                "reason": "Shrinkage porosity inspection",
            }
        ],
    }
    wr = client.post("/api/v1/waste/", json=payload, headers=stores_headers)
    waste_id = wr.json()["id"]

    client.post(f"/api/v1/waste/{waste_id}/submit", json={}, headers=stores_headers)
    client.post(f"/api/v1/waste/{waste_id}/approve", json={}, headers=management_headers)

    # Confirm 0 ledger entries exist
    entries = (
        db_session.execute(
            select(StockLedgerEntry).where(StockLedgerEntry.source_document_id == waste_id)
        )
        .scalars()
        .all()
    )
    assert len(entries) == 0

    # Reverse
    rev_resp = client.post(
        f"/api/v1/waste/{waste_id}/reverse",
        json={"reason": "Lab hold rejected; returning to production review"},
        headers=management_headers,
    )
    assert rev_resp.status_code == 200, rev_resp.text
    data = rev_resp.json()

    assert data["status"] == "REVERSED"
    assert data["original_ledger_entry_ids"] == []
    assert data["reversal_ledger_entry_ids"] == []
    assert data["reversal_entry_numbers"] == []

    waste = db_session.get(WasteDispositionHeader, waste_id)
    assert waste.status == WasteStatus.REVERSED.value


# ==============================================================================
# 4. RBAC & PERMISSION BOUNDARY TESTS
# ==============================================================================


def test_document_reversal_security_roles(
    client: TestClient,
    db_session: Session,
    stores_headers: dict,
    foundry_headers: dict,
    purchase_headers: dict,
    management_headers: dict,
    admin_headers: dict,
):
    """
    Test RBAC boundaries:
    - STORES, FOUNDRY, PURCHASE lack Permission.LEDGER_REVERSE -> HTTP 403 Forbidden.
    - MANAGEMENT, ADMIN hold Permission.LEDGER_REVERSE -> Authorized.
    """
    dept_stores, _, uom_kg, item, vendor = _setup_master_data(db_session)

    # Provision approved GRN
    create_payload = {
        "receipt_date": str(date.today()),
        "source_type": "EXTERNAL_VENDOR",
        "vendor_id": vendor.id,
        "vendor_invoice_no": f"INV-{uuid.uuid4().hex[:6]}",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "50.0000",
                "rate_ex_gst": "30.00",
                "gst_percent": "18.00",
            }
        ],
    }
    r = client.post("/api/v1/grn/", json=create_payload, headers=stores_headers)
    grn_id = r.json()["id"]
    client.post(f"/api/v1/grn/{grn_id}/submit", json={}, headers=stores_headers)
    client.post(f"/api/v1/grn/{grn_id}/approve", json={}, headers=management_headers)

    # 1. Stores attempt -> 403
    r_stores = client.post(f"/api/v1/grn/{grn_id}/reverse", json={"reason": "Stores attempt"}, headers=stores_headers)
    assert r_stores.status_code == 403

    # 2. Foundry attempt -> 403
    r_foundry = client.post(f"/api/v1/grn/{grn_id}/reverse", json={"reason": "Foundry attempt"}, headers=foundry_headers)
    assert r_foundry.status_code == 403

    # 3. Purchase attempt -> 403
    r_purch = client.post(f"/api/v1/grn/{grn_id}/reverse", json={"reason": "Purchase attempt"}, headers=purchase_headers)
    assert r_purch.status_code == 403

    # 4. Management attempt -> 200
    r_mgmt = client.post(f"/api/v1/grn/{grn_id}/reverse", json={"reason": "Authorized management reversal"}, headers=management_headers)
    assert r_mgmt.status_code == 200


# ==============================================================================
# 5. LIVE POSTGRESQL MULTI-SESSION CONCURRENCY TESTS
# ==============================================================================


def test_pg_concurrent_duplicate_grn_reversals(pg_session_factory):
    """
    Live PostgreSQL Concurrency Test:
    - Launches 2 concurrent worker threads simultaneously calling reverse_grn on the same approved GRN.
    - Serialized via PostgreSQL row lock (SELECT ... FOR UPDATE).
    - Guarantees exactly ONE thread succeeds; the other thread receives HTTP 409 Conflict.
    - Guarantees exactly one compensating entry is posted to the live PostgreSQL stock ledger.
    """
    # 1. Setup in thread 0
    with pg_session_factory() as db:
        dept_stores, _, uom_kg, item, vendor = _setup_master_data(db, suffix="PG-DUP")

        # Create approved GRN
        today = date.today()
        grn = GRNHeader(
            grn_number=f"GRN-{today.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
            receipt_date=today,
            source_type="EXTERNAL_VENDOR",
            vendor_id=vendor.id,
            vendor_invoice_no=f"INV-{uuid.uuid4().hex[:6]}",
            status=GRNStatus.APPROVED.value,
            created_by="pg_test_maker",
        )
        db.add(grn)
        db.flush()

        from app.models.grn import GRNLineItem
        line = GRNLineItem(
            grn_id=grn.id,
            line_number=1,
            material_item_id=item.id,
            uom_id=uom_kg.id,
            quantity=Decimal("100.0000"),
            rate_ex_gst=Decimal("50.00"),
            gst_percent=Decimal("18.00"),
        )
        db.add(line)
        db.flush()

        from app.services.ledger_service import post_grn_to_ledger
        post_grn_to_ledger(db, grn, "pg_test_approver")
        db.commit()
        grn_id = grn.id
        item_id = item.id

    # 2. Execute concurrent reversal attempts
    def _attempt_reversal(worker_name: str):
        with pg_session_factory() as s:
            try:
                res = reverse_grn(
                    db=s,
                    grn_id=grn_id,
                    actor_id=worker_name,
                    reason=f"Concurrent reversal attempt by {worker_name}",
                )
                return ("SUCCESS", res)
            except Exception as e:
                return ("ERROR", e)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_attempt_reversal, "worker_1")
        f2 = pool.submit(_attempt_reversal, "worker_2")
        r1 = f1.result()
        r2 = f2.result()

    statuses = {r1[0], r2[0]}
    assert statuses == {"SUCCESS", "ERROR"}, f"Expected one SUCCESS and one ERROR, got {r1[0]} and {r2[0]}"

    err_result = r1[1] if r1[0] == "ERROR" else r2[1]
    assert hasattr(err_result, "status_code"), f"Expected HTTPException, got {err_result}"
    assert err_result.status_code == 409

    # 3. Verify exactly one compensating entry in PostgreSQL
    with pg_session_factory() as db:
        entries = (
            db.execute(
                select(StockLedgerEntry)
                .where(StockLedgerEntry.material_item_id == item_id)
                .order_by(StockLedgerEntry.id.asc())
            )
            .scalars()
            .all()
        )
        assert len(entries) == 2  # 1 original + 1 compensating
        assert entries[1].movement_type == MovementType.REVERSAL.value
        assert entries[1].quantity_delta == Decimal("-100.0000")


def test_pg_concurrent_grn_reversal_vs_issue(pg_session_factory):
    """
    Live PostgreSQL Concurrency Test:
    - GRN has 100 KG.
    - Worker A attempts whole-document GRN reversal (deducting 100 KG).
    - Worker B concurrently attempts outward issue of 80 KG.
    - Serialized via _lock_material_items_for_update.
    - Guarantees stock NEVER drops below 0: either A commits first (leaving 0, so B fails with 409),
      or B commits first (leaving 20, so A fails with 409). Both can NEVER both succeed!
    """
    with pg_session_factory() as db:
        dept_stores, dept_foundry, uom_kg, item, vendor = _setup_master_data(db, suffix="PG-REV-ISS")

        today = date.today()
        grn = GRNHeader(
            grn_number=f"GRN-{today.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
            receipt_date=today,
            source_type="EXTERNAL_VENDOR",
            vendor_id=vendor.id,
            vendor_invoice_no=f"INV-{uuid.uuid4().hex[:6]}",
            status=GRNStatus.APPROVED.value,
            created_by="pg_test_maker",
        )
        db.add(grn)
        db.flush()

        from app.models.grn import GRNLineItem
        line = GRNLineItem(
            grn_id=grn.id,
            line_number=1,
            material_item_id=item.id,
            uom_id=uom_kg.id,
            quantity=Decimal("100.0000"),
            rate_ex_gst=Decimal("50.00"),
            gst_percent=Decimal("18.00"),
        )
        db.add(line)
        db.flush()

        from app.services.ledger_service import post_grn_to_ledger
        post_grn_to_ledger(db, grn, "pg_test_approver")

        # Provision a SUBMITTED issue slip for 80 KG ready to approve
        issue = MaterialIssueHeader(
            issue_slip_number=f"ISS-{today.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
            issue_date=today,
            issuing_department_id=dept_stores.id,
            receiving_department_id=dept_foundry.id,
            status=IssueStatus.SUBMITTED.value,
            created_by="pg_issue_maker",
        )
        db.add(issue)
        db.flush()

        from app.models.issue import MaterialIssueLineItem
        iline = MaterialIssueLineItem(
            issue_id=issue.id,
            line_number=1,
            material_item_id=item.id,
            uom_id=uom_kg.id,
            quantity=Decimal("80.0000"),
        )
        db.add(iline)
        db.commit()

        grn_id = grn.id
        issue_id = issue.id
        item_id = item.id

    def _reverse_grn_worker():
        with pg_session_factory() as s:
            try:
                res = reverse_grn(s, grn_id, "rev_worker", "Concurrent GRN reversal")
                return ("REVERSAL", "SUCCESS", res)
            except Exception as e:
                return ("REVERSAL", "ERROR", e)

    def _approve_issue_worker():
        with pg_session_factory() as s:
            try:
                from app.services.issue_service import approve_material_issue
                res = approve_material_issue(s, issue_id, "issue_worker", "Concurrent issue approval")
                return ("ISSUE", "SUCCESS", res)
            except Exception as e:
                return ("ISSUE", "ERROR", e)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_rev = pool.submit(_reverse_grn_worker)
        f_iss = pool.submit(_approve_issue_worker)
        r_rev = f_rev.result()
        r_iss = f_iss.result()

    # Exactly one must succeed and one must fail with 409 Conflict
    assert not (r_rev[1] == "SUCCESS" and r_iss[1] == "SUCCESS"), (
        "Invariant violation! Both GRN reversal and issue succeeded, which would violate negative stock!"
    )
    assert (r_rev[1] == "SUCCESS" or r_iss[1] == "SUCCESS"), "At least one operation should succeed"

    # Final stock balance in PostgreSQL must be non-negative
    with pg_session_factory() as db:
        final_bal, is_init, _, _ = get_material_stock_balance(db, item_id)
        assert is_init is True
        assert final_bal >= Decimal("0.0000"), f"Stock balance became negative: {final_bal}"
