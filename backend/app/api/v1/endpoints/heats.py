"""
Heat Log API Endpoints.
STRICT RULE: Heat log operations NEVER move inventory.
"""

from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import AuthenticatedUser, Permission, require_permission, get_current_user_context
from app.schemas.heat import (
    HeatCreate,
    HeatRead,
    HeelVerificationRequest,
    HeelProposeCarryForwardResponse,
)
from app.services.heat_service import (
    create_heat,
    get_heat_by_id,
    get_heat_by_number,
    list_heats,
    propose_heat_carry_forward,
    verify_heat_heel,
)

router = APIRouter()


@router.post("", response_model=HeatRead, status_code=status.HTTP_201_CREATED)
def api_create_heat(
    payload: HeatCreate,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_LOG_CREATE)),
):
    """
    Creates a new induction furnace heat record.
    Restricted to Foundry, Management, and Admin roles.
    """
    
    charge_data = [l.model_dump() for l in payload.charge_lines] if payload.charge_lines else None
    parts_data = [p.model_dump() for p in payload.parts_produced] if payload.parts_produced else None

    heat = create_heat(
        db=db,
        heat_number=payload.heat_number,
        heat_date=payload.heat_date,
        created_by=user.user_id,
        furnace_id=payload.furnace_id,
        shift=payload.shift,
        metal_tapped_weight=payload.metal_tapped_weight,
        metal_tapped_uom_id=payload.metal_tapped_uom_id,
        production_status=payload.production_status,
        source_document_reference=payload.source_document_reference,
        notes=payload.notes,
        opening_liquid_heel_kg=payload.opening_liquid_heel_kg,
        closing_liquid_heel_kg=payload.closing_liquid_heel_kg,
        heel_measurement_method=payload.heel_measurement_method,
        is_cold_start=payload.is_cold_start,
        is_furnace_empty=payload.is_furnace_empty,
        opening_heel_source_heat_id=payload.opening_heel_source_heat_id,
        charge_lines_data=charge_data,
        parts_produced_data=parts_data,
    )
    return heat


@router.get("", response_model=List[HeatRead])
def api_list_heats(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    furnace_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_LOG_READ)),
):
    """Lists heats with optional date range, furnace, and search filters."""
    items, _ = list_heats(
        db=db,
        date_from=date_from,
        date_to=date_to,
        furnace_id=furnace_id,
        status_filter=status_filter,
        search=search,
        limit=limit,
        offset=offset,
    )
    return items


@router.get("/active", response_model=List[HeatRead])
def api_list_active_heats(
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(get_current_user_context),
):
    """
    Returns only ACTIVE heats (production_status == 'IN_PROGRESS').
    Used by Stores to ensure materials are only issued against live, active heats.
    """
    items, _ = list_heats(
        db=db,
        status_filter="IN_PROGRESS",
        limit=100,
        offset=0,
    )
    return items


@router.get("/propose-carry-forward", response_model=HeelProposeCarryForwardResponse)
def api_propose_carry_forward(
    furnace_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_LOG_READ)),
):
    """
    Proposes opening liquid heel from latest heat on the specified furnace.
    Enforces that unverified closing heels or consumed closing heels block carry-forward.
    """
    return propose_heat_carry_forward(db=db, furnace_id=furnace_id)


@router.get("/{id}", response_model=HeatRead)
def api_get_heat_by_id(
    id: int,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_LOG_READ)),
):
    """Retrieves heat details including charge lines and parts produced."""
    heat = get_heat_by_id(db, id)
    if not heat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Heat ID {id} not found",
        )
    return heat


@router.get("/number/{heat_number}", response_model=HeatRead)
def api_get_heat_by_number(
    heat_number: str,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_LOG_READ)),
):
    """Retrieves heat details by raw or normalized heat number."""
    heat = get_heat_by_number(db, heat_number)
    if not heat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Heat '{heat_number}' not found",
        )
    return heat


@router.post("/{id}/verify-heel", response_model=HeatRead)
def api_verify_heat_heel(
    id: int,
    payload: HeelVerificationRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_LOG_CREATE)),
):
    """
    Verifies or rejects liquid heel measurement on a heat record.
    Enforces maker-checker: recorder cannot verify own measurement.
    """
    return verify_heat_heel(
        db=db,
        heat_id=id,
        decision=payload.decision,
        verified_by=user.user_id,
        comments=payload.comments,
    )


@router.post("/{id}/close", response_model=HeatRead)
def api_close_heat(
    id: int,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user_context),
):
    """
    Foundry Manager action: Closes an active heat when melting and pouring are completed.
    Once closed, Stores can no longer issue materials to this heat.
    """
    heat = get_heat_by_id(db, id)
    if not heat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Heat ID {id} not found",
        )
    heat.production_status = "COMPLETED"
    db.commit()
    db.refresh(heat)
    return heat


@router.post("/{id}/reopen", response_model=HeatRead)
def api_reopen_heat(
    id: int,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user_context),
):
    """
    Foundry Manager action: Reopens a closed heat back to active IN_PROGRESS status.
    """
    heat = get_heat_by_id(db, id)
    if not heat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Heat ID {id} not found",
        )
    heat.production_status = "IN_PROGRESS"
    db.commit()
    db.refresh(heat)
    return heat


@router.get("/{id}/consumption-cost")
def api_get_heat_consumption_cost(
    id: int,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(get_current_user_context),
):
    """
    Simplified Heat Consumption & Batch Costing:
    Calculates total raw materials consumed (kg) and total batch cost (₹ & ₹/kg)
    without requiring piece-rate part allocations.
    """
    from decimal import Decimal
    from sqlalchemy import desc
    from sqlalchemy.orm import joinedload
    from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem
    from app.models.material_return import MaterialReturnHeader, MaterialReturnLineItem
    from app.models.costing import ItemCostSnapshot

    heat = get_heat_by_id(db, id)
    if not heat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Heat ID {id} not found",
        )

    heat_refs = {heat.heat_number}
    if heat.normalized_heat_number:
        heat_refs.add(heat.normalized_heat_number)
    if heat.original_heat_number:
        heat_refs.add(heat.original_heat_number)

    issues = (
        db.query(MaterialIssueHeader)
        .options(
            joinedload(MaterialIssueHeader.lines).joinedload(MaterialIssueLineItem.material_item),
            joinedload(MaterialIssueHeader.lines).joinedload(MaterialIssueLineItem.uom),
        )
        .filter(
            MaterialIssueHeader.heat_reference_number.in_(list(heat_refs)),
            MaterialIssueHeader.status == "APPROVED",
        )
        .all()
    )

    returns = (
        db.query(MaterialReturnHeader)
        .options(
            joinedload(MaterialReturnHeader.lines).joinedload(MaterialReturnLineItem.material_item),
        )
        .filter(
            MaterialReturnHeader.heat_reference_number.in_(list(heat_refs)),
            MaterialReturnHeader.status == "ACCEPTED",
        )
        .all()
    )

    returned_qty_by_item: dict[int, Decimal] = {}
    for ret in returns:
        for rline in ret.lines:
            returned_qty_by_item[rline.material_item_id] = (
                returned_qty_by_item.get(rline.material_item_id, Decimal("0")) + Decimal(str(rline.quantity))
            )

    material_map: dict[int, dict] = {}

    for iss in issues:
        for line in iss.lines:
            item_id = line.material_item_id
            qty = Decimal(str(line.quantity))
            if item_id not in material_map:
                material_map[item_id] = {
                    "item_id": item_id,
                    "item_code": line.material_item.item_code if line.material_item else f"ITEM-{item_id}",
                    "item_name": line.material_item.name if line.material_item else "Raw Material",
                    "uom_code": line.uom.code if line.uom else "KG",
                    "gross_issued_qty": Decimal("0"),
                    "returned_qty": Decimal("0"),
                    "net_consumed_qty": Decimal("0"),
                }
            material_map[item_id]["gross_issued_qty"] += qty

    for cl in heat.charge_lines:
        item_id = cl.material_item_id
        if item_id:
            qty = Decimal(str(cl.charged_quantity))
            if item_id not in material_map:
                material_map[item_id] = {
                    "item_id": item_id,
                    "item_code": f"ITEM-{item_id}",
                    "item_name": cl.original_material_description,
                    "uom_code": "KG",
                    "gross_issued_qty": Decimal("0"),
                    "returned_qty": Decimal("0"),
                    "net_consumed_qty": Decimal("0"),
                }
            if material_map[item_id]["gross_issued_qty"] == Decimal("0"):
                material_map[item_id]["gross_issued_qty"] += qty

    total_consumed_kg = Decimal("0")
    total_cost_inr = Decimal("0")
    materials_list = []

    for item_id, data in material_map.items():
        ret_qty = returned_qty_by_item.get(item_id, Decimal("0"))
        data["returned_qty"] = ret_qty
        net_qty = max(Decimal("0"), data["gross_issued_qty"] - ret_qty)
        data["net_consumed_qty"] = net_qty

        snapshot = (
            db.query(ItemCostSnapshot)
            .filter(ItemCostSnapshot.material_item_id == item_id)
            .order_by(desc(ItemCostSnapshot.as_of_date), desc(ItemCostSnapshot.id))
            .first()
        )
        unit_rate = (
            Decimal(str(snapshot.weighted_average_rate))
            if snapshot and snapshot.weighted_average_rate is not None
            else Decimal("45.00")
        )
        line_total = net_qty * unit_rate

        total_consumed_kg += net_qty
        total_cost_inr += line_total

        materials_list.append({
            "item_id": item_id,
            "item_code": data["item_code"],
            "item_name": data["item_name"],
            "uom_code": data["uom_code"],
            "gross_issued_qty": float(data["gross_issued_qty"]),
            "returned_qty": float(data["returned_qty"]),
            "net_consumed_qty": float(net_qty),
            "unit_rate_inr": float(unit_rate),
            "line_total_cost_inr": float(line_total),
        })

    tapped_kg = Decimal(str(heat.metal_tapped_weight or 0))
    melt_loss_kg = max(Decimal("0"), total_consumed_kg - tapped_kg) if tapped_kg > 0 else Decimal("0")
    melt_loss_pct = ((melt_loss_kg / total_consumed_kg) * Decimal("100")) if total_consumed_kg > 0 and tapped_kg > 0 else Decimal("0")
    cost_per_kg = (total_cost_inr / tapped_kg) if tapped_kg > 0 else ((total_cost_inr / total_consumed_kg) if total_consumed_kg > 0 else Decimal("0"))

    return {
        "heat_id": heat.id,
        "heat_number": heat.heat_number,
        "normalized_heat_number": heat.normalized_heat_number,
        "heat_date": str(heat.heat_date),
        "furnace_id": heat.furnace_id,
        "production_status": heat.production_status,
        "total_consumed_kg": float(total_consumed_kg),
        "tapped_metal_weight_kg": float(tapped_kg),
        "melt_loss_kg": float(melt_loss_kg),
        "melt_loss_pct": round(float(melt_loss_pct), 2),
        "total_batch_cost_inr": round(float(total_cost_inr), 2),
        "cost_per_kg_liquid_metal": round(float(cost_per_kg), 2),
        "materials": materials_list,
    }
