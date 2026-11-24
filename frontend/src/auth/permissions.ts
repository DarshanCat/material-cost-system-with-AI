import type { ModuleId, UserRole } from '../types';

/**
 * Mirrors backend Permission enum in `backend/app/core/security.py`.
 * Read-only mirror for frontend visibility gating; backend endpoints enforce all authority.
 */
export type PermissionName =
  | 'receipt:create'
  | 'receipt:read'
  | 'receipt:approve'
  | 'receipt:quality'
  | 'payment:record'
  | 'issue:create'
  | 'issue:read'
  | 'issue:approve'
  | 'waste:log'
  | 'waste:read'
  | 'waste:approve'
  | 'excel:import'
  | 'item:read'
  | 'item:create'
  | 'item:update'
  | 'item_request:create'
  | 'item_request:submit'
  | 'item_request:cancel'
  | 'item_request:read'
  | 'item:approve'
  | 'item:reject'
  | 'vendor:read'
  | 'vendor:manage'
  | 'department:read'
  | 'department:manage'
  | 'uom:read'
  | 'uom:manage'
  | 'alias:create'
  | 'alias:approve'
  | 'alias:deactivate'
  | 'ledger:read'
  | 'ledger:reverse'
  | 'stock:adjust'
  | 'stock_audit:approve'
  | 'opening_balance:post'
  | 'heat_log:create'
  | 'heat_log:read'
  | 'heat:reconcile'
  | 'heat:exception_resolve'
  | 'costing:read'
  | 'costing:calculate'
  | 'audit:read'
  | 'user:manage';

/**
 * Exact mirror of `ROLE_PERMISSIONS` from `backend/app/core/security.py`.
 */
export const ROLE_PERMISSIONS: Record<UserRole, ReadonlySet<PermissionName>> = {
  Stores: new Set<PermissionName>([
    'receipt:create',
    'receipt:read',
    'issue:create',
    'issue:read',
    'waste:log',
    'waste:read',
    'excel:import',
    'ledger:read',
    'stock:adjust',
    'item:read',
    'item_request:create',
    'item_request:submit',
    'item_request:cancel',
    'item_request:read',
    'vendor:read',
    'department:read',
    'uom:read',
    'alias:create',
    'alias:deactivate',
    'heat_log:read',
  ]),
  Foundry: new Set<PermissionName>([
    'heat_log:create',
    'heat_log:read',
    'heat:reconcile',
    'issue:read',
    'ledger:read',
    'item:read',
    'item_request:create',
    'item_request:submit',
    'item_request:cancel',
    'item_request:read',
    'department:read',
    'uom:read',
    'alias:create',
  ]),
  Purchase: new Set<PermissionName>([
    'vendor:manage',
    'vendor:read',
    'item:read',
    'item_request:create',
    'item_request:submit',
    'item_request:cancel',
    'item_request:read',
    'receipt:read',
    'ledger:read',
    'department:read',
    'uom:read',
  ]),
  Quality: new Set<PermissionName>([
    'receipt:read',
    'receipt:quality',
    'item:read',
    'vendor:read',
    'department:read',
    'uom:read',
  ]),
  Accounts: new Set<PermissionName>([
    'receipt:read',
    'payment:record',
    'item:read',
    'vendor:read',
    'department:read',
    'uom:read',
    'ledger:read',
  ]),
  Management: new Set<PermissionName>([
    'receipt:read',
    'receipt:approve',
    'issue:read',
    'issue:approve',
    'waste:read',
    'waste:approve',
    'ledger:read',
    'ledger:reverse',
    'stock_audit:approve',
    'opening_balance:post',
    'heat_log:create',
    'heat_log:read',
    'heat:reconcile',
    'heat:exception_resolve',
    'costing:read',
    'costing:calculate',
    'audit:read',
    'item:read',
    'item:update',
    'item_request:create',
    'item_request:submit',
    'item_request:cancel',
    'item:approve',
    'item:reject',
    'item_request:read',
    'vendor:read',
    'department:read',
    'department:manage',
    'uom:read',
    'uom:manage',
    'alias:create',
    'alias:approve',
    'alias:deactivate',
  ]),
  Admin: new Set<PermissionName>([
    'user:manage',
    'audit:read',
    'item:read',
    'item:create',
    'item:update',
    'item_request:read',
    'item_request:create',
    'item_request:submit',
    'item_request:cancel',
    'item:approve',
    'item:reject',
    'vendor:read',
    'vendor:manage',
    'department:read',
    'department:manage',
    'uom:read',
    'uom:manage',
    'alias:create',
    'alias:approve',
    'alias:deactivate',
    'ledger:read',
    'receipt:read',
    'issue:read',
    'waste:read',
    'heat_log:read',
    'costing:read',
  ]),
};

/**
 * Required permissions to view each of the 19 modules in the UI.
 * `null` indicates a public module reachable without signing in.
 */
export const MODULE_REQUIRED_PERMISSIONS: Record<ModuleId, readonly PermissionName[] | null> = {
  dashboard: null,
  'heat-master': ['heat_log:read'],
  'material-master': ['item:read'],
  'vendor-master': ['vendor:read'],
  'p2p-cycle': ['receipt:read'],
  'purchase-requests': ['receipt:read'],
  'purchase-orders': ['receipt:read'],
  'item-requests': ['item_request:read'],
  references: ['department:read', 'uom:read'],
  'material-aliases': ['item:read'],
  'grn-management': ['receipt:read'],
  'material-issue': ['issue:read'],
  'return-to-store': ['issue:read'],
  'waste-disposition': ['waste:read'],
  'inventory-ledger': ['ledger:read'],
  'opening-balances': ['opening_balance:post'],
  'physical-audits': ['ledger:read'],
  'heat-log': ['heat_log:read'],
  'heat-reconciliation': ['heat_log:read'],
  'heat-import': ['heat_log:create'],
  'excel-import': ['excel:import'],
  costing: ['costing:read'],
  'system-health': null,
  'roles-responsibilities': ['item:read'],
  // User administration: Admin only (backend permission `user:manage`).
  users: ['user:manage'],
};

/**
 * Strict role-to-module operational scoping.
 * Each operational role only sees the UI & UX modules required for their specific responsibilities.
 */
export const ROLE_ALLOWED_MODULES: Record<UserRole, ReadonlySet<ModuleId>> = {
  Quality: new Set<ModuleId>(['dashboard', 'p2p-cycle', 'grn-management', 'roles-responsibilities', 'system-health']),
  Accounts: new Set<ModuleId>(['dashboard', 'p2p-cycle', 'grn-management', 'inventory-ledger', 'roles-responsibilities', 'system-health']),
  Purchase: new Set<ModuleId>([
    'dashboard',
    'p2p-cycle',
    'purchase-requests',
    'purchase-orders',
    'vendor-master',
    'material-master',
    'item-requests',
    'roles-responsibilities',
    'system-health',
  ]),
  Stores: new Set<ModuleId>([
    'dashboard',
    'heat-master',
    'p2p-cycle',
    'purchase-requests',
    'purchase-orders',
    'grn-management',
    'material-issue',
    'return-to-store',
    'waste-disposition',
    'inventory-ledger',
    'physical-audits',
    'material-master',
    'item-requests',
    'material-aliases',
    'roles-responsibilities',
    'system-health',
  ]),
  Foundry: new Set<ModuleId>([
    'dashboard',
    'heat-master',
    'heat-log',
    'heat-reconciliation',
    'heat-import',
    'material-issue',
    'return-to-store',
    'material-aliases',
    'material-master',
    'item-requests',
    'roles-responsibilities',
    'system-health',
  ]),
  Management: new Set<ModuleId>([
    'dashboard',
    'heat-master',
    'p2p-cycle',
    'material-master',
    'vendor-master',
    'purchase-requests',
    'purchase-orders',
    'item-requests',
    'references',
    'material-aliases',
    'grn-management',
    'material-issue',
    'return-to-store',
    'waste-disposition',
    'inventory-ledger',
    'opening-balances',
    'physical-audits',
    'heat-log',
    'heat-reconciliation',
    'heat-import',
    'excel-import',
    'costing',
    'roles-responsibilities',
    'system-health',
  ]),
  Admin: new Set<ModuleId>([
    'dashboard',
    'heat-master',
    'p2p-cycle',
    'material-master',
    'vendor-master',
    'purchase-requests',
    'purchase-orders',
    'item-requests',
    'references',
    'material-aliases',
    'grn-management',
    'material-issue',
    'return-to-store',
    'waste-disposition',
    'inventory-ledger',
    'opening-balances',
    'physical-audits',
    'heat-log',
    'heat-reconciliation',
    'heat-import',
    'excel-import',
    'costing',
    'roles-responsibilities',
    'system-health',
    'users',
  ]),
};

export function hasPermission(role: UserRole | null | undefined, permission: PermissionName): boolean {
  if (!role) return false;
  return ROLE_PERMISSIONS[role]?.has(permission) ?? false;
}

export function hasAllPermissions(
  role: UserRole | null | undefined,
  permissions: readonly PermissionName[]
): boolean {
  if (!role) return false;
  const granted = ROLE_PERMISSIONS[role];
  if (!granted) return false;
  return permissions.every((perm) => granted.has(perm));
}

export function canAccessModule(role: UserRole | null | undefined, moduleId: ModuleId): boolean {
  const required = MODULE_REQUIRED_PERMISSIONS[moduleId];
  if (required === null) return true;
  if (!role) return false;

  // Enforce role-based operational scope
  const allowed = ROLE_ALLOWED_MODULES[role];
  if (allowed && !allowed.has(moduleId)) return false;

  return hasAllPermissions(role, required);
}
