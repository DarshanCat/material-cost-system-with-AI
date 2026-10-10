"""
Idempotent Database Reference Data Seeding.
Seeds the 8 explicitly required plant departments and standard controlled UOMs with decimal precision.
Does NOT fabricate any material items, historical inventory, or synthetic vendors.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.department import Department
from app.models.uom import UOM

logger = logging.getLogger("vspl.db.seed")

# Explicit 8 Plant Departments
INITIAL_DEPARTMENTS = [
    {"code": "FDY", "name": "Foundry"},
    {"code": "MSP", "name": "Machine Shop"},
    {"code": "MNT", "name": "Maintenance"},
    {"code": "GNS", "name": "General/Stores"},
    {"code": "PKG", "name": "Packing"},
    {"code": "QLT", "name": "Quality"},
    {"code": "HMC", "name": "F3 HMC"},
    {"code": "CNC", "name": "F3 CNC"},
]

# Controlled Master UOMs with Decimal Precisions
INITIAL_UOMS = [
    {"code": "KG", "name": "Kilogram", "decimal_precision": 4},
    {"code": "MT", "name": "Metric Ton", "decimal_precision": 4},
    {"code": "NOS", "name": "Numbers / Pieces", "decimal_precision": 0},
    {"code": "LTR", "name": "Liter", "decimal_precision": 3},
    {"code": "MTR", "name": "Meter", "decimal_precision": 2},
    {"code": "BAG", "name": "Bag", "decimal_precision": 0},
    {"code": "SET", "name": "Set", "decimal_precision": 0},
]


def seed_reference_data(db: Session) -> dict[str, int]:
    """
    Idempotently seeds departments and UOMs into the database.
    Returns counts of added/updated entities.
    """
    dept_added = 0
    for dept_data in INITIAL_DEPARTMENTS:
        existing = db.scalar(
            select(Department).where(
                (Department.code == dept_data["code"]) | (Department.name == dept_data["name"])
            )
        )
        if not existing:
            dept = Department(
                code=dept_data["code"],
                name=dept_data["name"],
                is_active=True,
            )
            db.add(dept)
            dept_added += 1

    uom_added = 0
    for uom_data in INITIAL_UOMS:
        existing = db.scalar(select(UOM).where(UOM.code == uom_data["code"]))
        if not existing:
            uom = UOM(
                code=uom_data["code"],
                name=uom_data["name"],
                decimal_precision=uom_data["decimal_precision"],
                is_active=True,
            )
            db.add(uom)
            uom_added += 1

    db.commit()
    logger.info(f"Seed complete: {dept_added} departments added, {uom_added} UOMs added.")
    return {"departments_added": dept_added, "uoms_added": uom_added}
