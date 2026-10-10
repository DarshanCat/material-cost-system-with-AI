from fastapi.testclient import TestClient


def test_vendor_creation_and_normalization(client: TestClient, purchase_headers: dict):
    """Verify vendor creation preserves display name and enforces normalized deduplication."""
    payload = {
        "name": "Tata Steel Limited",
        "gstin": "27AAACT2727Q1ZW",
        "address": "Jamshedpur Works, Jharkhand",
        "contact_person": "Mr. R. Sharma",
        "phone": "+91 9876543210",
        "email": "procurement@tatasteel.com",
    }
    res = client.post("/api/v1/vendors", json=payload, headers=purchase_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Tata Steel Limited"
    assert data["normalized_name"] == "tata steel limited"
    assert data["gstin"] == "27AAACT2727Q1ZW"

    # Attempt creating duplicate with different case and punctuation
    dup_payload = {
        "name": "  TATA STEEL LIMITED.  ",
        "gstin": None,
    }
    dup_res = client.post("/api/v1/vendors", json=dup_payload, headers=purchase_headers)
    assert dup_res.status_code == 409
    assert "Duplicate vendor conflict" in dup_res.json()["detail"]


def test_vendor_optional_gstin_and_validation(client: TestClient, purchase_headers: dict):
    """Verify GSTIN is optional, but invalid formats are rejected."""
    # 1. Valid without GSTIN
    res_no_gst = client.post(
        "/api/v1/vendors",
        json={"name": "Local Industrial Supplies"},
        headers=purchase_headers,
    )
    assert res_no_gst.status_code == 201
    assert res_no_gst.json()["gstin"] is None

    # 2. Invalid GSTIN format rejected
    res_bad_gst = client.post(
        "/api/v1/vendors",
        json={"name": "Bad GST Vendor", "gstin": "INVALID123"},
        headers=purchase_headers,
    )
    assert res_bad_gst.status_code == 422


def test_vendor_search_and_pagination(client: TestClient, purchase_headers: dict, stores_headers: dict):
    """Verify vendor search by name, contact, and pagination."""
    vendors = [
        {"name": "Electro Alloys Corporation", "contact_person": "A. Kumar"},
        {"name": "Bhilai Auxiliary Chemicals", "contact_person": "S. Verma"},
        {"name": "Southern Refractories Ltd", "contact_person": "P. Rao"},
    ]
    for v in vendors:
        client.post("/api/v1/vendors", json=v, headers=purchase_headers)

    # Search by keyword
    search_res = client.get("/api/v1/vendors?q=alloys", headers=stores_headers)
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total"] == 1
    assert search_data["items"][0]["name"] == "Electro Alloys Corporation"

    # Pagination
    page_res = client.get("/api/v1/vendors?page=1&size=2", headers=stores_headers)
    assert page_res.status_code == 200
    page_data = page_res.json()
    assert len(page_data["items"]) == 2
    assert page_data["size"] == 2
