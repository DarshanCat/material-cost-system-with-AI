"""
Weighted-Average Costing & Inventory Valuation Service for VSPL.
Implements:
1. Deterministic weighted-average material unit rate reconstruction using business transaction dates.
2. Inventory valuation queries without ledger quantity mutation.
3. Induction furnace heat material costing (material-only scope, configured denominator).
4. Finished part material unit costing from unit cast weights.
5. Versioned, immutable Costing Run snapshots and run comparison.
Strictly uses Python Decimal and database NUMERIC types.
"""

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, desc, or_
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.ledger import StockLedgerEntry, MovementType
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.grn import GRNLineItem, GRNHeader
from app.models.heat import HeatHeader, HeatChargeLine, HeatPartsProduced, CastingClassification
from app.models.material_alias import MaterialAlias
from app.services.material_alias_service import resolve_material_by_description
from app.models.costing import (
    CostingRun,
    ItemCostSnapshot,
    ItemCostJournalEntry,
    HeatCostRecord,
    HeatCostLine,
    PartCostRecord,
    ItemOpeningValuation,
    DenominatorPolicy,
    CostScope,
    ValuationStatus,
    HeatCostStatus,
    PartCostStatus,
    CostingRunStatus,
)
from app.services.document_number_service import (
    DocumentType,
    generate_document_number,
    execute_with_document_number_retry,
)

RATE_PRECISION = Decimal("0.0001")
VALUE_PRECISION = Decimal("0.01")
COSTING_CUTOFF_DATE = date.fromisoformat(settings.COSTING_START_DATE)


def movement_sort_priority(movement_type: str, quantity_delta: Decimal) -> int:
    """
    Same-day deterministic tie-breaking order:
    1. OPENING_BALANCE
    2. INWARD_RECEIPT / INTERNAL_INWARD (deliveries received available to cost same-day issues)
    3. PHYSICAL_AUDIT_ADJUSTMENT (positive adjustment)
    4. OUTWARD_ISSUE / SCRAP_OUTWARD (outward movements costed at current average)
    5. PHYSICAL_AUDIT_ADJUSTMENT (negative adjustment)
    6. REVERSAL
    7. INTERNAL_RECOVERY
    8. Others
    """
    if movement_type == MovementType.OPENING_BALANCE.value:
        return 1
    elif movement_type in (MovementType.INWARD_RECEIPT.value, MovementType.INTERNAL_INWARD.value):
        return 2
    elif movement_type == MovementType.PHYSICAL_AUDIT_ADJUSTMENT.value and quantity_delta > 0:
        return 3
    elif movement_type in (MovementType.OUTWARD_ISSUE.value, MovementType.SCRAP_OUTWARD.value):
        return 4
    elif movement_type == MovementType.PHYSICAL_AUDIT_ADJUSTMENT.value and quantity_delta < 0:
        return 5
    elif movement_type == MovementType.REVERSAL.value:
        return 6
    elif movement_type == MovementType.INTERNAL_RECOVERY.value:
        return 7
    return 8


def generate_costing_run_number(db: Session, as_of: date) -> str:
    """Generates sequential serial: CRUN-YYYYMMDD-XXXX."""
    return generate_document_number(db, DocumentType.COSTING_RUN, as_of)


def reconstruct_item_rate_evolution(
    db: Session,
    material_item_id: int,
    as_of_date: Optional[date] = None,
) -> Tuple[Decimal, Optional[Decimal], str, Optional[str], List[Dict[str, Any]]]:
    """
    Reconstructs the weighted-average rate evolution for a material item from ledger movements.
    Returns:
    (current_quantity, weighted_average_rate, valuation_status, rate_source, journal_steps)
    """
    item = db.get(MaterialItem, material_item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material item ID {material_item_id} not found",
        )

    # 1. Fetch approved opening valuation if exists (latest approved version)
    approved_opening = db.execute(
        select(ItemOpeningValuation).where(
            ItemOpeningValuation.material_item_id == material_item_id,
            ItemOpeningValuation.status == "APPROVED",
        ).order_by(ItemOpeningValuation.version.desc())
    ).scalars().first()

    # 2. Fetch all ledger movements up to as_of_date
    query = select(StockLedgerEntry).where(StockLedgerEntry.material_item_id == material_item_id)
    if as_of_date:
        query = query.where(StockLedgerEntry.transaction_date <= as_of_date)

    raw_entries = db.execute(query).scalars().all()
    if not raw_entries:
        return Decimal("0.0000"), None, ValuationStatus.UNINITIALIZED.value, None, []

    # 3. Sort entries deterministically by (transaction_date, movement_sort_priority, id)
    entries = sorted(
        raw_entries,
        key=lambda e: (e.transaction_date, movement_sort_priority(e.movement_type, e.quantity_delta), e.id),
    )

    running_qty = Decimal("0.0000")
    running_avg_rate: Optional[Decimal] = None
    rate_source: Optional[str] = None
    has_unvalued_opening = False
    has_negative_stock = False
    has_missing_receipt_rate = False
    journal_steps: List[Dict[str, Any]] = []

    for entry in entries:
        m_type = entry.movement_type
        delta = entry.quantity_delta
        applied_rate: Optional[Decimal] = None
        receipt_rate: Optional[Decimal] = None
        extended_val: Optional[Decimal] = None
        step_status = "APPLIED"
        notes = entry.reason or ""

        if m_type == MovementType.OPENING_BALANCE.value:
            running_qty += delta
            if approved_opening and approved_opening.opening_rate_ex_gst is not None:
                running_avg_rate = approved_opening.opening_rate_ex_gst.quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
                rate_source = "APPROVED_OPENING_VALUATION"
                receipt_rate = running_avg_rate
                applied_rate = running_avg_rate
                extended_val = (delta * running_avg_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
                step_status = "OPENING_VALUED"
                notes = f"Opening balance valued via opening valuation v{approved_opening.version} (id={approved_opening.id})"
            else:
                has_unvalued_opening = True
                running_avg_rate = None
                step_status = "OPENING_VALUATION_MISSING"
                notes = "Opening balance established on 12-Oct-2026 without approved commercial rate"

        elif m_type == MovementType.INWARD_RECEIPT.value:
            # Look up GRNLineItem for rate_ex_gst
            grn_line = db.get(GRNLineItem, entry.source_line_id)
            if grn_line and grn_line.rate_ex_gst is not None and grn_line.rate_ex_gst > Decimal("0.00"):
                receipt_rate = grn_line.rate_ex_gst.quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
                applied_rate = receipt_rate
                extended_val = (delta * receipt_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
                
                if running_qty <= Decimal("0.0000"):
                    # Restart rate at receipt rate when prior stock was zero or negative
                    prior_neg = running_qty < Decimal("0.0000")
                    running_avg_rate = receipt_rate
                    running_qty += delta
                    rate_source = f"GRN_{entry.source_document_number}"
                    step_status = "NEGATIVE_STOCK_RESET" if prior_neg else "RECEIPT_RESTART"
                else:
                    # Positive prior stock: calculate new blended weighted average
                    if running_avg_rate is not None:
                        new_total_qty = running_qty + delta
                        new_total_val = (running_qty * running_avg_rate) + (delta * receipt_rate)
                        running_avg_rate = (new_total_val / new_total_qty).quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
                        running_qty = new_total_qty
                        rate_source = "WEIGHTED_AVERAGE"
                        step_status = "WEIGHTED_AVG_UPDATE"
                    else:
                        # Prior stock had missing rate; initialize rate to receipt rate
                        running_avg_rate = receipt_rate
                        running_qty += delta
                        rate_source = f"GRN_{entry.source_document_number}"
                        step_status = "FIRST_PRICED_RECEIPT"
            else:
                # Missing rate on receipt
                has_missing_receipt_rate = True
                running_qty += delta
                step_status = "MISSING_RECEIPT_RATE"
                notes = "External GRN receipt missing rate_ex_gst; cannot blend into weighted average"

        elif m_type == MovementType.INTERNAL_INWARD.value:
            # Internal receipt without commercial rate; policy pending
            running_qty += delta
            step_status = "INTERNAL_INWARD_POLICY_PENDING"
            notes = "Internal inward movement recorded with pending valuation policy"

        elif m_type in (MovementType.OUTWARD_ISSUE.value, MovementType.SCRAP_OUTWARD.value):
            # Consumes inventory at current running average rate
            applied_rate = running_avg_rate
            if running_avg_rate is not None:
                extended_val = (abs(delta) * running_avg_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
                step_status = "ISSUED_AT_AVERAGE_RATE"
            else:
                step_status = "UNVALUED_OUTWARD_MOVEMENT"
                notes = "Material issued without known applicable weighted-average rate"
            
            running_qty += delta  # delta is negative
            if running_qty < Decimal("0.0000"):
                has_negative_stock = True

        elif m_type == MovementType.PHYSICAL_AUDIT_ADJUSTMENT.value:
            applied_rate = running_avg_rate
            if running_avg_rate is not None:
                extended_val = (delta * running_avg_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
            running_qty += delta
            step_status = "AUDIT_ADJUSTMENT"

        elif m_type == MovementType.REVERSAL.value:
            # Reversal delta restores or cancels quantity
            applied_rate = running_avg_rate
            running_qty += delta
            step_status = "REVERSAL"

        elif m_type == MovementType.INTERNAL_RECOVERY.value:
            step_status = "INTERNAL_RECOVERY_POLICY_PENDING"
            notes = "Internal recovery scrap transfer logged with zero quantity delta (Rule C7)"

        else:
            running_qty += delta
            step_status = "UNRECOGNIZED_MOVEMENT"

        cumulative_val = (
            (running_qty * running_avg_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
            if (running_avg_rate is not None and running_qty >= Decimal("0.0000"))
            else None
        )

        journal_steps.append({
            "stock_ledger_entry_id": entry.id,
            "entry_number": entry.entry_number,
            "transaction_date": entry.transaction_date,
            "movement_type": m_type,
            "quantity_delta": delta,
            "running_quantity": running_qty,
            "receipt_rate": receipt_rate,
            "applied_rate": applied_rate,
            "resulting_average_rate": running_avg_rate,
            "movement_extended_value": extended_val,
            "cumulative_value": cumulative_val,
            "status": step_status,
            "notes": notes,
        })

    # 4. Resolve overall Valuation Status
    if running_qty == Decimal("0.0000"):
        val_status = ValuationStatus.ZERO_STOCK.value
    elif running_qty < Decimal("0.0000"):
        val_status = ValuationStatus.NEGATIVE_STOCK_FLAG.value
    else:  # running_qty > 0
        if running_avg_rate is not None:
            val_status = ValuationStatus.VALUED.value
        elif has_unvalued_opening:
            val_status = ValuationStatus.OPENING_VALUATION_MISSING.value
        elif has_missing_receipt_rate:
            val_status = ValuationStatus.INSUFFICIENT_COST_DATA.value
        else:
            val_status = ValuationStatus.UNVALUED_NO_RATE.value

    return running_qty, running_avg_rate, val_status, rate_source, journal_steps


def get_item_rate_as_of_date(
    db: Session,
    material_item_id: int,
    target_date: date,
) -> Optional[Decimal]:
    """
    Returns the effective weighted-average rate for an item as of target_date.
    Returns None if unvalued, uninitialized, or missing rates.
    """
    _, rate, val_status, _, _ = reconstruct_item_rate_evolution(db, material_item_id, target_date)
    if val_status in (ValuationStatus.VALUED.value, ValuationStatus.ZERO_STOCK.value, ValuationStatus.NEGATIVE_STOCK_FLAG.value):
        return rate
    return None


def calculate_heat_cost_detail(
    db: Session,
    heat: HeatHeader,
    item_rates_cache: Optional[Dict[int, Optional[Decimal]]] = None,
    denominator_policy: str = DenominatorPolicy.METAL_TAPPED.value,
) -> Dict[str, Any]:
    """
    Calculates material-only heat cost and cost per kg for a single heat record.
    Uses rates as of heat.heat_date.
    NOTE: NEVER mutates heat records, reconciliation outputs, or stock ledger entries.
    """
    if item_rates_cache is None:
        item_rates_cache = {}

    total_charged_qty = Decimal("0.0000")
    total_material_cost = Decimal("0.00")
    line_details: List[Dict[str, Any]] = []
    valued_count = 0
    unvalued_count = 0

    for line in heat.charge_lines:
        charged_qty = line.charged_quantity
        total_charged_qty += charged_qty
        
        # 1. Resolve material item
        mat_id = line.material_item_id
        if not mat_id and line.original_material_description:
            resolved_item = resolve_material_by_description(db, line.original_material_description)
            if resolved_item:
                mat_id = resolved_item.id

        if not mat_id:
            unvalued_count += 1
            line_details.append({
                "heat_charge_line_id": line.id,
                "line_number": line.line_number,
                "material_item_id": None,
                "raw_material_description": line.original_material_description,
                "charged_quantity": charged_qty,
                "applicable_rate": None,
                "line_cost": None,
                "rate_source": None,
                "is_included": False,
                "status": "UNMAPPED_ALIAS",
                "remarks": "Material description not mapped to canonical item",
            })
            continue

        # 2. Look up rate as of heat.heat_date
        if mat_id not in item_rates_cache:
            item_rates_cache[mat_id] = get_item_rate_as_of_date(db, mat_id, heat.heat_date)
            
        rate = item_rates_cache[mat_id]

        if rate is None:
            unvalued_count += 1
            line_details.append({
                "heat_charge_line_id": line.id,
                "line_number": line.line_number,
                "material_item_id": mat_id,
                "raw_material_description": line.original_material_description,
                "charged_quantity": charged_qty,
                "applicable_rate": None,
                "line_cost": None,
                "rate_source": None,
                "is_included": False,
                "status": "MISSING_RATE",
                "remarks": f"No approved weighted-average rate as of heat date {heat.heat_date}",
            })
            continue

        # 3. Calculate line cost
        line_cost = (charged_qty * rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
        total_material_cost += line_cost
        valued_count += 1

        line_details.append({
            "heat_charge_line_id": line.id,
            "line_number": line.line_number,
            "material_item_id": mat_id,
            "raw_material_description": line.original_material_description,
            "charged_quantity": charged_qty,
            "applicable_rate": rate,
            "line_cost": line_cost,
            "rate_source": f"WEIGHTED_AVG_{heat.heat_date}",
            "is_included": True,
            "status": "VALUED",
            "remarks": None,
        })

    # Overall heat costing status
    total_lines = len(heat.charge_lines)
    if total_lines == 0:
        heat_status = HeatCostStatus.INSUFFICIENT_COST_DATA.value
    elif valued_count == total_lines:
        heat_status = HeatCostStatus.COMPLETE.value
    elif valued_count > 0:
        heat_status = HeatCostStatus.PARTIAL_COST.value
    else:
        heat_status = HeatCostStatus.INSUFFICIENT_COST_DATA.value

    # Denominator & Cost per kg calculation
    cost_denominator_value: Optional[Decimal] = None
    cost_per_kg: Optional[Decimal] = None

    if denominator_policy == DenominatorPolicy.METAL_TAPPED.value:
        cost_denominator_value = heat.metal_tapped_weight
    elif denominator_policy == DenominatorPolicy.GOOD_CASTING_KG.value:
        # Sum of good castings weight
        good_wt = Decimal("0.0000")
        for p in heat.parts_produced:
            if p.classification == CastingClassification.GOOD.value and p.unit_cast_weight:
                good_wt += p.quantity_produced * p.unit_cast_weight
        cost_denominator_value = good_wt if good_wt > Decimal("0.0000") else None

    if cost_denominator_value and cost_denominator_value > Decimal("0.0000"):
        if total_material_cost > Decimal("0.00"):
            cost_per_kg = (total_material_cost / cost_denominator_value).quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
    else:
        # Denominator missing or zero
        if heat_status == HeatCostStatus.COMPLETE.value:
            heat_status = HeatCostStatus.DENOMINATOR_UNAVAILABLE.value

    return {
        "heat_id": heat.id,
        "heat_number": heat.heat_number,
        "heat_date": heat.heat_date,
        "total_charged_quantity": total_charged_qty,
        "total_material_cost": total_material_cost,
        "metal_tapped_weight": heat.metal_tapped_weight,
        "cost_denominator_value": cost_denominator_value,
        "denominator_type": denominator_policy,
        "cost_per_kg": cost_per_kg,
        "cost_scope": CostScope.MATERIAL_ONLY.value,
        "status": heat_status,
        "total_lines": total_lines,
        "valued_lines": valued_count,
        "unvalued_lines": unvalued_count,
        "lines": line_details,
    }


def calculate_part_cost_detail(
    part: HeatPartsProduced,
    heat_cost_per_kg: Optional[Decimal],
    heat_cost_status: str,
) -> Dict[str, Any]:
    """
    Calculates material-only cost per unit for a part produced.
    Formula: Unit Cast Weight * Heat Cost per kg.
    """
    unit_weight = part.unit_cast_weight
    qty = part.quantity_produced
    part_num = part.part_item.item_code if part.part_item else (part.source_row_reference or part.original_part_description)
    part_nm = part.part_item.name if part.part_item else part.original_part_description

    if unit_weight is None or unit_weight <= Decimal("0.0000"):
        return {
            "heat_parts_produced_id": part.id,
            "part_number": part_num,
            "part_name": part_nm,
            "part_item_id": part.part_item_id,
            "quantity_produced": qty,
            "unit_cast_weight": None,
            "weight_uom_id": part.weight_uom_id,
            "cost_per_kg": heat_cost_per_kg,
            "part_material_cost_per_unit": None,
            "total_part_material_cost": None,
            "cost_scope": CostScope.MATERIAL_ONLY.value,
            "status": PartCostStatus.MISSING_WEIGHT.value,
            "notes": "Unit cast weight not logged; cannot compute part material cost",
        }

    if heat_cost_per_kg is None or heat_cost_status != HeatCostStatus.COMPLETE.value:
        return {
            "heat_parts_produced_id": part.id,
            "part_number": part_num,
            "part_name": part_nm,
            "part_item_id": part.part_item_id,
            "quantity_produced": qty,
            "unit_cast_weight": unit_weight,
            "weight_uom_id": part.weight_uom_id,
            "cost_per_kg": heat_cost_per_kg,
            "part_material_cost_per_unit": None,
            "total_part_material_cost": None,
            "cost_scope": CostScope.MATERIAL_ONLY.value,
            "status": PartCostStatus.INSUFFICIENT_COST_DATA.value,
            "notes": f"Parent heat cost per kg unavailable or incomplete (Heat Status: {heat_cost_status})",
        }

    cost_per_unit = (unit_weight * heat_cost_per_kg).quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
    total_cost = (qty * cost_per_unit).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)

    return {
        "heat_parts_produced_id": part.id,
        "part_number": part_num,
        "part_name": part_nm,
        "part_item_id": part.part_item_id,
        "quantity_produced": qty,
        "unit_cast_weight": unit_weight,
        "weight_uom_id": part.weight_uom_id,
        "cost_per_kg": heat_cost_per_kg,
        "part_material_cost_per_unit": cost_per_unit,
        "total_part_material_cost": total_cost,
        "cost_scope": CostScope.MATERIAL_ONLY.value,
        "status": PartCostStatus.CALCULATED.value,
        "notes": "Provisional material-only unit cost based on unit cast weight",
    }


def execute_costing_run(
    db: Session,
    period_start: date,
    period_end: date,
    as_of_date: date,
    actor_id: str,
    denominator_policy: str = DenominatorPolicy.METAL_TAPPED.value,
    notes: Optional[str] = None,
) -> CostingRun:
    """
    Executes a complete, versioned, auditable Costing Run:
    1. Reconstructs weighted-average rates for all materials.
    2. Snapshots inventory quantities and extended values.
    3. Records step-by-step calculation journal entries.
    4. Calculates heat costs for all heats in period.
    5. Calculates part costs for all parts produced in period.
    6. Persists entire run under CostingRun without mutating stock ledger or heat sources.
    """
    def _create_run(run_num: str) -> CostingRun:
        run = CostingRun(
            run_number=run_num,
            calculation_version="v1.0.0",
            period_start=period_start,
            period_end=period_end,
            as_of_date=as_of_date,
            denominator_policy=denominator_policy,
            internal_recovery_policy="POLICY_PENDING",
            cost_scope=CostScope.MATERIAL_ONLY.value,
            status=CostingRunStatus.IN_PROGRESS.value,
            summary_notes=notes,
            created_by=actor_id,
        )
        db.add(run)
        return run

    costing_run = execute_with_document_number_retry(
        db=db,
        doc_type=DocumentType.COSTING_RUN,
        create_fn=_create_run,
        target_date=as_of_date,
    )

    # 1. Evaluate all active material items
    active_items = db.execute(select(MaterialItem).where(MaterialItem.is_active == True)).scalars().all()
    total_items = len(active_items)
    valued_items = 0
    unvalued_items = 0
    total_inv_val = Decimal("0.00")
    item_rates_cache: Dict[int, Optional[Decimal]] = {}

    for item in active_items:
        qty, avg_rate, val_status, rate_src, journal_steps = reconstruct_item_rate_evolution(
            db, item.id, as_of_date
        )
        item_rates_cache[item.id] = avg_rate

        ext_val: Optional[Decimal] = None
        if val_status == ValuationStatus.VALUED.value and avg_rate is not None:
            ext_val = (qty * avg_rate).quantize(VALUE_PRECISION, rounding=ROUND_HALF_UP)
            total_inv_val += ext_val
            valued_items += 1
        elif val_status == ValuationStatus.ZERO_STOCK.value:
            ext_val = Decimal("0.00")
            valued_items += 1
        else:
            unvalued_items += 1

        # Create ItemCostSnapshot
        snapshot = ItemCostSnapshot(
            costing_run_id=costing_run.id,
            material_item_id=item.id,
            as_of_date=as_of_date,
            inventory_quantity=qty,
            weighted_average_rate=avg_rate,
            extended_value=ext_val,
            valuation_status=val_status,
            uom_id=item.base_uom_id,
            rate_source=rate_src,
        )
        db.add(snapshot)

        # Create ItemCostJournalEntry records
        for step in journal_steps:
            j_entry = ItemCostJournalEntry(
                costing_run_id=costing_run.id,
                material_item_id=item.id,
                stock_ledger_entry_id=step["stock_ledger_entry_id"],
                transaction_date=step["transaction_date"],
                movement_type=step["movement_type"],
                quantity_delta=step["quantity_delta"],
                running_quantity=step["running_quantity"],
                receipt_rate=step["receipt_rate"],
                applied_rate=step["applied_rate"],
                resulting_average_rate=step["resulting_average_rate"],
                movement_extended_value=step["movement_extended_value"],
                cumulative_value=step["cumulative_value"],
                status=step["status"],
                notes=step["notes"],
            )
            db.add(j_entry)

    # 2. Evaluate heats in period
    heats_in_period = db.execute(
        select(HeatHeader).where(
            and_(
                HeatHeader.heat_date >= period_start,
                HeatHeader.heat_date <= period_end,
            )
        ).order_by(HeatHeader.heat_date, HeatHeader.id)
    ).scalars().all()

    total_heats = len(heats_in_period)
    completed_heats = 0
    partial_heats = 0
    total_heat_cost = Decimal("0.00")

    for heat in heats_in_period:
        heat_calc = calculate_heat_cost_detail(
            db, heat, item_rates_cache=item_rates_cache, denominator_policy=denominator_policy
        )
        total_heat_cost += heat_calc["total_material_cost"]

        if heat_calc["status"] == HeatCostStatus.COMPLETE.value:
            completed_heats += 1
        elif heat_calc["status"] == HeatCostStatus.PARTIAL_COST.value:
            partial_heats += 1

        heat_rec = HeatCostRecord(
            costing_run_id=costing_run.id,
            heat_id=heat.id,
            heat_number=heat.heat_number,
            heat_date=heat.heat_date,
            total_charged_quantity=heat_calc["total_charged_quantity"],
            total_material_cost=heat_calc["total_material_cost"],
            metal_tapped_weight=heat_calc["metal_tapped_weight"],
            cost_denominator_value=heat_calc["cost_denominator_value"],
            denominator_type=heat_calc["denominator_type"],
            cost_per_kg=heat_calc["cost_per_kg"],
            cost_scope=heat_calc["cost_scope"],
            status=heat_calc["status"],
            total_lines=heat_calc["total_lines"],
            valued_lines=heat_calc["valued_lines"],
            unvalued_lines=heat_calc["unvalued_lines"],
        )
        db.add(heat_rec)
        db.flush()

        for l_detail in heat_calc["lines"]:
            h_line = HeatCostLine(
                heat_cost_record_id=heat_rec.id,
                heat_charge_line_id=l_detail["heat_charge_line_id"],
                line_number=l_detail["line_number"],
                material_item_id=l_detail["material_item_id"],
                raw_material_description=l_detail["raw_material_description"],
                charged_quantity=l_detail["charged_quantity"],
                applicable_rate=l_detail["applicable_rate"],
                line_cost=l_detail["line_cost"],
                rate_source=l_detail["rate_source"],
                is_included=l_detail["is_included"],
                status=l_detail["status"],
                remarks=l_detail["remarks"],
            )
            db.add(h_line)

        # Part costs for heat
        for part in heat.parts_produced:
            part_calc = calculate_part_cost_detail(
                part, heat_calc["cost_per_kg"], heat_calc["status"]
            )
            p_rec = PartCostRecord(
                costing_run_id=costing_run.id,
                heat_cost_record_id=heat_rec.id,
                heat_parts_produced_id=part.id,
                part_number=part_calc["part_number"],
                part_name=part_calc["part_name"],
                part_item_id=part_calc["part_item_id"],
                quantity_produced=part_calc["quantity_produced"],
                unit_cast_weight=part_calc["unit_cast_weight"],
                weight_uom_id=part_calc["weight_uom_id"],
                cost_per_kg=part_calc["cost_per_kg"],
                part_material_cost_per_unit=part_calc["part_material_cost_per_unit"],
                total_part_material_cost=part_calc["total_part_material_cost"],
                cost_scope=part_calc["cost_scope"],
                status=part_calc["status"],
                notes=part_calc["notes"],
            )
            db.add(p_rec)

    # 3. Finalize run record
    costing_run.total_items_evaluated = total_items
    costing_run.valued_items_count = valued_items
    costing_run.unvalued_items_count = unvalued_items
    costing_run.total_inventory_valuation = total_inv_val
    costing_run.total_heats_evaluated = total_heats
    costing_run.completed_heats_count = completed_heats
    costing_run.partial_heats_count = partial_heats
    costing_run.total_heat_material_cost = total_heat_cost
    costing_run.status = CostingRunStatus.COMPLETED.value

    db.commit()
    db.refresh(costing_run)
    return costing_run


def compare_costing_runs(
    db: Session,
    run_id_1: int,
    run_id_2: int,
) -> Dict[str, Any]:
    """
    Compares two Costing Runs side-by-side to highlight variances in rates,
    inventory valuations, and heat production costs.
    """
    run1 = db.get(CostingRun, run_id_1)
    run2 = db.get(CostingRun, run_id_2)
    if not run1 or not run2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both costing run IDs not found for comparison",
        )

    # Compare summary metrics
    summary_diff = {
        "run_1_number": run1.run_number,
        "run_2_number": run2.run_number,
        "run_1_as_of": str(run1.as_of_date),
        "run_2_as_of": str(run2.as_of_date),
        "valuation_run_1": float(run1.total_inventory_valuation),
        "valuation_run_2": float(run2.total_inventory_valuation),
        "valuation_delta": float(run2.total_inventory_valuation - run1.total_inventory_valuation),
        "heat_cost_run_1": float(run1.total_heat_material_cost),
        "heat_cost_run_2": float(run2.total_heat_material_cost),
        "heat_cost_delta": float(run2.total_heat_material_cost - run1.total_heat_material_cost),
    }

    # Item rate differences
    r1_snaps = {s.material_item_id: s for s in run1.item_snapshots}
    r2_snaps = {s.material_item_id: s for s in run2.item_snapshots}
    all_item_ids = set(r1_snaps.keys()).union(set(r2_snaps.keys()))

    item_diffs: List[Dict[str, Any]] = []
    for m_id in sorted(all_item_ids):
        s1 = r1_snaps.get(m_id)
        s2 = r2_snaps.get(m_id)
        
        item = db.get(MaterialItem, m_id)
        item_code = item.item_code if item else f"ID {m_id}"
        item_name = item.name if item else "Unknown"

        r1_rate = float(s1.weighted_average_rate) if s1 and s1.weighted_average_rate is not None else None
        r2_rate = float(s2.weighted_average_rate) if s2 and s2.weighted_average_rate is not None else None
        
        r1_val = float(s1.extended_value) if s1 and s1.extended_value is not None else None
        r2_val = float(s2.extended_value) if s2 and s2.extended_value is not None else None

        rate_delta = None
        if r1_rate is not None and r2_rate is not None:
            rate_delta = round(r2_rate - r1_rate, 4)

        val_delta = None
        if r1_val is not None and r2_val is not None:
            val_delta = round(r2_val - r1_val, 2)

        if rate_delta != 0 or val_delta != 0:
            item_diffs.append({
                "material_item_id": m_id,
                "item_code": item_code,
                "item_name": item_name,
                "run_1_rate": r1_rate,
                "run_2_rate": r2_rate,
                "rate_delta": rate_delta,
                "run_1_value": r1_val,
                "run_2_value": r2_val,
                "value_delta": val_delta,
                "run_1_status": s1.valuation_status if s1 else None,
                "run_2_status": s2.valuation_status if s2 else None,
            })

    return {
        "summary": summary_diff,
        "item_differences": item_diffs,
    }
