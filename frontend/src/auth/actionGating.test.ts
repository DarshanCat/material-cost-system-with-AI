import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import type { UserRole } from '../types.ts';
import { ROLE_PERMISSIONS, hasPermission, type PermissionName } from './permissions.ts';

const ALL_ROLES: readonly UserRole[] = ['Stores', 'Foundry', 'Purchase', 'Management', 'Admin', 'Quality', 'Accounts'];

/**
 * Who holds each action permission, mirrored from backend `ROLE_PERMISSIONS` (security.py).
 * A button is shown only to these roles, so every role's screen shows exactly what it can do.
 */
const ACTION_HOLDERS: Record<string, readonly UserRole[]> = {
  'receipt:create': ['Stores'],
  'receipt:approve': ['Management'],
  'issue:create': ['Stores'],
  'issue:approve': ['Management'],
  'waste:log': ['Stores'],
  'waste:approve': ['Management'],
  'stock:adjust': ['Stores'],
  'stock_audit:approve': ['Management'],
  'opening_balance:post': ['Management'],
  'heat_log:create': ['Foundry', 'Management'],
  'heat:reconcile': ['Foundry', 'Management'],
  'costing:calculate': ['Management'],
  'vendor:manage': ['Purchase', 'Admin'],
  'department:manage': ['Management', 'Admin'],
  'uom:manage': ['Management', 'Admin'],
};

describe('Action-level gating follows the backend permission model', () => {
  for (const [permission, holders] of Object.entries(ACTION_HOLDERS)) {
    it(`${permission} is held only by ${holders.join(', ')}`, () => {
      const actual = ALL_ROLES.filter((role) => hasPermission(role, permission as PermissionName));
      assert.deepEqual([...actual].sort(), [...holders].sort());
    });
  }

  it('Admin holds none of the operational create, approve or posting permissions', () => {
    const operational = [
      'receipt:create', 'receipt:approve', 'issue:create', 'issue:approve', 'waste:log', 'waste:approve',
      'stock:adjust', 'stock_audit:approve', 'opening_balance:post', 'heat_log:create', 'heat:reconcile',
      'costing:calculate', 'ledger:reverse',
    ] as PermissionName[];
    for (const permission of operational) {
      assert.equal(ROLE_PERMISSIONS.Admin.has(permission), false, `Admin must not hold ${permission}`);
    }
  });

  it('no view lets the Admin role bypass a permission check by name', () => {
    const dir = new URL('../components/', import.meta.url);
    const offenders: string[] = [];
    for (const file of readdirSync(dir).filter((name) => name.endsWith('.tsx'))) {
      const source = readFileSync(new URL(file, dir), 'utf8');
      if (/hasPermission\([^)]*\)\s*\|\|\s*currentRole\s*===/.test(source)) offenders.push(file);
    }
    assert.deepEqual(offenders, [], `permission checks must not be overridden by role name: ${offenders.join(', ')}`);
  });
});
