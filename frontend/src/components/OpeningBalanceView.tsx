import React, { useState } from 'react';
import { 
  Download, 
  Upload, 
  CheckCircle, 
  AlertTriangle, 
  XCircle, 
  Database
} from 'lucide-react';
import type { UserRole } from '../types';
import { apiFetch } from '../api/client';
import { hasPermission } from '../auth/permissions';

interface OpeningBalanceViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

interface PreviewFinding {
  row_number: number;
  item_code: string;
  item_name?: string;
  uom_code: string;
  quantity: string | number;
  is_valid: boolean;
  errors: string[];
  warnings: string[];
}

interface PreviewSummary {
  total_rows: number;
  valid_rows_count: number;
  error_rows_count: number;
  can_commit: boolean;
  baseline_date: string;
  findings: PreviewFinding[];
}

export const OpeningBalanceView: React.FC<OpeningBalanceViewProps> = ({ currentRole, currentUserId }) => {
  const canPostOpeningBalances = hasPermission(currentRole, 'opening_balance:post');
  const [baselineDate, setBaselineDate] = useState<string>('2026-10-12');
  const [auditRef, setAuditRef] = useState<string>('');
  const [approverComments, setApproverComments] = useState<string>('');
  const [inputRowsText, setInputRowsText] = useState<string>(
    'FDY-RM-001, 15000.00, KG\nFDY-RM-002, 8500.00, KG'
  );
  const [preview, setPreview] = useState<PreviewSummary | null>(null);
  const [validating, setValidating] = useState<boolean>(false);
  const [posting, setPosting] = useState<boolean>(false);
  const [postResult, setPostResult] = useState<any | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleDownloadTemplate = () => {
    window.open('/api/v1/opening-balances/template', '_blank');
  };

  const handlePreview = async () => {
    setErrorMsg(null);
    setPostResult(null);
    setValidating(true);

    try {
      // Parse CSV-style text lines: ITEM_CODE, QUANTITY, UOM
      const lines = inputRowsText.split('\n').filter(l => l.trim().length > 0);
      const rows = lines.map(line => {
        const parts = line.split(',').map(p => p.trim());
        return {
          item_code: parts[0] || '',
          quantity: parts[1] || '0',
          uom_code: parts[2] || '',
          baseline_date: baselineDate,
        };
      });

      const res = await apiFetch(`/api/v1/opening-balances/preview?baseline_date=${baselineDate}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rows),
      });

      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.detail || 'Validation preview failed');
      } else {
        setPreview(data);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Error parsing opening balance input');
    } finally {
      setValidating(false);
    }
  };

  const handlePost = async () => {
    if (!preview || !preview.can_commit) return;
    if (!auditRef.trim()) {
      setErrorMsg('Audit Document Reference is mandatory to establish opening stock balances.');
      return;
    }

    setPosting(true);
    setErrorMsg(null);

    try {
      const payloadRows = preview.findings.map(f => ({
        item_code: f.item_code,
        quantity: f.quantity,
        uom_code: f.uom_code,
        baseline_date: baselineDate,
      }));

      const payload = {
        baseline_date: baselineDate,
        audit_reference: auditRef.trim(),
        rows: payloadRows,
        approver_id: `${currentRole} (${currentUserId})`,
        approver_comments: approverComments || 'Approved opening stock baseline',
      };

      const res = await apiFetch('/api/v1/opening-balances/post', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.detail || 'Atomic posting failed');
      } else {
        setPostResult(data);
        setPreview(null);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Error posting opening balances');
    } finally {
      setPosting(false);
    }
  };

  return (
    <div className="erp-view">
      <div className="view-header">
        <div>
          <h2>Opening Stock Balances (Baseline: 12 October 2026)</h2>
          <p className="subtitle">
            Establish immutable opening balance baseline entries from approved physical counts. No synthetic records.
          </p>
        </div>
        <div className="header-actions">
          {canPostOpeningBalances && (
            <button className="erp-btn btn-secondary" onClick={handleDownloadTemplate}>
              <Download size={14} className="btn-icon" /> Download Template (.xlsx)
            </button>
          )}
        </div>
      </div>

      {errorMsg && (
        <div className="alert-error p-3 mb-4 bg-red-50 text-red-700 text-sm rounded border border-red-200">
          <AlertTriangle size={16} className="inline mr-2" />
          {errorMsg}
        </div>
      )}

      {postResult && (
        <div className="p-4 mb-4 bg-emerald-50 text-emerald-800 rounded border border-emerald-200">
          <h4 className="font-semibold flex items-center gap-2 mb-2">
            <CheckCircle size={18} /> {postResult.message}
          </h4>
          <p className="text-sm">
            Posting Group: <code className="font-mono">{postResult.posting_group_id}</code> ({postResult.posted_count} items initialized)
          </p>
        </div>
      )}

      {/* Input Form */}
      <div className="bg-white p-4 rounded border border-slate-200 mb-4 shadow-sm">
        <div className="grid grid-cols-3 gap-4 mb-3">
          <div>
            <label className="form-label">Baseline Cutoff Date</label>
            <input
              type="date"
              className="form-control"
              value={baselineDate}
              onChange={(e) => setBaselineDate(e.target.value)}
              disabled
            />
            <span className="text-xs text-slate-500">Strictly 12 October 2026 per VSPL governance</span>
          </div>

          <div>
            <label className="form-label">Approved Audit Reference Document *</label>
            <input
              type="text"
              className="form-control"
              placeholder="e.g. AUD-20261012-YARD-001"
              value={auditRef}
              onChange={(e) => setAuditRef(e.target.value)}
            />
          </div>

          <div>
            <label className="form-label">Approver Justification / Sign-off Notes</label>
            <input
              type="text"
              className="form-control"
              placeholder="e.g. Verified by GM Operations & Stores Head"
              value={approverComments}
              onChange={(e) => setApproverComments(e.target.value)}
            />
          </div>
        </div>

        <div className="mb-3">
          <label className="form-label">Opening Items Entry (Format: Item Code, Quantity, UOM)</label>
          <textarea
            className="form-control font-mono text-xs"
            rows={4}
            value={inputRowsText}
            onChange={(e) => setInputRowsText(e.target.value)}
            placeholder="FDY-RM-001, 15000.00, KG&#10;FDY-RM-002, 8500.00, KG"
          />
        </div>

        <div>
          {canPostOpeningBalances && (
            <button
              className="erp-btn btn-primary"
              onClick={handlePreview}
              disabled={validating}
            >
              <Upload size={14} className="btn-icon" />
              {validating ? 'Verifying References...' : 'Validate & Preview Baseline'}
            </button>
          )}
        </div>
      </div>

      {/* Preview Card */}
      {preview && (
        <div className="bg-white p-4 rounded border border-slate-200 mb-4 shadow-sm">
          <div className="flex justify-between items-center mb-3">
            <div>
              <h3 className="text-base font-semibold">Opening Baseline Validation Preview</h3>
              <p className="text-xs text-slate-500">
                Checking master data existence, precision rules, and preventing duplicate initialization.
              </p>
            </div>
            {preview.can_commit && canPostOpeningBalances ? (
              <button
                className="erp-btn btn-success"
                onClick={handlePost}
                disabled={posting}
              >
                <Database size={14} className="btn-icon" />
                {posting ? 'Posting to Ledger...' : 'Post Approved Baseline'}
              </button>
            ) : !preview.can_commit ? (
              <div className="text-xs font-semibold text-red-600 bg-red-50 p-2 rounded border border-red-200">
                Errors Detected: Resolve item conflicts before posting
              </div>
            ) : null}
          </div>

          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="p-3 bg-slate-50 rounded border text-center">
              <div className="text-xl font-bold text-slate-700">{preview.total_rows}</div>
              <div className="text-xs text-slate-500">Total Items</div>
            </div>
            <div className="p-3 bg-emerald-50 rounded border border-emerald-100 text-center">
              <div className="text-xl font-bold text-emerald-600">{preview.valid_rows_count}</div>
              <div className="text-xs text-emerald-700">Valid & Uninitialized</div>
            </div>
            <div className="p-3 bg-red-50 rounded border border-red-100 text-center">
              <div className="text-xl font-bold text-red-600">{preview.error_rows_count}</div>
              <div className="text-xs text-red-700">Conflicts / Errors</div>
            </div>
          </div>

          <div className="erp-table-container max-h-80 overflow-y-auto">
            <table className="erp-table text-xs">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Item Code</th>
                  <th>Material Name</th>
                  <th>Quantity</th>
                  <th>UOM</th>
                  <th>Status</th>
                  <th>Errors / Findings</th>
                </tr>
              </thead>
              <tbody>
                {preview.findings.map((f) => (
                  <tr key={f.row_number} className={!f.is_valid ? 'bg-red-50/50' : ''}>
                    <td>{f.row_number}</td>
                    <td className="font-mono font-bold">{f.item_code}</td>
                    <td>{f.item_name || '—'}</td>
                    <td className="font-mono font-semibold">{f.quantity}</td>
                    <td>{f.uom_code}</td>
                    <td>
                      {f.is_valid ? (
                        <span className="badge badge-success flex items-center gap-1 w-fit">
                          <CheckCircle size={10} /> Valid
                        </span>
                      ) : (
                        <span className="badge badge-danger flex items-center gap-1 w-fit">
                          <XCircle size={10} /> Invalid
                        </span>
                      )}
                    </td>
                    <td>
                      {f.errors.map((e, i) => (
                        <div key={i} className="text-red-700 font-medium">• {e}</div>
                      ))}
                      {f.errors.length === 0 && <span className="text-slate-400">Ready to post</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
