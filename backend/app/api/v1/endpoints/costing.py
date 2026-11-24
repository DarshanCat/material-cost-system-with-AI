"""
FastAPI REST Endpoints for Phase 6 Costing, Inventory Valuation, and Financial Runs.
Strictly separates costing calculations from stock ledger quantity mutations.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc, func

from app.db.session import get_db
from app.core.security import (
    require_permission,
    get_current_user_id,
    get_current_user_role,
    Permission,
    UserRole,
)
from app.models.item import MaterialItem
from app.models.department import Department
from app.models.heat import HeatHeader
from app.models.costing import (
    CostingRun,
    ItemCostSnapshot,
    HeatCostRecord,
    PartCostRecord,
    ItemOpeningValuation,
    ValuationStatus,
    DenominatorPolicy,
    CostingRunStatus,
)
from app.schemas.costing import (
    ItemValuationResponse,
    InventoryValuationReport,
    ItemRateHistoryResponse,
    ItemCostJournalStep,
    HeatCostResponse,
    HeatCostLineResponse,
    PartCostResponse,
    CostingRunTriggerRequest,
    CostingRunSummaryResponse,
    CostingRunDetailResponse,
    CostingRunComparisonResponse,
    ItemOpeningValuationCreate,
    ItemOpeningValuationResponse,
    OpeningValuationAuditLogResponse,
    OpeningValuationActionRequest,
    OpeningValuationRejectRequest,
)
from app.services.opening_valuation_service import (
    propose_opening_valuation as svc_propose_opening_valuation,
    approve_opening_valuation as svc_approve_opening_valuation,
    reject_opening_valuation as svc_reject_opening_valuation,
    list_opening_valuations as svc_list_opening_valuations,
    get_opening_valuation_by_id as svc_get_opening_valuation_by_id,
)
from app.services.costing_service import (
    reconstruct_item_rate_evolution,
    calculate_heat_cost_detail,
    calculate_part_cost_detail,
    execute_costing_run,
    compare_costing_runs,
    RATE_PRECISION,
    VALUE_PRECISION,
)

router = APIRouter(prefix="/costing", tags=["Costing & Valuation"])


# --- Inventory Valuation Endpoints ---

@router.get(
    "/valuation/items/{material_item_id}",
    response_model=ItemValuationResponse,
    dependencies=[Depends(require_permission(Permission.COSTING_READ))],
)
def get_item_valuation(
    material_item_id: int = Path(..., description="Internal Material Item ID"),
    as_of: Optional[date] = Query(None, description="Valuation cutoff date (defaults to today)"),
    db: Session = Depends(get_db),
):
    """Retrieves single-item inventory balance, weighted-average rate, and extended value."""
    as_of_date = as_of or date.today()
    item = db.get(MaterialItem, material_item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material item ID {material_item_id} not found",
        )

    qty, rate, val_status, rate_src, _ = reconstruct_item_rate_evolution(db, material_item_id, as_of_date)
    ext_val = None
    if val_status == ValuationStatus.VALUED.value and rate is not None:
        ext_val = (qty * rate).quantize(VALUE_PRECISION)
    elif val_status == ValuationStatus.ZERO_STOCK.value:
        ext_val = Decimal("0.00")

    return ItemValuationResponse(
        material_item_id=item.id,
        item_code=item.item_code,
        item_name=item.name,
        department_name=item.department.name if item.department else None,
        category=item.category,
        inventory_quantity=qty,
        uom_code=item.base_uom.code if item.base_uom else "UOM",
        weighted_average_rate=rate,
        extended_value=ext_val,
        as_of_date=as_of_date,
        valuation_status=val_status,
        rate_source=rate_src,
        anomaly_notes="Stock baseline uninitialized" if val_status == ValuationStatus.UNINITIALIZED.value else None,
    )


@router.get(
    "/valuation/current",
    response_model=InventoryValuationReport,
    dependencies=[Depends(require_permission(Permission.COSTING_READ))],
)
def get_current_inventory_valuation(
    department_id: Optional[int] = Query(None, description="Filter by Department ID"),
    category: Optional[str] = Query(None, description="Filter by Category"),
    db: Session = Depends(get_db),
):
    """Generates real-time inventory valuation report as of today."""
    return _generate_valuation_report(db, date.today(), department_id, category)


@router.get(
    "/valuation/historical",
    response_model=InventoryValuationReport,
    dependencies=[Depends(require_permission(Permission.COSTING_READ))],
)
def get_historical_inventory_valuation(
    as_of_date: date = Query(..., description="Historical cutoff date"),
    department_id: Optional[int] = Query(None, description="Filter by Department ID"),
    category: Optional[str] = Query(None, description="Filter by Category"),
    db: Session = Depends(get_db),
):
    """Generates point-in-time historical inventory valuation report as of specified business date."""
    return _generate_valuation_report(db, as_of_date, department_id, category)


def _generate_valuation_report(
    db: Session,
    as_of_date: date,
    department_id: Optional[int] = None,
    category: Optional[str] = None,
) -> InventoryValuationReport:
    query = select(MaterialItem).where(MaterialItem.is_active == True)
    if department_id:
        query = query.where(MaterialItem.department_id == department_id)
    if category:
        # Same case-insensitive category match as GET /api/v1/items.
        query = query.where(func.lower(MaterialItem.category) == category.lower())

    items = db.execute(query.order_by(MaterialItem.item_code)).scalars().all()

    report_items: List[ItemValuationResponse] = []
    total_val = Decimal("0.00")
    valued_cnt = 0
    unvalued_cnt = 0
    zero_stock_cnt = 0
    neg_stock_cnt = 0

    for item in items:
        qty, rate, val_status, rate_src, _ = reconstruct_item_rate_evolution(db, item.id, as_of_date)
        ext_val = None
        if val_status == ValuationStatus.VALUED.value and rate is not None:
            ext_val = (qty * rate).quantize(VALUE_PRECISION)
            total_val += ext_val
            valued_cnt += 1
        elif val_status == ValuationStatus.ZERO_STOCK.value:
            ext_val = Decimal("0.00")
            zero_stock_cnt += 1
            valued_cnt += 1
        elif val_status == ValuationStatus.NEGATIVE_STOCK_FLAG.value:
            neg_stock_cnt += 1
            unvalued_cnt += 1
        else:
            unvalued_cnt += 1

        report_items.append(
            ItemValuationResponse(
                material_item_id=item.id,
                item_code=item.item_code,
                item_name=item.name,
                department_name=item.department.name if item.department else None,
                category=item.category,
                inventory_quantity=qty,
                uom_code=item.base_uom.code if item.base_uom else "UOM",
                weighted_average_rate=rate,
                extended_value=ext_val,
                as_of_date=as_of_date,
                valuation_status=val_status,
                rate_source=rate_src,
            )
        )

    return InventoryValuationReport(
        as_of_date=as_of_date,
        total_items=len(report_items),
        valued_items_count=valued_cnt,
        unvalued_items_count=unvalued_cnt,
        zero_stock_items_count=zero_stock_cnt,
        negative_stock_items_count=neg_stock_cnt,
        total_inventory_valuation=total_val,
        items=report_items,
    )


# --- Rate History & Reconstruction Journal ---

@router.get(
    "/rates/history/{material_item_id}",
    response_model=ItemRateHistoryResponse,
    dependencies=[Depends(require_permission(Permission.COSTING_READ))],
)
def get_item_rate_history(
    material_item_id: int = Path(..., description="Internal Material Item ID"),
    as_of: Optional[date] = Query(None, description="Cutoff date"),
    db: Session = Depends(get_db),
):
    """Returns step-by-step calculation journal tracking weighted-average rate evolution."""
    as_of_date = as_of or date.today()
    item = db.get(MaterialItem, material_item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material item ID {material_item_id} not found",
        )

    qty, rate, val_status, rate_src, journal_steps = reconstruct_item_rate_evolution(
        db, material_item_id, as_of_date
    )

    steps_res = [
        ItemCostJournalStep(
            stock_ledger_entry_id=s["stock_ledger_entry_id"],
            entry_number=s["entry_number"],
            transaction_date=s["transaction_date"],
            movement_type=s["movement_type"],
            quantity_delta=s["quantity_delta"],
            running_quantity=s["running_quantity"],
            receipt_rate=s["receipt_rate"],
            applied_rate=s["applied_rate"],
            resulting_average_rate=s["resulting_average_rate"],
            movement_extended_value=s["movement_extended_value"],
            cumulative_value=s["cumulative_value"],
            status=s["status"],
            notes=s["notes"],
        )
        for s in journal_steps
    ]

    return ItemRateHistoryResponse(
        material_item_id=item.id,
        item_code=item.item_code,
        item_name=item.name,
        uom_code=item.base_uom.code if item.base_uom else "UOM",
        current_quantity=qty,
        weighted_average_rate=rate,
        valuation_status=val_status,
        rate_source=rate_src,
        steps=steps_res,
    )


@router.get(
    "/exceptions",
    dependencies=[Depends(require_permission(Permission.COSTING_READ))],
)
def get_costing_exceptions(
    as_of: Optional[date] = Query(None, description="Cutoff date"),
    db: Session = Depends(get_db),
):
    """Exposes missing rates, unvalued stock, and negative stock exception queues."""
    as_of_date = as_of or date.today()
    items = db.execute(select(MaterialItem).where(MaterialItem.is_active == True)).scalars().all()

    missing_opening_val: List[Dict[str, Any]] = []
    unvalued_stock_items: List[Dict[str, Any]] = []
    negative_stock_items: List[Dict[str, Any]] = []

    for item in items:
        qty, rate, val_status, _, _ = reconstruct_item_rate_evolution(db, item.id, as_of_date)
        if val_status == ValuationStatus.OPENING_VALUATION_MISSING.value:
            missing_opening_val.append({
                "material_item_id": item.id,
                "item_code": item.item_code,
                "item_name": item.name,
                "quantity": float(qty),
                "uom": item.base_uom.code if item.base_uom else "UOM",
                "issue": "Opening balance established on 12-Oct-2026 without approved commercial rate",
            })
        elif val_status == ValuationStatus.UNVALUED_NO_RATE.value:
            unvalued_stock_items.append({
                "material_item_id": item.id,
                "item_code": item.item_code,
                "item_name": item.name,
                "quantity": float(qty),
                "uom": item.base_uom.code if item.base_uom else "UOM",
                "issue": "Material in stock without any approved priced receipts",
            })
        elif val_status == ValuationStatus.NEGATIVE_STOCK_FLAG.value:
            negative_stock_items.append({
                "material_item_id": item.id,
                "item_code": item.item_code,
                "item_name": item.name,
                "quantity": float(qty),
                "uom": item.base_uom.code if item.base_uom else "UOM",
                "issue": "Negative inventory balance detected; violates VSPL inventory policy",
            })

    return {
        "as_of_date": str(as_of_date),
        "total_exceptions": len(missing_opening_val) + len(unvalued_stock_items) + len(negative_stock_items),
        "missing_opening_valuation": missing_opening_val,
        "unvalued_stock": unvalued_stock_items,
        "negative_stock": negative_stock_items,
    }


# --- Heat Costing Endpoints ---

def _canonical_item_labels(db: Session, material_item_id: Optional[int]) -> Dict[str, Optional[str]]:
    """Mapped canonical item code/name for a heat charge line (None when the line is unmapped)."""
    item = db.get(MaterialItem, material_item_id) if material_item_id else None
    return {
        "canonical_item_code": item.item_code if item else None,
        "canonical_item_name": item.name if item else None,
    }


@router.get(
    "/heats",
    response_model=List[HeatCostResponse],
    dependencies=[Depends(require_permission(Permission.COSTING_READ))],
)
def list_heat_costs(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    denominator_policy: str = Query("METAL_TAPPED"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Calculates material-only heat costs for heats in date range."""
    query = select(HeatHeader)
    if start_date:
        query = query.where(HeatHeader.heat_date >= start_date)
    if end_date:
        query = query.where(HeatHeader.heat_date <= end_date)

    heats = db.execute(query.order_by(desc(HeatHeader.heat_date), desc(HeatHeader.id)).limit(limit)).scalars().all()
    results: List[HeatCostResponse] = []
    item_rates_cache: Dict[int, Optional[Decimal]] = {}

    for heat in heats:
        detail = calculate_heat_cost_detail(
            db, heat, item_rates_cache=item_rates_cache, denominator_policy=denominator_policy
        )
        lines_res = [
            HeatCostLineResponse(
                heat_charge_line_id=l["heat_charge_line_id"],
                line_number=l["line_number"],
                material_item_id=l["material_item_id"],
                raw_material_description=l["raw_material_description"],
                charged_quantity=l["charged_quantity"],
                applicable_rate=l["applicable_rate"],
                line_cost=l["line_cost"],
                rate_source=l["rate_source"],
                is_included=l["is_included"],
                status=l["status"],
                remarks=l["remarks"],
                **_canonical_item_labels(db, l["material_item_id"]),
            )
            for l in detail["lines"]
        ]
        results.append(
            HeatCostResponse(
                heat_id=detail["heat_id"],
                heat_number=detail["heat_number"],
                heat_date=detail["heat_date"],
                furnace_id=heat.furnace_id,
                total_charged_quantity=detail["total_charged_quantity"],
                total_material_cost=detail["total_material_cost"],
                metal_tapped_weight=detail["metal_tapped_weight"],
                cost_denominator_value=detail["cost_denominator_value"],
                denominator_type=detail["denominator_type"],
                cost_per_kg=detail["cost_per_kg"],
                cost_scope=detail["cost_scope"],
                status=detail["status"],
                total_lines=detail["total_lines"],
                valued_lines=detail["valued_lines"],
                unvalued_lines=detail["unvalued_lines"],
                lines=lines_res,
                measure_a_cost_per_kg=detail.get("measure_a_cost_per_kg"),
                measure_a_status=detail.get("measure_a_status"),
                measure_b_cost_per_kg=detail.get("measure_b_cost_per_kg"),
                measure_b_status=detail.get("measure_b_status"),
                measure_c_cost_per_kg=detail.get("measure_c_cost_per_kg"),
                measure_c_status=detail.get("measure_c_status"),
                opening_liquid_heel_kg=detail.get("opening_liquid_heel_kg"),
                opening_liquid_heel_value=detail.get("opening_liquid_heel_value"),
                closing_liquid_heel_kg=detail.get("closing_liquid_heel_kg"),
                closing_liquid_heel_value=detail.get("closing_liquid_heel_value"),
                approved_scrap_credit=detail.get("approved_scrap_credit"),
                true_melt_loss_kg=detail.get("true_melt_loss_kg"),
                true_melt_loss_pct=detail.get("true_melt_loss_pct"),
                melting_recovery_pct=detail.get("melting_recovery_pct"),
                casting_yield_pct=detail.get("casting_yield_pct"),
                conversion_cost_status=detail.get("conversion_cost_status", "NOT_AVAILABLE"),
                is_historical_exception=detail.get("is_historical_exception", False),
                anomalies=detail.get("anomalies", []),
            )
        )
    return results


@router.get(
    "/heats/{heat_id}",
    response_model=HeatCostResponse,
    dependencies=[Depends(require_permission(Permission.COSTING_READ))],
)
def get_heat_cost_detail_endpoint(
    heat_id: int = Path(...),
    denominator_policy: str = Query("METAL_TAPPED"),
    db: Session = Depends(get_db),
):
    """Returns line-by-line charge breakdown and cost per kg for a single heat."""
    heat = db.get(HeatHeader, heat_id)
    if not heat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Heat ID {heat_id} not found",
        )

    detail = calculate_heat_cost_detail(db, heat, denominator_policy=denominator_policy)
    lines_res = [
        HeatCostLineResponse(
            heat_charge_line_id=l["heat_charge_line_id"],
            line_number=l["line_number"],
            material_item_id=l["material_item_id"],
            raw_material_description=l["raw_material_description"],
            charged_quantity=l["charged_quantity"],
            applicable_rate=l["applicable_rate"],
            line_cost=l["line_cost"],
            rate_source=l["rate_source"],
            is_included=l["is_included"],
            status=l["status"],
            remarks=l["remarks"],
            **_canonical_item_labels(db, l["material_item_id"]),
        )
        for l in detail["lines"]
    ]
    return HeatCostResponse(
        heat_id=detail["heat_id"],
        heat_number=detail["heat_number"],
        heat_date=detail["heat_date"],
        furnace_id=heat.furnace_id,
        total_charged_quantity=detail["total_charged_quantity"],
        total_material_cost=detail["total_material_cost"],
        metal_tapped_weight=detail["metal_tapped_weight"],
        cost_denominator_value=detail["cost_denominator_value"],
        denominator_type=detail["denominator_type"],
        cost_per_kg=detail["cost_per_kg"],
        cost_scope=detail["cost_scope"],
        status=detail["status"],
        total_lines=detail["total_lines"],
        valued_lines=detail["valued_lines"],
        unvalued_lines=detail["unvalued_lines"],
        lines=lines_res,
        measure_a_cost_per_kg=detail.get("measure_a_cost_per_kg"),
        measure_a_status=detail.get("measure_a_status"),
        measure_b_cost_per_kg=detail.get("measure_b_cost_per_kg"),
        measure_b_status=detail.get("measure_b_status"),
        measure_c_cost_per_kg=detail.get("measure_c_cost_per_kg"),
        measure_c_status=detail.get("measure_c_status"),
        opening_liquid_heel_kg=detail.get("opening_liquid_heel_kg"),
        opening_liquid_heel_value=detail.get("opening_liquid_heel_value"),
        closing_liquid_heel_kg=detail.get("closing_liquid_heel_kg"),
        closing_liquid_heel_value=detail.get("closing_liquid_heel_value"),
        approved_scrap_credit=detail.get("approved_scrap_credit"),
        true_melt_loss_kg=detail.get("true_melt_loss_kg"),
        true_melt_loss_pct=detail.get("true_melt_loss_pct"),
        melting_recovery_pct=detail.get("melting_recovery_pct"),
        casting_yield_pct=detail.get("casting_yield_pct"),
        conversion_cost_status=detail.get("conversion_cost_status", "NOT_AVAILABLE"),
        is_historical_exception=detail.get("is_historical_exception", False),
        anomalies=detail.get("anomalies", []),
    )


# --- Part Costing Endpoints ---

@router.get(
    "/parts",
    response_model=List[PartCostResponse],
    dependencies=[Depends(require_permission(Permission.COSTING_READ))],
)
def list_part_costs(
    heat_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Calculates material-only unit costs for parts produced."""
    query = select(HeatHeader)
    if heat_id:
        query = query.where(HeatHeader.id == heat_id)

    heats = db.execute(query.order_by(desc(HeatHeader.heat_date)).limit(limit)).scalars().all()
    results: List[PartCostResponse] = []

    for heat in heats:
        heat_calc = calculate_heat_cost_detail(db, heat)
        cost_per_kg = heat_calc["cost_per_kg"]
        h_status = heat_calc["status"]

        for part in heat.parts_produced:
            part_calc = calculate_part_cost_detail(part, cost_per_kg, h_status)
            results.append(
                PartCostResponse(
                    heat_parts_produced_id=part_calc["heat_parts_produced_id"],
                    part_number=part_calc["part_number"],
                    part_name=part_calc["part_name"],
                    part_item_id=part_calc["part_item_id"],
                    quantity_produced=part_calc["quantity_produced"],
                    unit_cast_weight=part_calc["unit_cast_weight"],
                    cost_per_kg=part_calc["cost_per_kg"],
                    part_material_cost_per_unit=part_calc["part_material_cost_per_unit"],
                    total_part_material_cost=part_calc["total_part_material_cost"],
                    cost_scope=part_calc["cost_scope"],
                    status=part_calc["status"],
                    notes=part_calc["notes"],
                )
            )

    return results


# --- Costing Runs Endpoints ---

@router.post(
    "/runs",
    response_model=CostingRunSummaryResponse,
    dependencies=[Depends(require_permission(Permission.COSTING_CALCULATE))],
)
def trigger_costing_run(
    payload: CostingRunTriggerRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_current_user_id),
):
    """Executes and persists a complete, versioned Costing Run."""
    run = execute_costing_run(
        db=db,
        period_start=payload.period_start,
        period_end=payload.period_end,
        as_of_date=payload.as_of_date,
        actor_id=actor_id,
        denominator_policy=payload.denominator_policy,
        notes=payload.notes,
    )
    return CostingRunSummaryResponse(
        id=run.id,
        run_number=run.run_number,
        calculation_version=run.calculation_version,
        period_start=run.period_start,
        period_end=run.period_end,
        as_of_date=run.as_of_date,
        denominator_policy=run.denominator_policy,
        cost_scope=run.cost_scope,
        status=run.status,
        total_items_evaluated=run.total_items_evaluated,
        valued_items_count=run.valued_items_count,
        unvalued_items_count=run.unvalued_items_count,
        total_inventory_valuation=run.total_inventory_valuation,
        total_heats_evaluated=run.total_heats_evaluated,
        completed_heats_count=run.completed_heats_count,
        partial_heats_count=run.partial_heats_count,
        total_heat_material_cost=run.total_heat_material_cost,
        summary_notes=run.summary_notes,
        created_by=run.created_by,
        created_at=run.created_at,
    )


@router.get(
    "/runs",
    response_model=List[CostingRunSummaryResponse],
    dependencies=[Depends(require_permission(Permission.COSTING_READ))],
)
def list_costing_runs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Lists historical costing runs in reverse chronological order."""
    runs = db.execute(
        select(CostingRun).order_by(desc(CostingRun.created_at)).limit(limit)
    ).scalars().all()

    return [
        CostingRunSummaryResponse(
            id=r.id,
            run_number=r.run_number,
            calculation_version=r.calculation_version,
            period_start=r.period_start,
            period_end=r.period_end,
            as_of_date=r.as_of_date,
            denominator_policy=r.denominator_policy,
            cost_scope=r.cost_scope,
            status=r.status,
            total_items_evaluated=r.total_items_evaluated,
            valued_items_count=r.valued_items_count,
            unvalued_items_count=r.unvalued_items_count,
            total_inventory_valuation=r.total_inventory_valuation,
            total_heats_evaluated=r.total_heats_evaluated,
            completed_heats_count=r.completed_heats_count,
            partial_heats_count=r.partial_heats_count,
            total_heat_material_cost=r.total_heat_material_cost,
            summary_notes=r.summary_notes,
            created_by=r.created_by,
            created_at=r.created_at,
        )
        for r in runs
    ]


@router.get(
    "/runs/compare",
    response_model=CostingRunComparisonResponse,
    dependencies=[Depends(require_permission(Permission.COSTING_READ))],
)
def compare_runs_endpoint(
    run_id_1: int = Query(..., description="First run ID (baseline)"),
    run_id_2: int = Query(..., description="Second run ID (comparison target)"),
    db: Session = Depends(get_db),
):
    """Compares two costing runs side-by-side."""
    res = compare_costing_runs(db, run_id_1, run_id_2)
    return CostingRunComparisonResponse(
        summary=res["summary"],
        item_differences=res["item_differences"],
    )


@router.get(
    "/runs/{run_id}",
    response_model=CostingRunDetailResponse,
    dependencies=[Depends(require_permission(Permission.COSTING_READ))],
)
def get_costing_run_detail(
    run_id: int = Path(...),
    db: Session = Depends(get_db),
):
    """Returns detailed calculation snapshot for a costing run."""
    run = db.get(CostingRun, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Costing run ID {run_id} not found",
        )

    snapshots = [
        ItemValuationResponse(
            material_item_id=s.material_item_id,
            item_code=s.material_item.item_code if s.material_item else "N/A",
            item_name=s.material_item.name if s.material_item else "N/A",
            department_name=s.material_item.department.name if s.material_item and s.material_item.department else None,
            category=s.material_item.category if s.material_item else "N/A",
            inventory_quantity=s.inventory_quantity,
            uom_code=s.uom.code if s.uom else "UOM",
            weighted_average_rate=s.weighted_average_rate,
            extended_value=s.extended_value,
            as_of_date=s.as_of_date,
            valuation_status=s.valuation_status,
            rate_source=s.rate_source,
            anomaly_notes=s.anomaly_notes,
        )
        for s in run.item_snapshots
    ]

    heats_res = [
        HeatCostResponse(
            heat_id=h.heat_id,
            heat_number=h.heat_number,
            heat_date=h.heat_date,
            total_charged_quantity=h.total_charged_quantity,
            total_material_cost=h.total_material_cost,
            metal_tapped_weight=h.metal_tapped_weight,
            cost_denominator_value=h.cost_denominator_value,
            denominator_type=h.denominator_type,
            cost_per_kg=h.cost_per_kg,
            cost_scope=h.cost_scope,
            status=h.status,
            total_lines=h.total_lines,
            valued_lines=h.valued_lines,
            unvalued_lines=h.unvalued_lines,
            lines=[
                HeatCostLineResponse(
                    heat_charge_line_id=l.heat_charge_line_id,
                    line_number=l.line_number,
                    material_item_id=l.material_item_id,
                    raw_material_description=l.raw_material_description,
                    charged_quantity=l.charged_quantity,
                    applicable_rate=l.applicable_rate,
                    line_cost=l.line_cost,
                    rate_source=l.rate_source,
                    is_included=l.is_included,
                    status=l.status,
                    remarks=l.remarks,
                )
                for l in h.lines
            ],
        )
        for h in run.heat_costs
    ]

    parts_res = [
        PartCostResponse(
            heat_parts_produced_id=p.heat_parts_produced_id,
            part_number=p.part_number,
            part_name=p.part_name,
            part_item_id=p.part_item_id,
            quantity_produced=p.quantity_produced,
            unit_cast_weight=p.unit_cast_weight,
            cost_per_kg=p.cost_per_kg,
            part_material_cost_per_unit=p.part_material_cost_per_unit,
            total_part_material_cost=p.total_part_material_cost,
            cost_scope=p.cost_scope,
            status=p.status,
            notes=p.notes,
        )
        for p in run.part_costs
    ]

    return CostingRunDetailResponse(
        id=run.id,
        run_number=run.run_number,
        calculation_version=run.calculation_version,
        period_start=run.period_start,
        period_end=run.period_end,
        as_of_date=run.as_of_date,
        denominator_policy=run.denominator_policy,
        cost_scope=run.cost_scope,
        status=run.status,
        total_items_evaluated=run.total_items_evaluated,
        valued_items_count=run.valued_items_count,
        unvalued_items_count=run.unvalued_items_count,
        total_inventory_valuation=run.total_inventory_valuation,
        total_heats_evaluated=run.total_heats_evaluated,
        completed_heats_count=run.completed_heats_count,
        partial_heats_count=run.partial_heats_count,
        total_heat_material_cost=run.total_heat_material_cost,
        summary_notes=run.summary_notes,
        created_by=run.created_by,
        created_at=run.created_at,
        item_snapshots=snapshots,
        heat_costs=heats_res,
        part_costs=parts_res,
    )


# --- Opening Valuation Versioning & Approval Endpoints (SW-06) ---

def _serialize_opening_valuation(
    record: ItemOpeningValuation,
    include_audit: bool = False,
) -> ItemOpeningValuationResponse:
    item = record.material_item
    audit_logs = None
    if include_audit and record.audit_logs:
        audit_logs = [
            OpeningValuationAuditLogResponse(
                id=log.id,
                valuation_id=log.valuation_id,
                action=log.action,
                from_status=log.from_status,
                to_status=log.to_status,
                actor_id=log.actor_id,
                comments=log.comments,
                timestamp=log.timestamp,
            )
            for log in record.audit_logs
        ]
    return ItemOpeningValuationResponse(
        id=record.id,
        material_item_id=record.material_item_id,
        item_code=item.item_code if item else "",
        item_name=item.name if item else "",
        version=record.version,
        baseline_date=record.baseline_date,
        opening_rate_ex_gst=record.opening_rate_ex_gst,
        status=record.status,
        created_by=record.created_by,
        created_at=record.created_at,
        approved_by=record.approved_by,
        approved_at=record.approved_at,
        rejection_reason=record.rejection_reason,
        superseded_by_id=record.superseded_by_id,
        superseded_at=record.superseded_at,
        notes=record.notes,
        audit_logs=audit_logs,
    )


@router.post(
    "/opening-valuations",
    response_model=ItemOpeningValuationResponse,
    dependencies=[Depends(require_permission(Permission.COSTING_CALCULATE))],
)
def propose_opening_valuation_endpoint(
    payload: ItemOpeningValuationCreate,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_current_user_id),
):
    """Proposes a new versioned opening valuation rate for an item as of 12 October 2026."""
    record = svc_propose_opening_valuation(db, payload, actor_id=actor_id)
    return _serialize_opening_valuation(record)


@router.post(
    "/opening-valuations/{valuation_id}/approve",
    response_model=ItemOpeningValuationResponse,
    dependencies=[Depends(require_permission(Permission.COSTING_CALCULATE))],
)
def approve_opening_valuation_endpoint(
    valuation_id: int,
    action: Optional[OpeningValuationActionRequest] = None,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_current_user_id),
):
    """Approves a proposed opening valuation with maker-checker verification."""
    comments = action.comments if action else None
    record = svc_approve_opening_valuation(db, valuation_id, actor_id=actor_id, comments=comments)
    return _serialize_opening_valuation(record)


@router.post(
    "/opening-valuations/{valuation_id}/reject",
    response_model=ItemOpeningValuationResponse,
    dependencies=[Depends(require_permission(Permission.COSTING_CALCULATE))],
)
def reject_opening_valuation_endpoint(
    valuation_id: int,
    payload: OpeningValuationRejectRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_current_user_id),
):
    """Rejects a proposed opening valuation with a mandatory audit reason."""
    record = svc_reject_opening_valuation(db, valuation_id, actor_id=actor_id, reason=payload.reason)
    return _serialize_opening_valuation(record)


@router.get(
    "/opening-valuations",
    response_model=List[ItemOpeningValuationResponse],
    dependencies=[Depends(require_permission(Permission.COSTING_READ))],
)
def list_opening_valuations_endpoint(
    material_item_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Lists opening valuations with optional filters by material item and status."""
    records = svc_list_opening_valuations(db, material_item_id=material_item_id, status=status)
    return [_serialize_opening_valuation(r) for r in records]


@router.get(
    "/opening-valuations/{valuation_id}",
    response_model=ItemOpeningValuationResponse,
    dependencies=[Depends(require_permission(Permission.COSTING_READ))],
)
def get_opening_valuation_endpoint(
    valuation_id: int,
    db: Session = Depends(get_db),
):
    """Retrieves a single opening valuation including its complete audit trail."""
    record = svc_get_opening_valuation_by_id(db, valuation_id)
    return _serialize_opening_valuation(record, include_audit=True)
