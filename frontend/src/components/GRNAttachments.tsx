import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Paperclip, Download, Trash2, Upload } from 'lucide-react';
import {
  ATTACHMENT_ACCEPT,
  ATTACHMENT_EXTENSIONS,
  ATTACHMENT_MAX_MB,
  ATTACHMENT_MAX_PER_GRN,
  deleteGrnAttachment,
  downloadGrnAttachment,
  formatFileSize,
  listGrnAttachments,
  uploadManyGrnAttachments,
  validateAttachmentFile,
  type GrnAttachment,
} from '../api/grnAttachments';

interface GRNAttachmentsProps {
  grnId: number;
  grnStatus: string;
  canEdit: boolean;
}

/** Documents attached to one GRN: list, download, and (Draft / Submitted) add; (Draft only) remove. */
export const GRNAttachments: React.FC<GRNAttachmentsProps> = ({ grnId, grnStatus, canEdit }) => {
  const [items, setItems] = useState<GrnAttachment[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: 'error' | 'ok'; text: string } | null>(null);
  const picker = useRef<HTMLInputElement>(null);

  const canAdd = canEdit && (grnStatus === 'DRAFT' || grnStatus === 'SUBMITTED');
  const canRemove = canEdit && grnStatus === 'DRAFT';

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await listGrnAttachments(grnId));
    } catch (err) {
      setMessage({ kind: 'error', text: err instanceof Error ? err.message : 'Could not load the documents' });
    } finally {
      setLoading(false);
    }
  }, [grnId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    e.target.value = '';
    if (files.length === 0) return;
    setMessage(null);
    if (items.length + files.length > ATTACHMENT_MAX_PER_GRN) {
      setMessage({ kind: 'error', text: `A GRN can have at most ${ATTACHMENT_MAX_PER_GRN} documents.` });
      return;
    }
    // Upload the valid files; say why the others were left out.
    const problems = files.map(validateAttachmentFile).filter((p): p is string => p !== null);
    const valid = files.filter((f) => validateAttachmentFile(f) === null);
    if (valid.length === 0) {
      setMessage({ kind: 'error', text: problems.join(' ') });
      return;
    }
    setBusy(true);
    const { uploaded, failures } = await uploadManyGrnAttachments(grnId, valid);
    await load();
    setBusy(false);
    const issues = [...problems, ...failures];
    if (issues.length > 0) {
      setMessage({ kind: 'error', text: `${uploaded} added. ${issues.join(' ')}` });
    } else {
      setMessage({ kind: 'ok', text: `${uploaded} document${uploaded === 1 ? '' : 's'} added.` });
    }
  };

  const onDownload = async (a: GrnAttachment) => {
    setMessage(null);
    try {
      await downloadGrnAttachment(grnId, a);
    } catch (err) {
      setMessage({ kind: 'error', text: err instanceof Error ? err.message : 'Could not download the document' });
    }
  };

  const onDelete = async (a: GrnAttachment) => {
    if (!window.confirm(`Remove "${a.original_filename}" from this GRN?`)) return;
    setMessage(null);
    try {
      await deleteGrnAttachment(grnId, a.id);
      await load();
    } catch (err) {
      setMessage({ kind: 'error', text: err instanceof Error ? err.message : 'Could not remove the document' });
    }
  };

  return (
    <div className="audit-card p-3 mb-4 bg-slate-50 border border-slate-200 rounded" data-testid="grn-attachments">
      <div className="flex justify-between items-center mb-2">
        <h4 className="font-semibold text-sm flex items-center gap-1 text-slate-800">
          <Paperclip size={16} className="text-slate-600" /> Documents ({items.length})
        </h4>
        {canAdd && (
          <>
            <input
              ref={picker}
              type="file"
              multiple
              accept={ATTACHMENT_ACCEPT}
              onChange={onPick}
              style={{ display: 'none' }}
              aria-label="Choose documents to attach"
            />
            <button
              type="button"
              className="erp-btn btn-sm btn-primary text-xs"
              disabled={busy || items.length >= ATTACHMENT_MAX_PER_GRN}
              onClick={() => picker.current?.click()}
            >
              <Upload size={13} /> {busy ? 'Uploading...' : 'Add documents'}
            </button>
          </>
        )}
      </div>
      {message && (
        <div
          role={message.kind === 'error' ? 'alert' : 'status'}
          className={`text-xs mb-2 p-2 rounded border ${
            message.kind === 'error' ? 'bg-rose-50 border-rose-200 text-rose-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800'
          }`}
        >
          {message.text}
        </div>
      )}
      {loading ? (
        <p className="text-xs text-slate-500">Loading documents...</p>
      ) : items.length === 0 ? (
        <p className="text-xs text-slate-500">
          No documents attached.{canAdd ? ` Add the vendor invoice, delivery challan or test certificate (${ATTACHMENT_EXTENSIONS.join(', ')}; up to ${ATTACHMENT_MAX_MB} MB each).` : ''}
        </p>
      ) : (
        <table className="erp-table text-xs">
          <thead>
            <tr>
              <th>Document</th>
              <th>Size</th>
              <th>Added by</th>
              <th>When</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id}>
                <td>
                  {a.original_filename}
                  {a.description ? <span className="text-slate-500"> — {a.description}</span> : null}
                </td>
                <td>{formatFileSize(a.size_bytes)}</td>
                <td>{a.uploaded_by}</td>
                <td>{new Date(a.uploaded_at).toLocaleString()}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button type="button" className="erp-btn btn-sm btn-secondary p-1" title="Download" onClick={() => onDownload(a)}>
                    <Download size={13} />
                  </button>{' '}
                  {canRemove && (
                    <button type="button" className="erp-btn btn-sm btn-danger p-1" title="Remove" onClick={() => onDelete(a)}>
                      <Trash2 size={13} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};
