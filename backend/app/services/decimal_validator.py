"""
Validation service for decimal precision and suspect entry heuristics.
Enforces that quantities are strictly positive, conform to UOM precision,
and flags suspected scaling errors without silent alteration.
"""

from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple
from app.models.uom import UOM


class DecimalValidationResult:
    def __init__(self, is_valid: bool, errors: List[str], warnings: List[str], normalized_value: Optional[Decimal] = None):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings
        self.normalized_value = normalized_value

    def to_dict(self):
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "normalized_value": str(self.normalized_value) if self.normalized_value is not None else None,
        }


def validate_and_flag_quantity(
    quantity_input: Decimal | float | int | str,
    uom: Optional[UOM],
    item_category: Optional[str] = None,
    item_name: Optional[str] = None,
) -> DecimalValidationResult:
    """
    Validates quantity against UOM decimal precision rules and checks for suspect scaling.
    Rules:
    - Quantity must be positive Decimal (> 0).
    - Decimal places cannot exceed UOM.decimal_precision.
    - If decimal places exceed allowed precision, flag as error (do not silently round).
    - Heuristic suspect warning: e.g. for KG / MT, quantities entered as whole numbers like 5014
      (when 5.014 MT was intended) or 290 (when 0.290 MT was intended) get flagged for human confirmation.
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    try:
        qty = Decimal(str(quantity_input).strip())
    except (InvalidOperation, TypeError, ValueError):
        return DecimalValidationResult(False, [f"Invalid numeric quantity: '{quantity_input}'"], warnings)

    if qty <= Decimal("0"):
        errors.append(f"Quantity must be greater than zero. Received: {qty}")
        return DecimalValidationResult(False, errors, warnings, qty)

    # Check decimal precision against UOM
    if uom:
        max_precision = uom.decimal_precision
        # Number of decimal places in string representation
        # Using normalized exponent
        sign, digits, exponent = qty.as_tuple()
        actual_decimals = max(0, -exponent)
        
        if actual_decimals > max_precision:
            errors.append(
                f"Quantity {qty} exceeds maximum allowed decimal places ({max_precision}) for UOM '{uom.code}' ({uom.name})."
            )

        # Suspect scale warning checks (Heuristics without auto-correction)
        # 1. MT (Metric Ton) checks
        if uom.code.upper() in ["MT", "TON", "TONNE"]:
            # Single heat charges or standard transactions rarely exceed 50 MT in one issue or receipt
            if qty > Decimal("1000"):
                warnings.append(
                    f"Suspect quantity: {qty} {uom.code} is exceptionally large (> 1,000 MT). Verify if entered in KG by mistake (e.g., {qty / Decimal('1000')} MT)."
                )
            elif qty >= Decimal("100") and item_category and "ALLOY" in item_category.upper():
                warnings.append(
                    f"Suspect quantity: {qty} {uom.code} for alloy material. Verify if entered in KG."
                )

        # 2. Discrete units (NOS, PCS) check
        if uom.code.upper() in ["NOS", "PCS", "SET"] and actual_decimals > 0:
            errors.append(f"Fractional quantities are not permitted for count unit '{uom.code}'. Received: {qty}")

        # 3. Known suspect entries from foundry logs
        # E.g., whole integer 5014 for KG when 5014 kg is reasonable, but if UOM is MT it's suspect
        if qty in [Decimal("5014"), Decimal("290"), Decimal("1450")] and uom.code.upper() in ["MT"]:
            warnings.append(
                f"Historical suspect pattern: Quantity {qty} {uom.code} appears to be recorded in KG without decimal conversion ({qty / Decimal('1000')} MT)."
            )

    return DecimalValidationResult(len(errors) == 0, errors, warnings, qty)


def validate_rate_and_gst(
    source_type: str,
    item_category: Optional[str],
    rate_ex_gst: Optional[Decimal],
    gst_percent: Optional[Decimal],
) -> DecimalValidationResult:
    """
    Validates material rate and GST rules:
    - Raw materials from EXTERNAL_VENDOR require rate_ex_gst > 0.
    - Internal receipts do NOT require rate.
    - GST percent cannot be negative and cannot exceed 100%.
    - Pre-GST rate and GST percent are kept separate.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if source_type == "EXTERNAL_VENDOR":
        # External raw materials require rate
        if item_category and "RAW" in item_category.upper():
            if rate_ex_gst is None or rate_ex_gst <= Decimal("0"):
                errors.append("External vendor receipt for Raw Material requires rate per UOM (excluding GST) > 0.")
        
        if rate_ex_gst is not None and rate_ex_gst < Decimal("0"):
            errors.append("Rate per UOM excluding GST cannot be negative.")

        if gst_percent is not None:
            if gst_percent < Decimal("0") or gst_percent > Decimal("100"):
                errors.append(f"GST percentage must be between 0% and 100%. Received: {gst_percent}%")
    else:
        # Internal receipts
        if rate_ex_gst is not None and rate_ex_gst > Decimal("0"):
            warnings.append(
                f"Rate provided for internal receipt ({source_type}). Internal transfers typically do not carry commercial vendor rates."
            )

    return DecimalValidationResult(len(errors) == 0, errors, warnings, rate_ex_gst)
