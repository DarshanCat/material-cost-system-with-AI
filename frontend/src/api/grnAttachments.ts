/** Supporting documents (vendor invoice, delivery challan, test certificate, photos) attached to a GRN. */
import { apiFetch, readApiError } from './client.ts';

export interface GrnAttachment {
  id: number;
  grn_id: number;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  description: string | null;
  uploaded_by: string;
  uploaded_at: string;
}

export const ATTACHMENT_MAX_MB = 10;
export const ATTACHMENT_MAX_PER_GRN = 10;
export const ATTACHMENT_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'docx'] as const;
/** For the file picker's `accept` attribute. */
export const ATTACHMENT_ACCEPT = ATTACHMENT_EXTENSIONS.map((e) => `.${e}`).join(',');

/** The same checks the server makes (the server remains the authority); used to fail fast in the browser. */
export function validateAttachmentFile(file: { name: string; size: number }): string | null {
  if (file.size === 0) return `${file.name}: the file is empty.`;
  if (file.size > ATTACHMENT_MAX_MB * 1024 * 1024) return `${file.name}: larger than ${ATTACHMENT_MAX_MB} MB.`;
  const ext = file.name.includes('.') ? file.name.split('.').pop()!.toLowerCase() : '';
  if (!(ATTACHMENT_EXTENSIONS as readonly string[]).includes(ext)) {
    return `${file.name}: this file type is not allowed. Allowed: ${ATTACHMENT_EXTENSIONS.join(', ')}.`;
  }
  return null;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export async function listGrnAttachments(grnId: number): Promise<GrnAttachment[]> {
  const res = await apiFetch(`/api/v1/grn/${grnId}/attachments`);
  if (!res.ok) throw new Error(await readApiError(res, 'Could not load the documents'));
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function uploadGrnAttachment(grnId: number, file: File, description?: string): Promise<GrnAttachment> {
  const form = new FormData();
  form.append('file', file);
  if (description && description.trim()) form.append('description', description.trim());
  // No Content-Type header: the browser adds the multipart boundary itself.
  const res = await apiFetch(`/api/v1/grn/${grnId}/attachments`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(await readApiError(res, `Could not upload ${file.name}`));
  return res.json();
}

export async function deleteGrnAttachment(grnId: number, attachmentId: number): Promise<void> {
  const res = await apiFetch(`/api/v1/grn/${grnId}/attachments/${attachmentId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(await readApiError(res, 'Could not remove the document'));
}

/** Downloads through the authenticated API (a plain link could not carry the sign-in token). */
export async function downloadGrnAttachment(grnId: number, attachment: GrnAttachment): Promise<void> {
  const res = await apiFetch(`/api/v1/grn/${grnId}/attachments/${attachment.id}/download`);
  if (!res.ok) throw new Error(await readApiError(res, 'Could not download the document'));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement('a');
    link.href = url;
    link.download = attachment.original_filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  }
}

/** Uploads several files one by one; returns how many succeeded and the reasons for the others. */
export async function uploadManyGrnAttachments(
  grnId: number,
  files: File[],
): Promise<{ uploaded: number; failures: string[] }> {
  let uploaded = 0;
  const failures: string[] = [];
  for (const file of files) {
    try {
      await uploadGrnAttachment(grnId, file);
      uploaded += 1;
    } catch (err) {
      failures.push(err instanceof Error ? err.message : `Could not upload ${file.name}`);
    }
  }
  return { uploaded, failures };
}
