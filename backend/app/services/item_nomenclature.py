"""
VSPL Item Nomenclature Standard v1.0 — machine-readable rule tables and pure validators.

Source of truth: `VSPL_Item_Nomenclature_Standard.docx` (Version 1.0, Phase 1, owner Stores).
Every table below is transcribed from that document; nothing here is inferred from workbook data.
A change to any table requires a new, approved version of the standard (Section 9) — bump
STANDARD_VERSION together with the edit.

This module performs no database access, so it can be unit-tested without a database.

Legacy compatibility (grandfathering): items that already exist with codes outside v1.0 are reported
by `classify_existing_item` but are never rejected, renamed or deactivated because of it. New item
requests are validated strictly with `validate_new_item_proposal`-style helpers in the services.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.validators import normalize_alias_key

STANDARD_NAME = "VSPL Item Nomenclature Standard"
STANDARD_VERSION = "1.0"

# Section 2: CC-CAT-### — department (3 letters), category (2 letters), serial (3 digits, 001-999).
ITEM_CODE_PATTERN = re.compile(r"^([A-Z]{3})-([A-Z]{2})-([0-9]{3})$")
MIN_SERIAL = 1
MAX_SERIAL = 999

# Section 3: Departments (owning department, first part of the code).
DEPARTMENTS: dict[str, str] = {
    "FDY": "Foundry",
    "MCS": "Machine Shop",
    "MNT": "Maintenance",
    "QLY": "Quality",
    "PKD": "Packing / Dispatch",
    "UTL": "Utilities",
    "GEN": "General / Stores",
}


@dataclass(frozen=True)
class CategoryRule:
    code: str
    name: str
    department_code: str
    cost_head: str
    pattern: str
    example: str


# Section 4 (category, owning department, cost head) and Section 5.3 (description pattern by category).
CATEGORIES: dict[str, CategoryRule] = {
    rule.code: rule
    for rule in (
        CategoryRule("RM", "Raw Material", "FDY", "Material Cost", "Material Grade/Size", "Borings 450/10 · Copper · CRC"),
        CategoryRule("LN", "Lining Material", "FDY", "Lining Cost", "Product Grade", "SVLHTC (MGS) · Quick Cast"),
        CategoryRule("MD", "Moulding Material", "FDY", "Moulding Cost", "Material Grade", "Pre-Coated Sand · Chromite Sand"),
        CategoryRule("CN", "Consumables", "FDY", "Foundry Consumables", "Noun Spec", "CF Blanket · Mould Sealing Rope"),
        CategoryRule("PT", "Paints & Coatings", "FDY", "Foundry Consumables", "Paint Colour Base", "Paint Red Oil · Red Oxide Primer"),
        CategoryRule("CB", "Cutting Blades", "MCS", "Machining Consumables", "Type Size", "Band Saw Blade 3/4 3505"),
        CategoryRule("IT", "Inserts & Tools", "MCS", "Machining Consumables", "ISO designation (verbatim)", "WNMG080408-GHUC5115"),
        CategoryRule("OL", "Oils & Lubricants", "MNT", "Maintenance Cost", "Type Oil Grade", "Rust Preventive Oil RPL-120"),
        CategoryRule("BR", "Bearings", "MNT", "Maintenance Cost", "Bearing Number Suffix", "Bearing 6210 2Z C3"),
        CategoryRule("BL", "Belts", "MNT", "Maintenance Cost", "Belt Section-Size", "Belt C-68 · Belt B-44"),
        CategoryRule("BN", "Bolts & Nuts", "MNT", "Maintenance Cost", "Type Thread×Length Material", "Hex Bolt M12x50 MS · Nut M12"),
        CategoryRule("QC", "Quality Material", "QLY", "Quality Consumables", "Material Grade", "Silica Gel · Ethanol"),
        CategoryRule("PK", "Packing Material", "PKD", "Packing Cost", "Material Purpose", "Axxanol Packing · Ferrocote Dispatch"),
        CategoryRule("FU", "Fuel", "UTL", "Energy / Fuel", "Fuel type", "Diesel"),
        CategoryRule("SF", "Safety Material", "GEN", "Safety Cost", "Item Variant", "Helmet Yellow · Leather Gloves"),
    )
}

# Categories whose description is an ISO designation recorded verbatim (Section 5.3): no Title Case advice.
VERBATIM_DESCRIPTION_CATEGORIES = frozenset({"IT"})

# Section 6: the only UOMs for new items. Keys are the canonical (upper-case) codes stored in `uoms.code`,
# matching the existing seed convention; values are the spelling used in the standard.
APPROVED_UOMS: dict[str, str] = {
    "KG": "Kg",
    "NOS": "Nos",
    "LTR": "Ltr",
    "PACK": "Pack",
    "ROLL": "Roll",
    "MTR": "Mtr",
}
UOM_MEANINGS: dict[str, str] = {
    "KG": "Kilogram",
    "NOS": "Numbers / pieces",
    "LTR": "Litre",
    "PACK": "Pack",
    "ROLL": "Roll",
    "MTR": "Metre",
}
# Section 6: legacy variants mapped automatically (Kgs→Kg, Pieces/Pcs→Nos, Ltrs→Ltr). Keys are upper-case.
UOM_ALIASES: dict[str, str] = {
    "KGS": "KG",
    "PIECES": "NOS",
    "PCS": "NOS",
    "LTRS": "LTR",
}

# Section 5.4: standard abbreviations (exact spelling).
ABBREVIATIONS: dict[str, str] = {
    "MS": "Mild Steel",
    "SS": "Stainless Steel",
    "Dia": "Diameter",
    "Thk": "Thickness",
    "LH": "Left Hand",
    "RH": "Right Hand",
    "Assy": "Assembly",
    "Qty": "Quantity",
    "Approx": "Approximate",
    "mm": "millimetre",
    "m": "metre",
    "L": "litre",
    "kg": "kilogram",
}

# Section 5.1
NAMING_FORMULA = "Primary Noun → Type / Grade → Size / Specification → Material / Variant"

MAX_DESCRIPTION_LENGTH = 255  # material_items.name / item_requests.requested_name column width
MIN_DESCRIPTION_LENGTH = 2


# ----------------------------------------------------------------------------------------------
# Issues
# ----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Issue:
    """One validation finding. `code` is a stable machine-readable identifier."""

    field: str
    code: str
    message: str

    def as_dict(self) -> dict:
        return {"field": self.field, "code": self.code, "message": self.message}


@dataclass
class DescriptionCheck:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)


# ----------------------------------------------------------------------------------------------
# Lookups
# ----------------------------------------------------------------------------------------------

def resolve_category(value: Optional[str]) -> Optional[CategoryRule]:
    """
    Returns the v1.0 category for an exact category code ('BN') or exact category name ('Bolts & Nuts'),
    ignoring case and surrounding whitespace. Anything else — including legacy values such as
    'RAW_MATERIAL' or 'CONSUMABLE' — returns None. No abbreviation is ever derived from free text.
    """
    if not value:
        return None
    key = value.strip()
    rule = CATEGORIES.get(key.upper())
    if rule:
        return rule
    folded = key.casefold()
    for rule in CATEGORIES.values():
        if rule.name.casefold() == folded:
            return rule
    return None


def categories_for_department(department_code: str) -> list[CategoryRule]:
    return [rule for rule in CATEGORIES.values() if rule.department_code == department_code]


def cost_head_for_category(category_code: str) -> Optional[str]:
    rule = CATEGORIES.get(category_code)
    return rule.cost_head if rule else None


def normalize_uom_code(value: Optional[str]) -> Optional[str]:
    """Maps a UOM spelling to its approved canonical code ('Kgs' -> 'KG'); None if not approved."""
    if not value:
        return None
    key = value.strip().upper()
    key = UOM_ALIASES.get(key, key)
    return key if key in APPROVED_UOMS else None


def parse_item_code(code: Optional[str]) -> Optional[tuple[str, str, int]]:
    """Splits a v1.0-format code into (department, category, serial); None if the format differs."""
    if not code:
        return None
    match = ITEM_CODE_PATTERN.match(code)
    if not match:
        return None
    return match.group(1), match.group(2), int(match.group(3))


def format_item_code(department_code: str, category_code: str, serial: int) -> str:
    if not MIN_SERIAL <= serial <= MAX_SERIAL:
        raise ValueError(f"Serial {serial} is outside {MIN_SERIAL:03d}-{MAX_SERIAL:03d}")
    return f"{department_code}-{category_code}-{serial:03d}"


def code_prefix(department_code: str, category_code: str) -> str:
    return f"{department_code}-{category_code}-"


def serial_from_code(code: str, prefix: str) -> Optional[int]:
    """
    Serial number of `code` under `prefix` when the remainder is all digits (any width), else None.
    Used to find the highest serial ever issued; deliberately tolerant of legacy widths so that an
    over-long legacy serial still blocks reuse rather than being ignored.
    """
    if not code.startswith(prefix):
        return None
    suffix = code[len(prefix):]
    return int(suffix) if suffix.isdigit() else None


# ----------------------------------------------------------------------------------------------
# Description rules (Section 5)
# ----------------------------------------------------------------------------------------------

def description_key(text: str) -> str:
    """Normalised search key: lower-case, punctuation to spaces, collapsed whitespace."""
    return normalize_alias_key(text or "")


def compact_description_key(text: str) -> str:
    """Normalised key with all spaces removed, so 'Belt C-68' and 'Belt C68' compare equal."""
    return description_key(text).replace(" ", "")


_CONTROL_CHARS = re.compile(r"[\t\r\n\x00-\x1f\x7f]")
_PRICE_MARKERS = re.compile(r"(₹|\bRs\.?(?=\s|\d|$)|\bINR\b|/-)", re.IGNORECASE)
_LOWER_UNIT_TOKENS = {abbr for abbr in ABBREVIATIONS if abbr[0].islower()}
_VOWEL = re.compile(r"[AEIOU]")


def _strip_token(token: str) -> str:
    return token.strip("()[]{}.,;:'\"")


def validate_description(text: Optional[str], category_code: Optional[str], field_name: str = "description") -> DescriptionCheck:
    """
    Section 5.2 formatting rules.
    Hard errors: missing text, length, leading/trailing whitespace, repeated spaces, tabs/new lines.
    Warnings only: Title Case deviations, ALL CAPS, price markers, department codes in the text.
    Categories recorded verbatim (IT, ISO designations) skip the Title Case advice.
    """
    result = DescriptionCheck()
    if text is None or not text.strip():
        result.errors.append(Issue(field_name, "required", "Item description is required."))
        return result
    if text != text.strip():
        result.errors.append(Issue(field_name, "whitespace_edges", "Remove leading or trailing spaces from the description."))
    if _CONTROL_CHARS.search(text):
        result.errors.append(Issue(field_name, "whitespace_control", "Tabs and line breaks are not allowed in the description."))
    if "  " in text:
        result.errors.append(Issue(field_name, "whitespace_repeated", "Use a single space between words (double spaces found)."))
    stripped = text.strip()
    if len(stripped) < MIN_DESCRIPTION_LENGTH:
        result.errors.append(Issue(field_name, "too_short", f"Description must be at least {MIN_DESCRIPTION_LENGTH} characters."))
    if len(text) > MAX_DESCRIPTION_LENGTH:
        result.errors.append(Issue(field_name, "too_long", f"Description must be at most {MAX_DESCRIPTION_LENGTH} characters."))

    if _PRICE_MARKERS.search(stripped):
        result.warnings.append(Issue(field_name, "contains_price", "Prices do not belong in the description (Section 5.2)."))
    tokens = [_strip_token(t) for t in stripped.split()]
    tokens = [t for t in tokens if t]
    dept_tokens = sorted({t for t in tokens if t.upper() in DEPARTMENTS and t.isupper()})
    if dept_tokens:
        result.warnings.append(
            Issue(field_name, "contains_department", f"Department codes do not belong in the description: {', '.join(dept_tokens)}.")
        )

    if category_code in VERBATIM_DESCRIPTION_CATEGORIES:
        return result

    alpha_words = [t for t in tokens if t.isalpha()]
    # Acronyms and grade codes (CRC, CF, SVLHTC, MGS) are legitimately upper-case; only flag ALL CAPS when
    # at least two ordinary words (containing a vowel, not standard abbreviations) are capitalised.
    shouted = [w for w in alpha_words if w.isupper() and len(w) > 1 and w not in ABBREVIATIONS and _VOWEL.search(w)]
    if len(shouted) >= 2 and all(w.isupper() for w in alpha_words):
        result.warnings.append(Issue(field_name, "all_caps", "Use Title Case rather than ALL CAPS (Section 5.2)."))
    elif alpha_words and all(w.islower() for w in alpha_words) and not all(w in _LOWER_UNIT_TOKENS for w in alpha_words):
        result.warnings.append(Issue(field_name, "all_lower", "Use Title Case rather than all lower-case (Section 5.2)."))
    else:
        lower_words = [w for w in alpha_words if w[0].islower() and w not in _LOWER_UNIT_TOKENS]
        if lower_words:
            result.warnings.append(
                Issue(field_name, "title_case", f"Capitalise the main words (Title Case): {', '.join(dict.fromkeys(lower_words))}.")
            )
    return result


# ----------------------------------------------------------------------------------------------
# Legacy compliance (grandfathered records: report only, never reject or modify)
# ----------------------------------------------------------------------------------------------

def classify_existing_item(item_code: str, department_code: Optional[str], category_text: Optional[str]) -> list[str]:
    """
    Reasons why an existing item does not conform to v1.0; an empty list means it conforms.
    Informational only — callers must not reject, rename, deactivate or migrate records based on it.
    """
    reasons: list[str] = []
    parsed = parse_item_code(item_code)
    if parsed is None:
        reasons.append("Code does not match the v1.0 format DEPT-CAT-### (3 letters, 2 letters, 3 digits).")
        return reasons
    code_dept, code_cat, serial = parsed
    if code_dept not in DEPARTMENTS:
        reasons.append(f"Department prefix '{code_dept}' is not a v1.0 department.")
    rule = CATEGORIES.get(code_cat)
    if rule is None:
        reasons.append(f"Category '{code_cat}' is not a v1.0 category.")
    elif rule.department_code != code_dept:
        reasons.append(f"Category '{code_cat}' belongs to department '{rule.department_code}', not '{code_dept}'.")
    if serial < MIN_SERIAL:
        reasons.append("Serial 000 is outside the v1.0 range 001-999.")
    if department_code is not None and department_code != code_dept:
        reasons.append(f"Code prefix '{code_dept}' differs from the item's department code '{department_code}'.")
    if category_text is not None:
        resolved = resolve_category(category_text)
        if resolved is None:
            reasons.append(f"Stored category '{category_text}' is not a v1.0 category name or code.")
        elif rule is not None and resolved.code != rule.code:
            reasons.append(f"Stored category '{category_text}' ({resolved.code}) differs from the code's category '{code_cat}'.")
    return reasons


def rules_payload() -> dict:
    """Static part of the rules endpoint response (no database identifiers)."""
    return {
        "standard": STANDARD_NAME,
        "version": STANDARD_VERSION,
        "code_format": "DEPT-CAT-###",
        "code_pattern": ITEM_CODE_PATTERN.pattern,
        "serial_min": MIN_SERIAL,
        "serial_max": MAX_SERIAL,
        "naming_formula": NAMING_FORMULA,
        "departments": [{"code": code, "name": name} for code, name in DEPARTMENTS.items()],
        "categories": [
            {
                "code": rule.code,
                "name": rule.name,
                "department_code": rule.department_code,
                "cost_head": rule.cost_head,
                "pattern": rule.pattern,
                "example": rule.example,
                "verbatim_description": rule.code in VERBATIM_DESCRIPTION_CATEGORIES,
            }
            for rule in CATEGORIES.values()
        ],
        "uoms": [{"code": code, "label": label, "meaning": UOM_MEANINGS[code]} for code, label in APPROVED_UOMS.items()],
        "uom_aliases": [{"alias": alias.title(), "maps_to": APPROVED_UOMS[target]} for alias, target in UOM_ALIASES.items()],
        "abbreviations": [{"abbreviation": abbr, "meaning": meaning} for abbr, meaning in ABBREVIATIONS.items()],
    }
