"""P2P chain on a GRN: Stores creates/submits -> Quality inspects -> Management approves (stock is posted) -> Accounts pays."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.security import UserRole
from app.models.department import Department
from app.models.grn import GRNAuditLog
from app.models.item import MaterialItem
from app.models.ledger import StockLedgerEntry
from app.models.uom import UOM
from app.models.vendor import Vendor
from app.services.validators import normalize_vendor_name

pytestmark = pytest.mark.qa_gate  # these tests run with the QA gate switched ON (as in production)


@pytest.fixture
def quality_headers(role_headers):
    return role_headers(UserRole.QUALITY)


@pytest.fixture
def accounts_headers(role_headers):
    return role_headers(UserRole.ACCOUNTS)


@pytest.fixture
def submitted_grn(client, db_session: Session, stores_headers):
    vendor = Vendor(name="Tata Steel Ltd", normalized_name=normalize_vendor_name("Tata Steel Ltd"), gstin="27AAACT2727Q1ZW")
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()
    db_session.add(vendor)
    db_session.commit()
    item = MaterialItem(item_code="FDY-RM-001", name="Pig Iron", department_id=dept.id, category="RM", base_uom_id=uom.id)
    db_session.add(item)
    db_session.commit()
    res = client.post(
        "/api/v1/grn/",
        headers=stores_headers,
        json={
            "receipt_date": str(date.today()), "source_type": "EXTERNAL_VENDOR", "vendor_id": vendor.id,
            "vendor_invoice_no": "INV-9", "invoice_date": str(date.today()),
            # value = 10 x 40 x 1.18 = 472.00
            "lines": [{"line_number": 1, "material_item_id": item.id, "uom_id": uom.id, "quantity": "10", "rate_ex_gst": "40", "gst_percent": "18"}],
        },
    )
    assert res.status_code == 201, res.text
    grn = res.json()
    assert client.post(f"/api/v1/grn/{grn['id']}/submit", headers=stores_headers, json={}).status_code == 200
    return grn


def _qa(client, headers, grn_id, result="PASSED", **extra):
    return client.post(f"/api/v1/grn/{grn_id}/quality", headers=headers, json={"quality_inspection_status": result, **extra})


def _pay(client, headers, grn_id, amount="472.00", ref="UTR-1", **extra):
    return client.post(f"/api/v1/grn/{grn_id}/payment", headers=headers, json={"amount_paid": amount, "payment_reference": ref, **extra})


def _stock_rows(db_session):
    return db_session.query(StockLedgerEntry).count()


def test_cannot_approve_without_quality_pass(client, submitted_grn, management_headers, db_session):
    res = client.post(f"/api/v1/grn/{submitted_grn['id']}/approve", headers=management_headers, json={})
    assert res.status_code == 409 and "Quality" in res.json()["detail"]
    assert _stock_rows(db_session) == 0


def test_full_chain_stock_is_added_only_on_management_approval(
    client, submitted_grn, stores_headers, quality_headers, management_headers, accounts_headers, db_session
):
    gid = submitted_grn["id"]
    qa = _qa(client, quality_headers, gid, quality_document_number="MTC-77", quality_inspection_notes="Chemistry within spec")
    assert qa.status_code == 200, qa.text
    body = qa.json()
    assert body["status"] == "SUBMITTED" and body["quality_inspection_status"] == "PASSED"
    assert body["quality_inspected_by"] == "usr_quality_01" and body["quality_document_number"] == "MTC-77"
    assert _stock_rows(db_session) == 0  # QA does not add stock

    appr = client.post(f"/api/v1/grn/{gid}/approve", headers=management_headers, json={})
    assert appr.status_code == 200, appr.text
    assert appr.json()["status"] == "APPROVED" and appr.json()["payment_status"] == "UNPAID"
    assert Decimal(str(appr.json()["payable_total"])) == Decimal("472.00")
    assert _stock_rows(db_session) == 1  # stock added at approval

    first = _pay(client, accounts_headers, gid, "200.00", "UTR-A", payment_mode="UPI")
    assert first.status_code == 200, first.text
    assert first.json()["payment_status"] == "PARTIALLY_PAID" and Decimal(str(first.json()["amount_paid"])) == Decimal("200.00")
    last = _pay(client, accounts_headers, gid, "272.00", "UTR-B")
    assert last.status_code == 200 and last.json()["payment_status"] == "PAID" and last.json()["paid_by"] == "usr_accounts_01"

    # Payment is persisted, not just echoed back.
    again = client.get(f"/api/v1/grn/{gid}", headers=stores_headers).json()
    assert again["payment_status"] == "PAID" and again["payment_reference"] == "UTR-B"
    actions = [a.action for a in db_session.query(GRNAuditLog).filter_by(grn_id=gid).order_by(GRNAuditLog.id)]
    assert actions == ["CREATED", "SUBMITTED", "QA_PASSED", "APPROVED", "PAYMENT_RECORDED", "PAYMENT_RECORDED"]


def test_failed_qa_blocks_approval_and_management_can_reject(client, submitted_grn, quality_headers, management_headers, db_session):
    gid = submitted_grn["id"]
    assert _qa(client, quality_headers, gid, "REJECTED").status_code == 422  # notes are mandatory
    assert _qa(client, quality_headers, gid, "REJECTED", quality_inspection_notes="Hardness out of range").status_code == 200
    assert client.post(f"/api/v1/grn/{gid}/approve", headers=management_headers, json={}).status_code == 409
    assert client.post(f"/api/v1/grn/{gid}/reject", headers=management_headers, json={}).status_code == 422  # reason required
    res = client.post(f"/api/v1/grn/{gid}/reject", headers=management_headers, json={"comments": "Failed QA"})
    assert res.status_code == 200 and res.json()["status"] == "REJECTED"
    assert _stock_rows(db_session) == 0
    assert client.post(f"/api/v1/grn/{gid}/reject", headers=management_headers, json={"comments": "again"}).status_code == 409


def test_qa_can_be_corrected_while_submitted(client, submitted_grn, quality_headers, management_headers):
    gid = submitted_grn["id"]
    assert _qa(client, quality_headers, gid, "REJECTED", quality_inspection_notes="Wrong sample").status_code == 200
    assert _qa(client, quality_headers, gid, "CONDITIONALLY_ACCEPTED", quality_inspection_notes="Use for non-critical heats").status_code == 200
    assert client.post(f"/api/v1/grn/{gid}/approve", headers=management_headers, json={}).status_code == 200


def test_only_quality_role_can_inspect_and_only_accounts_can_pay(
    client, submitted_grn, stores_headers, management_headers, admin_headers, quality_headers, accounts_headers
):
    gid = submitted_grn["id"]
    for who in (stores_headers, management_headers, admin_headers, accounts_headers):
        assert _qa(client, who, gid).status_code == 403
    assert _qa(client, quality_headers, gid).status_code == 200
    assert client.post(f"/api/v1/grn/{gid}/approve", headers=management_headers, json={}).status_code == 200
    for who in (stores_headers, management_headers, admin_headers, quality_headers):
        assert _pay(client, who, gid).status_code == 403
    assert _pay(client, accounts_headers, gid).status_code == 200


def test_payment_rules(client, submitted_grn, quality_headers, management_headers, accounts_headers):
    gid = submitted_grn["id"]
    assert _pay(client, accounts_headers, gid).status_code == 409  # not approved yet
    assert _qa(client, quality_headers, gid).status_code == 200
    assert client.post(f"/api/v1/grn/{gid}/approve", headers=management_headers, json={}).status_code == 200
    assert _pay(client, accounts_headers, gid, "0").status_code == 422
    assert _pay(client, accounts_headers, gid, "472.01").status_code == 422  # more than the GRN value
    assert _pay(client, accounts_headers, gid, "100", ref=" ").status_code == 422  # reference required
    assert _pay(client, accounts_headers, gid, "100", payment_mode="CASH_IN_HAND").status_code == 422
    assert _pay(client, accounts_headers, gid, "472.00").status_code == 200
    assert _pay(client, accounts_headers, gid, "0.01").status_code == 422  # already fully paid


def test_creator_cannot_inspect_or_pay_their_own_grn(client, db_session, submitted_grn, quality_headers, management_headers, accounts_headers):
    gid = submitted_grn["id"]
    from app.models.grn import GRNHeader

    # Pretend the Quality / Accounts user also created the GRN: segregation of duties must still hold.
    db_session.get(GRNHeader, gid).created_by = "usr_quality_01"
    db_session.commit()
    assert _qa(client, quality_headers, gid).status_code == 403
    db_session.get(GRNHeader, gid).created_by = "usr_stores_01"
    db_session.commit()
    assert _qa(client, quality_headers, gid).status_code == 200
    assert client.post(f"/api/v1/grn/{gid}/approve", headers=management_headers, json={}).status_code == 200
    db_session.get(GRNHeader, gid).created_by = "usr_accounts_01"
    db_session.commit()
    assert _pay(client, accounts_headers, gid).status_code == 403


def test_qa_only_on_submitted_grn(client, stores_headers, submitted_grn, quality_headers, management_headers):
    gid = submitted_grn["id"]
    assert _qa(client, quality_headers, gid).status_code == 200
    assert client.post(f"/api/v1/grn/{gid}/approve", headers=management_headers, json={}).status_code == 200
    assert _qa(client, quality_headers, gid, "REJECTED", quality_inspection_notes="too late").status_code == 409
    bad = _qa(client, quality_headers, gid, "MAYBE")
    assert bad.status_code in (409, 422)
