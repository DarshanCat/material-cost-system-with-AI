"""
Unit & Integration Tests for Material Issue and Stock Ledger Posting Integrity.
Phase 1D-1 Remediation: Observation 4 (ISS-20261022-0042 Investigation & Posting Invariants).

Covers:
1. Approval with successful ledger posting (atomic status transition + negative delta entries).
2. Approval when posting fails (e.g. simulated ledger fault or negative stock disallowance) -> atomic rollback.
3. Duplicate posting prevention (calling post_issue_to_ledger twice is idempotent and returns existing entries).
4. Reversal traceability (compensating entries restore stock with explicit reversal_of_entry_id and parent doc linkage).
5. Source document linkage (ledger entry references source_document_type='ISSUE', source_document_id, source_line_id).
6. Unauthenticated and unauthorized approval attempts (HTTP 401 / 403 enforcement).
7. Negative stock policy enforcement (preventing approval if stock would fall below zero).
8. Maker-checker segregation (creator cannot approve their own issue slip).
"""

from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.issue import (
    MaterialIssueHeader,
    MaterialIssueLineItem,
    IssueStatus,
)
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.services.issue_service import (
    create_material_issue,
    submit_material_issue,
    approve_material_issue,
)
from app.services.ledger_service import (
    post_issue_to_ledger,
    reverse_material_issue,
)
from app.schemas.issue import MaterialIssueCreate, MaterialIssueLineItemCreate
from fastapi import HTTPException


@pytest.fixture
def test_setup_data(db_session: Session):
    """Provisions isolated departments, UOM, and stock-initialized material item."""
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    dept_gns = db_session.query(Department).filter_by(code="GNS").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-999",
        name="Test Pig Iron Grade A",
        department_id=dept_fdy.id,
        category="RAW_MATERIALS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initialize opening balance with 10,000 kg so issues have available inventory
    ob_entry = StockLedgerEntry(
        entry_number="ENT-OB-TEST-999",
        posting_group_id="POST-OB-999",
        material_item_id=item.id,
        uom_id=uom_kg.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("10000.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-TEST-999",
        posted_by="Admin",
    )
    db_session.add(ob_entry)
    db_session.commit()

    return {
        "dept_fdy": dept_fdy,
        "dept_gns": dept_gns,
        "uom_kg": uom_kg,
        "item": item,
    }


def test_issue_approval_atomically_posts_to_stock_ledger(db_session: Session, test_setup_data: dict):
    """Verify that approving a material issue transitions status to APPROVED and writes ledger entries."""
    item = test_setup_data["item"]
    dept_fdy = test_setup_data["dept_fdy"]
    dept_gns = test_setup_data["dept_gns"]
    uom_kg = test_setup_data["uom_kg"]

    # 1. Create DRAFT issue
    payload = MaterialIssueCreate(
        issue_date=date(2026, 10, 22),
        issuing_department_id=dept_gns.id,
        receiving_department_id=dept_fdy.id,
        heat_reference_number="102603-9991",
        notes="Furnace charge allocation",
        lines=[
            MaterialIssueLineItemCreate(
                line_number=1,
                material_item_id=item.id,
                uom_id=uom_kg.id,
                quantity=Decimal("2500.0000"),
                remarks="Charge line 1",
            )
        ],
    )
    header, warnings = create_material_issue(db_session, payload, created_by="usr_stores_01")
    assert header.status == IssueStatus.DRAFT.value
    issue_id = header.id

    # 2. Submit issue
    submit_material_issue(db_session, issue_id, actor_id="usr_stores_01")
    assert header.status == IssueStatus.SUBMITTED.value

    # Prior to approval, verify 0 ledger entries exist for this issue
    pre_ledger = db_session.execute(
        select(StockLedgerEntry).where(
            StockLedgerEntry.source_document_type == SourceDocumentType.ISSUE.value,
            StockLedgerEntry.source_document_id == issue_id,
        )
    ).scalars().all()
    assert len(pre_ledger) == 0

    # 3. Approve issue as distinct checker
    approved_header = approve_material_issue(db_session, issue_id, actor_id="usr_mgmt_01")
    assert approved_header.status == IssueStatus.APPROVED.value

    # 4. Verify stock ledger entry was atomically created
    post_ledger = db_session.execute(
        select(StockLedgerEntry).where(
            StockLedgerEntry.source_document_type == SourceDocumentType.ISSUE.value,
            StockLedgerEntry.source_document_id == issue_id,
        )
    ).scalars().all()
    assert len(post_ledger) == 1
    sle = post_ledger[0]
    assert sle.material_item_id == item.id
    assert sle.quantity_delta == Decimal("-2500.0000")  # Outward is negative
    assert sle.movement_type == MovementType.OUTWARD_ISSUE.value
    assert sle.source_document_number == approved_header.issue_slip_number
    assert sle.source_line_id == approved_header.lines[0].id
    assert sle.posted_by == "usr_mgmt_01"


def test_issue_approval_fails_and_rolls_back_when_insufficient_stock(db_session: Session, test_setup_data: dict):
    """Verify that if an issue requests more stock than available, approval fails and document remains SUBMITTED."""
    item = test_setup_data["item"]
    dept_fdy = test_setup_data["dept_fdy"]
    dept_gns = test_setup_data["dept_gns"]
    uom_kg = test_setup_data["uom_kg"]

    # Create issue with 25,000 kg (only 10,000 kg in stock)
    payload = MaterialIssueCreate(
        issue_date=date(2026, 10, 22),
        issuing_department_id=dept_gns.id,
        receiving_department_id=dept_fdy.id,
        notes="Massive charge exceeding inventory",
        lines=[
            MaterialIssueLineItemCreate(
                line_number=1,
                material_item_id=item.id,
                uom_id=uom_kg.id,
                quantity=Decimal("25000.0000"),
            )
        ],
    )
    header, _ = create_material_issue(db_session, payload, created_by="usr_stores_01")
    submit_material_issue(db_session, header.id, actor_id="usr_stores_01")

    # Attempt approval: must raise HTTPException (409 Conflict) for negative stock
    with pytest.raises(HTTPException) as exc_info:
        approve_material_issue(db_session, header.id, actor_id="usr_mgmt_01")
    assert exc_info.value.status_code == 409
    assert "Insufficient inventory" in exc_info.value.detail

    # Roll back session and verify issue did NOT get approved and NO ledger entry was posted
    db_session.rollback()
    refreshed_header = db_session.get(MaterialIssueHeader, header.id)
    assert refreshed_header.status == IssueStatus.SUBMITTED.value

    ledger_entries = db_session.execute(
        select(StockLedgerEntry).where(
            StockLedgerEntry.source_document_type == SourceDocumentType.ISSUE.value,
            StockLedgerEntry.source_document_id == header.id,
        )
    ).scalars().all()
    assert len(ledger_entries) == 0


def test_post_issue_to_ledger_idempotency(db_session: Session, test_setup_data: dict):
    """Verify that calling post_issue_to_ledger repeatedly does not create duplicate ledger entries."""
    item = test_setup_data["item"]
    dept_fdy = test_setup_data["dept_fdy"]
    dept_gns = test_setup_data["dept_gns"]
    uom_kg = test_setup_data["uom_kg"]

    payload = MaterialIssueCreate(
        issue_date=date(2026, 10, 22),
        issuing_department_id=dept_gns.id,
        receiving_department_id=dept_fdy.id,
        lines=[
            MaterialIssueLineItemCreate(
                line_number=1,
                material_item_id=item.id,
                uom_id=uom_kg.id,
                quantity=Decimal("500.0000"),
            )
        ],
    )
    header, _ = create_material_issue(db_session, payload, created_by="usr_stores_01")
    submit_material_issue(db_session, header.id, actor_id="usr_stores_01")
    approved = approve_material_issue(db_session, header.id, actor_id="usr_mgmt_01")

    # Manually call post_issue_to_ledger again
    entries_first = db_session.execute(
        select(StockLedgerEntry).where(
            StockLedgerEntry.source_document_type == SourceDocumentType.ISSUE.value,
            StockLedgerEntry.source_document_id == approved.id,
        )
    ).scalars().all()
    assert len(entries_first) == 1

    entries_second = post_issue_to_ledger(db_session, approved, actor_id="usr_mgmt_01")
    assert len(entries_second) == 1
    assert entries_second[0].id == entries_first[0].id

    # Count entries in DB
    total_ledger_for_issue = db_session.execute(
        select(StockLedgerEntry).where(
            StockLedgerEntry.source_document_type == SourceDocumentType.ISSUE.value,
            StockLedgerEntry.source_document_id == approved.id,
        )
    ).scalars().all()
    assert len(total_ledger_for_issue) == 1


def test_issue_reversal_creates_traceable_compensating_entries(db_session: Session, test_setup_data: dict):
    """Verify that whole-document reversal generates positive compensating entries linked to originals."""
    item = test_setup_data["item"]
    dept_fdy = test_setup_data["dept_fdy"]
    dept_gns = test_setup_data["dept_gns"]
    uom_kg = test_setup_data["uom_kg"]

    payload = MaterialIssueCreate(
        issue_date=date(2026, 10, 22),
        issuing_department_id=dept_gns.id,
        receiving_department_id=dept_fdy.id,
        lines=[
            MaterialIssueLineItemCreate(
                line_number=1,
                material_item_id=item.id,
                uom_id=uom_kg.id,
                quantity=Decimal("1200.0000"),
            )
        ],
    )
    header, _ = create_material_issue(db_session, payload, created_by="usr_stores_01")
    submit_material_issue(db_session, header.id, actor_id="usr_stores_01")
    approved = approve_material_issue(db_session, header.id, actor_id="usr_mgmt_01")

    # Execute reversal
    reversal_resp = reverse_material_issue(
        db_session, approved.id, actor_id="usr_admin_01", reason="Erroneous heat charge allocation"
    )
    assert reversal_resp.status == "REVERSED"
    refreshed_issue = db_session.get(MaterialIssueHeader, approved.id)
    assert refreshed_issue.status == IssueStatus.REVERSED.value
    assert len(reversal_resp.reversal_entry_numbers) == 1

    # Check compensating entry properties
    rev_sle_num = reversal_resp.reversal_entry_numbers[0]
    rev_sle = db_session.execute(
        select(StockLedgerEntry).where(StockLedgerEntry.entry_number == rev_sle_num)
    ).scalar_one()

    assert rev_sle.movement_type == MovementType.REVERSAL.value
    assert rev_sle.quantity_delta == Decimal("1200.0000")  # Positive restores stock
    assert rev_sle.source_document_type == SourceDocumentType.MANUAL_REVERSAL.value
    assert rev_sle.reversal_of_entry_id is not None

    # Cannot reverse twice
    with pytest.raises(HTTPException) as exc_info:
        reverse_material_issue(db_session, approved.id, actor_id="usr_admin_01", reason="Duplicate attempt")
    assert exc_info.value.status_code == 409
    assert "already been reversed" in exc_info.value.detail


def test_maker_checker_enforcement_on_issue_approval(db_session: Session, test_setup_data: dict):
    """Verify that the creator of an issue slip cannot approve it."""
    item = test_setup_data["item"]
    dept_fdy = test_setup_data["dept_fdy"]
    dept_gns = test_setup_data["dept_gns"]
    uom_kg = test_setup_data["uom_kg"]

    payload = MaterialIssueCreate(
        issue_date=date(2026, 10, 22),
        issuing_department_id=dept_gns.id,
        receiving_department_id=dept_fdy.id,
        lines=[
            MaterialIssueLineItemCreate(
                line_number=1,
                material_item_id=item.id,
                uom_id=uom_kg.id,
                quantity=Decimal("300.0000"),
            )
        ],
    )
    header, _ = create_material_issue(db_session, payload, created_by="usr_stores_01")
    submit_material_issue(db_session, header.id, actor_id="usr_stores_01")

    # Creator attempts to approve
    with pytest.raises(HTTPException) as exc_info:
        approve_material_issue(db_session, header.id, actor_id="usr_stores_01")
    assert exc_info.value.status_code == 403
    assert "Maker-checker violation" in exc_info.value.detail


def test_unauthenticated_and_unauthorized_issue_approval_http(
    client: TestClient, db_session: Session, test_setup_data: dict, stores_headers: dict
):
    """Verify HTTP route access controls: 401 unauthenticated, 403 unauthorized for non-approvers."""
    item = test_setup_data["item"]
    dept_fdy = test_setup_data["dept_fdy"]
    dept_gns = test_setup_data["dept_gns"]
    uom_kg = test_setup_data["uom_kg"]

    # Create & submit issue via client with stores_headers
    client.headers.update(stores_headers)
    resp = client.post(
        "/api/v1/issues/",
        json={
            "issue_date": str(date.today()),
            "issuing_department_id": dept_gns.id,
            "receiving_department_id": dept_fdy.id,
            "lines": [
                {
                    "line_number": 1,
                    "material_item_id": item.id,
                    "uom_id": uom_kg.id,
                    "quantity": "100.0000",
                }
            ],
        },
    )
    assert resp.status_code == 201
    issue_id = resp.json()["id"]

    client.post(f"/api/v1/issues/{issue_id}/submit", json={})

    # 1. Unauthenticated approval attempt (no headers)
    client.headers.clear()
    unauth_resp = client.post(f"/api/v1/issues/{issue_id}/approve", json={})
    assert unauth_resp.status_code == 401

    # 2. Unauthorized approval attempt (Stores role lacks issue:approve permission)
    client.headers.update(stores_headers)
    unauthorized_resp = client.post(f"/api/v1/issues/{issue_id}/approve", json={})
    assert unauthorized_resp.status_code == 403
    assert "lacks permission 'issue:approve'" in unauthorized_resp.text
