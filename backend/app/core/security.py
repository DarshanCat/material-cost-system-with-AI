"""
VSPL Security & RBAC Architectural Foundation.

Role-Based Access Control (RBAC) Specification:
- Stores: Material receipts (GRNs), material issues, scrap/waste logs, physical stock audit entries.
- Foundry: Heat logs, charge detail logging, issue-to-heat reconciliation view, foundry inventory view.
- Purchase: Vendor master management, purchase rates verification, PO tracking.
- Management: Costing reports, variance analysis, executive dashboards, inventory valuation.
- Admin: User lifecycle, role assignments, master approval requests, system audit logs.

CRITICAL ARCHITECTURAL DIRECTIVE:
Frontend route hiding is NOT security. Backend route and service dependencies
must enforce authentication tokens and role permission scopes at the API layer.
No hardcoded credentials or bypass backdoors are permitted.
"""

from enum import Enum
from typing import Set


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

    # Master Data & Approvals
    ITEM_CREATE = "item:create"
    ITEM_APPROVE = "item:approve"
    VENDOR_MANAGE = "vendor:manage"

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


# Role-to-Permissions Mapping matrix for subsequent Authentication phase implementation
ROLE_PERMISSIONS: dict[UserRole, Set[Permission]] = {
    UserRole.STORES: {
        Permission.RECEIPT_CREATE,
        Permission.RECEIPT_READ,
        Permission.ISSUE_CREATE,
        Permission.ISSUE_READ,
        Permission.WASTE_LOG,
        Permission.LEDGER_READ,
        Permission.STOCK_ADJUST,
    },
    UserRole.FOUNDRY: {
        Permission.HEAT_LOG_CREATE,
        Permission.HEAT_LOG_READ,
        Permission.HEAT_RECONCILE,
        Permission.ISSUE_READ,
        Permission.LEDGER_READ,
    },
    UserRole.PURCHASE: {
        Permission.VENDOR_MANAGE,
        Permission.ITEM_CREATE,
        Permission.RECEIPT_READ,
        Permission.LEDGER_READ,
    },
    UserRole.MANAGEMENT: {
        Permission.RECEIPT_READ,
        Permission.ISSUE_READ,
        Permission.LEDGER_READ,
        Permission.HEAT_LOG_READ,
        Permission.COSTING_READ,
        Permission.COSTING_CALCULATE,
        Permission.AUDIT_READ,
    },
    UserRole.ADMIN: set(Permission),  # All permissions
}
