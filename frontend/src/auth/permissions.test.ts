import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import type { ModuleId, UserRole } from '../types.ts';
import {
  MODULE_REQUIRED_PERMISSIONS,
  ROLE_PERMISSIONS,
  canAccessModule,
  hasAllPermissions,
  hasPermission,
} from './permissions.ts';

const ALL_ROLES: readonly UserRole[] = ['Stores', 'Foundry', 'Purchase', 'Management', 'Admin', 'Quality', 'Accounts'];

const ALL_MODULES = Object.keys(MODULE_REQUIRED_PERMISSIONS) as ModuleId[];

describe('Frontend RBAC Permissions & Module Gating (QA-01)', () => {
  it('covers all 25 modules in MODULE_REQUIRED_PERMISSIONS', () => {
    assert.equal(ALL_MODULES.length, 25);
  });

  it('shows the User Management module to the Admin role only (permission user:manage)', () => {
    assert.deepEqual(MODULE_REQUIRED_PERMISSIONS.users, ['user:manage']);
    for (const role of ALL_ROLES) {
      assert.equal(canAccessModule(role, 'users'), role === 'Admin', `${role} on users`);
      assert.equal(hasPermission(role, 'user:manage'), role === 'Admin', `${role} user:manage`);
    }
    assert.equal(canAccessModule(null, 'users'), false);
    assert.equal(canAccessModule(undefined, 'users'), false);
  });

  it('allows unauthenticated (null/undefined) users only public dashboard and system-health modules', () => {
    const publicModules = ALL_MODULES.filter((m) => canAccessModule(null, m));
    assert.deepEqual(publicModules.sort(), ['dashboard', 'system-health']);
    assert.equal(canAccessModule(undefined, 'references'), false);
    assert.equal(canAccessModule(null, 'material-master'), false);
    assert.equal(canAccessModule(null, 'purchase-orders'), false);
    assert.equal(hasPermission(null, 'audit:read'), false);
    assert.equal(hasAllPermissions(undefined, ['department:read', 'uom:read']), false);
  });

  it('enforces Condition 1: Purchase Orders strictly follows receipt:* backend permissions', () => {
    // Only Foundry lacks receipt:read; Stores, Purchase, Management, Admin can view POs
    assert.equal(canAccessModule('Stores', 'purchase-orders'), true);
    assert.equal(canAccessModule('Foundry', 'purchase-orders'), false);
    assert.equal(canAccessModule('Purchase', 'purchase-orders'), true);
    assert.equal(canAccessModule('Management', 'purchase-orders'), true);
    assert.equal(canAccessModule('Admin', 'purchase-orders'), true);

    // Only Stores holds receipt:create
    assert.equal(hasPermission('Stores', 'receipt:create'), true);
    assert.equal(hasPermission('Purchase', 'receipt:create'), false);
    assert.equal(hasPermission('Management', 'receipt:create'), false);
    assert.equal(hasPermission('Admin', 'receipt:create'), false);

    // Only Management holds receipt:approve
    assert.equal(hasPermission('Management', 'receipt:approve'), true);
    assert.equal(hasPermission('Admin', 'receipt:approve'), false);
    assert.equal(hasPermission('Stores', 'receipt:approve'), false);
    assert.equal(hasPermission('Purchase', 'receipt:approve'), false);
  });

  it('enforces Condition 2: System Health is public, Strict DB Check requires audit:read', () => {
    assert.equal(canAccessModule(null, 'system-health'), true);
    for (const role of ALL_ROLES) {
      assert.equal(canAccessModule(role, 'system-health'), true);
    }
    assert.equal(hasPermission(null, 'audit:read'), false);
    assert.equal(hasPermission('Stores', 'audit:read'), false);
    assert.equal(hasPermission('Foundry', 'audit:read'), false);
    assert.equal(hasPermission('Purchase', 'audit:read'), false);
    assert.equal(hasPermission('Management', 'audit:read'), true);
    assert.equal(hasPermission('Admin', 'audit:read'), true);
  });

  it('matches backend separation of operational approvals vs Admin permissions', () => {
    // Costing calculation: Management only, not Admin
    assert.equal(hasPermission('Management', 'costing:calculate'), true);
    assert.equal(hasPermission('Admin', 'costing:calculate'), false);

    // Opening balances: Management only (QA-05/06 preserved untouched)
    assert.equal(canAccessModule('Management', 'opening-balances'), true);
    assert.equal(canAccessModule('Stores', 'opening-balances'), false);
    assert.equal(canAccessModule('Admin', 'opening-balances'), false);

    // Heat log creation & reconciliation: Foundry & Management only, not Admin
    assert.equal(hasPermission('Foundry', 'heat_log:create'), true);
    assert.equal(hasPermission('Management', 'heat_log:create'), true);
    assert.equal(hasPermission('Admin', 'heat_log:create'), false);
    assert.equal(hasPermission('Foundry', 'heat:reconcile'), true);
    assert.equal(hasPermission('Management', 'heat:reconcile'), true);
    assert.equal(hasPermission('Admin', 'heat:reconcile'), false);

    // Heat exception resolution: Management only
    assert.equal(hasPermission('Management', 'heat:exception_resolve'), true);
    assert.equal(hasPermission('Foundry', 'heat:exception_resolve'), false);
    assert.equal(hasPermission('Admin', 'heat:exception_resolve'), false);

    // Alias deactivate: Stores, Management, Admin (not Foundry)
    assert.equal(hasPermission('Foundry', 'alias:deactivate'), false);
    assert.equal(hasPermission('Stores', 'alias:deactivate'), true);
    assert.equal(hasPermission('Management', 'alias:deactivate'), true);
    assert.equal(hasPermission('Admin', 'alias:deactivate'), true);

    // Vendor manage: Purchase & Admin only
    assert.equal(hasPermission('Purchase', 'vendor:manage'), true);
    assert.equal(hasPermission('Admin', 'vendor:manage'), true);
    assert.equal(hasPermission('Stores', 'vendor:manage'), false);
    assert.equal(hasPermission('Management', 'vendor:manage'), false);
  });

  it('keeps Purchase role strictly scoped to purchase modules', () => {
    const allowed = ALL_MODULES.filter((m) => canAccessModule('Purchase', m));
    assert.equal(allowed.includes('material-issue'), false);
    assert.equal(allowed.includes('waste-disposition'), false);
    assert.equal(allowed.includes('heat-log'), false);
    assert.equal(allowed.includes('costing'), false);
    assert.equal(allowed.includes('excel-import'), false);
    assert.equal(allowed.includes('opening-balances'), false);
    assert.equal(ROLE_PERMISSIONS.Purchase.has('vendor:manage'), true);
  });
});
