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


def normalize_heat_number(raw_heat_number: str) -> str:
    """
    Normalizes furnace heat reference identifier.
    Convention: '102603-3721' -> 'H-102603-3721'.
    Preserves existing 'H-' prefix if already present (e.g. 'h-102603-3721' -> 'H-102603-3721').
    Strips surrounding whitespace.
    Rejects malformed inputs.
    """
    if not raw_heat_number or not raw_heat_number.strip():
        raise ValueError("Heat number cannot be empty")
    cleaned = raw_heat_number.strip().upper()
    if cleaned.startswith("H-"):
        body = cleaned[2:].strip()
    elif cleaned.startswith("H"):
        body = cleaned[1:].lstrip("-").strip()
    else:
        body = cleaned
    
    if not body:
        raise ValueError(f"Invalid heat number body in '{raw_heat_number}'")
    
    # Must be valid alphanumeric with optional hyphen
    if not re.match(r"^[A-Z0-9]+(-[A-Z0-9]+)*$", body):
        raise ValueError(f"Malformed heat number format: '{raw_heat_number}'")
    
    return f"H-{body}"


def normalize_alias_key(text: str) -> str:
    """
    Normalizes material alias text for deterministic matching and dictionary lookup.
    Example: 'CRC Scrap-Low High MN' -> 'crc scrap low high mn'.
    Converts to lowercase, removes special punctuation, collapses whitespace.
    """
    if not text:
        return ""
    cleaned = text.strip().lower()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

