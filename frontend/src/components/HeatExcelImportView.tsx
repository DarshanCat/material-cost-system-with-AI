import React, { useState, useRef } from 'react';
import { 
  Upload, 
  Download,
  CheckCircle, 
  AlertTriangle, 
  FileSpreadsheet, 
  XCircle,
  Database,
  FileText,
  X
} from 'lucide-react';
import type { UserRole } from '../types';
import { apiFetch } from '../api/client';
import { hasPermission } from '../auth/permissions';

interface HeatExcelImportViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

interface HeatPreviewFinding {
  row_number: number;
  heat_number: string;
  normalized_heat_number: string;
  heat_date: string;
  material_description: string;
  resolved_item_code?: string | null;
  resolved_item_name?: string | null;
  alias_status: string;
  charged_quantity: string | number;
  uom_code: string;
  is_valid: boolean;
  errors: string[];
}

interface HeatPreviewResult {
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  can_commit: boolean;
  findings: HeatPreviewFinding[];
  rows?: Record<string, any>[];
  source_filename?: string;
}

export const HeatExcelImportView: React.FC<HeatExcelImportViewProps> = ({ currentRole }) => {
  const canReadHeatLogs = hasPermission(currentRole, 'heat_log:read');
  const canCreateHeatLogs = hasPermission(currentRole, 'heat_log:create');
  const [importMode, setImportMode] = useState<'excel' | 'csv'>('excel');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [csvContent, setCsvContent] = useState<string>('');
  const [validating, setValidating] = useState<boolean>(false);
  const [downloadingTemplate, setDownloadingTemplate] = useState<boolean>(false);
  const [committing, setCommitting] = useState<boolean>(false);
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);
  const [previewResult, setPreviewResult] = useState<HeatPreviewResult | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const sampleCsv = `heat_number,heat_date,furnace_id,shift,material_description,charged_quantity,uom_code,part_description,quantity_produced
102603-3801,2026-10-22,FURNACE-1,SHIFT_A,Pig Iron Foundry Grade,3500.0000,KG,Differential Housing,40
102603-3801,2026-10-22,FURNACE-1,SHIFT_A,Cast Iron Borings,1500.0000,KG,,
102603-3802,2026-10-22,FURNACE-2,SHIFT_B,CRC Scrap High Manganese,4500.0000,KG,Axle Housing,25`;

  const parseCsvToRows = (text: string) => {
    const lines = text.trim().split('\n').map(l => l.trim()).filter(l => l.length > 0);
    if (lines.length < 2) return [];

    const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
    const rows = [];

    for (let i = 1; i < lines.length; i++) {
      const parts = lines[i].split(',').map(p => p.trim());
      const row: Record<string, string> = {};
      headers.forEach((h, idx) => {
        row[h] = parts[idx] || '';
      });
      rows.push(row);
    }
    return rows;
  };

  const handleDownloadTemplate = async () => {
    setDownloadingTemplate(true);
    setFeedback(null);
    try {
      const res = await apiFetch('/api/v1/heats/import/template');
      if (!res.ok) {
        throw new Error('Failed to download Excel template from server.');
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'VSPL_Heat_Log_Import_Template.xlsx';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Error downloading template.' });
    } finally {
      setDownloadingTemplate(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const lower = file.name.toLowerCase();
      if (!lower.endsWith('.xlsx') && !lower.endsWith('.xlsm')) {
        setFeedback({ type: 'error', message: 'Only modern Excel (.xlsx, .xlsm) files are accepted.' });
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        return;
      }
      setSelectedFile(file);
      setPreviewResult(null);
      setFeedback(null);
    }
  };

  const handleClearFile = () => {
    setSelectedFile(null);
    setPreviewResult(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleExcelPreview = async () => {
    if (!selectedFile) {
      setFeedback({ type: 'error', message: 'Please select an Excel (.xlsx) file first.' });
      return;
    }

    setFeedback(null);
    setPreviewResult(null);
    setValidating(true);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const res = await apiFetch('/api/v1/heats/import/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (res.ok) {
        setPreviewResult(data);
      } else {
        setFeedback({ type: 'error', message: data.detail || 'Excel preview validation failed.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error uploading Excel file for preview.' });
    } finally {
      setValidating(false);
    }
  };

  const handleCsvPreview = async () => {
    setFeedback(null);
    setPreviewResult(null);

    const rows = parseCsvToRows(csvContent);
    if (rows.length === 0) {
      setFeedback({ type: 'error', message: 'No valid data rows found in CSV.' });
      return;
    }

    setValidating(true);
    try {
      const res = await apiFetch('/api/v1/heats/import/preview', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ rows }),
      });

      const data = await res.json();
      if (res.ok) {
        setPreviewResult({
          ...data,
          rows,
          source_filename: 'Batch_Heat_Import.csv',
        });
      } else {
        setFeedback({ type: 'error', message: data.detail || 'CSV preview validation failed.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error validating CSV import.' });
    } finally {
      setValidating(false);
    }
  };

  const handleCommitConfirm = async () => {
    if (!previewResult || !previewResult.can_commit) return;
    setCommitting(true);
    setFeedback(null);

    const rowsToCommit = previewResult.rows || (importMode === 'csv' ? parseCsvToRows(csvContent) : []);
    const sourceFilename = previewResult.source_filename || selectedFile?.name || 'Batch_Heat_Import.csv';

    try {
      const res = await apiFetch('/api/v1/heats/import/commit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rows: rowsToCommit,
          source_filename: sourceFilename,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setFeedback({ 
          type: 'success', 
          message: `Successfully imported ${data.heats_created_count} heats (${data.total_rows_imported} charge rows). Zero stock movements created.` 
        });
        setPreviewResult(null);
        setSelectedFile(null);
        setCsvContent('');
        if (fileInputRef.current) fileInputRef.current.value = '';
        setShowConfirmModal(false);
      } else {
        setFeedback({ type: 'error', message: data.detail || 'Import commit failed.' });
        setShowConfirmModal(false);
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error committing import batch.' });
      setShowConfirmModal(false);
    } finally {
      setCommitting(false);
    }
  };

  // Calculate distinct heats count for confirmation display
  const distinctHeatsCount = previewResult?.findings
    ? new Set(previewResult.findings.map(f => f.normalized_heat_number || f.heat_number)).size
    : 0;

  return (
    <div className="erp-module">
      <div className="module-header flex-between">
        <div>
          <h2 className="module-title">Induction Furnace Heat Log Excel Import</h2>
          <p className="module-subtitle">
            Bulk ingest induction furnace heat records, charge detail mixes, and castings cast with atomic preview validation.
          </p>
        </div>
        {canReadHeatLogs && (
          <button 
            className="erp-btn btn-outline"
            onClick={handleDownloadTemplate}
            disabled={downloadingTemplate}
          >
            <Download size={14} className="btn-icon" />
            {downloadingTemplate ? 'Downloading Template...' : 'Download Excel Template'}
          </button>
        )}
      </div>

      {feedback && (
        <div className={`notification-banner ${feedback.type === 'success' ? 'banner-success' : 'banner-error'}`}>
          {feedback.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Isolation Info Card */}
      <div className="info-banner mb-4">
        <div>
          <strong>Strict Accounting Boundary:</strong> Importing heat charge rows creates heat master records and charge details, but 
          <strong> NEVER creates stock ledger movements or updates warehouse inventory balances</strong>.
        </div>
      </div>

      {/* Mode Switcher Tabs */}
      <div className="flex-gap mb-4">
        <button 
          className={`tab-btn ${importMode === 'excel' ? 'tab-btn-active' : ''}`}
          onClick={() => {
            setImportMode('excel');
            setPreviewResult(null);
            setFeedback(null);
          }}
        >
          <FileSpreadsheet size={14} /> Direct Excel Upload (.xlsx)
        </button>
        <button 
          className={`tab-btn ${importMode === 'csv' ? 'tab-btn-active' : ''}`}
          onClick={() => {
            setImportMode('csv');
            setPreviewResult(null);
            setFeedback(null);
          }}
        >
          <FileText size={14} /> Paste CSV / Text Data
        </button>
      </div>

      {/* Excel Upload Mode */}
      {importMode === 'excel' && (
        <div className="erp-card mb-4">
          <div className="card-header flex-between">
            <h3>Upload Native Excel Workbook</h3>
            <span className="badge badge-secondary">Supports Single-Sheet or Multi-Sheet Workbooks</span>
          </div>
          <div className="card-body">
            <p className="text-sm text-muted mb-3">
              Upload induction furnace heat records in modern Excel format (<code>.xlsx</code> or <code>.xlsm</code>).
              Supports both flattened single-sheet formats and multi-sheet workbooks with separate <em>Heat Log</em> and <em>Charge Details</em> worksheets.
            </p>

            <div className="flex-gap items-center mb-3">
              <input 
                type="file" 
                ref={fileInputRef}
                accept=".xlsx,.xlsm"
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
              <button 
                type="button"
                className="erp-btn btn-outline"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload size={14} className="btn-icon" /> Select Excel File
              </button>

              {selectedFile && (
                <div className="flex-gap" style={{ alignItems: 'center', backgroundColor: '#f1f5f9', padding: '0.4rem 0.75rem', borderRadius: '4px', border: '1px solid #cbd5e1' }}>
                  <FileSpreadsheet size={16} />
                  <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{selectedFile.name}</span>
                  <span className="text-muted" style={{ fontSize: '0.75rem' }}>({(selectedFile.size / 1024).toFixed(1)} KB)</span>
                  <button 
                    type="button" 
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 0.25rem', color: '#64748b' }}
                    onClick={handleClearFile}
                    title="Remove file"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}
            </div>

            <div className="mt-4 flex-gap">
              {canCreateHeatLogs && (
                <button 
                  type="button"
                  className="erp-btn btn-primary"
                  onClick={handleExcelPreview}
                  disabled={validating || !selectedFile}
                >
                  <Upload size={14} className="btn-icon" /> {validating ? 'Parsing & Validating Workbook...' : 'Upload & Preview Validation'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* CSV Paste Mode */}
      {importMode === 'csv' && (
        <div className="erp-card mb-4">
          <div className="card-header flex-between">
            <h3>Paste Heat Log CSV Data</h3>
            <button 
              type="button"
              className="erp-btn btn-sm btn-outline"
              onClick={() => setCsvContent(sampleCsv)}
            >
              <FileSpreadsheet size={12} className="btn-icon" /> Load Sample CSV Template
            </button>
          </div>
          <div className="card-body">
            <textarea 
              className="w-full font-mono text-sm p-3 border rounded"
              rows={8}
              placeholder="heat_number,heat_date,furnace_id,shift,material_description,charged_quantity,uom_code,part_description,quantity_produced"
              value={csvContent}
              onChange={(e) => setCsvContent(e.target.value)}
            />
            <div className="mt-3 flex-gap">
              {canCreateHeatLogs && (
                <button 
                  type="button"
                  className="erp-btn btn-primary"
                  onClick={handleCsvPreview}
                  disabled={validating || !csvContent.trim()}
                >
                  <Upload size={14} className="btn-icon" /> {validating ? 'Validating Batch...' : 'Preview Validation'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Preview Validation Findings */}
      {previewResult && (
        <div className="erp-card">
          <div className="card-header flex-between">
            <div className="flex-gap items-center">
              <h3>Preview Validation Results</h3>
              {previewResult.source_filename && (
                <span className="text-xs text-muted">Source: {previewResult.source_filename}</span>
              )}
            </div>
            <div className="badge-group">
              <span className="badge badge-secondary">Total Rows: {previewResult.total_rows}</span>
              <span className="badge badge-success">Valid Rows: {previewResult.valid_rows}</span>
              {previewResult.error_rows > 0 && (
                <span className="badge badge-danger">Error Rows: {previewResult.error_rows}</span>
              )}
            </div>
          </div>
          <div className="card-body">
            <div className="erp-table-container">
              <table className="erp-table">
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Heat Number</th>
                    <th>Normalized Ref</th>
                    <th>Date</th>
                    <th>Material Description</th>
                    <th>Mapped Item</th>
                    <th>Alias Status</th>
                    <th>Quantity</th>
                    <th>UOM</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {previewResult.findings.map((f) => (
                    <tr key={f.row_number} className={!f.is_valid ? 'row-error' : ''}>
                      <td>{f.row_number}</td>
                      <td><strong>{f.heat_number}</strong></td>
                      <td><code className="code-badge">{f.normalized_heat_number || '-'}</code></td>
                      <td>{f.heat_date}</td>
                      <td>{f.material_description}</td>
                      <td>
                        {f.resolved_item_code ? (
                          <span><strong>{f.resolved_item_code}</strong> ({f.resolved_item_name})</span>
                        ) : (
                          <span className="text-warning">Unmapped</span>
                        )}
                      </td>
                      <td>
                        <span className={`badge ${f.alias_status === 'MAPPED' ? 'badge-success' : 'badge-warning'}`}>
                          {f.alias_status}
                        </span>
                      </td>
                      <td>{f.charged_quantity}</td>
                      <td>{f.uom_code}</td>
                      <td>
                        {f.is_valid ? (
                          <span className="badge badge-success"><CheckCircle size={10} className="inline-icon" /> Valid</span>
                        ) : (
                          <div>
                            <span className="badge badge-danger"><XCircle size={10} className="inline-icon" /> Blocked</span>
                            <ul className="error-list text-xs text-danger mt-1">
                              {f.errors.map((e, ei) => <li key={ei}>{e}</li>)}
                            </ul>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 flex-between items-center">
              <div>
                {!previewResult.can_commit ? (
                  <p className="text-danger text-sm font-semibold">
                    Atomic commit is blocked until all errors are resolved in the source file. Zero partial writes permitted.
                  </p>
                ) : (
                  <p className="text-success text-sm font-semibold">
                    All {previewResult.valid_rows} rows passed validation. Ready for atomic commit.
                  </p>
                )}
              </div>
              {canCreateHeatLogs && (
                <button 
                  type="button"
                  className="erp-btn btn-success"
                  onClick={() => setShowConfirmModal(true)}
                  disabled={!previewResult.can_commit || committing}
                >
                  <Database size={14} className="btn-icon" /> Review &amp; Commit Heat Batch...
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal */}
      {showConfirmModal && previewResult && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3 className="modal-title">Confirm Atomic Heat Log Import</h3>
              <button 
                type="button" 
                className="modal-close-btn"
                onClick={() => setShowConfirmModal(false)}
                disabled={committing}
              >
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <div className="info-banner mb-3">
                <AlertTriangle size={16} className="inline-icon mr-1 text-warning" />
                <strong>Audit &amp; Stock Isolation Notice:</strong>
                <p className="text-xs mt-1">
                  This operation writes furnace heat logs and charge records directly to the Heat Master.
                  As per VSPL accounting doctrine, <strong>zero stock ledger entries or physical stock deductions will be posted</strong>.
                </p>
              </div>

              <div className="modal-info-grid mb-4">
                <div className="info-item">
                  <span className="text-muted text-xs">Import Source:</span>
                  <strong>{previewResult.source_filename || selectedFile?.name || 'Manual CSV Batch'}</strong>
                </div>
                <div className="info-item">
                  <span className="text-muted text-xs">Distinct Heats:</span>
                  <strong>{distinctHeatsCount} Heats</strong>
                </div>
                <div className="info-item">
                  <span className="text-muted text-xs">Total Charge Rows:</span>
                  <strong>{previewResult.total_rows} Rows</strong>
                </div>
                <div className="info-item">
                  <span className="text-muted text-xs">Batch Status:</span>
                  <strong className="text-success">100% Valid (All Rows Pass)</strong>
                </div>
              </div>

              <p className="text-sm">
                Are you sure you want to commit this batch? The entire batch will be executed atomically in a single database transaction.
              </p>
            </div>
            <div className="modal-footer">
              <button 
                type="button" 
                className="erp-btn btn-outline"
                onClick={() => setShowConfirmModal(false)}
                disabled={committing}
              >
                Cancel
              </button>
              <button 
                type="button" 
                className="erp-btn btn-success"
                onClick={handleCommitConfirm}
                disabled={committing}
              >
                <Database size={14} className="btn-icon" />
                {committing ? 'Committing Batch...' : 'Confirm & Execute Commit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
