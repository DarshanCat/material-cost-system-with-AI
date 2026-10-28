"""
Database-free tests for the Item Nomenclature Standard v1.0 rule tables, validators, legacy classification,
and the frozen SQL / mappings in migrations 008 (applied) and 009 (proposed).

No database is created or touched: run with `pytest --noconftest tests/test_item_nomenclature.py`.
"""

import importlib.util
from pathlib import Path

import pytest

import app.models  # noqa: F401  (load models first, as the application does, before the guard modules)
from app.services import item_nomenclature as std

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _load_migration(relative: str):
    spec = importlib.util.spec_from_file_location(Path(relative).stem, BACKEND_DIR / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ----------------------------------------------------------------------------------------------
# Rule tables transcribed from the standard (Sections 3, 4, 6)
# ----------------------------------------------------------------------------------------------

def test_departments_match_section_3():
    assert set(std.DEPARTMENTS) == {"FDY", "MCS", "MNT", "QLY", "PKD", "UTL", "GEN"}


def test_categories_match_section_4():
    expected = {
        "RM": ("Raw Material", "FDY", "Material Cost"),
        "LN": ("Lining Material", "FDY", "Lining Cost"),
        "MD": ("Moulding Material", "FDY", "Moulding Cost"),
        "CN": ("Consumables", "FDY", "Foundry Consumables"),
        "PT": ("Paints & Coatings", "FDY", "Foundry Consumables"),
        "CB": ("Cutting Blades", "MCS", "Machining Consumables"),
        "IT": ("Inserts & Tools", "MCS", "Machining Consumables"),
        "OL": ("Oils & Lubricants", "MNT", "Maintenance Cost"),
        "BR": ("Bearings", "MNT", "Maintenance Cost"),
        "BL": ("Belts", "MNT", "Maintenance Cost"),
        "BN": ("Bolts & Nuts", "MNT", "Maintenance Cost"),
        "QC": ("Quality Material", "QLY", "Quality Consumables"),
        "PK": ("Packing Material", "PKD", "Packing Cost"),
        "FU": ("Fuel", "UTL", "Energy / Fuel"),
        "SF": ("Safety Material", "GEN", "Safety Cost"),
    }
    actual = {code: (r.name, r.department_code, r.cost_head) for code, r in std.CATEGORIES.items()}
    assert actual == expected
    assert all(r.department_code in std.DEPARTMENTS for r in std.CATEGORIES.values())


def test_uoms_match_section_6():
    assert set(std.APPROVED_UOMS.values()) == {"Kg", "Nos", "Ltr", "Pack", "Roll", "Mtr"}
    assert std.normalize_uom_code("Kgs") == "KG"
    assert std.normalize_uom_code("pcs") == "NOS"
    assert std.normalize_uom_code("Pieces") == "NOS"
    assert std.normalize_uom_code("Ltrs") == "LTR"
    assert std.normalize_uom_code("Nos") == "NOS"
    for not_approved in ("MT", "Set", "BAG", "FT", "Box", "", None):
        assert std.normalize_uom_code(not_approved) is None


# ----------------------------------------------------------------------------------------------
# Category resolution: exact code or name only; legacy values never derived
# ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("value,code", [("RM", "RM"), ("rm", "RM"), ("Raw Material", "RM"), (" bolts & nuts ", "BN")])
def test_resolve_category_accepts_exact_code_or_name(value, code):
    assert std.resolve_category(value).code == code


@pytest.mark.parametrize("value", ["RAW_MATERIAL", "ALLOY", "CONSUMABLE", "CON", "FA", "GC", "Machine Spareparts", "Raw", "", None])
def test_resolve_category_rejects_legacy_and_unknown(value):
    assert std.resolve_category(value) is None


# ----------------------------------------------------------------------------------------------
# Code format and serials
# ----------------------------------------------------------------------------------------------

def test_format_and_parse_item_code():
    assert std.format_item_code("FDY", "RM", 1) == "FDY-RM-001"
    assert std.format_item_code("MCS", "CB", 999) == "MCS-CB-999"
    assert std.parse_item_code("MCS-CB-004") == ("MCS", "CB", 4)
    for bad in ("FDY-RM-0001", "FDY-RM-01", "FDY-RMX-001", "F2-SP-001", "MCS-IT-TNMG160408", "VSPL-DV-72", "fdy-rm-001"):
        assert std.parse_item_code(bad) is None
    with pytest.raises(ValueError):
        std.format_item_code("FDY", "RM", 1000)
    with pytest.raises(ValueError):
        std.format_item_code("FDY", "RM", 0)


def test_serial_from_code_counts_any_numeric_width_under_prefix():
    prefix = std.code_prefix("FDY", "RM")
    assert std.serial_from_code("FDY-RM-032", prefix) == 32
    assert std.serial_from_code("FDY-RM-1000", prefix) == 1000  # legacy over-long serial still blocks reuse
    assert std.serial_from_code("FDY-RM-0A1", prefix) is None
    assert std.serial_from_code("FDY-RMX-001", prefix) is None


# ----------------------------------------------------------------------------------------------
# Description rules (Section 5)
# ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text,category",
    [
        ("Bearing 6210 2Z C3", "BR"),
        ("Hex Bolt M12x50 MS", "BN"),
        ("Band Saw Blade 3/4 3505", "CB"),
        ("Rust Preventive Oil RPL-120", "OL"),
        ("Belt C-68", "BL"),
        ("CF Blanket", "CN"),
        ("SVLHTC (MGS)", "LN"),
        ("Pipe 100 mm Dia", "CN"),
        ("WNMG080408-GHUC5115", "IT"),
        ("TNMG 160408", "IT"),
    ],
)
def test_standard_examples_have_no_errors_or_warnings(text, category):
    check = std.validate_description(text, category)
    assert check.errors == []
    assert check.warnings == []


@pytest.mark.parametrize(
    "text,code",
    [
        ("", "required"),
        ("   ", "required"),
        (None, "required"),
        (" Belt C-68", "whitespace_edges"),
        ("Belt C-68 ", "whitespace_edges"),
        ("Belt  C-68", "whitespace_repeated"),
        ("Belt\tC-68", "whitespace_control"),
        ("Belt\nC-68", "whitespace_control"),
        ("X", "too_short"),
        ("A" * 256, "too_long"),
    ],
)
def test_description_hard_errors(text, code):
    assert code in {e.code for e in std.validate_description(text, "BL").errors}


@pytest.mark.parametrize(
    "text,code",
    [
        ("HEX BOLT M12X50", "all_caps"),
        ("hex bolt m12x50", "all_lower"),
        ("Hex bolt M12x50", "title_case"),
        ("Paint Red Oil Rs 450", "contains_price"),
        ("Paint Red Oil FDY", "contains_department"),
    ],
)
def test_description_warnings_are_not_errors(text, code):
    check = std.validate_description(text, "BN")
    assert check.errors == []
    assert code in {w.code for w in check.warnings}


def test_iso_designations_are_kept_verbatim_for_inserts():
    check = std.validate_description("WNMG 080408 MP", "IT")
    assert check.errors == [] and check.warnings == []
    # Hard whitespace rules still apply to verbatim categories.
    assert std.validate_description("WNMG  080408", "IT").errors


def test_description_keys_normalise_case_punctuation_and_spacing():
    assert std.description_key("Borings-450/10") == std.description_key("borings 450 10")
    assert std.compact_description_key("Belt C-68") == std.compact_description_key("Belt C68")
    assert std.description_key("Belt C-68") != std.description_key("Belt C68")


# ----------------------------------------------------------------------------------------------
# Legacy classification (report only)
# ----------------------------------------------------------------------------------------------

def test_conforming_items_have_no_findings():
    assert std.classify_existing_item("MNT-BN-012", "MNT", "Bolts & Nuts") == []
    assert std.classify_existing_item("FDY-RM-001", "FDY", "RM") == []


@pytest.mark.parametrize(
    "code,dept,category,fragment",
    [
        ("MCS-IT-TNMG160408", "MCS", "Inserts & Tools", "does not match the v1.0 format"),
        ("F2-SP-001", "F2", "Machine Spareparts", "does not match the v1.0 format"),
        ("GEN-GC-001", "GEN", "General Consumables", "Category 'GC' is not a v1.0 category"),
        ("MNT-CN-001", "MNT", "Consumables", "belongs to department 'FDY'"),
        ("MSP-CB-001", "MSP", "Cutting Blades", "Department prefix 'MSP'"),
        ("MNT-BN-136", "FDY", "Bolts & Nuts", "differs from the item's department code"),
        ("FDY-RM-001", "FDY", "RAW_MATERIAL", "is not a v1.0 category name or code"),
        ("QLY-QC-027", "QLY", "Consumables", "differs from the code's category"),
    ],
)
def test_non_standard_items_are_classified_with_reasons(code, dept, category, fragment):
    reasons = std.classify_existing_item(code, dept, category)
    assert any(fragment in r for r in reasons), reasons


# ----------------------------------------------------------------------------------------------
# Migrations: frozen SQL and mappings stay in step with application code
# ----------------------------------------------------------------------------------------------

def test_migration_008_trigger_sql_matches_guard():
    from app.db import item_code_guard as guard

    migration = _load_migration("migrations/versions/008_item_code_registry.py")
    assert migration.revision == "008_item_code_registry"
    assert migration.down_revision == "007_opening_val_versioning"
    assert set(migration.PROTECTED_TABLES) == set(guard.PROTECTED_TABLES)
    for table in guard.PROTECTED_TABLES:
        assert [s.split() for s in migration._pg_upgrade_sql(table)] == [s.split() for s in guard.pg_upgrade_sql(table)]
        assert migration._pg_downgrade_sql(table) == guard.pg_downgrade_sql(table)


def test_migration_008_tables_match_models():
    from app.db.base import Base
    import app.models  # noqa: F401  (registers models)

    for table in ("item_code_sequences", "item_code_registry", "item_master_audit_logs"):
        assert table in Base.metadata.tables


def test_proposed_cost_head_migration_is_not_in_alembic_versions_and_matches_standard():
    assert not (BACKEND_DIR / "migrations" / "versions" / "009_material_item_cost_head.py").exists()
    proposal = _load_migration("migrations/proposed/009_material_item_cost_head.py")
    assert proposal.down_revision == "008_item_code_registry"
    mapping = {code: (name, dept, head) for code, name, dept, head in proposal.CATEGORY_COST_HEADS}
    assert mapping == {code: (r.name, r.department_code, r.cost_head) for code, r in std.CATEGORIES.items()}


def test_rules_payload_is_complete():
    payload = std.rules_payload()
    assert payload["version"] == std.STANDARD_VERSION
    assert payload["serial_max"] == 999
    assert len(payload["categories"]) == 15
    assert {c["code"] for c in payload["categories"] if c["verbatim_description"]} == {"IT"}
