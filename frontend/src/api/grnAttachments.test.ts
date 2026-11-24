import test from 'node:test';
import assert from 'node:assert/strict';
import {
  formatFileSize,
  listGrnAttachments,
  uploadGrnAttachment,
  uploadManyGrnAttachments,
  validateAttachmentFile,
} from './grnAttachments.ts';

const realFetch = globalThis.fetch;
function mockFetch(handler: (url: string, init: RequestInit) => Response): { calls: Array<{ url: string; init: RequestInit }> } {
  const calls: Array<{ url: string; init: RequestInit }> = [];
  globalThis.fetch = (async (url: string, init: RequestInit = {}) => {
    calls.push({ url: String(url), init });
    return handler(String(url), init);
  }) as typeof fetch;
  return { calls };
}
test.afterEach(() => {
  globalThis.fetch = realFetch;
});

test('validateAttachmentFile accepts allowed types and rejects the rest', () => {
  assert.equal(validateAttachmentFile({ name: 'Invoice 42.PDF', size: 1000 }), null);
  assert.equal(validateAttachmentFile({ name: 'photo.jpeg', size: 1000 }), null);
  assert.match(validateAttachmentFile({ name: 'run.exe', size: 1000 })!, /not allowed/);
  assert.match(validateAttachmentFile({ name: 'noextension', size: 1000 })!, /not allowed/);
  assert.match(validateAttachmentFile({ name: 'big.pdf', size: 11 * 1024 * 1024 })!, /larger than 10 MB/);
  assert.match(validateAttachmentFile({ name: 'empty.pdf', size: 0 })!, /empty/);
});

test('formatFileSize is human readable', () => {
  assert.equal(formatFileSize(512), '512 B');
  assert.equal(formatFileSize(2048), '2.0 KB');
  assert.equal(formatFileSize(5 * 1024 * 1024), '5.0 MB');
});

test('uploadGrnAttachment posts multipart form data without forcing a content type', async () => {
  const { calls } = mockFetch(() =>
    new Response(JSON.stringify({ id: 7, grn_id: 3, original_filename: 'a.pdf' }), { status: 201, headers: { 'content-type': 'application/json' } }),
  );
  const file = new File([new Uint8Array([37, 80, 68, 70])], 'a.pdf', { type: 'application/pdf' });
  const result = await uploadGrnAttachment(3, file, '  Original invoice ');
  assert.equal(result.id, 7);
  assert.equal(calls[0].url, '/api/v1/grn/3/attachments');
  assert.equal(calls[0].init.method, 'POST');
  assert.ok(calls[0].init.body instanceof FormData);
  const form = calls[0].init.body as FormData;
  assert.equal((form.get('file') as File).name, 'a.pdf');
  assert.equal(form.get('description'), 'Original invoice');
  assert.equal(new Headers(calls[0].init.headers).has('Content-Type'), false);
});

test('upload errors carry the server message', async () => {
  mockFetch(() => new Response(JSON.stringify({ detail: 'The file content does not match its type.' }), { status: 422, headers: { 'content-type': 'application/json' } }));
  await assert.rejects(() => uploadGrnAttachment(3, new File(['x'], 'fake.pdf')), /does not match its type/);
});

test('uploadManyGrnAttachments keeps going after a failure and reports each reason', async () => {
  let n = 0;
  mockFetch(() => {
    n += 1;
    return n === 2
      ? new Response(JSON.stringify({ detail: 'A GRN can have at most 10 documents.' }), { status: 409, headers: { 'content-type': 'application/json' } })
      : new Response(JSON.stringify({ id: n }), { status: 201, headers: { 'content-type': 'application/json' } });
  });
  const files = ['a.pdf', 'b.pdf', 'c.pdf'].map((name) => new File(['x'], name));
  const out = await uploadManyGrnAttachments(9, files);
  assert.equal(out.uploaded, 2);
  assert.deepEqual(out.failures, ['A GRN can have at most 10 documents.']);
});

test('listGrnAttachments returns an array and surfaces errors', async () => {
  mockFetch(() => new Response(JSON.stringify([{ id: 1 }]), { status: 200, headers: { 'content-type': 'application/json' } }));
  assert.equal((await listGrnAttachments(1)).length, 1);
  mockFetch(() => new Response(JSON.stringify({ detail: 'Access denied' }), { status: 403, headers: { 'content-type': 'application/json' } }));
  await assert.rejects(() => listGrnAttachments(1), /Access denied/);
});
