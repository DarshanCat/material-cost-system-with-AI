"""
Induction Furnace Heat Log Calculation Service.
Encapsulates canonical business calculations according to VSPL_Foundry_Heat_Log_TEMPLATE.xlsx.
Provides deterministic calculation of:
- Total Charge
- Melt Loss
- Melt Loss %
- Melting Recovery %
- Good Castings (sum of GOOD parts weight in kg)
- Casting Yield %
- RM per Good kg
- Material-wise % of Charge
- Physical RM Allocated (kg) per produced part
- Heat-level physical allocation reconciliation
- Anomaly flags and exception handling
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel


RATE_PRECISION = Decimal("0.0001")
PERCENT_PRECISION = Decimal("0.0001")
WEIGHT_PRECISION = Decimal("0.0001")
RATIO_PRECISION = Decimal("0.0001")
VALUE_PRECISION = Decimal("0.01")
RECONCILIATION_TOLERANCE = Decimal("0.0500")  # 50 grams tolerance for rounding across parts


class HeatKPIs(BaseModel):
    total_charge_kg: Decimal
    metal_tapped_kg: Optional[Decimal]
    melt_loss_kg: Optional[Decimal]
    melt_loss_pct: Optional[Decimal]
    melting_recovery_pct: Optional[Decimal]
    good_castings_kg: Optional[Decimal]
    casting_yield_pct: Optional[Decimal]
    rm_per_good_kg: Optional[Decimal]
    total_parts_count: int
    anomalies: List[str]

    # Mass-balance & Liquid Heel KPIs
    opening_liquid_heel_kg: Optional[Decimal] = None
    closing_liquid_heel_kg: Optional[Decimal] = None
    heel_status: str = "UNRECORDED"  # COMPLETE, INCOMPLETE_HEEL_DATA, UNRECORDED
    total_liquid_metal_available_kg: Optional[Decimal] = None
    total_metal_accounted_kg: Optional[Decimal] = None
    true_melt_loss_kg: Optional[Decimal] = None
    mass_balance_recovery_pct: Optional[Decimal] = None
    tapped_metal_recovery_pct: Optional[Decimal] = None


class ChargeLineCalculation(BaseModel):
    line_number: Optional[int] = None
    original_material_description: Optional[str] = None
    material_item_id: Optional[int] = None
    charged_quantity: Decimal
    percentage_of_charge: Optional[Decimal] = None
    status: str = "VALID"


class PartAllocationCalculation(BaseModel):
    line_number: Optional[int] = None
    original_part_description: Optional[str] = None
    part_item_id: Optional[int] = None
    quantity_produced: Decimal
    unit_cast_weight: Optional[Decimal] = None
    total_weight_kg: Optional[Decimal] = None
    rm_allocated_kg: Optional[Decimal] = None
    classification: str = "GOOD"
    allocation_status: str


class HeatReconciliation(BaseModel):
    total_heat_charge_kg: Decimal
    total_good_castings_kg: Optional[Decimal] = None
    total_allocated_rm_kg: Decimal
    allocation_variance_kg: Decimal
    reconciliation_status: str
    is_reconciled: bool
    discrepancy_reason: Optional[str] = None


class HeatCalculationResult(BaseModel):
    kpis: HeatKPIs
    charge_lines: List[ChargeLineCalculation]
    parts_allocated: List[PartAllocationCalculation]
    reconciliation: HeatReconciliation


class HeatCostingMeasures(BaseModel):
    """
    Authoritative Costing Measures for Induction Furnace Heats (Phase 2B-2B & Phase 2B-2C).
    Provides 3 distinct, non-conflicting metrics:
    - Measure A: Solid Material Charge Cost per kg
    - Measure B: Molten Metal Tapped Cost per kg (accounting for Liquid Heel)
    - Measure C: Raw Material Cost per kg of Good Casting
    """
    # Measure A: Solid Charge Cost
    total_charged_kg: Decimal
    total_charged_material_cost: Optional[Decimal] = None
    cost_per_kg_solid_charge: Optional[Decimal] = None
    measure_a_status: str = "VALUED"  # VALUED, PARTIAL_COST, MISSING_RATE, ZERO_CHARGE

    # Measure B: Tapped Metal Cost (accounting for liquid heel)
    opening_liquid_heel_kg: Optional[Decimal] = None
    opening_liquid_heel_value: Optional[Decimal] = None
    opening_liquid_heel_rate: Optional[Decimal] = None
    metal_tapped_kg: Optional[Decimal] = None
    closing_liquid_heel_kg: Optional[Decimal] = None
    closing_liquid_heel_value: Optional[Decimal] = None
    cost_per_kg_metal_tapped: Optional[Decimal] = None
    measure_b_status: str = "VALUED"  # VALUED, INCOMPLETE_HEEL_VALUATION, MISSING_TAPPED_WEIGHT, MISSING_CHARGE_COST, ZERO_LIQUID_OUTPUT

    # Measure C: Good Casting Cost
    good_castings_kg: Optional[Decimal] = None
    raw_material_cost_per_kg_good_casting: Optional[Decimal] = None
    measure_c_status: str = "VALUED"  # VALUED, ZERO_GOOD_CASTINGS, MISSING_INPUT_COST

    # Scrap Credit (FIN-DEC-03)
    approved_scrap_credit: Optional[Decimal] = None

    # Mass-Balance, Melting Loss & Recovery (FIN-DEC-04)
    total_liquid_metal_available_kg: Optional[Decimal] = None
    total_metal_accounted_kg: Optional[Decimal] = None
    true_melt_loss_kg: Optional[Decimal] = None
    true_melt_loss_pct: Optional[Decimal] = None
    mass_balance_recovery_pct: Optional[Decimal] = None
    tapped_metal_recovery_pct: Optional[Decimal] = None
    casting_yield_pct: Optional[Decimal] = None

    # Conversion Cost Separation (FIN-DEC-05)
    conversion_cost_status: str = "NOT_AVAILABLE"

    # Lineage & Historical Status (FIN-DEC-06)
    is_historical_exception: bool = False
    has_unverified_heel: bool = False
    is_charge_fully_backed_by_issues: bool = True
    costing_status: str = "COMPLETE"  # FINAL, PROVISIONAL, INCOMPLETE, PROVISIONAL_HISTORICAL, PENDING_REVIEW
    anomalies: List[str] = []


def calculate_material_charge_percentages(
    charge_lines: List[Dict[str, Any]],
    total_charge_kg: Optional[Decimal] = None,
) -> List[ChargeLineCalculation]:
    """
    Calculates material percentage for each charge line:
    Material % = (Charged Quantity / Total Heat Charge) * 100.
    Handles zero or missing charge safely.
    Preserves precision to 4 decimal places with ROUND_HALF_UP.
    """
    raw_qtys = [Decimal(str(l.get("charged_quantity") or 0)) for l in charge_lines]
    if total_charge_kg is None:
        total_charge_kg = sum(raw_qtys, Decimal("0.0000"))

    results: List[ChargeLineCalculation] = []
    for l in charge_lines:
        qty = Decimal(str(l.get("charged_quantity") or 0))
        pct: Optional[Decimal] = None
        if total_charge_kg > Decimal("0.0000"):
            pct = ((qty / total_charge_kg) * Decimal("100")).quantize(
                PERCENT_PRECISION, rounding=ROUND_HALF_UP
            )

        results.append(
            ChargeLineCalculation(
                line_number=l.get("line_number"),
                original_material_description=l.get("original_material_description"),
                material_item_id=l.get("material_item_id"),
                charged_quantity=qty.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP),
                percentage_of_charge=pct,
                status=l.get("validation_status") or "VALID",
            )
        )
    return results


def calculate_parts_rm_allocation(
    parts_produced: Optional[List[Dict[str, Any]]],
    total_charge_kg: Decimal,
    heat_good_castings_kg: Optional[Decimal] = None,
) -> Tuple[List[PartAllocationCalculation], HeatReconciliation]:
    """
    Calculates physical RM allocated (kg) per produced part:
    Part Total Weight = Quantity Cast * Unit Cast Weight.
    RM Allocated = (Part Total Weight / Total Good Casting Weight) * Total Heat Charge.

    Rules:
    - Denominator is strictly weight in kg, not part count.
    - Excludes REJECT, RUNNERS, GATING from raw material allocation.
    - Missing unit weight yields PENDING_UNIT_WEIGHT / MISSING_UNIT_WEIGHT.
    - Zero good casting weight yields safe non-calculable result.
    - Verifies complete reconciliation vs Total Charge.
    """
    if not parts_produced:
        reconciliation = HeatReconciliation(
            total_heat_charge_kg=total_charge_kg.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP),
            total_good_castings_kg=None,
            total_allocated_rm_kg=Decimal("0.0000"),
            allocation_variance_kg=total_charge_kg.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP),
            reconciliation_status="UNALLOCATED",
            is_reconciled=False,
            discrepancy_reason="No parts recorded for heat.",
        )
        return [], reconciliation

    # 1. Pre-scan parts
    has_missing_good_weight = False
    good_weights_sum = Decimal("0.0000")
    parsed_parts: List[Dict[str, Any]] = []

    for p in parts_produced:
        qty = Decimal(str(p.get("quantity_produced") or 0))
        classification = str(p.get("classification") or "GOOD").strip().upper()
        unit_wt_raw = p.get("unit_cast_weight")

        unit_wt: Optional[Decimal] = None
        total_wt: Optional[Decimal] = None

        if unit_wt_raw is not None and str(unit_wt_raw).strip() != "":
            unit_wt = Decimal(str(unit_wt_raw))
            if unit_wt > Decimal("0.0000"):
                total_wt = (qty * unit_wt).quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP)

        is_good = classification == "GOOD"
        if is_good:
            if total_wt is not None:
                good_weights_sum += total_wt
            else:
                has_missing_good_weight = True

        parsed_parts.append({
            "line_number": p.get("line_number"),
            "original_part_description": p.get("original_part_description"),
            "part_item_id": p.get("part_item_id"),
            "quantity_produced": qty,
            "unit_cast_weight": unit_wt,
            "total_weight_kg": total_wt,
            "classification": classification,
            "is_good": is_good,
        })

    # 2. Determine effective Good Castings denominator
    if heat_good_castings_kg is not None:
        effective_good_castings_kg = heat_good_castings_kg
    else:
        effective_good_castings_kg = good_weights_sum if good_weights_sum > Decimal("0.0000") else None

    # 3. Calculate individual allocations
    allocated_parts: List[PartAllocationCalculation] = []
    total_allocated_rm = Decimal("0.0000")

    for item in parsed_parts:
        qty = item["quantity_produced"]
        unit_wt = item["unit_cast_weight"]
        total_wt = item["total_weight_kg"]
        classification = item["classification"]
        is_good = item["is_good"]

        rm_allocated: Optional[Decimal] = None
        status: str

        if not is_good:
            # Rejects, runners, gating
            status = "CLASSIFICATION_EXCLUDED"
            rm_allocated = None
        elif unit_wt is None or unit_wt <= Decimal("0.0000"):
            status = "MISSING_UNIT_WEIGHT"
            rm_allocated = None
        elif total_charge_kg <= Decimal("0.0000"):
            status = "MISSING_OR_ZERO_CHARGE"
            rm_allocated = None
        elif effective_good_castings_kg is None or effective_good_castings_kg <= Decimal("0.0000"):
            status = "ZERO_GOOD_CASTING_WEIGHT"
            rm_allocated = None
        elif has_missing_good_weight and heat_good_castings_kg is None:
            # Denominator is incomplete; do not silently redistribute across partial parts
            status = "INCOMPLETE_ALLOCATION"
            rm_allocated = None
        else:
            # Eligible good part with valid denominator
            rm_allocated = (
                (total_wt / effective_good_castings_kg) * total_charge_kg
            ).quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP)
            total_allocated_rm += rm_allocated
            status = "ALLOCATED"

        allocated_parts.append(
            PartAllocationCalculation(
                line_number=item["line_number"],
                original_part_description=item["original_part_description"],
                part_item_id=item["part_item_id"],
                quantity_produced=qty,
                unit_cast_weight=unit_wt.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP) if unit_wt is not None else None,
                total_weight_kg=total_wt,
                rm_allocated_kg=rm_allocated,
                classification=classification,
                allocation_status=status,
            )
        )

    # 4. Determine reconciliation status and variance
    total_allocated_rm = total_allocated_rm.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP)
    variance = (total_charge_kg - total_allocated_rm).quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP)

    reconciliation_status: str
    is_reconciled: bool
    discrepancy_reason: Optional[str] = None

    if total_charge_kg <= Decimal("0.0000"):
        reconciliation_status = "MISSING_OR_ZERO_CHARGE"
        is_reconciled = False
        discrepancy_reason = "Total heat charge is missing or zero."
    elif effective_good_castings_kg is None or effective_good_castings_kg <= Decimal("0.0000"):
        reconciliation_status = "ZERO_GOOD_CASTING_WEIGHT"
        is_reconciled = False
        discrepancy_reason = "Total good casting weight is zero."
    elif has_missing_good_weight:
        reconciliation_status = "INCOMPLETE_ALLOCATION"
        is_reconciled = False
        discrepancy_reason = "One or more GOOD parts has missing unit cast weight."
    elif abs(variance) <= RECONCILIATION_TOLERANCE:
        reconciliation_status = "RECONCILED"
        is_reconciled = True
        discrepancy_reason = None
    else:
        reconciliation_status = "INCOMPLETE_ALLOCATION"
        is_reconciled = False
        discrepancy_reason = (
            f"Allocated RM ({total_allocated_rm} kg) does not reconcile to Total Charge ({total_charge_kg} kg). "
            f"Variance: {variance} kg."
        )

    reconciliation = HeatReconciliation(
        total_heat_charge_kg=total_charge_kg.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP),
        total_good_castings_kg=effective_good_castings_kg.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP) if effective_good_castings_kg is not None else None,
        total_allocated_rm_kg=total_allocated_rm,
        allocation_variance_kg=variance,
        reconciliation_status=reconciliation_status,
        is_reconciled=is_reconciled,
        discrepancy_reason=discrepancy_reason,
    )

    return allocated_parts, reconciliation


def calculate_heat_kpis(
    charge_quantities: List[Decimal],
    metal_tapped_weight: Optional[Decimal],
    parts_produced: Optional[List[Dict[str, Any]]] = None,
    opening_liquid_heel_kg: Optional[Decimal] = None,
    closing_liquid_heel_kg: Optional[Decimal] = None,
) -> HeatKPIs:
    """
    Computes all standard Heat Log KPIs following canonical Excel reference formulas
    and extended Induction Furnace Mass-Balance principles.
    Preserves negative melt loss (does NOT clamp).
    Explicitly flags physical anomalies without discarding values.
    """
    anomalies: List[str] = []

    # 1. Total Charge = SUM(all material charge quantities)
    total_charge = sum(charge_quantities, Decimal("0.0000"))
    if total_charge <= Decimal("0.0000"):
        anomalies.append("MISSING_OR_ZERO_CHARGE: Total charge weight must be strictly positive.")

    # 2. Metal Tapped
    tapped = metal_tapped_weight

    # 3. Simple Apparent Melt Loss = Total Charge - Metal Tapped
    melt_loss_kg: Optional[Decimal] = None
    melt_loss_pct: Optional[Decimal] = None
    melting_recovery_pct: Optional[Decimal] = None

    if tapped is not None:
        melt_loss_kg = total_charge - tapped

        if total_charge > Decimal("0.0000"):
            melt_loss_pct = ((melt_loss_kg / total_charge) * Decimal("100")).quantize(
                PERCENT_PRECISION, rounding=ROUND_HALF_UP
            )
            melting_recovery_pct = ((tapped / total_charge) * Decimal("100")).quantize(
                PERCENT_PRECISION, rounding=ROUND_HALF_UP
            )

        # Check anomalies
        if tapped > total_charge:
            anomalies.append(
                f"TAPPED_EXCEEDS_CHARGE: Metal tapped ({tapped} kg) exceeds total charge ({total_charge} kg). "
                "Possible scale miscalibration, unrecorded charge addition, or crucible heel carryover."
            )
        if melt_loss_kg < Decimal("0.0000"):
            anomalies.append(
                f"NEGATIVE_MELT_LOSS: Melt loss is negative ({melt_loss_kg} kg)."
            )

    # 4. Good Castings & Parts Count
    total_parts_count = 0
    good_castings_kg: Optional[Decimal] = None
    if parts_produced:
        good_wt = Decimal("0.0000")
        has_good_weight = False

        for p in parts_produced:
            qty = Decimal(str(p.get("quantity_produced") or 0))
            total_parts_count += int(qty)
            classification = str(p.get("classification") or "GOOD").upper()
            unit_wt_raw = p.get("unit_cast_weight")

            if classification == "GOOD" and unit_wt_raw is not None and str(unit_wt_raw).strip() != "":
                unit_wt = Decimal(str(unit_wt_raw))
                if unit_wt > Decimal("0.0000"):
                    good_wt += (qty * unit_wt)
                    has_good_weight = True

        if has_good_weight:
            good_castings_kg = good_wt.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP)

    # 5. Casting Yield % = (Good Castings / Total Charge) * 100
    casting_yield_pct: Optional[Decimal] = None
    if good_castings_kg is not None and total_charge > Decimal("0.0000"):
        casting_yield_pct = ((good_castings_kg / total_charge) * Decimal("100")).quantize(
            PERCENT_PRECISION, rounding=ROUND_HALF_UP
        )

    # 6. RM per Good kg = Total Charge / Good Castings
    rm_per_good_kg: Optional[Decimal] = None
    if good_castings_kg is not None and good_castings_kg > Decimal("0.0000"):
        rm_per_good_kg = (total_charge / good_castings_kg).quantize(
            RATIO_PRECISION, rounding=ROUND_HALF_UP
        )

    # 7. Check Good Castings vs Tapped
    if good_castings_kg is not None and tapped is not None:
        if good_castings_kg > tapped:
            anomalies.append(
                f"GOOD_CASTINGS_EXCEED_TAPPED: Good castings weight ({good_castings_kg} kg) "
                f"exceeds metal tapped ({tapped} kg). Physical yield impossibility."
            )

    # 8. Mass-Balance & Liquid Heel Calculations
    if opening_liquid_heel_kg is not None and opening_liquid_heel_kg < Decimal("0.0000"):
        anomalies.append(
            f"NEGATIVE_OPENING_HEEL: Opening liquid heel ({opening_liquid_heel_kg} kg) cannot be negative."
        )
    if closing_liquid_heel_kg is not None and closing_liquid_heel_kg < Decimal("0.0000"):
        anomalies.append(
            f"NEGATIVE_CLOSING_HEEL: Closing liquid heel ({closing_liquid_heel_kg} kg) cannot be negative."
        )

    heel_status = "UNRECORDED"
    if opening_liquid_heel_kg is not None and closing_liquid_heel_kg is not None:
        heel_status = "COMPLETE"
    elif opening_liquid_heel_kg is not None or closing_liquid_heel_kg is not None:
        heel_status = "INCOMPLETE_HEEL_DATA"
        anomalies.append(
            "INCOMPLETE_HEEL_DATA: Both opening and closing liquid heels are required for mass-balance verification."
        )

    total_liquid_metal_available_kg: Optional[Decimal] = None
    total_metal_accounted_kg: Optional[Decimal] = None
    true_melt_loss_kg: Optional[Decimal] = None
    mass_balance_recovery_pct: Optional[Decimal] = None
    tapped_metal_recovery_pct: Optional[Decimal] = None

    # Total Liquid Metal Available = total_solid_charge_kg + opening_liquid_heel_kg
    if opening_liquid_heel_kg is not None:
        total_liquid_metal_available_kg = (total_charge + opening_liquid_heel_kg).quantize(
            WEIGHT_PRECISION, rounding=ROUND_HALF_UP
        )
        if total_liquid_metal_available_kg <= Decimal("0.0000"):
            anomalies.append(
                "ZERO_TOTAL_AVAILABLE_METAL: Total liquid metal available is zero or negative."
            )

    # Total Metal Accounted = metal_tapped_kg + closing_liquid_heel_kg
    if tapped is not None and closing_liquid_heel_kg is not None:
        total_metal_accounted_kg = (tapped + closing_liquid_heel_kg).quantize(
            WEIGHT_PRECISION, rounding=ROUND_HALF_UP
        )

    # True Melt Loss = Total Liquid Metal Available - Total Metal Accounted
    if total_liquid_metal_available_kg is not None and total_metal_accounted_kg is not None:
        true_melt_loss_kg = (total_liquid_metal_available_kg - total_metal_accounted_kg).quantize(
            WEIGHT_PRECISION, rounding=ROUND_HALF_UP
        )
        if true_melt_loss_kg < Decimal("0.0000"):
            anomalies.append(
                f"NEGATIVE_TRUE_MELT_LOSS: True melt loss is negative ({true_melt_loss_kg} kg). "
                "Accounted metal exceeds total available liquid metal."
            )

        # Mass Balance Recovery % = (Total Metal Accounted / Total Liquid Metal Available) * 100
        if total_liquid_metal_available_kg > Decimal("0.0000"):
            mass_balance_recovery_pct = (
                (total_metal_accounted_kg / total_liquid_metal_available_kg) * Decimal("100")
            ).quantize(PERCENT_PRECISION, rounding=ROUND_HALF_UP)
            if mass_balance_recovery_pct > Decimal("100.0000"):
                anomalies.append(
                    f"MASS_BALANCE_RECOVERY_EXCEEDS_100: Mass balance recovery is {mass_balance_recovery_pct}%, "
                    "exceeding physical 100% threshold."
                )

    # Tapped Metal Recovery % = (Metal Tapped / Total Liquid Metal Available) * 100
    if tapped is not None and total_liquid_metal_available_kg is not None:
        if total_liquid_metal_available_kg > Decimal("0.0000"):
            tapped_metal_recovery_pct = (
                (tapped / total_liquid_metal_available_kg) * Decimal("100")
            ).quantize(PERCENT_PRECISION, rounding=ROUND_HALF_UP)
            if tapped_metal_recovery_pct > Decimal("100.0000"):
                anomalies.append(
                    f"TAPPED_RECOVERY_EXCEEDS_100: Tapped metal recovery is {tapped_metal_recovery_pct}%, "
                    "exceeding physical 100% threshold."
                )

    return HeatKPIs(
        total_charge_kg=total_charge.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP),
        metal_tapped_kg=tapped.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP) if tapped is not None else None,
        melt_loss_kg=melt_loss_kg.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP) if melt_loss_kg is not None else None,
        melt_loss_pct=melt_loss_pct,
        melting_recovery_pct=melting_recovery_pct,
        good_castings_kg=good_castings_kg,
        casting_yield_pct=casting_yield_pct,
        rm_per_good_kg=rm_per_good_kg,
        total_parts_count=total_parts_count,
        anomalies=anomalies,
        opening_liquid_heel_kg=opening_liquid_heel_kg.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP) if opening_liquid_heel_kg is not None else None,
        closing_liquid_heel_kg=closing_liquid_heel_kg.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP) if closing_liquid_heel_kg is not None else None,
        heel_status=heel_status,
        total_liquid_metal_available_kg=total_liquid_metal_available_kg,
        total_metal_accounted_kg=total_metal_accounted_kg,
        true_melt_loss_kg=true_melt_loss_kg,
        mass_balance_recovery_pct=mass_balance_recovery_pct,
        tapped_metal_recovery_pct=tapped_metal_recovery_pct,
    )


def calculate_heat_full_summary(
    charge_lines: List[Dict[str, Any]],
    metal_tapped_weight: Optional[Decimal],
    parts_produced: Optional[List[Dict[str, Any]]] = None,
    heat_good_castings_kg: Optional[Decimal] = None,
    opening_liquid_heel_kg: Optional[Decimal] = None,
    closing_liquid_heel_kg: Optional[Decimal] = None,
) -> HeatCalculationResult:
    """
    Computes full Heat Log calculations combining KPIs, line charge percentages,
    physical RM allocation across parts, and heat-level allocation reconciliation.
    """
    charge_qtys = [Decimal(str(l.get("charged_quantity") or 0)) for l in charge_lines]
    kpis = calculate_heat_kpis(
        charge_qtys,
        metal_tapped_weight,
        parts_produced,
        opening_liquid_heel_kg=opening_liquid_heel_kg,
        closing_liquid_heel_kg=closing_liquid_heel_kg,
    )
    charge_calcs = calculate_material_charge_percentages(charge_lines, kpis.total_charge_kg)
    parts_calcs, reconciliation = calculate_parts_rm_allocation(
        parts_produced, kpis.total_charge_kg, heat_good_castings_kg or kpis.good_castings_kg
    )

    return HeatCalculationResult(
        kpis=kpis,
        charge_lines=charge_calcs,
        parts_allocated=parts_calcs,
        reconciliation=reconciliation,
    )


def calculate_heat_costing_measures(
    total_charged_kg: Decimal,
    total_charged_material_cost: Optional[Decimal],
    metal_tapped_kg: Optional[Decimal],
    good_castings_kg: Optional[Decimal],
    opening_liquid_heel_kg: Optional[Decimal] = None,
    opening_liquid_heel_value: Optional[Decimal] = None,
    closing_liquid_heel_kg: Optional[Decimal] = None,
    has_unverified_heel: bool = False,
    is_charge_fully_backed_by_issues: bool = True,
    approved_scrap_credit: Optional[Decimal] = None,
    is_historical_exception: bool = False,
    normal_melt_loss_threshold_pct: Decimal = Decimal("3.5000"),
) -> HeatCostingMeasures:
    """
    Authoritative computation of the three standard foundry costing measures (Phase 2B-2B & Phase 2B-2C).
    Guarantees mass and financial value conservation across furnace cycles:
    Total Liquid Metal Accounted = Metal Tapped + Closing Liquid Heel
    Total Input Value = Opening Heel Value + Charged Material Cost
    Unit Molten Metal Rate = Total Input Value / Total Liquid Metal Accounted
    Closing Heel Value = Closing Heel Weight * Unit Molten Metal Rate
    Measure C Raw Material Cost = (Allocated Tapped Value - Approved Scrap Credit) / Good Castings Weight
    """
    anomalies: List[str] = []

    if not is_charge_fully_backed_by_issues:
        anomalies.append(
            "CHARGE_NOT_FULLY_BACKED_BY_STORES_ISSUES: Solid charge materials lack approved Stores Issue Slips."
        )

    if has_unverified_heel:
        anomalies.append(
            "UNVERIFIED_HEEL_VALUATION: Prior heat closing heel valuation is unverified or missing."
        )

    if is_historical_exception:
        anomalies.append(
            "HISTORICAL_EXCEPTION: Heat belongs to historical unverified campaign (Oct 2026). Costs are provisional."
        )

    # ---------------------------------------------------------
    # Measure A: Solid Material Charge Cost per kg
    # ---------------------------------------------------------
    cost_per_kg_solid_charge: Optional[Decimal] = None
    if total_charged_kg > Decimal("0.0000"):
        if total_charged_material_cost is not None:
            cost_per_kg_solid_charge = (
                total_charged_material_cost / total_charged_kg
            ).quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
            measure_a_status = "VALUED"
        else:
            measure_a_status = "MISSING_RATE"
    else:
        measure_a_status = "ZERO_CHARGE"

    # ---------------------------------------------------------
    # Measure B: Metal Tapped Cost per kg (accounting for heel)
    # ---------------------------------------------------------
    op_heel_kg = opening_liquid_heel_kg or Decimal("0.0000")
    cl_heel_kg = closing_liquid_heel_kg or Decimal("0.0000")
    tapped_kg = metal_tapped_kg or Decimal("0.0000")
    op_heel_val = opening_liquid_heel_value or Decimal("0.00")
    op_heel_rate = (
        (op_heel_val / op_heel_kg).quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
        if op_heel_kg > Decimal("0.0000")
        else None
    )

    liquid_accounted_kg = tapped_kg + cl_heel_kg
    cost_per_kg_metal_tapped: Optional[Decimal] = None
    closing_liquid_heel_value: Optional[Decimal] = None

    if has_unverified_heel:
        measure_b_status = "INCOMPLETE_HEEL_VALUATION"
    elif metal_tapped_kg is None or metal_tapped_kg <= Decimal("0.0000"):
        measure_b_status = "MISSING_TAPPED_WEIGHT"
    elif total_charged_material_cost is None:
        measure_b_status = "MISSING_CHARGE_COST"
    elif liquid_accounted_kg <= Decimal("0.0000"):
        measure_b_status = "ZERO_LIQUID_OUTPUT"
    else:
        # Conservation of value: Total input value allocated across total accounted liquid metal
        total_input_val = op_heel_val + total_charged_material_cost
        bath_rate = (total_input_val / liquid_accounted_kg).quantize(
            RATE_PRECISION, rounding=ROUND_HALF_UP
        )
        cost_per_kg_metal_tapped = bath_rate
        closing_liquid_heel_value = (cl_heel_kg * bath_rate).quantize(
            VALUE_PRECISION, rounding=ROUND_HALF_UP
        )
        measure_b_status = "VALUED"

    # ---------------------------------------------------------
    # Measure C: Raw Material Cost per kg of Good Casting
    # Accounts for approved return-scrap credit (FIN-DEC-03)
    # ---------------------------------------------------------
    cost_per_kg_good: Optional[Decimal] = None
    scrap_credit_val = approved_scrap_credit or Decimal("0.00")

    if good_castings_kg is not None and good_castings_kg > Decimal("0.0000"):
        if cost_per_kg_metal_tapped is not None and tapped_kg > Decimal("0.0000"):
            tapped_val = (tapped_kg * cost_per_kg_metal_tapped).quantize(
                VALUE_PRECISION, rounding=ROUND_HALF_UP
            )
            net_rm_cost = max(Decimal("0.00"), tapped_val - scrap_credit_val)
            cost_per_kg_good = (net_rm_cost / good_castings_kg).quantize(
                RATE_PRECISION, rounding=ROUND_HALF_UP
            )
            measure_c_status = "VALUED"
        elif total_charged_material_cost is not None:
            net_rm_cost = max(Decimal("0.00"), total_charged_material_cost - scrap_credit_val)
            cost_per_kg_good = (
                net_rm_cost / good_castings_kg
            ).quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
            measure_c_status = "VALUED"
        else:
            measure_c_status = "MISSING_INPUT_COST"
    else:
        measure_c_status = "ZERO_GOOD_CASTINGS"

    # ---------------------------------------------------------
    # Mass-Balance, Melting Loss & Recovery (FIN-DEC-04)
    # ---------------------------------------------------------
    total_liquid_metal_available_kg = (total_charged_kg + op_heel_kg).quantize(
        WEIGHT_PRECISION, rounding=ROUND_HALF_UP
    )
    total_metal_accounted_kg = (tapped_kg + cl_heel_kg).quantize(
        WEIGHT_PRECISION, rounding=ROUND_HALF_UP
    )
    true_melt_loss_kg = (total_liquid_metal_available_kg - total_metal_accounted_kg).quantize(
        WEIGHT_PRECISION, rounding=ROUND_HALF_UP
    )

    true_melt_loss_pct: Optional[Decimal] = None
    mass_balance_recovery_pct: Optional[Decimal] = None
    if total_liquid_metal_available_kg > Decimal("0.0000"):
        true_melt_loss_pct = (
            (true_melt_loss_kg / total_liquid_metal_available_kg) * Decimal("100.0000")
        ).quantize(PERCENT_PRECISION, rounding=ROUND_HALF_UP)
        mass_balance_recovery_pct = (
            (total_metal_accounted_kg / total_liquid_metal_available_kg) * Decimal("100.0000")
        ).quantize(PERCENT_PRECISION, rounding=ROUND_HALF_UP)

    tapped_metal_recovery_pct: Optional[Decimal] = None
    if total_charged_kg > Decimal("0.0000") and tapped_kg > Decimal("0.0000"):
        tapped_metal_recovery_pct = (
            (tapped_kg / total_charged_kg) * Decimal("100.0000")
        ).quantize(PERCENT_PRECISION, rounding=ROUND_HALF_UP)

    casting_yield_pct: Optional[Decimal] = None
    if tapped_kg > Decimal("0.0000") and good_castings_kg is not None:
        casting_yield_pct = (
            (good_castings_kg / tapped_kg) * Decimal("100.0000")
        ).quantize(PERCENT_PRECISION, rounding=ROUND_HALF_UP)

    # FIN-DEC-04 Melt loss anomaly check
    if true_melt_loss_pct is not None:
        if true_melt_loss_pct > normal_melt_loss_threshold_pct:
            anomalies.append(
                f"EXCESSIVE_MELT_LOSS: Melting loss of {true_melt_loss_pct:.2f}% exceeds normal threshold of {normal_melt_loss_threshold_pct:.2f}%. Investigation required."
            )
        elif true_melt_loss_pct < Decimal("0.0000"):
            anomalies.append(
                f"NEGATIVE_MELT_LOSS: Accounted metal ({total_metal_accounted_kg:.1f} kg) exceeds available liquid metal ({total_liquid_metal_available_kg:.1f} kg). Unrecorded heel or scale error."
            )

    # ---------------------------------------------------------
    # Overall Costing Status (FIN-DEC-06)
    # ---------------------------------------------------------
    if is_historical_exception:
        costing_status = "PROVISIONAL_HISTORICAL"
    elif (
        measure_a_status == "VALUED"
        and measure_b_status == "VALUED"
        and measure_c_status in ("VALUED", "ZERO_GOOD_CASTINGS")
    ):
        if not is_charge_fully_backed_by_issues:
            costing_status = "PROVISIONAL"
        else:
            costing_status = "FINAL"
    elif measure_b_status == "INCOMPLETE_HEEL_VALUATION" or has_unverified_heel:
        costing_status = "INCOMPLETE"
    elif measure_a_status != "VALUED" or measure_b_status != "VALUED":
        costing_status = "INCOMPLETE"
    else:
        costing_status = "PROVISIONAL"

    return HeatCostingMeasures(
        total_charged_kg=total_charged_kg.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP),
        total_charged_material_cost=total_charged_material_cost.quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP) if total_charged_material_cost is not None else None,
        cost_per_kg_solid_charge=cost_per_kg_solid_charge,
        measure_a_status=measure_a_status,
        opening_liquid_heel_kg=opening_liquid_heel_kg.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP) if opening_liquid_heel_kg is not None else None,
        opening_liquid_heel_value=opening_liquid_heel_value.quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP) if opening_liquid_heel_value is not None else None,
        opening_liquid_heel_rate=op_heel_rate,
        metal_tapped_kg=metal_tapped_kg.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP) if metal_tapped_kg is not None else None,
        closing_liquid_heel_kg=closing_liquid_heel_kg.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP) if closing_liquid_heel_kg is not None else None,
        closing_liquid_heel_value=closing_liquid_heel_value,
        cost_per_kg_metal_tapped=cost_per_kg_metal_tapped,
        measure_b_status=measure_b_status,
        good_castings_kg=good_castings_kg.quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP) if good_castings_kg is not None else None,
        raw_material_cost_per_kg_good_casting=cost_per_kg_good,
        measure_c_status=measure_c_status,
        approved_scrap_credit=approved_scrap_credit.quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP) if approved_scrap_credit is not None else None,
        total_liquid_metal_available_kg=total_liquid_metal_available_kg,
        total_metal_accounted_kg=total_metal_accounted_kg,
        true_melt_loss_kg=true_melt_loss_kg,
        true_melt_loss_pct=true_melt_loss_pct,
        mass_balance_recovery_pct=mass_balance_recovery_pct,
        tapped_metal_recovery_pct=tapped_metal_recovery_pct,
        casting_yield_pct=casting_yield_pct,
        conversion_cost_status="NOT_AVAILABLE",
        is_historical_exception=is_historical_exception,
        has_unverified_heel=has_unverified_heel,
        is_charge_fully_backed_by_issues=is_charge_fully_backed_by_issues,
        costing_status=costing_status,
        anomalies=anomalies,
    )
