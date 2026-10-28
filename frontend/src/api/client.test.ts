import test from 'node:test';
import assert from 'node:assert/strict';
import { extractItems } from './client.ts';

test('extractItems unwraps PaginatedResponse envelope with items array', () => {
  const envelope = {
    items: [
      { id: 1, item_code: 'FDY-RM-001', name: 'Pig Iron Grade 1' },
      { id: 2, item_code: 'FDY-RM-002', name: 'Pig Iron Grade 2' },
    ],
    total: 2,
    page: 1,
    size: 25,
  };

  const result = extractItems<any>(envelope);
  assert.equal(Array.isArray(result), true);
  assert.equal(result.length, 2);
  assert.equal(result[0].item_code, 'FDY-RM-001');
  assert.equal(result[1].item_code, 'FDY-RM-002');
});

test('extractItems handles direct array without envelope', () => {
  const arrayPayload = [
    { id: 10, code: 'KG', name: 'Kilograms' },
    { id: 20, code: 'NOS', name: 'Numbers' },
  ];

  const result = extractItems<any>(arrayPayload);
  assert.equal(Array.isArray(result), true);
  assert.equal(result.length, 2);
  assert.equal(result[0].code, 'KG');
});

test('extractItems throws contract error on null or undefined instead of returning empty array', () => {
  assert.throws(
    () => extractItems(null),
    /Invalid items response contract: expected array or { items: \[...\] }, got null/
  );
  assert.throws(
    () => extractItems(undefined),
    /Invalid items response contract: expected array or { items: \[...\] }, got undefined/
  );
});

test('extractItems throws contract error on primitive types', () => {
  assert.throws(
    () => extractItems('string data'),
    /Invalid items response contract/
  );
  assert.throws(
    () => extractItems(12345),
    /Invalid items response contract/
  );
  assert.throws(
    () => extractItems(true),
    /Invalid items response contract/
  );
});

test('extractItems throws contract error on empty object missing items key', () => {
  assert.throws(
    () => extractItems({}),
    /Invalid items response contract/
  );
  assert.throws(
    () => extractItems({ data: [] }),
    /Invalid items response contract/
  );
});

test('extractItems throws contract error when items property is not an array', () => {
  assert.throws(
    () => extractItems({ items: 'not an array' }),
    /Invalid items response contract/
  );
  assert.throws(
    () => extractItems({ items: { 0: 'a' } }),
    /Invalid items response contract/
  );
  assert.throws(
    () => extractItems({ items: null }),
    /Invalid items response contract/
  );
});
