"""
Sprint 3 step 1 - Costing dashboard API contract tests.

The frontend declares the costing response shapes in frontend/src/types.ts. The backend schemas
(app/schemas/costing.py) are the authority. These tests fail if the two drift apart, which is how
the Exceptions tab (reading keys the API never returned) was able to crash the UI.

1. Static: every field declared in the TS interface exists in the backend response schema, and a TS field
   declared non-nullable is always present (required in the schema's serialized form).
2. Runtime: real API responses (seeded data, Management role) contain exactly the keys the TS
   interfaces declare for the untyped endpoints (exceptions, comparison) and the typed ones.
"""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.item import MaterialItem
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.models.uom import UOM

TYPES_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types.ts"

# TS interface -> backend response schema (component name in OpenAPI)
CONTRACT = {
    "InventoryValuationReport": "InventoryValuationReport",
    "ItemValuationSummary": "ItemValuationResponse",
    "ItemRateJournal": "ItemRateHistoryResponse",
    "ItemRateJournalEntry": "ItemCostJournalStep",
    "HeatCostSummary": "HeatCostResponse",
    "HeatCostLineSummary": "HeatCostLineResponse",
    "PartCostSummary": "PartCostResponse",
    "CostingRunSummary": "CostingRunSummaryResponse",
}


def _ts_interface(name: str) -> dict[str, bool]:
    """Field name -> required (not optional and not nullable) for `export interface <name> { ... }`."""
    source = TYPES_TS.read_text(encoding="utf-8")
    match = re.search(rf"export interface {name}\s*\{{(.*?)\n\}}", source, re.S)
    assert match, f"{name} missing from types.ts"
    fields: dict[str, bool] = {}
    for line in match.group(1).splitlines():
        m = re.match(r"\s*(\w+)(\?)?:\s*(.+?);\s*(//.*)?$", line)
        if m:
            name_, optional, type_ = m.group(1), bool(m.group(2)), m.group(3)
            fields[name_] = not optional and "null" not in type_
    assert fields, f"no fields parsed for {name}"
    return fields


@pytest.fixture(scope="module")
def schemas():
    from app.main import app
    return app.openapi()["components"]["schemas"]


@pytest.mark.parametrize("ts_name,schema_name", sorted(CONTRACT.items()))
def test_typescript_interface_matches_backend_schema(schemas, ts_name, schema_name):
    schema = schemas[schema_name]
    props, required = set(schema["properties"]), set(schema.get("required", []))
    for field, ts_required in _ts_interface(ts_name).items():
        assert field in props, f"{ts_name}.{field} is not returned by backend schema {schema_name}"
        # A field with a default is always serialized by FastAPI responses, so it is safe to treat as present.
        if ts_required and "default" not in schema["properties"][field]:
            assert field in required, (
                f"{ts_name}.{field} is non-nullable in TypeScript but optional in {schema_name}; "
                "declare it `?: T | null` in types.ts"
            )


# --- runtime shapes ----------------------------------------------------------------------------------

@pytest.fixture
def seeded(db_session: Session):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    kg = db_session.query(UOM).filter_by(code="KG").first()
    item = MaterialItem(item_code="FDY-RM-555", name="Contract Test Pig Iron", department_id=dept.id,
                        category="RAW_MATERIALS", base_uom_id=kg.id, is_active=True)
    db_session.add(item)
    db_session.commit()
    db_session.add(StockLedgerEntry(
        entry_number="STK-CT-OB", posting_group_id="POST-CT", material_item_id=item.id, uom_id=kg.id,
        transaction_date=date(2026, 10, 12), movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("500.0000"), source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0, source_line_id=item.id, source_document_number="OB-CT", posted_by="usr_seed",
    ))
    db_session.commit()
    return {"item": item, "kg": kg}


def _declared(name: str) -> set[str]:
    return set(_ts_interface(name))


def test_valuation_and_rate_history_responses_carry_declared_fields(anon_client, seeded, management_headers):
    val = anon_client.get("/api/v1/costing/valuation/historical?as_of_date=2026-10-22", headers=management_headers)
    assert val.status_code == 200, val.text
    body = val.json()
    assert _declared("InventoryValuationReport") <= set(body)
    assert body["items"], "seeded item should appear in the valuation report"
    assert _declared("ItemValuationSummary") <= set(body["items"][0])

    hist = anon_client.get(f"/api/v1/costing/rates/history/{seeded['item'].id}", headers=management_headers)
    assert hist.status_code == 200, hist.text
    h = hist.json()
    assert _declared("ItemRateJournal") <= set(h)
    assert h["steps"] and _declared("ItemRateJournalEntry") <= set(h["steps"][0])


def test_exceptions_response_matches_declared_shape(anon_client, seeded, management_headers):
    resp = anon_client.get("/api/v1/costing/exceptions", headers=management_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == _declared("CostingExceptionsReport")
    # The seeded opening balance has no approved rate, so it must be listed with the declared row shape.
    rows = body["missing_opening_valuation"] + body["unvalued_stock"] + body["negative_stock"]
    assert rows
    for row in rows:
        assert set(row) == _declared("CostingExceptionRow")
    # The keys the old UI read must not exist (guards against reintroducing the crash).
    assert "pending_openings" not in body and "missing_rates" not in body


def test_runs_and_comparison_responses_match_declared_shape(anon_client, seeded, management_headers):
    payload = {"period_start": "2026-10-12", "period_end": "2026-10-22", "as_of_date": "2026-10-22"}
    ids = []
    for _ in range(2):
        created = anon_client.post("/api/v1/costing/runs", json=payload, headers=management_headers)
        assert created.status_code == 200, created.text
        assert _declared("CostingRunSummary") <= set(created.json())
        ids.append(created.json()["id"])

    listed = anon_client.get("/api/v1/costing/runs", headers=management_headers)
    assert listed.status_code == 200 and listed.json()
    assert _declared("CostingRunSummary") <= set(listed.json()[0])

    cmp_ = anon_client.get(f"/api/v1/costing/runs/compare?run_id_1={ids[0]}&run_id_2={ids[1]}", headers=management_headers)
    assert cmp_.status_code == 200, cmp_.text
    body = cmp_.json()
    assert set(body) == {"summary", "item_differences"}
    assert set(body["summary"]) == {
        "run_1_number", "run_2_number", "run_1_as_of", "run_2_as_of", "valuation_run_1", "valuation_run_2",
        "valuation_delta", "heat_cost_run_1", "heat_cost_run_2", "heat_cost_delta",
    }


def test_heat_cost_response_includes_furnace_and_canonical_item(anon_client, db_session, seeded, management_headers, foundry_headers):
    heat = {
        "heat_number": "H-102610-0001", "heat_date": "2026-10-15", "furnace_id": "FURNACE-1",
        "metal_tapped_weight": "400.0000", "metal_tapped_uom_id": seeded["kg"].id, "production_status": "COMPLETED",
        "charge_lines": [{"original_material_description": "Contract Test Pig Iron", "charged_quantity": "400.0000",
                          "uom_id": seeded["kg"].id}],
    }
    assert anon_client.post("/api/v1/heats", json=heat, headers=foundry_headers).status_code == 201

    resp = anon_client.get("/api/v1/costing/heats", headers=management_headers)
    assert resp.status_code == 200, resp.text
    first = resp.json()[0]
    assert _declared("HeatCostSummary") <= set(first)
    assert first["furnace_id"] == "FURNACE-1"
    assert first["lines"] and _declared("HeatCostLineSummary") <= set(first["lines"][0])


# --- every frontend API path resolves to a backend route without a redirect ------------------------------

FRONTEND_SRC = TYPES_TS.parent


def _frontend_api_paths() -> set[str]:
    paths = set()
    for file in FRONTEND_SRC.rglob("*.ts*"):
        for literal in re.findall(r"""['"`](/api/v1/[^'"`?\s]*)""", file.read_text(encoding="utf-8")):
            paths.add(re.sub(r"\$\{[^}]*\}", "X", literal))
    return paths


def test_frontend_api_paths_match_backend_routes_exactly():
    """
    A path that differs only by a trailing slash makes FastAPI answer 307 with an absolute Location on the
    backend host; browsers drop the Authorization header on that cross-origin redirect, so the call fails
    with 401/CORS even though the user is signed in. Paths must therefore match the route templates exactly.
    """
    from app.main import app

    backend = [p.split("/") for p in app.openapi()["paths"]]

    def matches(frontend_path: str) -> bool:
        segs = frontend_path.split("/")
        for template in backend:
            if len(template) != len(segs):
                continue
            # "X" is an interpolated value (an id or an action name): it may stand for a parameter or a literal.
            if all(t.startswith("{") or s == "X" or s == t for s, t in zip(segs, template)):
                return True
        return False

    paths = _frontend_api_paths()
    assert len(paths) > 40  # sanity: the scan actually found the API calls
    unmatched = sorted(p for p in paths if not matches(p))
    assert unmatched == [], f"Frontend calls paths with no exact backend route (missing/extra trailing slash?): {unmatched}"
