from fastapi import APIRouter
from app.api.v1.endpoints import (
    health,
    departments,
    uoms,
    items,
    vendors,
    item_requests,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["System Health"])
api_router.include_router(departments.router, prefix="/departments", tags=["Department Master"])
api_router.include_router(uoms.router, prefix="/uoms", tags=["UOM Master"])
api_router.include_router(items.router, prefix="/items", tags=["Material Item Master"])
api_router.include_router(vendors.router, prefix="/vendors", tags=["Vendor Master"])
api_router.include_router(item_requests.router, prefix="/item-requests", tags=["Item Approval Workflow"])
