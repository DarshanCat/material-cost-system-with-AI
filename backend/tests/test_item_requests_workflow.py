from fastapi.testclient import TestClient


def test_item_request_full_approval_lifecycle(
    client: TestClient,
    stores_headers: dict,
    management_headers: dict,
):
    """
    Verify standard lifecycle:
    Draft Creation -> Draft Update -> Submission -> Management Approval -> Material Item Created
    """
    # 1. Fetch department and UOM IDs
    depts = client.get("/api/v1/departments", headers=stores_headers).json()
    fdy_id = next(d["id"] for d in depts if d["code"] == "FDY")

    uoms = client.get("/api/v1/uoms", headers=stores_headers).json()
    kg_id = next(u["id"] for u in uoms if u["code"] == "KG")

    # 2. Stores creates Draft Request
    create_payload = {
        "requested_name": "Inoculant FeSi-75 Premium",
        "proposed_department_id": fdy_id,
        "proposed_category": "ALLOY",
        "proposed_subcategory": "INOCULANT",
        "proposed_uom_id": kg_id,
        "justification": "Required for SG iron ladle nodulizing treatment.",
    }
    create_res = client.post("/api/v1/item-requests", json=create_payload, headers=stores_headers)
    assert create_res.status_code == 201
    req = create_res.json()
    req_id = req["id"]
    assert req["status"] == "DRAFT"
    assert req["request_number"].startswith("REQ-")
    assert len(req["audit_logs"]) == 1
    assert req["audit_logs"][0]["action"] == "CREATED"

    # 3. Stores updates draft details
    update_payload = dict(create_payload)
    update_payload["justification"] = "Updated: Critical for ductile iron heat grade 500/7."
    update_res = client.put(f"/api/v1/item-requests/{req_id}", json=update_payload, headers=stores_headers)
    assert update_res.status_code == 200
    assert update_res.json()["justification"] == update_payload["justification"]

    # 4. Stores submits request
    submit_res = client.post(f"/api/v1/item-requests/{req_id}/submit", headers=stores_headers)
    assert submit_res.status_code == 200
    submitted_req = submit_res.json()
    assert submitted_req["status"] == "SUBMITTED"
    assert submitted_req["submitted_at"] is not None

    # 5. Cannot edit submitted request
    edit_after_submit = client.put(f"/api/v1/item-requests/{req_id}", json=update_payload, headers=stores_headers)
    assert edit_after_submit.status_code == 400

    # 6. Check pending queue shows the submitted request
    pending_res = client.get("/api/v1/item-requests/pending", headers=management_headers)
    assert pending_res.status_code == 200
    assert any(r["id"] == req_id for r in pending_res.json()["items"])

    # 7. Management approves request
    approve_res = client.post(
        f"/api/v1/item-requests/{req_id}/approve",
        json={"comments": "Approved for purchase and stores cataloging."},
        headers=management_headers,
    )
    assert approve_res.status_code == 200
    approved_req = approve_res.json()
    assert approved_req["status"] == "APPROVED"
    assert approved_req["linked_item_id"] is not None

    # 8. Verify MaterialItem was created in database with standard code convention
    item_res = client.get(f"/api/v1/items/{approved_req['linked_item_id']}", headers=stores_headers)
    assert item_res.status_code == 200
    item = item_res.json()
    assert item["name"] == "Inoculant FeSi-75 Premium"
    assert item["item_code"] == "FDY-FA-001"
    assert item["department_id"] == fdy_id

    # 9. Verify repeated approval fails (Idempotency / State Guard)
    dup_approve = client.post(
        f"/api/v1/item-requests/{req_id}/approve",
        json={"comments": "Repeat attempt"},
        headers=management_headers,
    )
    assert dup_approve.status_code == 400


def test_self_approval_prevention(client: TestClient, management_headers: dict):
    """
    CRITICAL BUSINESS RULE:
    A manager cannot approve an item request they themselves requested (No self-approval).
    """
    depts = client.get("/api/v1/departments", headers=management_headers).json()
    fdy_id = depts[0]["id"]
    uoms = client.get("/api/v1/uoms", headers=management_headers).json()
    kg_id = uoms[0]["id"]

    # Manager creates request
    create_res = client.post(
        "/api/v1/item-requests",
        json={
            "requested_name": "Special Ferro Silicon",
            "proposed_department_id": fdy_id,
            "proposed_category": "ALLOY",
            "proposed_uom_id": kg_id,
            "justification": "Test self approval",
        },
        headers=management_headers,
    )
    req_id = create_res.json()["id"]

    # Manager submits request
    client.post(f"/api/v1/item-requests/{req_id}/submit", headers=management_headers)

    # Manager attempts to approve their own request
    self_approve_res = client.post(
        f"/api/v1/item-requests/{req_id}/approve",
        json={"comments": "Approving my own item"},
        headers=management_headers,  # Same user ID!
    )
    assert self_approve_res.status_code == 403
    assert "Self-approval violation" in self_approve_res.json()["detail"]


def test_unauthorized_approval_attempt(client: TestClient, stores_headers: dict, foundry_headers: dict):
    """Stores or Foundry role cannot approve item requests."""
    depts = client.get("/api/v1/departments", headers=stores_headers).json()
    fdy_id = depts[0]["id"]
    uoms = client.get("/api/v1/uoms", headers=stores_headers).json()
    kg_id = uoms[0]["id"]

    # Stores creates and submits
    create_res = client.post(
        "/api/v1/item-requests",
        json={
            "requested_name": "Bentonite Clay Powder",
            "proposed_department_id": fdy_id,
            "proposed_category": "CONSUMABLE",
            "proposed_uom_id": kg_id,
            "justification": "Moulding sand binder.",
        },
        headers=stores_headers,
    )
    req_id = create_res.json()["id"]
    client.post(f"/api/v1/item-requests/{req_id}/submit", headers=stores_headers)

    # Foundry role tries to approve
    fdy_approve_res = client.post(
        f"/api/v1/item-requests/{req_id}/approve",
        json={"comments": "Foundry approval"},
        headers=foundry_headers,
    )
    assert fdy_approve_res.status_code == 403


def test_rejection_workflow_with_mandatory_reason(
    client: TestClient,
    stores_headers: dict,
    management_headers: dict,
):
    """Verify rejection requires a reason and does NOT create a material item."""
    depts = client.get("/api/v1/departments", headers=stores_headers).json()
    fdy_id = depts[0]["id"]
    uoms = client.get("/api/v1/uoms", headers=stores_headers).json()
    kg_id = uoms[0]["id"]

    create_res = client.post(
        "/api/v1/item-requests",
        json={
            "requested_name": "Unapproved Chemical Solvent",
            "proposed_department_id": fdy_id,
            "proposed_category": "CONSUMABLE",
            "proposed_uom_id": kg_id,
            "justification": "General cleaning.",
        },
        headers=stores_headers,
    )
    req_id = create_res.json()["id"]
    client.post(f"/api/v1/item-requests/{req_id}/submit", headers=stores_headers)

    # 1. Attempt rejection with empty reason -> 400
    empty_rej = client.post(
        f"/api/v1/item-requests/{req_id}/reject",
        json={"comments": "   "},
        headers=management_headers,
    )
    assert empty_rej.status_code == 400
    assert "Rejection requires an explicit explanation" in empty_rej.json()["detail"]

    # 2. Reject with valid reason
    rej_res = client.post(
        f"/api/v1/item-requests/{req_id}/reject",
        json={"comments": "Safety hazard; alternative eco-friendly solvent already exists in stores."},
        headers=management_headers,
    )
    assert rej_res.status_code == 200
    rejected_req = rej_res.json()
    assert rejected_req["status"] == "REJECTED"
    assert rejected_req["linked_item_id"] is None

    # Verify no material item was created
    items_list = client.get("/api/v1/items?q=Unapproved", headers=stores_headers).json()
    assert items_list["total"] == 0


def test_duplicate_item_conflict_detection(
    client: TestClient,
    stores_headers: dict,
    management_headers: dict,
):
    """Verify duplicate active item name in same department is blocked."""
    depts = client.get("/api/v1/departments", headers=stores_headers).json()
    fdy_id = depts[0]["id"]
    uoms = client.get("/api/v1/uoms", headers=stores_headers).json()
    kg_id = uoms[0]["id"]

    # 1. Create and approve first item
    res1 = client.post(
        "/api/v1/item-requests",
        json={
            "requested_name": "Low Sulphur Petroleum Coke",
            "proposed_department_id": fdy_id,
            "proposed_category": "RAW_MATERIAL",
            "proposed_uom_id": kg_id,
            "justification": "Furnace recarburizer.",
        },
        headers=stores_headers,
    )
    req1_id = res1.json()["id"]
    client.post(f"/api/v1/item-requests/{req1_id}/submit", headers=stores_headers)
    client.post(f"/api/v1/item-requests/{req1_id}/approve", headers=management_headers)

    # 2. Attempt to create and submit another request with identical item name in same department
    res2 = client.post(
        "/api/v1/item-requests",
        json={
            "requested_name": "  low sulphur petroleum coke  ",
            "proposed_department_id": fdy_id,
            "proposed_category": "RAW_MATERIAL",
            "proposed_uom_id": kg_id,
            "justification": "Duplicate request.",
        },
        headers=stores_headers,
    )
    req2_id = res2.json()["id"]
    submit_dup = client.post(f"/api/v1/item-requests/{req2_id}/submit", headers=stores_headers)
    assert submit_dup.status_code == 409
    assert "Conflict detected" in submit_dup.json()["detail"]
