import test from 'node:test';
import assert from 'node:assert/strict';
import { IMPLEMENTATION_ROADMAP } from './roadmap.ts';

test('roadmap contains exactly 6 structured phases', () => {
  assert.equal(IMPLEMENTATION_ROADMAP.length, 6);
  const ids = IMPLEMENTATION_ROADMAP.map((p) => p.id);
  assert.deepEqual(ids, [1, 2, 3, 4, 5, 6]);
});

test('Phases 1-3 are marked completed and operational', () => {
  for (let i = 0; i < 3; i++) {
    const phase = IMPLEMENTATION_ROADMAP[i];
    assert.equal(phase.implementationStatus, 'COMPLETED', `${phase.number} implementation must be COMPLETED`);
    assert.equal(phase.approvalStatus, 'OPERATIONAL', `${phase.number} approval must be OPERATIONAL`);
  }
});

test('Phase 4 reflects implemented code but pending opening-stock sign-off', () => {
  const phase4 = IMPLEMENTATION_ROADMAP.find((p) => p.id === 4);
  assert.ok(phase4, 'Phase 4 must exist');
  assert.equal(phase4.implementationStatus, 'IMPLEMENTED');
  assert.equal(phase4.approvalStatus, 'PENDING_APPROVAL');
  assert.notEqual(phase4.approvalStatus, 'OPERATIONAL', 'Phase 4 must not be marked operational without opening-stock certification');
  assert.equal(phase4.moduleId, 'inventory-ledger');
});

test('Phase 5 reflects implemented code and is NOT queued', () => {
  const phase5 = IMPLEMENTATION_ROADMAP.find((p) => p.id === 5);
  assert.ok(phase5, 'Phase 5 must exist');
  assert.equal(phase5.implementationStatus, 'IMPLEMENTED');
  assert.notEqual(phase5.implementationStatus, 'QUEUED', 'Phase 5 must not be marked QUEUED when code and tests exist');
  assert.equal(phase5.approvalStatus, 'PENDING_UAT');
  assert.equal(phase5.approvalLabel, 'PENDING UAT & SIGN-OFF');
  assert.notEqual(phase5.approvalStatus, 'OPERATIONAL', 'Phase 5 must not be marked operational without UAT sign-off');
  assert.equal(phase5.moduleId, 'heat-reconciliation');
});

test('Phase 6 reflects implemented costing engine awaiting live ledger data', () => {
  const phase6 = IMPLEMENTATION_ROADMAP.find((p) => p.id === 6);
  assert.ok(phase6, 'Phase 6 must exist');
  assert.equal(phase6.implementationStatus, 'IMPLEMENTED');
  assert.equal(phase6.approvalStatus, 'QUEUED_FOR_DATA');
  assert.notEqual(phase6.approvalStatus, 'OPERATIONAL', 'Phase 6 must not be marked operational before live ledger data');
  assert.equal(phase6.moduleId, 'costing');
});

test('All phases with interactive modules have valid navigation identifiers', () => {
  const validModules = new Set([
    'material-master',
    'grn-management',
    'inventory-ledger',
    'heat-reconciliation',
    'costing',
  ]);

  for (const phase of IMPLEMENTATION_ROADMAP) {
    if (phase.moduleId) {
      assert.ok(
        validModules.has(phase.moduleId),
        `Module ${phase.moduleId} in ${phase.number} must be a known module id`
      );
    }
  }
});
