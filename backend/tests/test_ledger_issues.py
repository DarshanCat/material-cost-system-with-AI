"""
Tests for Negative Stock Prevention & Material Issue Ledger Postings.
Includes:
- SQLite tests for uninitialized stock, insufficient stock, and multi-line cumulative stock checks.
- Live PostgreSQL multi-session concurrency tests for per-item SELECT ... FOR UPDATE row locking
  in post_issue_to_ledger() and reverse_stock_ledger_entry(), plus PostgreSQL trigger 006 immutability.
"""

from datetime import date
from decimal import Decimal
import threading
import uuid
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueStatus
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.services.issue_service import approve_material_issue
from app.services.ledger_service import get_material_stock_balance, reverse_stock_ledger_entry
from app.models.waste import WasteDispositionHeader, WasteDispositionLineItem, WasteStatus, WasteType, DispositionType
from app.services.waste_service import approve_waste_disposition
from app.models.physical_audit import PhysicalAuditHeader, PhysicalAuditLine, AuditStatus
from app.services.physical_audit_service import approve_physical_audit


def test_issue_approval_blocked_on_uninitialized_stock(client: TestClient, db_session: Session, management_headers: dict):
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    # Create uninitialized item
    item = MaterialItem(
        item_code="FDY-RM-201",
        name="Uninitialized Scrap",
        department_id=dept_fdy.id,
        category="RAW_MATERIALS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # Create & submit issue slip
    payload = {
        "issue_date": str(date.today()),
        "issuing_department_id": dept_fdy.id,
        "receiving_department_id": dept_ms.id,
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "50.00",
            }
        ],
    }
    resp = client.post("/api/v1/issues/", json=payload)
    assert resp.status_code == 201
    issue_id = resp.json()["id"]

    client.post(f"/api/v1/issues/{issue_id}/submit", json={})

    # Approving must fail because stock is uninitialized!
    app_resp = client.post(f"/api/v1/issues/{issue_id}/approve", json={}, headers=management_headers)
    assert app_resp.status_code == 409
    assert "Stock baseline has not been initialized" in app_resp.json()["detail"]


def test_issue_approval_blocked_on_insufficient_stock(client: TestClient, db_session: Session, management_headers: dict):
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-202",
        name="Limited Supply Ferro Manganese",
        department_id=dept_fdy.id,
        category="ALLOYS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initialized with only 20 kg
    ob = StockLedgerEntry(
        entry_number="STK-TEST-202",
        posting_group_id="POST-OB-202",
        material_item_id=item.id,
        uom_id=uom_kg.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("20.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-202",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    # Attempt to issue 50 kg (exceeds 20 kg)
    payload = {
        "issue_date": str(date.today()),
        "issuing_department_id": dept_fdy.id,
        "receiving_department_id": dept_ms.id,
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "50.00",
            }
        ],
    }
    resp = client.post("/api/v1/issues/", json=payload)
    assert resp.status_code == 201
    issue_id = resp.json()["id"]

    client.post(f"/api/v1/issues/{issue_id}/submit", json={})

    # Approval must be rejected with 409 Conflict
    app_resp = client.post(f"/api/v1/issues/{issue_id}/approve", json={}, headers=management_headers)
    assert app_resp.status_code == 409
    assert "Insufficient inventory" in app_resp.json()["detail"]


def test_multiline_same_item_issue_cannot_overdraw_stock(client: TestClient, db_session: Session, management_headers: dict):
    """
    [SQLite Test] Verifies that a single issue slip with multiple lines for the same item
    tracks cumulative deduction across lines and rejects if total exceeds available stock.
    """
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-203",
        name="Cumulative Line Check Alloy",
        department_id=dept_fdy.id,
        category="ALLOYS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    ob = StockLedgerEntry(
        entry_number="STK-TEST-203",
        posting_group_id="POST-OB-203",
        material_item_id=item.id,
        uom_id=uom_kg.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("100.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-203",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    payload = {
        "issue_date": str(date.today()),
        "issuing_department_id": dept_fdy.id,
        "receiving_department_id": dept_ms.id,
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "60.00",
            },
            {
                "line_number": 2,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "60.00",
            },
        ],
    }
    resp = client.post("/api/v1/issues/", json=payload)
    assert resp.status_code == 201
    issue_id = resp.json()["id"]

    client.post(f"/api/v1/issues/{issue_id}/submit", json={})

    app_resp = client.post(f"/api/v1/issues/{issue_id}/approve", json={}, headers=management_headers)
    assert app_resp.status_code == 409
    assert "Insufficient inventory" in app_resp.json()["detail"]

    bal, _, _, _ = get_material_stock_balance(db_session, item.id)
    assert bal == Decimal("100.0000")


def test_postgres_live_concurrent_issue_approvals_cannot_cause_negative_stock(pg_session_factory):
    """
    [Real PostgreSQL Concurrency Test] Creates an item with 100.0000 kg stock and two
    SUBMITTED issue slips of 80.0000 kg each. Approves both concurrently across independent
    PostgreSQL sessions synchronized via threading.Barrier.
    Verifies that SELECT ... FOR UPDATE on MaterialItem serializes the stock check so
    exactly ONE issue succeeds (leaving 20.0000 kg) and the other fails with HTTP 409.
    """
    suffix = uuid.uuid4().hex[:6].upper()
    with pg_session_factory() as setup_db:
        dept_fdy = setup_db.execute(select(Department).where(Department.code == "FDY")).scalar_one()
        dept_ms = setup_db.execute(select(Department).where(Department.code == "MSP")).scalar_one()
        uom_kg = setup_db.execute(select(UOM).where(UOM.code == "KG")).scalar_one()

        item = MaterialItem(
            item_code=f"FDY-PGC-{suffix}",
            name=f"PG Concurrent Issue Item {suffix}",
            department_id=dept_fdy.id,
            category="RAW_MATERIALS",
            base_uom_id=uom_kg.id,
        )
        setup_db.add(item)
        setup_db.flush()

        ob = StockLedgerEntry(
            entry_number=f"STK-OB-{suffix}",
            posting_group_id=f"POST-OB-{suffix}",
            material_item_id=item.id,
            uom_id=uom_kg.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("100.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=item.id,
            source_line_id=item.id,
            source_document_number=f"OB-{suffix}",
            posted_by="usr_admin_01",
        )
        setup_db.add(ob)

        issue_ids = []
        for idx in (1, 2):
            hdr = MaterialIssueHeader(
                issue_slip_number=f"ISS-PGC-{suffix}-{idx}",
                issue_date=date(2026, 10, 24),
                issuing_department_id=dept_fdy.id,
                receiving_department_id=dept_ms.id,
                status=IssueStatus.SUBMITTED.value,
                created_by="usr_stores_01",
            )
            setup_db.add(hdr)
            setup_db.flush()
            line = MaterialIssueLineItem(
                issue_id=hdr.id,
                line_number=1,
                material_item_id=item.id,
                uom_id=uom_kg.id,
                quantity=Decimal("80.0000"),
            )
            setup_db.add(line)
            issue_ids.append(hdr.id)

        setup_db.commit()
        target_item_id = item.id

    barrier = threading.Barrier(2)
    outcomes = [None, None]

    def _approve_worker(idx: int, target_issue_id: int):
        with pg_session_factory() as worker_db:
            barrier.wait(timeout=10)
            try:
                approved = approve_material_issue(
                    worker_db,
                    target_issue_id,
                    actor_id=f"usr_mgmt_0{idx + 1}",
                )
                outcomes[idx] = ("APPROVED", approved.status)
            except HTTPException as exc:
                outcomes[idx] = ("REJECTED", exc.status_code, exc.detail)

    t1 = threading.Thread(target=_approve_worker, args=(0, issue_ids[0]))
    t2 = threading.Thread(target=_approve_worker, args=(1, issue_ids[1]))
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    approved_count = sum(1 for o in outcomes if o and o[0] == "APPROVED")
    rejected_409 = [o for o in outcomes if o and o[0] == "REJECTED" and o[1] == 409]
    assert approved_count == 1, f"Expected exactly 1 approval, got: {outcomes}"
    assert len(rejected_409) == 1, f"Expected exactly 1 HTTP 409 rejection, got: {outcomes}"
    assert "Insufficient inventory" in rejected_409[0][2]

    with pg_session_factory() as check_db:
        final_bal, is_init, _, mov_cnt = get_material_stock_balance(check_db, target_item_id)
        assert is_init is True
        assert final_bal == Decimal("20.0000"), f"Expected 20.0000 kg remaining, got {final_bal}"
        assert mov_cnt == 2  # 1 opening balance + 1 outward issue


def test_postgres_live_concurrent_issue_and_inward_reversal_cannot_cause_negative_stock(pg_session_factory):
    """
    [Real PostgreSQL Concurrency Test] Creates an item with a 100.0000 kg INWARD_RECEIPT
    ledger entry and a SUBMITTED issue slip for 80.0000 kg. Concurrently runs
    approve_material_issue (-80 kg) in Session 1 and reverse_stock_ledger_entry (-100 kg)
    in Session 2. Verifies per-item FOR UPDATE locking prevents both from succeeding.
    """
    suffix = uuid.uuid4().hex[:6].upper()
    with pg_session_factory() as setup_db:
        dept_fdy = setup_db.execute(select(Department).where(Department.code == "FDY")).scalar_one()
        dept_ms = setup_db.execute(select(Department).where(Department.code == "MSP")).scalar_one()
        uom_kg = setup_db.execute(select(UOM).where(UOM.code == "KG")).scalar_one()

        item = MaterialItem(
            item_code=f"FDY-PGR-{suffix}",
            name=f"PG Concurrent Reversal Item {suffix}",
            department_id=dept_fdy.id,
            category="RAW_MATERIALS",
            base_uom_id=uom_kg.id,
        )
        setup_db.add(item)
        setup_db.flush()

        inward = StockLedgerEntry(
            entry_number=f"STK-INW-{suffix}",
            posting_group_id=f"POST-INW-{suffix}",
            material_item_id=item.id,
            uom_id=uom_kg.id,
            transaction_date=date(2026, 10, 20),
            movement_type=MovementType.INWARD_RECEIPT.value,
            quantity_delta=Decimal("100.0000"),
            source_document_type=SourceDocumentType.GRN.value,
            source_document_id=item.id + 50000,
            source_line_id=item.id + 50000,
            source_document_number=f"GRN-{suffix}",
            posted_by="usr_mgmt_01",
        )
        setup_db.add(inward)

        hdr = MaterialIssueHeader(
            issue_slip_number=f"ISS-PGR-{suffix}",
            issue_date=date(2026, 10, 24),
            issuing_department_id=dept_fdy.id,
            receiving_department_id=dept_ms.id,
            status=IssueStatus.SUBMITTED.value,
            created_by="usr_stores_01",
        )
        setup_db.add(hdr)
        setup_db.flush()
        line = MaterialIssueLineItem(
            issue_id=hdr.id,
            line_number=1,
            material_item_id=item.id,
            uom_id=uom_kg.id,
            quantity=Decimal("80.0000"),
        )
        setup_db.add(line)
        setup_db.commit()

        target_item_id = item.id
        target_inward_id = inward.id
        target_issue_id = hdr.id

    barrier = threading.Barrier(2)
    outcomes = [None, None]

    def _issue_worker():
        with pg_session_factory() as worker_db:
            barrier.wait(timeout=10)
            try:
                approve_material_issue(worker_db, target_issue_id, actor_id="usr_mgmt_01")
                outcomes[0] = ("ISSUE_APPROVED", 200)
            except HTTPException as exc:
                outcomes[0] = ("ISSUE_REJECTED", exc.status_code, exc.detail)

    def _reversal_worker():
        with pg_session_factory() as worker_db:
            barrier.wait(timeout=10)
            try:
                reverse_stock_ledger_entry(
                    worker_db,
                    target_inward_id,
                    reason="Concurrent reversal contention check",
                    actor_id="usr_mgmt_02",
                )
                outcomes[1] = ("REVERSAL_SUCCEEDED", 200)
            except HTTPException as exc:
                outcomes[1] = ("REVERSAL_REJECTED", exc.status_code, exc.detail)

    t1 = threading.Thread(target=_issue_worker)
    t2 = threading.Thread(target=_reversal_worker)
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    successes = [o for o in outcomes if o and o[1] == 200]
    rejections = [o for o in outcomes if o and o[1] == 409]
    assert len(successes) == 1, f"Expected exactly 1 operation to succeed, got: {outcomes}"
    assert len(rejections) == 1, f"Expected exactly 1 operation to be rejected with 409, got: {outcomes}"

    with pg_session_factory() as check_db:
        final_bal, _, _, _ = get_material_stock_balance(check_db, target_item_id)
        assert final_bal >= Decimal("0.0000"), f"Negative stock occurred: {final_bal}"
        assert final_bal in (Decimal("20.0000"), Decimal("0.0000"))


def test_postgres_live_concurrent_waste_scrap_outward_cannot_cause_negative_stock(pg_session_factory):
    """
    [Real PostgreSQL Concurrency Test] Creates an item with 100 kg OPENING_BALANCE
    and two concurrent SUBMITTED Waste Dispositions (SCRAP_OUTWARD) of 70 kg each.
    Row locks serialize approval so exactly one succeeds and the other receives 409.
    """
    suffix = uuid.uuid4().hex[:6].upper()
    with pg_session_factory() as setup_db:
        dept_fdy = setup_db.execute(select(Department).where(Department.code == "FDY")).scalar_one()
        dept_ms = setup_db.execute(select(Department).where(Department.code == "MSP")).scalar_one()
        uom_kg = setup_db.execute(select(UOM).where(UOM.code == "KG")).scalar_one()

        item = MaterialItem(
            item_code=f"FDY-WST-{suffix}",
            name=f"PG Concurrent Waste Item {suffix}",
            department_id=dept_fdy.id,
            category="RAW_MATERIALS",
            base_uom_id=uom_kg.id,
        )
        setup_db.add(item)
        setup_db.flush()

        ob = StockLedgerEntry(
            entry_number=f"STK-OBW-{suffix}",
            posting_group_id=f"POST-OBW-{suffix}",
            material_item_id=item.id,
            uom_id=uom_kg.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("100.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=0,
            source_line_id=item.id,
            source_document_number=f"OB-{suffix}",
            posted_by="usr_mgmt_01",
        )
        setup_db.add(ob)

        w1 = WasteDispositionHeader(
            waste_number=f"WST-A-{suffix}",
            disposition_date=date(2026, 10, 24),
            waste_type=WasteType.SLAG.value,
            disposition_type=DispositionType.SCRAP_OUTWARD.value,
            source_department_id=dept_ms.id,
            status=WasteStatus.SUBMITTED.value,
            created_by="usr_stores_01",
        )
        setup_db.add(w1)
        setup_db.flush()
        w1_line = WasteDispositionLineItem(
            waste_id=w1.id,
            line_number=1,
            material_item_id=item.id,
            uom_id=uom_kg.id,
            quantity=Decimal("70.0000"),
        )
        setup_db.add(w1_line)

        w2 = WasteDispositionHeader(
            waste_number=f"WST-B-{suffix}",
            disposition_date=date(2026, 10, 24),
            waste_type=WasteType.SLAG.value,
            disposition_type=DispositionType.SCRAP_OUTWARD.value,
            source_department_id=dept_ms.id,
            status=WasteStatus.SUBMITTED.value,
            created_by="usr_stores_02",
        )
        setup_db.add(w2)
        setup_db.flush()
        w2_line = WasteDispositionLineItem(
            waste_id=w2.id,
            line_number=1,
            material_item_id=item.id,
            uom_id=uom_kg.id,
            quantity=Decimal("70.0000"),
        )
        setup_db.add(w2_line)
        setup_db.commit()

        target_item_id = item.id
        target_w1_id = w1.id
        target_w2_id = w2.id

    barrier = threading.Barrier(2)
    outcomes = [None, None]

    def _worker(idx, waste_id):
        with pg_session_factory() as worker_db:
            barrier.wait(timeout=10)
            try:
                approve_waste_disposition(worker_db, waste_id, actor_id="usr_mgmt_01")
                outcomes[idx] = ("APPROVED", 200)
            except HTTPException as exc:
                outcomes[idx] = ("REJECTED", exc.status_code, exc.detail)

    t1 = threading.Thread(target=_worker, args=(0, target_w1_id))
    t2 = threading.Thread(target=_worker, args=(1, target_w2_id))
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    successes = [o for o in outcomes if o and o[1] == 200]
    rejections = [o for o in outcomes if o and o[1] == 409]
    assert len(successes) == 1, f"Expected exactly 1 waste approval to succeed: {outcomes}"
    assert len(rejections) == 1, f"Expected exactly 1 waste approval to be rejected: {outcomes}"
    assert "Insufficient inventory" in rejections[0][2]

    with pg_session_factory() as check_db:
        final_bal, _, _, _ = get_material_stock_balance(check_db, target_item_id)
        assert final_bal == Decimal("30.0000"), f"Expected 30 kg remaining, got {final_bal}"


def test_postgres_live_concurrent_audit_negative_adjustment_cannot_cause_negative_stock(pg_session_factory):
    """
    [Real PostgreSQL Concurrency Test] Creates an item with 100 kg OPENING_BALANCE
    and two concurrent SUBMITTED physical audits with downward variance (-70 kg each).
    Row locks serialize approval so exactly one succeeds and the other receives 409.
    """
    suffix = uuid.uuid4().hex[:6].upper()
    with pg_session_factory() as setup_db:
        dept_fdy = setup_db.execute(select(Department).where(Department.code == "FDY")).scalar_one()
        uom_kg = setup_db.execute(select(UOM).where(UOM.code == "KG")).scalar_one()

        item = MaterialItem(
            item_code=f"FDY-AUD-{suffix}",
            name=f"PG Concurrent Audit Item {suffix}",
            department_id=dept_fdy.id,
            category="RAW_MATERIALS",
            base_uom_id=uom_kg.id,
        )
        setup_db.add(item)
        setup_db.flush()

        ob = StockLedgerEntry(
            entry_number=f"STK-OBA-{suffix}",
            posting_group_id=f"POST-OBA-{suffix}",
            material_item_id=item.id,
            uom_id=uom_kg.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("100.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=0,
            source_line_id=item.id,
            source_document_number=f"OB-{suffix}",
            posted_by="usr_mgmt_01",
        )
        setup_db.add(ob)

        a1 = PhysicalAuditHeader(
            audit_number=f"AUD-A-{suffix}",
            audit_date=date(2026, 10, 24),
            department_id=dept_fdy.id,
            status=AuditStatus.SUBMITTED.value,
            created_by="usr_stores_01",
        )
        setup_db.add(a1)
        setup_db.flush()
        a1_line = PhysicalAuditLine(
            audit_id=a1.id,
            line_number=1,
            material_item_id=item.id,
            uom_id=uom_kg.id,
            system_quantity=Decimal("100.0000"),
            physical_quantity=Decimal("30.0000"),
            variance=Decimal("-70.0000"),
        )
        setup_db.add(a1_line)

        a2 = PhysicalAuditHeader(
            audit_number=f"AUD-B-{suffix}",
            audit_date=date(2026, 10, 24),
            department_id=dept_fdy.id,
            status=AuditStatus.SUBMITTED.value,
            created_by="usr_stores_02",
        )
        setup_db.add(a2)
        setup_db.flush()
        a2_line = PhysicalAuditLine(
            audit_id=a2.id,
            line_number=1,
            material_item_id=item.id,
            uom_id=uom_kg.id,
            system_quantity=Decimal("100.0000"),
            physical_quantity=Decimal("30.0000"),
            variance=Decimal("-70.0000"),
        )
        setup_db.add(a2_line)
        setup_db.commit()

        target_item_id = item.id
        target_a1_id = a1.id
        target_a2_id = a2.id

    barrier = threading.Barrier(2)
    outcomes = [None, None]

    def _worker(idx, audit_id):
        with pg_session_factory() as worker_db:
            barrier.wait(timeout=10)
            try:
                approve_physical_audit(worker_db, audit_id, actor_id="usr_mgmt_01")
                outcomes[idx] = ("APPROVED", 200)
            except HTTPException as exc:
                outcomes[idx] = ("REJECTED", exc.status_code, exc.detail)

    t1 = threading.Thread(target=_worker, args=(0, target_a1_id))
    t2 = threading.Thread(target=_worker, args=(1, target_a2_id))
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    successes = [o for o in outcomes if o and o[1] == 200]
    rejections = [o for o in outcomes if o and o[1] == 409]
    assert len(successes) == 1, f"Expected exactly 1 audit adjustment to succeed: {outcomes}"
    assert len(rejections) == 1, f"Expected exactly 1 audit adjustment to be rejected: {outcomes}"
    assert any(msg in rejections[0][2] for msg in ("Stale audit snapshot detected", "Insufficient inventory for audit adjustment"))

    with pg_session_factory() as check_db:
        final_bal, _, _, _ = get_material_stock_balance(check_db, target_item_id)
        assert final_bal == Decimal("30.0000"), f"Expected 30 kg remaining, got {final_bal}"


def test_postgres_live_concurrent_mixed_issue_and_waste_scrap(pg_session_factory):
    """
    [Real PostgreSQL Concurrency Test] Mixed outward operations: Material Issue (-70 kg)
    and Waste SCRAP_OUTWARD (-70 kg) competing concurrently for 100 kg stock.
    Verifies mutual exclusion across different transaction types.
    """
    suffix = uuid.uuid4().hex[:6].upper()
    with pg_session_factory() as setup_db:
        dept_fdy = setup_db.execute(select(Department).where(Department.code == "FDY")).scalar_one()
        dept_ms = setup_db.execute(select(Department).where(Department.code == "MSP")).scalar_one()
        uom_kg = setup_db.execute(select(UOM).where(UOM.code == "KG")).scalar_one()

        item = MaterialItem(
            item_code=f"FDY-MIX-{suffix}",
            name=f"PG Concurrent Mixed Item {suffix}",
            department_id=dept_fdy.id,
            category="RAW_MATERIALS",
            base_uom_id=uom_kg.id,
        )
        setup_db.add(item)
        setup_db.flush()

        ob = StockLedgerEntry(
            entry_number=f"STK-OBM-{suffix}",
            posting_group_id=f"POST-OBM-{suffix}",
            material_item_id=item.id,
            uom_id=uom_kg.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("100.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=0,
            source_line_id=item.id,
            source_document_number=f"OB-{suffix}",
            posted_by="usr_mgmt_01",
        )
        setup_db.add(ob)

        # Issue slip for 70 kg
        issue = MaterialIssueHeader(
            issue_slip_number=f"ISS-MIX-{suffix}",
            issue_date=date(2026, 10, 24),
            issuing_department_id=dept_fdy.id,
            receiving_department_id=dept_ms.id,
            status=IssueStatus.SUBMITTED.value,
            created_by="usr_stores_01",
        )
        setup_db.add(issue)
        setup_db.flush()
        issue_line = MaterialIssueLineItem(
            issue_id=issue.id,
            line_number=1,
            material_item_id=item.id,
            uom_id=uom_kg.id,
            quantity=Decimal("70.0000"),
        )
        setup_db.add(issue_line)

        # Waste scrap for 70 kg
        waste = WasteDispositionHeader(
            waste_number=f"WST-MIX-{suffix}",
            disposition_date=date(2026, 10, 24),
            waste_type=WasteType.SLAG.value,
            disposition_type=DispositionType.SCRAP_OUTWARD.value,
            source_department_id=dept_ms.id,
            status=WasteStatus.SUBMITTED.value,
            created_by="usr_stores_02",
        )
        setup_db.add(waste)
        setup_db.flush()
        waste_line = WasteDispositionLineItem(
            waste_id=waste.id,
            line_number=1,
            material_item_id=item.id,
            uom_id=uom_kg.id,
            quantity=Decimal("70.0000"),
        )
        setup_db.add(waste_line)
        setup_db.commit()

        target_item_id = item.id
        target_issue_id = issue.id
        target_waste_id = waste.id

    barrier = threading.Barrier(2)
    outcomes = [None, None]

    def _issue_worker():
        with pg_session_factory() as worker_db:
            barrier.wait(timeout=10)
            try:
                approve_material_issue(worker_db, target_issue_id, actor_id="usr_mgmt_01")
                outcomes[0] = ("ISSUE_APPROVED", 200)
            except HTTPException as exc:
                outcomes[0] = ("ISSUE_REJECTED", exc.status_code, exc.detail)

    def _waste_worker():
        with pg_session_factory() as worker_db:
            barrier.wait(timeout=10)
            try:
                approve_waste_disposition(worker_db, target_waste_id, actor_id="usr_mgmt_02")
                outcomes[1] = ("WASTE_APPROVED", 200)
            except HTTPException as exc:
                outcomes[1] = ("WASTE_REJECTED", exc.status_code, exc.detail)

    t1 = threading.Thread(target=_issue_worker)
    t2 = threading.Thread(target=_waste_worker)
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    successes = [o for o in outcomes if o and o[1] == 200]
    rejections = [o for o in outcomes if o and o[1] == 409]
    assert len(successes) == 1, f"Expected 1 mixed operation to succeed: {outcomes}"
    assert len(rejections) == 1, f"Expected 1 mixed operation to be rejected: {outcomes}"

    with pg_session_factory() as check_db:
        final_bal, _, _, _ = get_material_stock_balance(check_db, target_item_id)
        assert final_bal == Decimal("30.0000"), f"Expected 30 kg remaining, got {final_bal}"


def test_postgres_live_multiline_deadlock_freedom_and_integrity(pg_session_factory):
    """
    [Real PostgreSQL Concurrency Test] Verifies that deterministic ascending item-ID locking
    prevents PostgreSQL transaction deadlocks when two multi-line transactions touch the same items
    in inverse line order.
    """
    suffix = uuid.uuid4().hex[:6].upper()
    with pg_session_factory() as setup_db:
        dept_fdy = setup_db.execute(select(Department).where(Department.code == "FDY")).scalar_one()
        dept_ms = setup_db.execute(select(Department).where(Department.code == "MSP")).scalar_one()
        uom_kg = setup_db.execute(select(UOM).where(UOM.code == "KG")).scalar_one()

        item1 = MaterialItem(
            item_code=f"FDY-DL1-{suffix}",
            name=f"Deadlock Test Item 1 {suffix}",
            department_id=dept_fdy.id,
            category="RAW_MATERIALS",
            base_uom_id=uom_kg.id,
        )
        item2 = MaterialItem(
            item_code=f"FDY-DL2-{suffix}",
            name=f"Deadlock Test Item 2 {suffix}",
            department_id=dept_fdy.id,
            category="RAW_MATERIALS",
            base_uom_id=uom_kg.id,
        )
        setup_db.add_all([item1, item2])
        setup_db.flush()

        item_low = item1 if item1.id < item2.id else item2
        item_high = item2 if item1.id < item2.id else item1

        for itm in (item_low, item_high):
            ob = StockLedgerEntry(
                entry_number=f"STK-DLOB-{itm.id}-{suffix}",
                posting_group_id=f"POST-DLOB-{itm.id}-{suffix}",
                material_item_id=itm.id,
                uom_id=uom_kg.id,
                transaction_date=date(2026, 10, 12),
                movement_type=MovementType.OPENING_BALANCE.value,
                quantity_delta=Decimal("100.0000"),
                source_document_type=SourceDocumentType.OPENING_BALANCE.value,
                source_document_id=0,
                source_line_id=itm.id,
                source_document_number=f"OB-{itm.id}-{suffix}",
                posted_by="usr_mgmt_01",
            )
            setup_db.add(ob)

        # Issue 1 touches item_low then item_high
        iss1 = MaterialIssueHeader(
            issue_slip_number=f"ISS-DL1-{suffix}",
            issue_date=date(2026, 10, 24),
            issuing_department_id=dept_fdy.id,
            receiving_department_id=dept_ms.id,
            status=IssueStatus.SUBMITTED.value,
            created_by="usr_stores_01",
        )
        setup_db.add(iss1)
        setup_db.flush()
        setup_db.add(MaterialIssueLineItem(issue_id=iss1.id, line_number=1, material_item_id=item_low.id, uom_id=uom_kg.id, quantity=Decimal("40.0000")))
        setup_db.add(MaterialIssueLineItem(issue_id=iss1.id, line_number=2, material_item_id=item_high.id, uom_id=uom_kg.id, quantity=Decimal("40.0000")))

        # Issue 2 touches item_high then item_low (REVERSE ORDER!)
        iss2 = MaterialIssueHeader(
            issue_slip_number=f"ISS-DL2-{suffix}",
            issue_date=date(2026, 10, 24),
            issuing_department_id=dept_fdy.id,
            receiving_department_id=dept_ms.id,
            status=IssueStatus.SUBMITTED.value,
            created_by="usr_stores_02",
        )
        setup_db.add(iss2)
        setup_db.flush()
        setup_db.add(MaterialIssueLineItem(issue_id=iss2.id, line_number=1, material_item_id=item_high.id, uom_id=uom_kg.id, quantity=Decimal("40.0000")))
        setup_db.add(MaterialIssueLineItem(issue_id=iss2.id, line_number=2, material_item_id=item_low.id, uom_id=uom_kg.id, quantity=Decimal("40.0000")))
        setup_db.commit()

        target_iss1_id = iss1.id
        target_iss2_id = iss2.id
        id_low = item_low.id
        id_high = item_high.id

    barrier = threading.Barrier(2)
    outcomes = [None, None]

    def _worker(idx, issue_id):
        with pg_session_factory() as worker_db:
            barrier.wait(timeout=10)
            try:
                approve_material_issue(worker_db, issue_id, actor_id="usr_mgmt_01")
                outcomes[idx] = ("APPROVED", 200)
            except Exception as exc:
                outcomes[idx] = ("FAILED", getattr(exc, "status_code", 500), str(exc))

    t1 = threading.Thread(target=_worker, args=(0, target_iss1_id))
    t2 = threading.Thread(target=_worker, args=(1, target_iss2_id))
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    assert outcomes[0] == ("APPROVED", 200), f"Session 1 failed: {outcomes[0]}"
    assert outcomes[1] == ("APPROVED", 200), f"Session 2 failed: {outcomes[1]}"

    with pg_session_factory() as check_db:
        bal_low, _, _, _ = get_material_stock_balance(check_db, id_low)
        bal_high, _, _, _ = get_material_stock_balance(check_db, id_high)
        assert bal_low == Decimal("20.0000"), f"Expected 20 kg for low item, got {bal_low}"
        assert bal_high == Decimal("20.0000"), f"Expected 20 kg for high item, got {bal_high}"


def test_postgres_live_rejection_leaves_ledger_state_unchanged(pg_session_factory):
    """
    [Real PostgreSQL Concurrency Test] Verifies atomicity on rejection: when an outward
    transaction is rejected with 409 (insufficient stock), zero ledger entries remain posted
    and balance is completely unaltered.
    """
    suffix = uuid.uuid4().hex[:6].upper()
    with pg_session_factory() as setup_db:
        dept_fdy = setup_db.execute(select(Department).where(Department.code == "FDY")).scalar_one()
        dept_ms = setup_db.execute(select(Department).where(Department.code == "MSP")).scalar_one()
        uom_kg = setup_db.execute(select(UOM).where(UOM.code == "KG")).scalar_one()

        item = MaterialItem(
            item_code=f"FDY-ATOMIC-{suffix}",
            name=f"PG Atomic Rollback Item {suffix}",
            department_id=dept_fdy.id,
            category="RAW_MATERIALS",
            base_uom_id=uom_kg.id,
        )
        setup_db.add(item)
        setup_db.flush()

        # Initial balance = 50 kg
        ob = StockLedgerEntry(
            entry_number=f"STK-OBAT-{suffix}",
            posting_group_id=f"POST-OBAT-{suffix}",
            material_item_id=item.id,
            uom_id=uom_kg.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("50.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=0,
            source_line_id=item.id,
            source_document_number=f"OB-{suffix}",
            posted_by="usr_mgmt_01",
        )
        setup_db.add(ob)

        # Waste disposition with 2 lines: line 1 = 30 kg, line 2 = 40 kg (total 70 kg > 50 kg)
        waste = WasteDispositionHeader(
            waste_number=f"WST-AT-{suffix}",
            disposition_date=date(2026, 10, 24),
            waste_type=WasteType.SLAG.value,
            disposition_type=DispositionType.SCRAP_OUTWARD.value,
            source_department_id=dept_ms.id,
            status=WasteStatus.SUBMITTED.value,
            created_by="usr_stores_01",
        )
        setup_db.add(waste)
        setup_db.flush()
        setup_db.add(WasteDispositionLineItem(waste_id=waste.id, line_number=1, material_item_id=item.id, uom_id=uom_kg.id, quantity=Decimal("30.0000")))
        setup_db.add(WasteDispositionLineItem(waste_id=waste.id, line_number=2, material_item_id=item.id, uom_id=uom_kg.id, quantity=Decimal("40.0000")))
        setup_db.commit()

        target_item_id = item.id
        target_waste_id = waste.id

    with pg_session_factory() as run_db:
        with pytest.raises(HTTPException) as exc_info:
            approve_waste_disposition(run_db, target_waste_id, actor_id="usr_mgmt_01")
        assert exc_info.value.status_code == 409
        assert "Insufficient inventory" in exc_info.value.detail
        run_db.rollback()

    with pg_session_factory() as verify_db:
        # Zero waste ledger entries must exist
        waste_entries = verify_db.execute(
            select(StockLedgerEntry).where(
                StockLedgerEntry.source_document_type == SourceDocumentType.WASTE.value,
                StockLedgerEntry.source_document_id == target_waste_id,
            )
        ).scalars().all()
        assert len(waste_entries) == 0, f"Expected 0 waste ledger entries, found {len(waste_entries)}"

        final_bal, _, _, m_count = get_material_stock_balance(verify_db, target_item_id)
        assert final_bal == Decimal("50.0000")
        assert m_count == 1


def test_postgres_live_concurrent_issue_versus_audit_approval(pg_session_factory):
    """
    [Real PostgreSQL Concurrency Test] Tests contention between Material Issue (-30 kg)
    and Physical Audit Approval (variance -10 kg against cutoff balance 100 kg).
    Demonstrates SW-08: If the issue commits first, the audit approval detects that
    live stock has moved since cutoff and rejects with 409 Stale Audit Snapshot.
    """
    suffix = uuid.uuid4().hex[:6].upper()
    with pg_session_factory() as setup_db:
        dept_fdy = setup_db.execute(select(Department).where(Department.code == "FDY")).scalar_one()
        dept_ms = setup_db.execute(select(Department).where(Department.code == "MSP")).scalar_one()
        uom_kg = setup_db.execute(select(UOM).where(UOM.code == "KG")).scalar_one()

        item = MaterialItem(
            item_code=f"FDY-IA-{suffix}",
            name=f"PG Issue vs Audit Item {suffix}",
            department_id=dept_fdy.id,
            category="RAW_MATERIALS",
            base_uom_id=uom_kg.id,
        )
        setup_db.add(item)
        setup_db.flush()

        ob = StockLedgerEntry(
            entry_number=f"STK-OBIA-{suffix}",
            posting_group_id=f"POST-OBIA-{suffix}",
            material_item_id=item.id,
            uom_id=uom_kg.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("100.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=0,
            source_line_id=item.id,
            source_document_number=f"OB-{suffix}",
            posted_by="usr_mgmt_01",
        )
        setup_db.add(ob)

        # Issue slip for 30 kg
        issue = MaterialIssueHeader(
            issue_slip_number=f"ISS-IA-{suffix}",
            issue_date=date(2026, 10, 24),
            issuing_department_id=dept_fdy.id,
            receiving_department_id=dept_ms.id,
            status=IssueStatus.SUBMITTED.value,
            created_by="usr_stores_01",
        )
        setup_db.add(issue)
        setup_db.flush()
        setup_db.add(MaterialIssueLineItem(issue_id=issue.id, line_number=1, material_item_id=item.id, uom_id=uom_kg.id, quantity=Decimal("30.0000")))

        # Audit with physical = 90 kg (variance = -10 kg, cutoff = 100 kg)
        audit = PhysicalAuditHeader(
            audit_number=f"AUD-IA-{suffix}",
            audit_date=date(2026, 10, 24),
            department_id=dept_fdy.id,
            status=AuditStatus.SUBMITTED.value,
            created_by="usr_stores_02",
        )
        setup_db.add(audit)
        setup_db.flush()
        setup_db.add(PhysicalAuditLine(audit_id=audit.id, line_number=1, material_item_id=item.id, uom_id=uom_kg.id, system_quantity=Decimal("100.0000"), physical_quantity=Decimal("90.0000"), variance=Decimal("-10.0000")))
        setup_db.commit()

        target_item_id = item.id
        target_issue_id = issue.id
        target_audit_id = audit.id

    barrier = threading.Barrier(2)
    outcomes = [None, None]

    def _issue_worker():
        with pg_session_factory() as worker_db:
            barrier.wait(timeout=10)
            try:
                approve_material_issue(worker_db, target_issue_id, actor_id="usr_mgmt_01")
                outcomes[0] = ("ISSUE_APPROVED", 200)
            except HTTPException as exc:
                outcomes[0] = ("ISSUE_REJECTED", exc.status_code, exc.detail)

    def _audit_worker():
        with pg_session_factory() as worker_db:
            barrier.wait(timeout=10)
            try:
                approve_physical_audit(worker_db, target_audit_id, actor_id="usr_mgmt_02")
                outcomes[1] = ("AUDIT_APPROVED", 200)
            except HTTPException as exc:
                outcomes[1] = ("AUDIT_REJECTED", exc.status_code, exc.detail)

    t1 = threading.Thread(target=_issue_worker)
    t2 = threading.Thread(target=_audit_worker)
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    with pg_session_factory() as check_db:
        final_bal, _, _, _ = get_material_stock_balance(check_db, target_item_id)
        if outcomes[0][1] == 200 and outcomes[1][1] == 409:
            # Issue committed first: balance = 70 kg, audit caught stale snapshot
            assert "Stale audit snapshot detected" in outcomes[1][2]
            assert final_bal == Decimal("70.0000")
        elif outcomes[0][1] == 200 and outcomes[1][1] == 200:
            # Audit committed first (-10 kg -> 90 kg), then issue (-30 kg -> 60 kg)
            assert final_bal == Decimal("60.0000")
        else:
            pytest.fail(f"Unexpected outcomes in concurrent issue vs audit: {outcomes}")


def test_postgres_live_concurrent_waste_versus_audit_approval(pg_session_factory):
    """
    [Real PostgreSQL Concurrency Test] Contention between Waste Scrap Outward (-30 kg)
    and Physical Audit Approval (variance -10 kg against cutoff balance 100 kg).
    """
    suffix = uuid.uuid4().hex[:6].upper()
    with pg_session_factory() as setup_db:
        dept_fdy = setup_db.execute(select(Department).where(Department.code == "FDY")).scalar_one()
        dept_ms = setup_db.execute(select(Department).where(Department.code == "MSP")).scalar_one()
        uom_kg = setup_db.execute(select(UOM).where(UOM.code == "KG")).scalar_one()

        item = MaterialItem(
            item_code=f"FDY-WA-{suffix}",
            name=f"PG Waste vs Audit Item {suffix}",
            department_id=dept_fdy.id,
            category="RAW_MATERIALS",
            base_uom_id=uom_kg.id,
        )
        setup_db.add(item)
        setup_db.flush()

        ob = StockLedgerEntry(
            entry_number=f"STK-OBWA-{suffix}",
            posting_group_id=f"POST-OBWA-{suffix}",
            material_item_id=item.id,
            uom_id=uom_kg.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("100.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=0,
            source_line_id=item.id,
            source_document_number=f"OB-{suffix}",
            posted_by="usr_mgmt_01",
        )
        setup_db.add(ob)

        waste = WasteDispositionHeader(
            waste_number=f"WST-WA-{suffix}",
            disposition_date=date(2026, 10, 24),
            waste_type=WasteType.SLAG.value,
            disposition_type=DispositionType.SCRAP_OUTWARD.value,
            source_department_id=dept_ms.id,
            status=WasteStatus.SUBMITTED.value,
            created_by="usr_stores_01",
        )
        setup_db.add(waste)
        setup_db.flush()
        setup_db.add(WasteDispositionLineItem(waste_id=waste.id, line_number=1, material_item_id=item.id, uom_id=uom_kg.id, quantity=Decimal("30.0000")))

        audit = PhysicalAuditHeader(
            audit_number=f"AUD-WA-{suffix}",
            audit_date=date(2026, 10, 24),
            department_id=dept_fdy.id,
            status=AuditStatus.SUBMITTED.value,
            created_by="usr_stores_02",
        )
        setup_db.add(audit)
        setup_db.flush()
        setup_db.add(PhysicalAuditLine(audit_id=audit.id, line_number=1, material_item_id=item.id, uom_id=uom_kg.id, system_quantity=Decimal("100.0000"), physical_quantity=Decimal("90.0000"), variance=Decimal("-10.0000")))
        setup_db.commit()

        target_item_id = item.id
        target_waste_id = waste.id
        target_audit_id = audit.id

    barrier = threading.Barrier(2)
    outcomes = [None, None]

    def _waste_worker():
        with pg_session_factory() as worker_db:
            barrier.wait(timeout=10)
            try:
                approve_waste_disposition(worker_db, target_waste_id, actor_id="usr_mgmt_01")
                outcomes[0] = ("WASTE_APPROVED", 200)
            except HTTPException as exc:
                outcomes[0] = ("WASTE_REJECTED", exc.status_code, exc.detail)

    def _audit_worker():
        with pg_session_factory() as worker_db:
            barrier.wait(timeout=10)
            try:
                approve_physical_audit(worker_db, target_audit_id, actor_id="usr_mgmt_02")
                outcomes[1] = ("AUDIT_APPROVED", 200)
            except HTTPException as exc:
                outcomes[1] = ("AUDIT_REJECTED", exc.status_code, exc.detail)

    t1 = threading.Thread(target=_waste_worker)
    t2 = threading.Thread(target=_audit_worker)
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    with pg_session_factory() as check_db:
        final_bal, _, _, _ = get_material_stock_balance(check_db, target_item_id)
        if outcomes[0][1] == 200 and outcomes[1][1] == 409:
            assert "Stale audit snapshot detected" in outcomes[1][2]
            assert final_bal == Decimal("70.0000")
        elif outcomes[0][1] == 200 and outcomes[1][1] == 200:
            assert final_bal == Decimal("60.0000")
        else:
            pytest.fail(f"Unexpected outcomes in concurrent waste vs audit: {outcomes}")


def test_postgres_live_concurrent_duplicate_audit_approval(pg_session_factory):
    """
    [Real PostgreSQL Concurrency Test] Two concurrent attempts to approve the exact same physical audit.
    Row-level locking on PhysicalAuditHeader serializes execution: exactly one succeeds (200),
    and the other receives HTTP 400 (already approved).
    """
    suffix = uuid.uuid4().hex[:6].upper()
    with pg_session_factory() as setup_db:
        dept_fdy = setup_db.execute(select(Department).where(Department.code == "FDY")).scalar_one()
        uom_kg = setup_db.execute(select(UOM).where(UOM.code == "KG")).scalar_one()

        item = MaterialItem(
            item_code=f"FDY-DA-{suffix}",
            name=f"PG Duplicate Audit Item {suffix}",
            department_id=dept_fdy.id,
            category="RAW_MATERIALS",
            base_uom_id=uom_kg.id,
        )
        setup_db.add(item)
        setup_db.flush()

        ob = StockLedgerEntry(
            entry_number=f"STK-OBDA-{suffix}",
            posting_group_id=f"POST-OBDA-{suffix}",
            material_item_id=item.id,
            uom_id=uom_kg.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("100.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=0,
            source_line_id=item.id,
            source_document_number=f"OB-{suffix}",
            posted_by="usr_mgmt_01",
        )
        setup_db.add(ob)

        audit = PhysicalAuditHeader(
            audit_number=f"AUD-DA-{suffix}",
            audit_date=date(2026, 10, 24),
            department_id=dept_fdy.id,
            status=AuditStatus.SUBMITTED.value,
            created_by="usr_stores_01",
        )
        setup_db.add(audit)
        setup_db.flush()
        setup_db.add(PhysicalAuditLine(audit_id=audit.id, line_number=1, material_item_id=item.id, uom_id=uom_kg.id, system_quantity=Decimal("100.0000"), physical_quantity=Decimal("90.0000"), variance=Decimal("-10.0000")))
        setup_db.commit()

        target_item_id = item.id
        target_audit_id = audit.id

    barrier = threading.Barrier(2)
    outcomes = [None, None]

    def _worker(idx):
        with pg_session_factory() as worker_db:
            barrier.wait(timeout=10)
            try:
                approve_physical_audit(worker_db, target_audit_id, actor_id="usr_mgmt_01")
                outcomes[idx] = ("APPROVED", 200)
            except HTTPException as exc:
                outcomes[idx] = ("REJECTED", exc.status_code, exc.detail)

    t1 = threading.Thread(target=_worker, args=(0,))
    t2 = threading.Thread(target=_worker, args=(1,))
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    successes = [o for o in outcomes if o and o[1] == 200]
    rejections = [o for o in outcomes if o and o[1] == 400]
    assert len(successes) == 1, f"Expected exactly 1 approval to succeed: {outcomes}"
    assert len(rejections) == 1, f"Expected exactly 1 duplicate to be rejected: {outcomes}"
    assert "Cannot approve audit in status 'APPROVED'" in rejections[0][2]

    with pg_session_factory() as check_db:
        final_bal, _, _, _ = get_material_stock_balance(check_db, target_item_id)
        assert final_bal == Decimal("90.0000"), f"Expected 90 kg balance, got {final_bal}"
        audit_records = check_db.execute(
            select(StockLedgerEntry).where(
                StockLedgerEntry.source_document_type == SourceDocumentType.AUDIT_ADJUSTMENT.value,
                StockLedgerEntry.source_document_id == target_audit_id,
            )
        ).scalars().all()
        assert len(audit_records) == 1, f"Expected exactly 1 ledger adjustment entry, got {len(audit_records)}"


def test_postgres_live_migration_006_append_only_triggers_enforce_immutability(pg_session_factory):
    """
    [Real PostgreSQL Trigger Test] Verifies that Alembic migration 006 triggers
    (trg_stock_ledger_entries_no_update_delete and trg_stock_ledger_entries_no_truncate)
    reject raw SQL UPDATE, DELETE, and TRUNCATE on PostgreSQL 16.
    """
    for forbidden_sql in (
        "UPDATE stock_ledger_entries SET reason = 'tampered'",
        "DELETE FROM stock_ledger_entries",
        "TRUNCATE TABLE stock_ledger_entries CASCADE",
    ):
        with pg_session_factory() as pg_db:
            with pytest.raises(DatabaseError, match="append-only"):
                pg_db.execute(text(forbidden_sql))
            pg_db.rollback()


@pytest.fixture(autouse=True)
def _authenticate_as_admin(client: TestClient, admin_headers: dict):
    """Workflow tests exercise domain rules as Admin; RBAC itself is covered by test_security_routes.py."""
    client.headers.update(admin_headers)
