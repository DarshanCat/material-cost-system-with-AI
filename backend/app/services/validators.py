"""
Domain Validation Utilities for Master Data and Identifiers.
"""

import re
from typing import Optional

# Standard Indian GSTIN Regex: 15 alphanumeric characters
# Format: 2 digits (State code), 5 letters (PAN), 4 digits, 1 letter, 1 alphanumeric (entity code), 'Z', 1 checksum
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")

# Item Code Pattern: DEPT-CATEGORY-SERIAL (e.g. FDY-RM-016)
ITEM_CODE_REGEX = re.compile(r"^[A-Z0-9]{2,5}-[A-Z0-9]{2,5}-[0-9]{3,6}$")


def normalize_vendor_name(name: str) -> str:
    """
    Normalizes vendor name for duplicate detection and search indexing.
    Converts to lowercase, collapses multiple whitespaces, strips punctuation.
    Preserves original name for legal display and GST reporting.
    """
    if not name:
        return ""
    # Strip leading/trailing whitespace and lowercase
    cleaned = name.strip().lower()
    # Remove special punctuation like '.', ',', '-', '&'
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    # Collapse multiple whitespaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def validate_gstin_format(gstin: Optional[str]) -> bool:
    """
    Syntactically validates GSTIN format if provided.
    Does NOT claim external verification with the GST portal.
    """
    if not gstin:
        return True  # GSTIN is optional per VSPL business rules
    clean_gstin = gstin.strip().upper()
    return bool(GSTIN_REGEX.match(clean_gstin))


def get_category_code(category: str) -> str:
    """
    Maps category name to standard item code abbreviation.
    """
    mapping = {
        "RAW_MATERIAL": "RM",
        "RAW MATERIAL": "RM",
        "ALLOY": "FA",
        "FERRO_ALLOY": "FA",
        "FERRO ALLOY": "FA",
        "CONSUMABLE": "CON",
        "CONSUMABLES": "CON",
        "RETURN": "RET",
        "RETURNS": "RET",
        "BORING": "BOR",
        "BORINGS": "BOR",
        "GATING": "GAT",
        "GATINGS": "GAT",
        "MAINTENANCE": "MNT",
        "PACKING": "PKG",
    }
    cat_upper = category.strip().upper().replace("-", "_")
    return mapping.get(cat_upper, cat_upper[:3].replace(" ", ""))
