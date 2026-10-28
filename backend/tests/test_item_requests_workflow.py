"""
Item request workflow under the Item Nomenclature Standard v1.0.

Obsolete assumptions removed: the legacy categories ALLOY / CONSUMABLE / RAW_MATERIAL and codes such as
FDY-FA-001 are not part of v1.0. Requests now use v1.0 category codes (e.g. RM) and the seeded FDY
department and KG UOM, which are both v1.0-approved.
"""

from fastapi.testclient import TestClient


def _ref_ids(client: TestClient, headers: dict) -> tuple[int, int]:
    depts = client.get("/api/v1/departments", headers=headers).json()
    fdy_id = next(d["id"] for d in depts if d["code"] == "FDY")
    uoms = client.get("/api/v1/uoms", headers=headers).json()
    kg_id = next(u["id"] for u in uoms if u["code"] == "KG")
    return fdy_id, kg_id


def _create(client: TestClient, headers: dict, name: str, category: str = "RM", justification: str = "Required for production.") -> dict:
    fdy_id, kg_id = _ref_ids(client, headers)
    res = client.post(
        "/api/v1/item-requests",
        json={
            "requested_name": name,
            "proposed_department_id": fdy_id,
            "proposed_category": category,
            "proposed_uom_id": kg_id,
            "justification": justification,
        },
        headers=headers,
    )
    return res


def test_item_request_full_approval_lifecycle(
    client: TestClient,
    stores_headers: dict,
    management_headers: dict,
):
    """
    Verify standard lifecycle:
    Draft Creation -> Draft Update -> Submission -> Management Approval -> Material Item Created
    """
    fdy_id, kg_id = _ref_ids(client, stores_headers)

    # 1. Stores creates Draft Request (category given by v1.0 name; stored as its code)
    create_payload = {
        "requested_name": "Low Sulphur Petroleum Coke",
        "proposed_department_id": fdy_id,
        "proposed_category": "Raw Material",
        "proposed_subcategory": "RECARBURISER",
        "proposed_uom_id": kg_id,
        "justification": "Required for SG iron furnace recarburising.",
    }
    create_res = client.post("/api/v1/item-requests", json=create_payload, headers=stores_headers)
    assert create_res.status_code == 201, create_res.text
    req = create_res.json()
    req_id = req["id"]
    assert req["status"] == "DRAFT"
    assert req["proposed_category"] == "RM"
    assert req["request_number"].startswith("REQ-")
    assert len(req["audit_logs"]) == 1
    assert req["audit_logs"][0]["action"] == "CREATED"

    # 2. Stores updates draft details
    update_payload = dict(create_payload)
    update_payload["justification"] = "Updated: Critical for ductile iron heat grade 500/7."
    update_res = client.put(f"/api/v1/item-requests/{req_id}", json=update_payload, headers=stores_headers)
    assert update_res.status_code == 200, update_res.text
    assert update_res.json()["justification"] == update_payload["justification"]

    # 3. Stores submits request
    submit_res = client.post(f"/api/v1/item-requests/{req_id}/submit", headers=stores_headers)
    assert submit_res.status_code == 200, submit_res.text
    submitted_req = submit_res.json()
    assert submitted_req["status"] == "SUBMITTED"
    assert submitted_req["submitted_at"] is not None

    # 4. Cannot edit submitted request
    edit_after_submit = client.put(f"/api/v1/item-requests/{req_id}", json=update_payload, headers=stores_headers)
    assert edit_after_submit.status_code == 400

    # 5. Pending queue shows the submitted request
    pending_res = client.get("/api/v1/item-requests/pending", headers=management_headers)
    assert pending_res.status_code == 200
    assert any(r["id"] == req_id for r in pending_res.json()["items"])

    # 6. Management approves request
    approve_res = client.post(
        f"/api/v1/item-requests/{req_id}/approve",
        json={"comments": "Approved for purchase and stores cataloging."},
        headers=management_headers,
    )
    assert approve_res.status_code == 200, approve_res.text
    approved_req = approve_res.json()
    assert approved_req["status"] == "APPROVED"
    assert approved_req["linked_item_id"] is not None
    assert approved_req["linked_item_code"] == "FDY-RM-001"

    # 7. MaterialItem created with the v1.0 code and the standard category name
    item_res = client.get(f"/api/v1/items/{approved_req['linked_item_id']}", headers=stores_headers)
    assert item_res.status_code == 200
    item = item_res.json()
    assert item["name"] == "Low Sulphur Petroleum Coke"
    assert item["item_code"] == "FDY-RM-001"
    assert item["category"] == "Raw Material"
    assert item["department_id"] == fdy_id

    # 8. Registration recorded in the permanent registry and item history
    history = client.get(f"/api/v1/items/{item['id']}/history", headers=stores_headers).json()
    assert history["registry"]["item_code"] == "FDY-RM-001"
    assert history["registry"]["serial"] == 1
    assert history["registry"]["item_request_id"] == req_id
    assert [e["action"] for e in history["events"]] == ["REGISTERED"]

    # 9. Repeated approval fails (Idempotency / State Guard)
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
    create_res = _create(client, management_headers, "Special Ferro Silicon")
    assert create_res.status_code == 201, create_res.text
    req_id = create_res.json()["id"]
    assert client.post(f"/api/v1/item-requests/{req_id}/submit", headers=management_headers).status_code == 200

    self_approve_res = client.post(
        f"/api/v1/item-requests/{req_id}/approve",
        json={"comments": "Approving my own item"},
        headers=management_headers,  # Same user ID!
    )
    assert self_approve_res.status_code == 403
    assert "Self-approval violation" in self_approve_res.json()["detail"]


def test_unauthorized_approval_attempt(client: TestClient, stores_headers: dict, foundry_headers: dict):
    """Stores or Foundry role cannot approve item requests."""
    create_res = _create(client, stores_headers, "Bentonite Clay Powder", category="MD")
    assert create_res.status_code == 201, create_res.text
    req_id = create_res.json()["id"]
    client.post(f"/api/v1/item-requests/{req_id}/submit", headers=stores_headers)

    for headers in (foundry_headers, stores_headers):
        res = client.post(f"/api/v1/item-requests/{req_id}/approve", json={"comments": "x"}, headers=headers)
        assert res.status_code == 403


def test_rejection_workflow_with_mandatory_reason(
    client: TestClient,
    stores_headers: dict,
    management_headers: dict,
):
    """Verify rejection requires a reason and does NOT create a material item."""
    create_res = _create(client, stores_headers, "Unapproved Chemical Solvent", category="CN")
    assert create_res.status_code == 201, create_res.text
    req_id = create_res.json()["id"]
    client.post(f"/api/v1/item-requests/{req_id}/submit", headers=stores_headers)

    empty_rej = client.post(
        f"/api/v1/item-requests/{req_id}/reject",
        json={"comments": "   "},
        headers=management_headers,
    )
    assert empty_rej.status_code == 400
    assert "Rejection requires an explicit explanation" in empty_rej.json()["detail"]

    rej_res = client.post(
        f"/api/v1/item-requests/{req_id}/reject",
        json={"comments": "Safety hazard; alternative eco-friendly solvent already exists in stores."},
        headers=management_headers,
    )
    assert rej_res.status_code == 200
    rejected_req = rej_res.json()
    assert rejected_req["status"] == "REJECTED"
    assert rejected_req["linked_item_id"] is None

    items_list = client.get("/api/v1/items?q=Unapproved", headers=stores_headers).json()
    assert items_list["total"] == 0


def test_duplicate_item_conflict_detection(
    client: TestClient,
    stores_headers: dict,
    management_headers: dict,
):
    """A normalised duplicate of an approved item (case, punctuation, spacing) is blocked at creation."""
    res1 = _create(client, stores_headers, "Low Sulphur Petroleum Coke")
    req1_id = res1.json()["id"]
    client.post(f"/api/v1/item-requests/{req1_id}/submit", headers=stores_headers)
    assert client.post(f"/api/v1/item-requests/{req1_id}/approve", headers=management_headers).status_code == 200

    for variant in ("Low Sulphur Petroleum-Coke", "Low SulphurPetroleum Coke"):
        dup = _create(client, stores_headers, variant)
        assert dup.status_code == 409, dup.text
        detail = dup.json()["detail"]
        assert "FDY-RM-001" in detail["message"]
        assert detail["duplicates"][0]["source"] == "ITEM"


def test_legacy_category_and_whitespace_rejected_for_new_requests(client: TestClient, stores_headers: dict):
    """Legacy categories are never mapped or abbreviated for new requests; invalid whitespace is rejected."""
    legacy = _create(client, stores_headers, "Inoculant FeSi-75 Premium", category="ALLOY")
    assert legacy.status_code == 422
    assert legacy.json()["detail"]["errors"][0]["code"] == "not_in_standard"

    padded = _create(client, stores_headers, "  Petroleum Coke  ")
    assert padded.status_code == 422
    assert any(e["code"] == "whitespace_edges" for e in padded.json()["detail"]["errors"])

    wrong_owner = _create(client, stores_headers, "Bearing 6210 2Z C3", category="BR")  # BR belongs to MNT
    assert wrong_owner.status_code == 422
    assert any(e["code"] == "department_mismatch" for e in wrong_owner.json()["detail"]["errors"])
