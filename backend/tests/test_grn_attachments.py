"""GRN supporting documents: validation, permissions, status rules, audit trail, storage independence."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app as fastapi_app
from app.models.department import Department
from app.models.grn import GRNAttachment, GRNAuditLog
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.vendor import Vendor
from app.services import attachment_store as store_mod
from app.services.attachment_store import LocalStore, check_upload, get_attachment_store, safe_display_name
from app.services.validators import normalize_vendor_name

PDF = b"%PDF-1.4\n%test document\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
XLSX = b"PK\x03\x04" + b"\x00" * 32


class MemoryStore:
    def __init__(self):
        self.files = {}

    def save(self, key, data, content_type):
        self.files[key] = data

    def read(self, key):
        return self.files[key]

    def delete(self, key):
        self.files.pop(key, None)


@pytest.fixture
def memory_store():
    mem = MemoryStore()
    fastapi_app.dependency_overrides[get_attachment_store] = lambda: mem
    yield mem
    fastapi_app.dependency_overrides.pop(get_attachment_store, None)


@pytest.fixture
def grn(client: TestClient, db_session: Session, stores_headers):
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
            "vendor_invoice_no": "INV-1", "invoice_date": str(date.today()),
            "lines": [{"line_number": 1, "material_item_id": item.id, "uom_id": uom.id, "quantity": "10", "rate_ex_gst": "40", "gst_percent": "18"}],
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _upload(client, headers, grn_id, name="invoice.pdf", data=PDF, **extra):
    return client.post(f"/api/v1/grn/{grn_id}/attachments", headers=headers, files={"file": (name, data)}, data=extra)


def test_upload_list_download_delete_round_trip(client, grn, stores_headers, memory_store, db_session):
    res = _upload(client, stores_headers, grn["id"], "Vendor Invoice 42.pdf", description="Original invoice")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["original_filename"] == "Vendor Invoice 42.pdf" and body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(PDF) and body["description"] == "Original invoice" and body["uploaded_by"]
    assert len(memory_store.files) == 1 and next(iter(memory_store.files)).startswith(f"grn/{grn['id']}/")

    listing = client.get(f"/api/v1/grn/{grn['id']}/attachments", headers=stores_headers).json()
    assert [a["id"] for a in listing] == [body["id"]]

    down = client.get(f"/api/v1/grn/{grn['id']}/attachments/{body['id']}/download", headers=stores_headers)
    assert down.status_code == 200 and down.content == PDF
    assert down.headers["content-type"] == "application/pdf"
    assert down.headers["content-disposition"].startswith("attachment;") and down.headers["x-content-type-options"] == "nosniff"

    actions = [a.action for a in db_session.query(GRNAuditLog).filter_by(grn_id=grn["id"]).all()]
    assert "ATTACHMENT_ADDED" in actions

    assert client.delete(f"/api/v1/grn/{grn['id']}/attachments/{body['id']}", headers=stores_headers).status_code == 204
    assert memory_store.files == {} and client.get(f"/api/v1/grn/{grn['id']}/attachments", headers=stores_headers).json() == []
    assert "ATTACHMENT_REMOVED" in [a.action for a in db_session.query(GRNAuditLog).filter_by(grn_id=grn["id"]).all()]


@pytest.mark.parametrize(
    "name,data,expected",
    [
        ("virus.exe", b"MZ\x90\x00", "not allowed"),
        ("page.html", b"<script>alert(1)</script>", "not allowed"),
        ("fake.pdf", b"this is not a pdf", "does not match"),
        ("fake.png", PDF, "does not match"),
        ("empty.pdf", b"", "empty"),
        ("noext", PDF, "not allowed"),
    ],
)
def test_bad_files_are_rejected(client, grn, stores_headers, memory_store, name, data, expected):
    res = _upload(client, stores_headers, grn["id"], name, data)
    assert res.status_code == 422 and expected in res.json()["detail"]
    assert memory_store.files == {}


def test_size_limit(client, grn, stores_headers, memory_store, monkeypatch):
    monkeypatch.setattr(store_mod.settings, "ATTACHMENT_MAX_MB", 1)
    big = PDF + b"0" * (1024 * 1024)
    res = _upload(client, stores_headers, grn["id"], "big.pdf", big)
    assert res.status_code == 422 and "larger than 1 MB" in res.json()["detail"]


def test_per_grn_limit(client, grn, stores_headers, memory_store, monkeypatch):
    from app.api.v1.endpoints import grn as grn_endpoints

    monkeypatch.setattr(grn_endpoints.settings, "ATTACHMENT_MAX_PER_DOCUMENT", 2)
    assert _upload(client, stores_headers, grn["id"], "a.pdf").status_code == 201
    assert _upload(client, stores_headers, grn["id"], "b.png", PNG).status_code == 201
    assert _upload(client, stores_headers, grn["id"], "c.xlsx", XLSX).status_code == 409


def test_filename_cannot_reach_the_storage_path(client, grn, stores_headers, memory_store):
    res = _upload(client, stores_headers, grn["id"], "..\\..\\etc\\passwd.pdf")
    assert res.status_code == 201
    assert res.json()["original_filename"] == "passwd.pdf"
    key = next(iter(memory_store.files))
    assert ".." not in key and "passwd" not in key and key.endswith(".pdf")


def test_permissions(client, grn, stores_headers, foundry_headers, purchase_headers, memory_store):
    assert client.post(f"/api/v1/grn/{grn['id']}/attachments", files={"file": ("a.pdf", PDF)}).status_code == 401
    assert _upload(client, foundry_headers, grn["id"]).status_code == 403  # may not create GRNs
    assert _upload(client, stores_headers, grn["id"]).status_code == 201
    att = client.get(f"/api/v1/grn/{grn['id']}/attachments", headers=stores_headers).json()[0]["id"]
    assert client.get(f"/api/v1/grn/{grn['id']}/attachments/{att}/download").status_code == 401
    assert client.delete(f"/api/v1/grn/{grn['id']}/attachments/{att}", headers=foundry_headers).status_code == 403


def test_documents_are_locked_once_the_grn_is_approved_or_cancelled(client, grn, stores_headers, management_headers, memory_store):
    att = _upload(client, stores_headers, grn["id"]).json()["id"]
    assert client.post(f"/api/v1/grn/{grn['id']}/submit", headers=stores_headers, json={"comments": "ok"}).status_code == 200
    assert _upload(client, stores_headers, grn["id"], "more.pdf").status_code == 201  # Submitted: still allowed
    assert client.delete(f"/api/v1/grn/{grn['id']}/attachments/{att}", headers=stores_headers).status_code == 409  # not Draft
    assert client.post(f"/api/v1/grn/{grn['id']}/approve", headers=management_headers, json={"comments": "ok"}).status_code == 200
    assert _upload(client, stores_headers, grn["id"], "late.pdf").status_code == 409
    assert client.get(f"/api/v1/grn/{grn['id']}/attachments", headers=stores_headers).status_code == 200  # still readable


def test_attachment_of_another_grn_is_not_reachable(client, grn, stores_headers, memory_store):
    att = _upload(client, stores_headers, grn["id"]).json()["id"]
    assert client.get(f"/api/v1/grn/{grn['id'] + 999}/attachments", headers=stores_headers).status_code == 404
    assert client.get(f"/api/v1/grn/{grn['id'] + 999}/attachments/{att}/download", headers=stores_headers).status_code == 404


def test_validation_helpers():
    assert safe_display_name("C:\\docs\\a\\b.pdf") == "b.pdf" and safe_display_name("../../x.PDF") == "x.PDF"
    assert safe_display_name("") == "document" and len(safe_display_name("a" * 500 + ".pdf")) <= 150
    assert check_upload("scan.JPG", b"\xff\xd8\xff\xe0" + b"0" * 10).content_type == "image/jpeg"
    with pytest.raises(store_mod.AttachmentRejected):
        check_upload("a.pdf", PNG)


def test_local_store_refuses_paths_outside_its_folder(tmp_path):
    local = LocalStore(str(tmp_path))
    local.save("grn/1/a.pdf", PDF, "application/pdf")
    assert local.read("grn/1/a.pdf") == PDF
    with pytest.raises(ValueError):
        local.save("../escape.pdf", PDF, "application/pdf")
    local.delete("grn/1/a.pdf")
    local.delete("grn/1/a.pdf")  # deleting twice is harmless
