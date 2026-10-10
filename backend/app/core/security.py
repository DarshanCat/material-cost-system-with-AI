"""
VSPL Security & RBAC Architectural Foundation.

Role-Based Access Control (RBAC) Specification:
- Stores: Material receipts (GRNs), material issues, scrap/waste logs, physical stock audit entries.
- Foundry: Heat logs, charge detail logging, issue-to-heat reconciliation view, foundry inventory view.
- Purchase: Vendor master management, purchase rates verification, PO tracking.
- Management: Costing reports, variance analysis, executive dashboards, inventory valuation, item approval.
- Admin: User lifecycle, role assignments, master approval requests, system audit logs.

CRITICAL ARCHITECTURAL DIRECTIVE:
Frontend route hiding is NOT security. Backend route and service dependencies
must enforce authentication tokens and role permission scopes at the API layer.
No hardcoded credentials or bypass backdoors are permitted.

NOTE ON CURRENT AUTHENTICATION STATUS (PHASE 2):
Production authentication (JWT / SSO / LDAP) is scheduled for Phase 8.
For Phase 2 development and testing, an explicit Development User Context (`DevUserContext`)
is extracted from HTTP headers (`X-User-Id`, `X-User-Role`, `X-User-Department`).
THIS IS NOT PRODUCTION-SECURE AND MUST NEVER BE DEPLOYED TO PRODUCTION WITHOUT PHASE 8 AUTH.
"""

from enum import Enum
from typing import Set, Optional
from fastapi import Header, HTTPException, status, Depends
from pydantic import BaseModel


class UserRole(str, Enum):
    STORES = "Stores"
    FOUNDRY = "Foundry"
    PURCHASE = "Purchase"
    MANAGEMENT = "Management"
    ADMIN = "Admin"


class Permission(str, Enum):
    # Material Entry
    RECEIPT_CREATE = "receipt:create"
    RECEIPT_READ = "receipt:read"
    ISSUE_CREATE = "issue:create"
    ISSUE_READ = "issue:read"
    WASTE_LOG = "waste:log"

    # Master Data & Requests
    ITEM_READ = "item:read"
    ITEM_CREATE = "item:create"
    ITEM_UPDATE = "item:update"
    ITEM_REQUEST_CREATE = "item_request:create"
    ITEM_REQUEST_SUBMIT = "item_request:submit"
    ITEM_REQUEST_CANCEL = "item_request:cancel"
    ITEM_REQUEST_READ = "item_request:read"
    ITEM_APPROVE = "item:approve"
    ITEM_REJECT = "item:reject"
    VENDOR_READ = "vendor:read"
    VENDOR_MANAGE = "vendor:manage"
    DEPARTMENT_READ = "department:read"
    UOM_READ = "uom:read"

    # Inventory Ledger
    LEDGER_READ = "ledger:read"
    STOCK_ADJUST = "stock:adjust"

    # Heat Reconciliation
    HEAT_LOG_CREATE = "heat_log:create"
    HEAT_LOG_READ = "heat_log:read"
    HEAT_RECONCILE = "heat:reconcile"

    # Costing & Financials
    COSTING_READ = "costing:read"
    COSTING_CALCULATE = "costing:calculate"

    # System & Audit
    AUDIT_READ = "audit:read"
    USER_MANAGE = "user:manage"


# Role-to-Permissions Mapping matrix
ROLE_PERMISSIONS: dict[UserRole, Set[Permission]] = {
    UserRole.STORES: {
        Permission.RECEIPT_CREATE,
        Permission.RECEIPT_READ,
        Permission.ISSUE_CREATE,
        Permission.ISSUE_READ,
        Permission.WASTE_LOG,
        Permission.LEDGER_READ,
        Permission.STOCK_ADJUST,
        Permission.ITEM_READ,
        Permission.ITEM_REQUEST_CREATE,
        Permission.ITEM_REQUEST_SUBMIT,
        Permission.ITEM_REQUEST_CANCEL,
        Permission.ITEM_REQUEST_READ,
        Permission.VENDOR_READ,
        Permission.DEPARTMENT_READ,
        Permission.UOM_READ,
    },
    UserRole.FOUNDRY: {
        Permission.HEAT_LOG_CREATE,
        Permission.HEAT_LOG_READ,
        Permission.HEAT_RECONCILE,
        Permission.ISSUE_READ,
        Permission.LEDGER_READ,
        Permission.ITEM_READ,
        Permission.ITEM_REQUEST_CREATE,
        Permission.ITEM_REQUEST_SUBMIT,
        Permission.ITEM_REQUEST_CANCEL,
        Permission.ITEM_REQUEST_READ,
        Permission.DEPARTMENT_READ,
        Permission.UOM_READ,
    },
    UserRole.PURCHASE: {
        Permission.VENDOR_MANAGE,
        Permission.VENDOR_READ,
        Permission.ITEM_READ,
        Permission.ITEM_REQUEST_CREATE,
        Permission.ITEM_REQUEST_SUBMIT,
        Permission.ITEM_REQUEST_CANCEL,
        Permission.ITEM_REQUEST_READ,
        Permission.RECEIPT_READ,
        Permission.LEDGER_READ,
        Permission.DEPARTMENT_READ,
        Permission.UOM_READ,
    },
    UserRole.MANAGEMENT: {
        Permission.RECEIPT_READ,
        Permission.ISSUE_READ,
        Permission.LEDGER_READ,
        Permission.HEAT_LOG_READ,
        Permission.COSTING_READ,
        Permission.COSTING_CALCULATE,
        Permission.AUDIT_READ,
        Permission.ITEM_READ,
        Permission.ITEM_REQUEST_CREATE,
        Permission.ITEM_REQUEST_SUBMIT,
        Permission.ITEM_REQUEST_CANCEL,
        Permission.ITEM_APPROVE,
        Permission.ITEM_REJECT,
        Permission.ITEM_REQUEST_READ,
        Permission.VENDOR_READ,
        Permission.DEPARTMENT_READ,
        Permission.UOM_READ,
    },
    UserRole.ADMIN: set(Permission),  # All permissions
}


class DevUserContext(BaseModel):
    """
    Explicit Development & Testing User Context.
    Identifies the actor during Phase 2 development.
    """
    user_id: str
    role: UserRole
    department: str


def get_current_user_context(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_user_department: Optional[str] = Header(None, alias="X-User-Department"),
) -> DevUserContext:
    """
    FastAPI dependency extracting the user context from request headers for local development.
    Defaults to an operational Stores user if headers are omitted in dev mode.
    """
    user_id = x_user_id or "dev_stores_user"
    role_str = x_user_role or UserRole.STORES.value
    department = x_user_department or "General/Stores"

    try:
        role = UserRole(role_str)
    except ValueError:
        role = UserRole.STORES

    return DevUserContext(user_id=user_id, role=role, department=department)


def require_permission(required_permission: Permission):
    """
    Dependency generator enforcing granular backend authorization based on user role.
    """
    def permission_checker(user: DevUserContext = Depends(get_current_user_context)) -> DevUserContext:
        user_permissions = ROLE_PERMISSIONS.get(user.role, set())
        if required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Role '{user.role.value}' lacks permission '{required_permission.value}'",
            )
        return user

    return permission_checker


def get_current_user_role(context: DevUserContext = Depends(get_current_user_context)) -> str:
    """Helper dependency returning current user role string."""
    return context.role.value


def get_current_user_id(context: DevUserContext = Depends(get_current_user_context)) -> str:
    """Helper dependency returning current user id string."""
    return context.user_id

