"""
VSPL Security & RBAC Foundation.

Role-Based Access Control (RBAC) Specification:
- Stores: Material receipts (GRNs), material issues, scrap/waste logs, physical stock audit entries.
- Foundry: Heat logs, charge detail logging, issue-to-heat reconciliation view, foundry inventory view.
- Purchase: Vendor master management, purchase rates verification, PO tracking.
- Management: Costing reports, variance analysis, executive dashboards, inventory valuation, approvals.
- Admin: User lifecycle, role assignments, master approval requests, system audit logs.

IDENTITY MODEL (Security Hardening Sprint 1):
Identity is established ONLY by a server-verified credential (`Authorization: Bearer <token>`),
checked by the configured `AuthProvider` (see `app/core/auth.py`). Client-supplied `X-User-*`
headers, query parameters and request bodies never establish identity or role.
- Missing / invalid / expired credential  -> HTTP 401.
- Verified identity whose role is unknown -> HTTP 401 (a role is never defaulted).
- Verified identity lacking a permission  -> HTTP 403.
- With no provider configured (AUTH_PROVIDER=none, the default) every protected route returns 401.

The production authentication mechanism (JWT / Entra ID / session) is NOT yet approved by the
IT Head. See docs/security/AUTHENTICATION_INTEGRATION.md for what is needed to plug it in.
"""

from enum import Enum
from typing import Set, Optional
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel


class UserRole(str, Enum):
    STORES = "Stores"
    FOUNDRY = "Foundry"
    PURCHASE = "Purchase"
    MANAGEMENT = "Management"
    ADMIN = "Admin"
    QUALITY = "Quality"
    ACCOUNTS = "Accounts"


class Permission(str, Enum):
    # Material Entry
    RECEIPT_CREATE = "receipt:create"
    RECEIPT_READ = "receipt:read"
    RECEIPT_APPROVE = "receipt:approve"
    RECEIPT_QUALITY = "receipt:quality"   # QA inspection of a submitted GRN (Quality role only)
    PAYMENT_RECORD = "payment:record"     # settle an approved GRN (Accounts role only)
    ISSUE_CREATE = "issue:create"
    ISSUE_READ = "issue:read"
    ISSUE_APPROVE = "issue:approve"
    WASTE_LOG = "waste:log"
    WASTE_READ = "waste:read"
    WASTE_APPROVE = "waste:approve"
    EXCEL_IMPORT = "excel:import"

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
    DEPARTMENT_MANAGE = "department:manage"
    UOM_READ = "uom:read"
    UOM_MANAGE = "uom:manage"
    ALIAS_CREATE = "alias:create"
    ALIAS_APPROVE = "alias:approve"
    ALIAS_DEACTIVATE = "alias:deactivate"

    # Inventory Ledger
    LEDGER_READ = "ledger:read"
    LEDGER_REVERSE = "ledger:reverse"
    STOCK_ADJUST = "stock:adjust"
    STOCK_AUDIT_APPROVE = "stock_audit:approve"
    OPENING_BALANCE_POST = "opening_balance:post"

    # Heat Reconciliation
    HEAT_LOG_CREATE = "heat_log:create"
    HEAT_LOG_READ = "heat_log:read"
    HEAT_RECONCILE = "heat:reconcile"
    HEAT_EXCEPTION_RESOLVE = "heat:exception_resolve"

    # Costing & Financials
    COSTING_READ = "costing:read"
    COSTING_CALCULATE = "costing:calculate"

    # System & Audit
    AUDIT_READ = "audit:read"
    USER_MANAGE = "user:manage"


# Role-to-Permissions Mapping matrix.
# PROVISIONAL (needs Plant Head / Management sign-off, backlog SW-02): the approve / reverse /
# opening-balance / import grants below were not defined in the repository's business rules.
# They follow the only stated rules (Rule L8: physical-audit approval by Management or Admin;
# Rule L5: reversal by an "authorized supervisor") and otherwise keep the narrowest role set
# that still lets each module work. Admin holds only administrative and read-only inspection permissions.
ROLE_PERMISSIONS: dict[UserRole, Set[Permission]] = {
    UserRole.STORES: {
        Permission.RECEIPT_CREATE,
        Permission.RECEIPT_READ,
        Permission.ISSUE_CREATE,
        Permission.ISSUE_READ,
        Permission.WASTE_LOG,
        Permission.WASTE_READ,
        Permission.EXCEL_IMPORT,
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
        Permission.ALIAS_CREATE,
        Permission.ALIAS_DEACTIVATE,
        Permission.HEAT_LOG_READ,
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
        Permission.ALIAS_CREATE,
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
    UserRole.QUALITY: {
        Permission.RECEIPT_READ,
        Permission.RECEIPT_QUALITY,
        Permission.ITEM_READ,
        Permission.VENDOR_READ,
        Permission.DEPARTMENT_READ,
        Permission.UOM_READ,
    },
    UserRole.ACCOUNTS: {
        Permission.RECEIPT_READ,
        Permission.PAYMENT_RECORD,
        Permission.ITEM_READ,
        Permission.VENDOR_READ,
        Permission.DEPARTMENT_READ,
        Permission.UOM_READ,
        Permission.LEDGER_READ,
    },
    UserRole.MANAGEMENT: {
        Permission.RECEIPT_READ,
        Permission.RECEIPT_APPROVE,
        Permission.ISSUE_READ,
        Permission.ISSUE_APPROVE,
        Permission.WASTE_READ,
        Permission.WASTE_APPROVE,
        Permission.LEDGER_READ,
        Permission.LEDGER_REVERSE,
        Permission.STOCK_AUDIT_APPROVE,
        Permission.OPENING_BALANCE_POST,
        Permission.HEAT_LOG_CREATE,
        Permission.HEAT_LOG_READ,
        Permission.HEAT_RECONCILE,
        Permission.HEAT_EXCEPTION_RESOLVE,
        Permission.COSTING_READ,
        Permission.COSTING_CALCULATE,
        Permission.AUDIT_READ,
        Permission.ITEM_READ,
        Permission.ITEM_UPDATE,
        Permission.ITEM_REQUEST_CREATE,
        Permission.ITEM_REQUEST_SUBMIT,
        Permission.ITEM_REQUEST_CANCEL,
        Permission.ITEM_APPROVE,
        Permission.ITEM_REJECT,
        Permission.ITEM_REQUEST_READ,
        Permission.VENDOR_READ,
        Permission.DEPARTMENT_READ,
        Permission.DEPARTMENT_MANAGE,
        Permission.UOM_READ,
        Permission.UOM_MANAGE,
        Permission.ALIAS_CREATE,
        Permission.ALIAS_APPROVE,
        Permission.ALIAS_DEACTIVATE,
    },
    UserRole.ADMIN: {
        # System & Audit Administration
        Permission.USER_MANAGE,
        Permission.AUDIT_READ,
        # Master Data Management & Approvals
        Permission.ITEM_READ,
        Permission.ITEM_CREATE,
        Permission.ITEM_UPDATE,
        Permission.ITEM_REQUEST_READ,
        Permission.ITEM_REQUEST_CREATE,
        Permission.ITEM_REQUEST_SUBMIT,
        Permission.ITEM_REQUEST_CANCEL,
        Permission.ITEM_APPROVE,
        Permission.ITEM_REJECT,
        Permission.VENDOR_READ,
        Permission.VENDOR_MANAGE,
        Permission.DEPARTMENT_READ,
        Permission.DEPARTMENT_MANAGE,
        Permission.UOM_READ,
        Permission.UOM_MANAGE,
        Permission.ALIAS_CREATE,
        Permission.ALIAS_APPROVE,
        Permission.ALIAS_DEACTIVATE,
        # Ledger & Module Visibility
        Permission.LEDGER_READ,
        Permission.RECEIPT_READ,
        Permission.ISSUE_READ,
        Permission.WASTE_READ,
        Permission.HEAT_LOG_READ,
        Permission.COSTING_READ,
    },
}


class AuthenticatedUser(BaseModel):
    """
    Verified identity of the caller, produced only by an AuthProvider.
    Never construct this from request headers, query parameters or bodies.
    """
    user_id: str
    role: UserRole
    department: str


# Backward-compatible name used by services and endpoints.
DevUserContext = AuthenticatedUser


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_context(request: Request) -> AuthenticatedUser:
    """
    FastAPI dependency returning the verified caller, or raising 401.
    Delegates to the configured AuthProvider; fails closed when none is configured.
    """
    # Imported lazily: auth.py imports UserRole/AuthenticatedUser from this module.
    from app.core.auth import get_auth_provider

    user: Optional[AuthenticatedUser] = get_auth_provider().authenticate(request)
    if user is None:
        raise _unauthorized("Authentication required: missing, invalid or expired credentials.")
    return user


def require_permission(required_permission: Permission, admin_bypass: bool = True):
    """
    Dependency generator enforcing authentication (401) and granular authorization (403).
    Superuser rule: Admin holds universal authority to inspect, create, and audit all data.
    `admin_bypass=False` is for segregation-of-duty steps (QA sign-off, payment) that even Admin may not perform.
    """
    def permission_checker(user: AuthenticatedUser = Depends(get_current_user_context)) -> AuthenticatedUser:
        if admin_bypass and user.role == UserRole.ADMIN:
            return user
        user_permissions = ROLE_PERMISSIONS.get(user.role, set())
        if required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Role '{user.role.value}' lacks permission '{required_permission.value}'",
            )
        return user

    return permission_checker


def get_current_user_role(context: AuthenticatedUser = Depends(get_current_user_context)) -> str:
    """Helper dependency returning the verified role string."""
    return context.role.value


def get_current_user_id(context: AuthenticatedUser = Depends(get_current_user_context)) -> str:
    """Helper dependency returning the verified user id string."""
    return context.user_id
