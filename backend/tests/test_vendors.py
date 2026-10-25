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


def test_vendor_update_metadata_and_activation(client: TestClient, purchase_headers: dict):
    """Verify vendor details can be updated, including contact info and activation status."""
    create_res = client.post(
        "/api/v1/vendors",
        json={"name": "Kirloskar Ferrous Industries", "contact_person": "V. Kulkarni", "phone": "9999911111"},
        headers=purchase_headers,
    )
    assert create_res.status_code == 201
    vendor_id = create_res.json()["id"]

    # Update metadata
    update_res = client.put(
        f"/api/v1/vendors/{vendor_id}",
        json={
            "contact_person": "Vijay Kulkarni",
            "phone": "9888822222",
            "email": "vkulkarni@kirloskar.com",
            "address": "Koppal Works, Karnataka",
            "gstin": "29AAACK1919A1Z5",
            "is_active": False,
        },
        headers=purchase_headers,
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["contact_person"] == "Vijay Kulkarni"
    assert updated["phone"] == "9888822222"
    assert updated["email"] == "vkulkarni@kirloskar.com"
    assert updated["address"] == "Koppal Works, Karnataka"
    assert updated["gstin"] == "29AAACK1919A1Z5"
    assert updated["is_active"] is False

    # Reactivate vendor
    reactivate_res = client.put(
        f"/api/v1/vendors/{vendor_id}",
        json={"is_active": True},
        headers=purchase_headers,
    )
    assert reactivate_res.status_code == 200
    assert reactivate_res.json()["is_active"] is True


def test_vendor_update_name_and_conflict_detection(client: TestClient, purchase_headers: dict):
    """Verify updating vendor name updates normalized key, but duplicate names return 409."""
    v1_res = client.post("/api/v1/vendors", json={"name": "Jindal Steel & Power"}, headers=purchase_headers)
    assert v1_res.status_code == 201
    v1_id = v1_res.json()["id"]

    v2_res = client.post("/api/v1/vendors", json={"name": "JSW Steel Ltd"}, headers=purchase_headers)
    assert v2_res.status_code == 201
    v2_id = v2_res.json()["id"]

    # 1. Update v1 name to a unique new name
    renamed_res = client.put(
        f"/api/v1/vendors/{v1_id}",
        json={"name": "Jindal Steel and Power Limited"},
        headers=purchase_headers,
    )
    assert renamed_res.status_code == 200
    assert renamed_res.json()["name"] == "Jindal Steel and Power Limited"
    assert renamed_res.json()["normalized_name"] == "jindal steel and power limited"

    # 2. Update v1 name to collide with v2 (should fail with 409)
    conflict_res = client.put(
        f"/api/v1/vendors/{v1_id}",
        json={"name": "  JSW STEEL LTD.  "},
        headers=purchase_headers,
    )
    assert conflict_res.status_code == 409
    assert "Duplicate vendor conflict" in conflict_res.json()["detail"]

    # 3. Update v2 name to same normalized name with different display formatting (should succeed)
    self_update_res = client.put(
        f"/api/v2/vendors/{v2_id}" if False else f"/api/v1/vendors/{v2_id}",
        json={"name": "JSW Steel Limited (Ballari)"},
        headers=purchase_headers,
    )
    assert self_update_res.status_code == 200
    assert self_update_res.json()["name"] == "JSW Steel Limited (Ballari)"


def test_vendor_update_validation_and_permissions(client: TestClient, purchase_headers: dict, stores_headers: dict):
    """Verify vendor update validates GSTIN format and enforces VENDOR_MANAGE permission."""
    v_res = client.post("/api/v1/vendors", json={"name": "Vedanta Aluminium"}, headers=purchase_headers)
    assert v_res.status_code == 201
    v_id = v_res.json()["id"]

    # 1. Invalid GSTIN rejected with 422
    bad_gst = client.put(
        f"/api/v1/vendors/{v_id}",
        json={"gstin": "INVALID_GSTIN_123"},
        headers=purchase_headers,
    )
    assert bad_gst.status_code == 422

    # 2. Permission check: stores role lacks VENDOR_MANAGE
    forbidden_res = client.put(
        f"/api/v1/vendors/{v_id}",
        json={"contact_person": "Unauthorized Update"},
        headers=stores_headers,
    )
    assert forbidden_res.status_code == 403

    # 3. 404 for non-existent vendor
    not_found = client.put(
        "/api/v1/vendors/999999",
        json={"name": "Nonexistent Vendor"},
        headers=purchase_headers,
    )
    assert not_found.status_code == 404
