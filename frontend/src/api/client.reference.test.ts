import test from 'node:test';
import assert from 'node:assert/strict';
import { fetchAllPages, fetchList, fetchReferenceItems, fetchReferenceUoms, validateRecords } from './client.ts';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const item = (id: number) => ({ id, item_code: `FDY-RM-${id}`, name: `Item ${id}`, base_uom_id: 1 });

/** Serves `total` items in pages of the requested size and records every URL requested. */
function pagedItems(total: number) {
  const urls: string[] = [];
  const fetcher = async (input: string) => {
    urls.push(input);
    const params = new URL(input, 'http://test').searchParams;
    const page = Number(params.get('page'));
    const size = Number(params.get('size'));
    const start = (page - 1) * size;
    const rows = Array.from({ length: Math.max(0, Math.min(size, total - start)) }, (_, i) => item(start + i + 1));
    return json({ items: rows, total, page, size });
  };
  return { urls, fetcher };
}

test('fetchAllPages retrieves every page up to the reported total', async () => {
  const { urls, fetcher } = pagedItems(2500);
  const rows = await fetchAllPages<{ id: number }>('/api/v1/items', 'material items', { id: 'number' }, { fetcher });
  assert.equal(rows.length, 2500);
  assert.deepEqual(urls, [
    '/api/v1/items?page=1&size=1000',
    '/api/v1/items?page=2&size=1000',
    '/api/v1/items?page=3&size=1000',
  ]);
});

test('fetchAllPages stops after one request when the list is empty', async () => {
  const { urls, fetcher } = pagedItems(0);
  const rows = await fetchAllPages('/api/v1/items', 'material items', {}, { fetcher });
  assert.deepEqual(rows, []);
  assert.equal(urls.length, 1);
});

test('fetchAllPages appends paging parameters to an existing query string', async () => {
  const { urls, fetcher } = pagedItems(3);
  await fetchAllPages('/api/v1/items?category=RAW_MATERIAL', 'material items', {}, { fetcher, pageSize: 2 });
  assert.deepEqual(urls, [
    '/api/v1/items?category=RAW_MATERIAL&page=1&size=2',
    '/api/v1/items?category=RAW_MATERIAL&page=2&size=2',
  ]);
});

test('fetchAllPages rejects a short read instead of returning a partial list', async () => {
  const fetcher = async (input: string) =>
    input.includes('page=1') ? json({ items: [item(1)], total: 5, page: 1, size: 1 }) : json({ items: [], total: 5 });
  await assert.rejects(
    fetchAllPages('/api/v1/items', 'material items', {}, { fetcher, pageSize: 1 }),
    /Incomplete material items list: server reported 5 records but returned 1/,
  );
});

test('fetchAllPages rejects a bare array or a missing total', async () => {
  await assert.rejects(
    fetchAllPages('/api/v1/items', 'material items', {}, { fetcher: async () => json([item(1)]) }),
    /Invalid material items response contract/,
  );
  await assert.rejects(
    fetchAllPages('/api/v1/items', 'material items', {}, { fetcher: async () => json({ items: [] }) }),
    /Invalid material items response contract/,
  );
});

test('fetchAllPages surfaces the API error detail for a failed page', async () => {
  const fetcher = async () => json({ detail: 'Insufficient permissions' }, 403);
  await assert.rejects(fetchAllPages('/api/v1/vendors', 'vendors', {}, { fetcher }), /Insufficient permissions/);
});

test('fetchAllPages keeps one record per id when pages overlap', async () => {
  const pages: Record<string, unknown> = {
    '1': { items: [item(1), item(2)], total: 4 },
    '2': { items: [item(2), item(3)], total: 4 },
  };
  const fetcher = async (input: string) => json(pages[new URL(input, 'http://test').searchParams.get('page')!]);
  const rows = await fetchAllPages<{ id: number }>('/api/v1/items', 'material items', {}, { fetcher, pageSize: 2 });
  assert.deepEqual(rows.map((r) => r.id), [1, 2, 3]);
});

test('fetchReferenceItems validates item fields used by the dropdowns', async () => {
  const fetcher = async () => json({ items: [item(1), { id: 2, name: 'No code', base_uom_id: 1 }], total: 2 });
  await assert.rejects(fetchReferenceItems(fetcher), /Invalid material items record at index 1: 'item_code' must be a string/);
});

test('fetchList returns a validated array and rejects an envelope', async () => {
  const uoms = [{ id: 1, code: 'KG', name: 'Kilograms' }];
  assert.deepEqual(await fetchReferenceUoms(async () => json(uoms)), uoms);
  await assert.rejects(
    fetchList('/api/v1/uoms', 'units of measure', {}, async () => json({ items: uoms })),
    /Invalid units of measure response contract: expected an array, got object/,
  );
  await assert.rejects(fetchReferenceUoms(async () => json(null)), /expected an array, got null/);
});

test('validateRecords rejects non-object rows', () => {
  assert.throws(() => validateRecords([1], 'departments', { id: 'number' }), /Invalid departments record at index 0/);
});
