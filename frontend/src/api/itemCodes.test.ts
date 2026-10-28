import test from 'node:test';
import assert from 'node:assert/strict';
import {
  canSubmitPreview,
  categoriesForDepartment,
  categoryLabel,
  describeDuplicate,
  issuesForField,
  parseItemCodeError,
} from './itemCodes.ts';
import type { ItemCodePreview, ItemCodeRules } from '../types';

const rules = {
  categories: [
    { code: 'RM', name: 'Raw Material', department_code: 'FDY', cost_head: 'Material Cost', pattern: '', example: '', verbatim_description: false },
    { code: 'CN', name: 'Consumables', department_code: 'FDY', cost_head: 'Foundry Consumables', pattern: '', example: '', verbatim_description: false },
    { code: 'BN', name: 'Bolts & Nuts', department_code: 'MNT', cost_head: 'Maintenance Cost', pattern: '', example: '', verbatim_description: false },
  ],
} as unknown as ItemCodeRules;

const preview = (overrides: Partial<ItemCodePreview>): ItemCodePreview =>
  ({ valid: true, errors: [], warnings: [], duplicates: [], ...overrides }) as ItemCodePreview;

test('categoriesForDepartment returns only categories owned by the department', () => {
  assert.deepEqual(categoriesForDepartment(rules, 'FDY').map((c) => c.code), ['RM', 'CN']);
  assert.deepEqual(categoriesForDepartment(rules, 'MSP'), []);
  assert.deepEqual(categoriesForDepartment(null, 'FDY'), []);
});

test('categoryLabel shows v1.0 categories and flags legacy values without mapping them', () => {
  assert.equal(categoryLabel(rules, 'BN'), 'BN · Bolts & Nuts');
  assert.equal(categoryLabel(rules, 'bolts & nuts'), 'BN · Bolts & Nuts');
  assert.equal(categoryLabel(rules, 'RAW_MATERIAL'), 'RAW_MATERIAL (not in v1.0)');
});

test('parseItemCodeError handles structured, string and validation-list details', () => {
  const structured = parseItemCodeError(
    { detail: { message: 'Item request rejected', errors: [{ field: 'uom', code: 'not_in_standard', message: 'Use Kg' }] } },
    'fallback',
  );
  assert.equal(structured.message, 'Item request rejected');
  assert.equal(structured.errors[0].field, 'uom');

  assert.deepEqual(parseItemCodeError({ detail: 'Self-approval violation' }, 'fallback'), {
    message: 'Self-approval violation',
    errors: [],
    duplicates: [],
  });

  const list = parseItemCodeError({ detail: [{ loc: ['body', 'justification'], msg: 'too short', type: 'string_too_short' }] }, 'Invalid');
  assert.equal(list.message, 'Invalid');
  assert.deepEqual(list.errors[0], { field: 'justification', code: 'string_too_short', message: 'too short' });

  assert.equal(parseItemCodeError(null, 'fallback').message, 'fallback');
});

test('canSubmitPreview requires a valid preview without blocking duplicates', () => {
  assert.equal(canSubmitPreview(null), false);
  assert.equal(canSubmitPreview(preview({})), true);
  assert.equal(canSubmitPreview(preview({ valid: false })), false);
  const dup = { source: 'ITEM', match_type: 'EXACT', name: 'Nut M12', blocking: true } as const;
  assert.equal(canSubmitPreview(preview({ duplicates: [dup] })), false);
  assert.equal(canSubmitPreview(preview({ duplicates: [{ ...dup, source: 'REQUEST', blocking: false }] })), true);
});

test('issuesForField and describeDuplicate', () => {
  const issues = [
    { field: 'uom', code: 'x', message: 'a' },
    { field: 'description', code: 'y', message: 'b' },
  ];
  assert.deepEqual(issuesForField(issues, 'uom').map((i) => i.message), ['a']);
  assert.equal(
    describeDuplicate({ source: 'ITEM', match_type: 'EXACT', name: 'Nut M12', item_code: 'MNT-BN-001', is_active: false, blocking: true }),
    'MNT-BN-001 (retired): Nut M12',
  );
  assert.equal(
    describeDuplicate({ source: 'REQUEST', match_type: 'EXACT', name: 'Nut M12', request_number: 'REQ-1', request_status: 'DRAFT', blocking: false }),
    'Request REQ-1 (DRAFT): Nut M12',
  );
});
