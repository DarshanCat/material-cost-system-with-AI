import React, { useState } from 'react';
import { 
  Upload, 
  Download, 
  CheckCircle, 
  AlertTriangle, 
  XCircle, 
  Database
} from 'lucide-react';
import type { UserRole } from '../types';

interface ExcelImportViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

interface ValidationFinding {
  row_number: number;
  status: 'VALID' | 'WARNING' | 'ERROR';
  errors: string[];
  warnings: string[];
  raw_data: Record<string, any>;
}

interface ValidationSummary {
  total_rows: number;
  valid_rows_count: number;
  warning_rows_count: number;
  error_rows_count: number;
  can_commit: boolean;
  message: string;
  findings: ValidationFinding[];
}

export const ExcelImportView: React.FC<ExcelImportViewProps> = ({ currentRole, currentUserId }) => {
  const [importType, setImportType] = useState<'GRN' | 'ISSUE' | 'WASTE'>('GRN');
  const [file, setFile] = useState<File | null>(null);
  const [validating, setValidating] = useState<boolean>(false);
  const [committing, setCommitting] = useState<boolean>(false);
  const [summary, setSummary] = useState<ValidationSummary | null>(null);
  const [commitResult, setCommitResult] = useState<any | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleDownloadTemplate = () => {
    window.open(`/api/v1/excel-import/template/${importType}`, '_blank');
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setSummary(null);
      setCommitResult(null);
      setErrorMsg(null);
    }
  };

  const handleValidate = async () => {
    if (!file) return;
    setValidating(true);
    setErrorMsg(null);
    setCommitResult(null);

    try {
      const formData = new FormData();
      formData.append('import_type', importType);
      formData.append('file', file);

      const res = await fetch('/api/v1/excel-import/validate', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.detail || 'Validation request failed');
      } else {
        setSummary(data);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Error occurred during file validation');
    } finally {
      setValidating(false);
    }
  };

  const handleCommit = async () => {
    if (!summary || !summary.can_commit) return;
    setCommitting(true);
    setErrorMsg(null);

    try {
      const payload = {
        import_type: importType,
        rows: summary.findings.map(f => f.raw_data),
        created_by: `${currentRole} (${currentUserId})`,
      };

      const res = await fetch('/api/v1/excel-import/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.detail || 'Atomic commit failed');
      } else {
        setCommitResult(data);
        setSummary(null);
        setFile(null);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Error executing atomic commit');
    } finally {
      setCommitting(false);
    }
  };

  return (
    <div className="erp-view">
      <div className="view-header">
        <div>
          <h2>Atomic Excel Import Engine</h2>
          <p className="subtitle">
            Upload and batch-validate Goods Receipt Notes, Material Issues, or Scrap Dispositions with zero partial writes.
          </p>
        </div>
        <div className="header-actions">
          <button className="erp-btn btn-secondary" onClick={handleDownloadTemplate}>
            <Download size={14} className="btn-icon" /> Download {importType} Template
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="alert-error p-3 mb-4 bg-red-50 text-red-700 text-sm rounded border border-red-200">
          <AlertTriangle size={16} className="inline mr-2" />
          {errorMsg}
        </div>
      )}

      {commitResult && (
        <div className="p-4 mb-4 bg-emerald-50 text-emerald-800 rounded border border-emerald-200">
          <h4 className="font-semibold flex items-center gap-2 mb-2">
            <CheckCircle size={18} /> {commitResult.message}
          </h4>
          <p className="text-sm mb-2">
            Created {commitResult.created_count} transaction document(s) in draft status:
          </p>
          <div className="flex flex-wrap gap-2">
            {commitResult.created_documents?.map((doc: string) => (
              <span key={doc} className="badge badge-success font-mono">
                {doc}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Configuration & Upload Card */}
      <div className="bg-white p-4 rounded border border-slate-200 mb-4 shadow-sm">
        <div className="grid grid-cols-3 gap-4 items-end">
          <div>
            <label className="form-label">Select Transaction Type</label>
            <select
              className="form-control"
              value={importType}
              onChange={(e: any) => {
                setImportType(e.target.value);
                setSummary(null);
                setCommitResult(null);
              }}
            >
              <option value="GRN">Goods Receipt Notes (GRN)</option>
              <option value="ISSUE">Material Issue Slips</option>
              <option value="WASTE">Waste & Scrap Disposition</option>
            </select>
          </div>

          <div>
            <label className="form-label">Excel Workbook (.xlsx, .xlsm)</label>
            <input
              type="file"
              accept=".xlsx,.xlsm"
              className="form-control text-sm"
              onChange={handleFileChange}
            />
          </div>

          <div>
            <button
              className="erp-btn btn-primary w-full"
              onClick={handleValidate}
              disabled={!file || validating}
            >
              <Upload size={14} className="btn-icon" />
              {validating ? 'Inspecting Worksheet...' : 'Validate & Preview'}
            </button>
          </div>
        </div>
      </div>

      {/* Validation Summary Card */}
      {summary && (
        <div className="bg-white p-4 rounded border border-slate-200 mb-4 shadow-sm">
          <div className="flex justify-between items-center mb-3">
            <div>
              <h3 className="text-base font-semibold">Pre-Commit Validation Summary</h3>
              <p className="text-xs text-slate-500">
                Foundry business rule verification: Decimal precision, rate exclusions, and master reference checks.
              </p>
            </div>
            {summary.can_commit ? (
              <button
                className="erp-btn btn-success"
                onClick={handleCommit}
                disabled={committing}
              >
                <Database size={14} className="btn-icon" />
                {committing ? 'Writing Batch...' : 'Atomic Commit (Commit All)'}
              </button>
            ) : (
              <div className="text-xs font-semibold text-red-600 bg-red-50 p-2 rounded border border-red-200">
                Commit Blocked: Fix errors below and re-validate
              </div>
            )}
          </div>

          <div className="grid grid-cols-4 gap-3 mb-4">
            <div className="p-3 bg-slate-50 rounded border text-center">
              <div className="text-2xl font-bold text-slate-700">{summary.total_rows}</div>
              <div className="text-xs text-slate-500">Total Rows</div>
            </div>
            <div className="p-3 bg-emerald-50 rounded border border-emerald-100 text-center">
              <div className="text-2xl font-bold text-emerald-600">{summary.valid_rows_count}</div>
              <div className="text-xs text-emerald-700">Valid Rows</div>
            </div>
            <div className="p-3 bg-amber-50 rounded border border-amber-100 text-center">
              <div className="text-2xl font-bold text-amber-600">{summary.warning_rows_count}</div>
              <div className="text-xs text-amber-700">Warnings (Traceable)</div>
            </div>
            <div className="p-3 bg-red-50 rounded border border-red-100 text-center">
              <div className="text-2xl font-bold text-red-600">{summary.error_rows_count}</div>
              <div className="text-xs text-red-700">Blocking Errors</div>
            </div>
          </div>

          {/* Row Findings Table */}
          <h4 className="font-semibold text-sm mb-2">Worksheet Row Findings</h4>
          <div className="erp-table-container max-h-96 overflow-y-auto">
            <table className="erp-table text-xs">
              <thead>
                <tr>
                  <th style={{ width: '80px' }}>Row #</th>
                  <th style={{ width: '100px' }}>Status</th>
                  <th>Extracted Data Preview</th>
                  <th>Validation Messages / Errors</th>
                </tr>
              </thead>
              <tbody>
                {summary.findings.map((f) => (
                  <tr key={f.row_number} className={f.status === 'ERROR' ? 'bg-red-50/50' : f.status === 'WARNING' ? 'bg-amber-50/50' : ''}>
                    <td className="font-mono font-bold">Row {f.row_number}</td>
                    <td>
                      {f.status === 'VALID' && (
                        <span className="badge badge-success flex items-center gap-1 w-fit">
                          <CheckCircle size={10} /> Valid
                        </span>
                      )}
                      {f.status === 'WARNING' && (
                        <span className="badge badge-warning flex items-center gap-1 w-fit">
                          <AlertTriangle size={10} /> Warning
                        </span>
                      )}
                      {f.status === 'ERROR' && (
                        <span className="badge badge-danger flex items-center gap-1 w-fit">
                          <XCircle size={10} /> Error
                        </span>
                      )}
                    </td>
                    <td className="font-mono text-slate-600">
                      {Object.entries(f.raw_data).map(([k, v]) => `${k}: ${v ?? '—'}`).join(' | ')}
                    </td>
                    <td>
                      {f.errors.length > 0 && (
                        <div className="text-red-700 font-medium">
                          {f.errors.map((e, i) => <div key={i}>• {e}</div>)}
                        </div>
                      )}
                      {f.warnings.length > 0 && (
                        <div className="text-amber-700 mt-1">
                          {f.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
                        </div>
                      )}
                      {f.errors.length === 0 && f.warnings.length === 0 && (
                        <span className="text-slate-400">Ready for commit</span>
                      )}
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
