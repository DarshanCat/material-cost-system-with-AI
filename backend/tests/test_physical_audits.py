"""
Tests for Physical Inventory Stock Audits.
Verifies cutoff balance comparison, variance formula (Physical - System),
draft isolation, and adjustment journal posting.
"""

from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType


def test_physical_audit_variance_and_adjustment_posting(client: TestClient, db_session: Session, management_headers: dict):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-401",
        name="Silico Manganese 60/14",
        department_id=dept.id,
        category="ALLOYS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    # System balance in ledger = 1,000 kg
    ob = StockLedgerEntry(
        entry_number="STK-TEST-401",
        posting_group_id="POST-OB-401",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("1000.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-401",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    # 1. Create audit on 2026-10-15 with physical count = 980 kg (Variance = 980 - 1000 = -20 kg)
    audit_payload = {
        "audit_date": "2026-10-15",
        "department_id": dept.id,
        "notes": "Monthly physical audit for alloy yard",
        "lines": [
            {
                "material_item_id": item.id,
                "uom_id": uom.id,
                "physical_quantity": "980.00",
                "reason": "Normal handling & weighing shrinkage",
            }
        ],
    }

    create_resp = client.post("/api/v1/physical-audits/", json=audit_payload)
    assert create_resp.status_code == 201
    audit_data = create_resp.json()
    assert audit_data["status"] == "DRAFT"
    assert Decimal(str(audit_data["lines"][0]["system_quantity"])) == Decimal("1000.0000")
    assert Decimal(str(audit_data["lines"][0]["variance"])) == Decimal("-20.0000")
    audit_id = audit_data["id"]

    # Draft audit must not change stock balance
    bal_during = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_during.json()["current_balance"])) == Decimal("1000.0000")

    # 2. Submit
    sub_resp = client.post(f"/api/v1/physical-audits/{audit_id}/submit", json={})
    assert sub_resp.status_code == 200

    # 3. Approve -> Posts adjustment to ledger
    app_resp = client.post(f"/api/v1/physical-audits/{audit_id}/approve", json={"comments": "Variance approved"}, headers=management_headers)
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"

    # Verify ledger balance is now adjusted to exactly 980 kg (1000 + (-20) = 980)
    bal_after = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_after.json()["current_balance"])) == Decimal("980.0000")
    assert bal_after.json()["movement_count"] == 2  # Opening balance + Audit adjustment


def test_physical_audit_negative_variance_blocked_on_uninitialized_stock(db_session: Session):
    from fastapi import HTTPException
    from app.models.physical_audit import PhysicalAuditHeader, PhysicalAuditLine, AuditStatus
    from app.services.ledger_service import post_audit_adjustment_to_ledger

    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-AUD-UNINIT",
        name="Uninitialized Audit Item",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    # Draft audit header with negative variance
    audit = PhysicalAuditHeader(
        audit_number="AUD-20261024-UNINIT",
        audit_date=date(2026, 10, 24),
        department_id=dept.id,
        status=AuditStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(audit)
    db_session.flush()

    line = PhysicalAuditLine(
        audit_id=audit.id,
        line_number=1,
        material_item_id=item.id,
        uom_id=uom.id,
        system_quantity=Decimal("0.0000"),
        physical_quantity=Decimal("0.0000"),
        variance=Decimal("-15.0000"),
        reason="Shrinkage on uninitialized item",
    )
    db_session.add(line)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        post_audit_adjustment_to_ledger(db_session, audit, actor_id="usr_mgmt_01")
    assert exc_info.value.status_code == 409
    assert "Stock baseline has not been initialized" in exc_info.value.detail


def test_physical_audit_negative_variance_blocked_on_insufficient_stock(client: TestClient, db_session: Session, management_headers: dict):
    from app.services.issue_service import approve_material_issue
    from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueStatus

    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    dept_msp = db_session.query(Department).filter_by(code="MSP").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-AUD-INSUFF",
        name="Insufficient Stock Audit Item",
        department_id=dept_fdy.id,
        category="ALLOYS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initial balance = 100 kg
    ob = StockLedgerEntry(
        entry_number="STK-AUD-OB-01",
        posting_group_id="POST-AUD-OB-01",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("100.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-AUD-01",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    # 1. Create audit when system balance is 100 kg; physical count = 10 kg -> variance = -90 kg
    audit_payload = {
        "audit_date": str(date.today()),
        "department_id": dept_fdy.id,
        "notes": "Audit prior to intervening stock issue",
        "lines": [
            {
                "material_item_id": item.id,
                "uom_id": uom.id,
                "physical_quantity": "10.00",
                "reason": "Missing material suspected",
            }
        ],
    }
    create_resp = client.post("/api/v1/physical-audits/", json=audit_payload)
    assert create_resp.status_code == 201
    audit_id = create_resp.json()["id"]

    sub_resp = client.post(f"/api/v1/physical-audits/{audit_id}/submit", json={})
    assert sub_resp.status_code == 200

    # 2. Intervening stock issue: 80 kg issued to MSP, leaving only 20 kg in inventory
    issue = MaterialIssueHeader(
        issue_slip_number="ISS-AUD-INTERVENE",
        issue_date=date.today(),
        issuing_department_id=dept_fdy.id,
        receiving_department_id=dept_msp.id,
        status=IssueStatus.SUBMITTED.value,
        created_by="usr_stores_01",
    )
    db_session.add(issue)
    db_session.flush()
    issue_line = MaterialIssueLineItem(
        issue_id=issue.id,
        line_number=1,
        material_item_id=item.id,
        uom_id=uom.id,
        quantity=Decimal("80.0000"),
    )
    db_session.add(issue_line)
    db_session.commit()

    approve_material_issue(db_session, issue.id, actor_id="usr_mgmt_01")
    db_session.commit()

    # Balance is now 20 kg
    bal_mid = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_mid.json()["current_balance"])) == Decimal("20.0000")

    # 3. Attempt to approve without supervisor override: blocked because stock moved (SW-08)
    app_resp = client.post(f"/api/v1/physical-audits/{audit_id}/approve", json={"comments": "Approve variance"}, headers=management_headers)
    assert app_resp.status_code == 409
    assert "Stale audit snapshot detected" in app_resp.json()["detail"]

    # 4. Attempt to approve WITH supervisor override: still blocked because -90 kg exceeds 20 kg available (Rule L6)
    app_resp2 = client.post(
        f"/api/v1/physical-audits/{audit_id}/approve",
        json={"comments": "Override attempted by manager", "supervisor_override": True},
        headers=management_headers,
    )
    assert app_resp2.status_code == 409
    assert "Insufficient inventory for audit adjustment" in app_resp2.json()["detail"]

    # Balance remains 20 kg
    bal_after = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_after.json()["current_balance"])) == Decimal("20.0000")


def test_physical_audit_negative_variance_multiline_cumulative_check(client: TestClient, db_session: Session, management_headers: dict):
    from app.models.physical_audit import PhysicalAuditHeader, PhysicalAuditLine, AuditStatus

    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-AUD-MULTILINE",
        name="Multiline Audit Item",
        department_id=dept.id,
        category="ALLOYS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initial balance = 100 kg
    ob = StockLedgerEntry(
        entry_number="STK-AUD-OB-02",
        posting_group_id="POST-AUD-OB-02",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("100.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-AUD-02",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    # Audit with two lines for same item: -60 kg and -50 kg (cumulative = -110 kg > 100 kg)
    audit = PhysicalAuditHeader(
        audit_number="AUD-20261024-MULTI",
        audit_date=date.today(),
        department_id=dept.id,
        status=AuditStatus.SUBMITTED.value,
        created_by="usr_stores_01",
    )
    db_session.add(audit)
    db_session.flush()

    line1 = PhysicalAuditLine(
        audit_id=audit.id,
        line_number=1,
        material_item_id=item.id,
        uom_id=uom.id,
        system_quantity=Decimal("100.0000"),
        physical_quantity=Decimal("40.0000"),
        variance=Decimal("-60.0000"),
    )
    line2 = PhysicalAuditLine(
        audit_id=audit.id,
        line_number=2,
        material_item_id=item.id,
        uom_id=uom.id,
        system_quantity=Decimal("40.0000"),
        physical_quantity=Decimal("0.0000"),
        variance=Decimal("-50.0000"),
    )
    db_session.add(line1)
    db_session.add(line2)
    db_session.commit()

    # With supervisor override, it proceeds to ledger posting where cumulative deduction is evaluated
    app_resp = client.post(
        f"/api/v1/physical-audits/{audit.id}/approve",
        json={"comments": "Cumulative negative variance override", "supervisor_override": True},
        headers=management_headers,
    )
    assert app_resp.status_code == 409
    assert "Insufficient inventory for audit adjustment" in app_resp.json()["detail"]

    # Balance must remain unchanged at 100.0000 kg with exactly 1 ledger entry
    bal_after = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_after.json()["current_balance"])) == Decimal("100.0000")
    assert bal_after.json()["movement_count"] == 1


def test_physical_audit_receipt_after_cutoff_requires_override(client: TestClient, db_session: Session, management_headers: dict):
    from app.models.grn import GRNHeader, GRNLineItem, GRNStatus, GRNSourceType
    from app.services.grn_service import approve_grn

    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-AUD-RCPT",
        name="Receipt Drift Audit Item",
        department_id=dept.id,
        category="ALLOYS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initial balance = 100 kg
    ob = StockLedgerEntry(
        entry_number="STK-AUD-RCPT-01",
        posting_group_id="POST-AUD-RCPT-01",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("100.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-RCPT-01",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    # 1. Create audit on 2026-10-15: cutoff balance = 100 kg, physical = 90 kg -> variance = -10 kg
    audit_payload = {
        "audit_date": "2026-10-15",
        "department_id": dept.id,
        "notes": "Testing intervening GRN receipt",
        "lines": [
            {
                "material_item_id": item.id,
                "uom_id": uom.id,
                "physical_quantity": "90.00",
                "reason": "Shrinkage",
            }
        ],
    }
    create_resp = client.post("/api/v1/physical-audits/", json=audit_payload)
    assert create_resp.status_code == 201
    audit_id = create_resp.json()["id"]

    client.post(f"/api/v1/physical-audits/{audit_id}/submit", json={})

    # 2. Intervening GRN receipt after cutoff: +50 kg received
    grn = GRNHeader(
        grn_number="GRN-AUD-INTERVENE",
        receipt_date=date(2026, 10, 18),
        vendor_id=None,
        vendor_invoice_no="INV-AUD-01",
        source_type=GRNSourceType.INTERNAL_VSPL.value,
        status=GRNStatus.SUBMITTED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn)
    db_session.flush()
    grn_line = GRNLineItem(
        grn_id=grn.id,
        line_number=1,
        material_item_id=item.id,
        uom_id=uom.id,
        quantity=Decimal("50.0000"),
        rate_ex_gst=Decimal("100.00"),
    )
    db_session.add(grn_line)
    db_session.commit()

    approve_grn(db_session, grn.id, actor_id="usr_mgmt_01")
    db_session.commit()

    # Live balance is now 150 kg (100 + 50)
    bal_live = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_live.json()["current_balance"])) == Decimal("150.0000")

    # 3. Attempt approval without override -> blocked by SW-08 revalidation
    app_resp = client.post(
        f"/api/v1/physical-audits/{audit_id}/approve",
        json={"comments": "Standard approval"},
        headers=management_headers,
    )
    assert app_resp.status_code == 409
    err = app_resp.json()["detail"]
    assert "Stale audit snapshot detected" in err
    assert "Cutoff balance was 100.0000" in err
    assert "live balance is now 150.0000" in err

    # Verify no ledger entries posted from audit and balance remains 150 kg
    bal_after = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_after.json()["current_balance"])) == Decimal("150.0000")


def test_physical_audit_waste_posting_after_cutoff_requires_override(client: TestClient, db_session: Session, management_headers: dict):
    from app.models.waste import WasteDispositionHeader, WasteDispositionLineItem, WasteStatus, WasteType, DispositionType
    from app.services.waste_service import approve_waste_disposition

    dept = db_session.query(Department).filter_by(code="FDY").first()
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-AUD-WST",
        name="Waste Drift Audit Item",
        department_id=dept.id,
        category="ALLOYS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initial balance = 100 kg
    ob = StockLedgerEntry(
        entry_number="STK-AUD-WST-01",
        posting_group_id="POST-AUD-WST-01",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("100.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-WST-01",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    # Create audit on 2026-10-15
    audit_payload = {
        "audit_date": "2026-10-15",
        "department_id": dept.id,
        "notes": "Testing intervening waste disposition",
        "lines": [{"material_item_id": item.id, "uom_id": uom.id, "physical_quantity": "95.00"}],
    }
    create_resp = client.post("/api/v1/physical-audits/", json=audit_payload)
    audit_id = create_resp.json()["id"]
    client.post(f"/api/v1/physical-audits/{audit_id}/submit", json={})

    # Intervening waste scrap of 30 kg
    w = WasteDispositionHeader(
        waste_number="WST-AUD-INTERVENE",
        disposition_date=date(2026, 10, 18),
        waste_type=WasteType.SLAG.value,
        disposition_type=DispositionType.SCRAP_OUTWARD.value,
        source_department_id=dept_ms.id,
        status=WasteStatus.SUBMITTED.value,
        created_by="usr_stores_01",
    )
    db_session.add(w)
    db_session.flush()
    db_session.add(WasteDispositionLineItem(waste_id=w.id, line_number=1, material_item_id=item.id, uom_id=uom.id, quantity=Decimal("30.0000")))
    db_session.commit()

    approve_waste_disposition(db_session, w.id, actor_id="usr_mgmt_01")
    db_session.commit()

    # Live balance is now 70 kg
    bal_mid = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_mid.json()["current_balance"])) == Decimal("70.0000")

    # Attempt audit approval without override -> rejected 409
    app_resp = client.post(f"/api/v1/physical-audits/{audit_id}/approve", json={"comments": "Normal"}, headers=management_headers)
    assert app_resp.status_code == 409
    assert "Stale audit snapshot detected" in app_resp.json()["detail"]


def test_physical_audit_reversal_after_cutoff_requires_override(client: TestClient, db_session: Session, management_headers: dict):
    from app.services.ledger_service import reverse_stock_ledger_entry

    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-AUD-REV",
        name="Reversal Drift Audit Item",
        department_id=dept.id,
        category="ALLOYS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initial balance = 100 kg
    ob = StockLedgerEntry(
        entry_number="STK-AUD-REV-01",
        posting_group_id="POST-AUD-REV-01",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.INWARD_RECEIPT.value,
        quantity_delta=Decimal("100.0000"),
        source_document_type=SourceDocumentType.GRN.value,
        source_document_id=1,
        source_line_id=1,
        source_document_number="GRN-REV-01",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    # Create audit on 2026-10-15: cutoff balance = 100 kg, physical = 100 kg (variance = 0)
    audit_payload = {
        "audit_date": "2026-10-15",
        "department_id": dept.id,
        "notes": "Testing intervening reversal",
        "lines": [{"material_item_id": item.id, "uom_id": uom.id, "physical_quantity": "100.00"}],
    }
    create_resp = client.post("/api/v1/physical-audits/", json=audit_payload)
    audit_id = create_resp.json()["id"]
    client.post(f"/api/v1/physical-audits/{audit_id}/submit", json={})

    # Intervening inward reversal: -100 kg reversal entry posted
    reverse_stock_ledger_entry(db_session, ob.id, reason="Reversal test", actor_id="usr_mgmt_01")
    db_session.commit()

    # Balance is now 0 kg
    bal_mid = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_mid.json()["current_balance"])) == Decimal("0.0000")

    # Attempt audit approval -> rejected 409
    app_resp = client.post(f"/api/v1/physical-audits/{audit_id}/approve", json={"comments": "Approve after rev"}, headers=management_headers)
    assert app_resp.status_code == 409
    assert "Stale audit snapshot detected" in app_resp.json()["detail"]


def test_physical_audit_changed_discrepancy_with_supervisor_override_succeeds(client: TestClient, db_session: Session, management_headers: dict):
    from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueStatus
    from app.services.issue_service import approve_material_issue

    dept = db_session.query(Department).filter_by(code="FDY").first()
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-AUD-OVR",
        name="Supervisor Override Audit Item",
        department_id=dept.id,
        category="ALLOYS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initial balance = 100 kg
    ob = StockLedgerEntry(
        entry_number="STK-AUD-OVR-01",
        posting_group_id="POST-AUD-OVR-01",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("100.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-OVR-01",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    # Create audit on 2026-10-15: physical count = 95 kg (cutoff balance = 100 kg, variance = -5 kg)
    audit_payload = {
        "audit_date": "2026-10-15",
        "department_id": dept.id,
        "notes": "Testing supervisor override flow",
        "lines": [{"material_item_id": item.id, "uom_id": uom.id, "physical_quantity": "95.00"}],
    }
    create_resp = client.post("/api/v1/physical-audits/", json=audit_payload)
    audit_id = create_resp.json()["id"]
    client.post(f"/api/v1/physical-audits/{audit_id}/submit", json={})

    # Intervening issue of 20 kg
    iss = MaterialIssueHeader(
        issue_slip_number="ISS-AUD-OVR",
        issue_date=date(2026, 10, 18),
        issuing_department_id=dept.id,
        receiving_department_id=dept_ms.id,
        status=IssueStatus.SUBMITTED.value,
        created_by="usr_stores_01",
    )
    db_session.add(iss)
    db_session.flush()
    db_session.add(MaterialIssueLineItem(issue_id=iss.id, line_number=1, material_item_id=item.id, uom_id=uom.id, quantity=Decimal("20.0000")))
    db_session.commit()

    approve_material_issue(db_session, iss.id, actor_id="usr_mgmt_01")
    db_session.commit()

    # Live balance is 80 kg
    bal_mid = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_mid.json()["current_balance"])) == Decimal("80.0000")

    # Inspect GET response before approval: requires_supervisor_override is True!
    get_resp = client.get(f"/api/v1/physical-audits/{audit_id}")
    assert get_resp.status_code == 200
    audit_view = get_resp.json()
    assert audit_view["requires_supervisor_override"] is True
    assert Decimal(str(audit_view["lines"][0]["live_system_quantity"])) == Decimal("80.0000")
    assert Decimal(str(audit_view["lines"][0]["live_discrepancy"])) == Decimal("15.0000")  # 95 - 80
    assert Decimal(str(audit_view["lines"][0]["discrepancy_drift"])) == Decimal("20.0000")  # 15 - (-5)

    # Approve WITH supervisor override and valid comments
    app_resp = client.post(
        f"/api/v1/physical-audits/{audit_id}/approve",
        json={"comments": "Verified 20kg issue occurred after physical count. Cutoff variance -5kg approved.", "supervisor_override": True},
        headers=management_headers,
    )
    assert app_resp.status_code == 200
    app_data = app_resp.json()
    assert app_data["status"] == "APPROVED"
    assert app_data["supervisor_override_by"] == "usr_mgmt_01"
    assert app_data["supervisor_override_at"] is not None

    # Ledger balance is now 75 kg (80 live + (-5) cutoff variance)
    bal_after = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_after.json()["current_balance"])) == Decimal("75.0000")


def test_physical_audit_supervisor_override_missing_comments_rejected(client: TestClient, db_session: Session, management_headers: dict):
    from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueStatus
    from app.services.issue_service import approve_material_issue

    dept = db_session.query(Department).filter_by(code="FDY").first()
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-AUD-NOCMT",
        name="No Comments Override Audit Item",
        department_id=dept.id,
        category="ALLOYS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initial balance = 100 kg
    ob = StockLedgerEntry(
        entry_number="STK-AUD-NOCMT-01",
        posting_group_id="POST-AUD-NOCMT-01",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("100.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-NOCMT-01",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    audit_payload = {
        "audit_date": "2026-10-15",
        "department_id": dept.id,
        "lines": [{"material_item_id": item.id, "uom_id": uom.id, "physical_quantity": "95.00"}],
    }
    create_resp = client.post("/api/v1/physical-audits/", json=audit_payload)
    audit_id = create_resp.json()["id"]
    client.post(f"/api/v1/physical-audits/{audit_id}/submit", json={})

    # Intervening issue
    iss = MaterialIssueHeader(
        issue_slip_number="ISS-AUD-NOCMT",
        issue_date=date(2026, 10, 18),
        issuing_department_id=dept.id,
        receiving_department_id=dept_ms.id,
        status=IssueStatus.SUBMITTED.value,
        created_by="usr_stores_01",
    )
    db_session.add(iss)
    db_session.flush()
    db_session.add(MaterialIssueLineItem(issue_id=iss.id, line_number=1, material_item_id=item.id, uom_id=uom.id, quantity=Decimal("10.0000")))
    db_session.commit()
    approve_material_issue(db_session, iss.id, actor_id="usr_mgmt_01")
    db_session.commit()

    # Override attempted with empty comments
    app_resp = client.post(
        f"/api/v1/physical-audits/{audit_id}/approve",
        json={"comments": "   ", "supervisor_override": True},
        headers=management_headers,
    )
    assert app_resp.status_code == 400
    assert "Supervisor override requires explicit comments" in app_resp.json()["detail"]


def test_physical_audit_duplicate_approval_rejected(client: TestClient, db_session: Session, management_headers: dict):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-AUD-DUP",
        name="Duplicate Approval Audit Item",
        department_id=dept.id,
        category="ALLOYS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initial balance = 100 kg
    ob = StockLedgerEntry(
        entry_number="STK-AUD-DUP-01",
        posting_group_id="POST-AUD-DUP-01",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("100.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-DUP-01",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    audit_payload = {
        "audit_date": "2026-10-15",
        "department_id": dept.id,
        "lines": [{"material_item_id": item.id, "uom_id": uom.id, "physical_quantity": "100.00"}],
    }
    create_resp = client.post("/api/v1/physical-audits/", json=audit_payload)
    audit_id = create_resp.json()["id"]
    client.post(f"/api/v1/physical-audits/{audit_id}/submit", json={})

    # First approval -> 200
    app_resp1 = client.post(f"/api/v1/physical-audits/{audit_id}/approve", json={"comments": "First approval"}, headers=management_headers)
    assert app_resp1.status_code == 200

    # Second approval -> 400
    app_resp2 = client.post(f"/api/v1/physical-audits/{audit_id}/approve", json={"comments": "Second approval attempt"}, headers=management_headers)
    assert app_resp2.status_code == 400
    assert "Cannot approve audit in status 'APPROVED'" in app_resp2.json()["detail"]


@pytest.fixture(autouse=True)
def _authenticate_as_admin(client: TestClient, admin_headers: dict):
    """Workflow tests exercise domain rules as Admin; RBAC itself is covered by test_security_routes.py."""
    client.headers.update(admin_headers)
