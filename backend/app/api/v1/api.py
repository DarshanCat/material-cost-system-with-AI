from fastapi import APIRouter
from app.api.v1.endpoints import (
    health,
    departments,
    uoms,
    items,
    vendors,
    item_requests,
    grn,
    issues,
    waste,
    excel_import,
    ledger,
    opening_balances,
    physical_audits,
    heats,
    material_aliases,
    reconciliation,
    heat_import,
    costing,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["System Health"])
api_router.include_router(departments.router, prefix="/departments", tags=["Department Master"])
api_router.include_router(uoms.router, prefix="/uoms", tags=["UOM Master"])
api_router.include_router(items.router, prefix="/items", tags=["Material Item Master"])
api_router.include_router(vendors.router, prefix="/vendors", tags=["Vendor Master"])
api_router.include_router(item_requests.router, prefix="/item-requests", tags=["Item Approval Workflow"])
api_router.include_router(grn.router, prefix="/grn", tags=["Goods Receipt Note (GRN)"])
api_router.include_router(issues.router, prefix="/issues", tags=["Material Issue"])
api_router.include_router(waste.router, prefix="/waste", tags=["Waste Disposition"])
api_router.include_router(excel_import.router, prefix="/excel-import", tags=["Excel Import Validation"])
api_router.include_router(ledger.router, prefix="/ledger", tags=["Append-Only Stock Ledger"])
api_router.include_router(opening_balances.router, prefix="/opening-balances", tags=["Opening Stock Balances"])
api_router.include_router(physical_audits.router, prefix="/physical-audits", tags=["Physical Inventory Audits"])
api_router.include_router(heats.router, prefix="/heats", tags=["Induction Furnace Heat Log"])
api_router.include_router(material_aliases.router, prefix="/material-aliases", tags=["Material Description Aliases"])
api_router.include_router(reconciliation.router, prefix="/reconciliation", tags=["Issue-to-Heat Reconciliation"])
api_router.include_router(heat_import.router, prefix="/heats/import", tags=["Heat Log Excel Import"])
api_router.include_router(costing.router, tags=["Costing & Valuation"])
