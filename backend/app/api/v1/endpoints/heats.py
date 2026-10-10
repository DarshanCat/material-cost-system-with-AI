"""
Heat Log API Endpoints.
STRICT RULE: Heat log operations NEVER move inventory.
"""

from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user_role, get_current_user_id
from app.schemas.heat import HeatCreate, HeatRead
from app.services.heat_service import create_heat, get_heat_by_id, get_heat_by_number, list_heats

router = APIRouter()


@router.post("", response_model=HeatRead, status_code=status.HTTP_201_CREATED)
def api_create_heat(
    payload: HeatCreate,
    db: Session = Depends(get_db),
    current_role: str = Depends(get_current_user_role),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Creates a new induction furnace heat record.
    Restricted to Foundry, Management, and Admin roles.
    """
    if current_role not in ("Foundry", "Management", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_role}' is not authorized to create heat records",
        )
    
    charge_data = [l.model_dump() for l in payload.charge_lines] if payload.charge_lines else None
    parts_data = [p.model_dump() for p in payload.parts_produced] if payload.parts_produced else None

    heat = create_heat(
        db=db,
        heat_number=payload.heat_number,
        heat_date=payload.heat_date,
        created_by=current_user_id,
        furnace_id=payload.furnace_id,
        shift=payload.shift,
        metal_tapped_weight=payload.metal_tapped_weight,
        metal_tapped_uom_id=payload.metal_tapped_uom_id,
        production_status=payload.production_status,
        source_document_reference=payload.source_document_reference,
        notes=payload.notes,
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


@router.get("/{id}", response_model=HeatRead)
def api_get_heat_by_id(
    id: int,
    db: Session = Depends(get_db),
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
):
    """Retrieves heat details by raw or normalized heat number."""
    heat = get_heat_by_number(db, heat_number)
    if not heat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Heat '{heat_number}' not found",
        )
    return heat
