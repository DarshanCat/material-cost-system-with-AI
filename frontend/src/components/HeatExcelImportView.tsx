import React, { useState } from 'react';
import { 
  Upload, 
  CheckCircle, 
  AlertTriangle, 
  FileSpreadsheet, 
  XCircle,
  Database
} from 'lucide-react';
import type { UserRole } from '../types';
import { apiFetch } from '../api/client';

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

export const HeatExcelImportView: React.FC<HeatExcelImportViewProps> = () => {
  const [csvContent, setCsvContent] = useState<string>('');
  const [validating, setValidating] = useState<boolean>(false);
  const [committing, setCommitting] = useState<boolean>(false);
  const [previewResult, setPreviewResult] = useState<{
    total_rows: number;
    valid_rows: number;
    error_rows: number;
    can_commit: boolean;
    findings: HeatPreviewFinding[];
  } | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

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

  const handlePreview = async () => {
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

      if (res.ok) {
        const data = await res.json();
        setPreviewResult(data);
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Preview validation failed.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error validating import.' });
    } finally {
      setValidating(false);
    }
  };

  const handleCommit = async () => {
    if (!previewResult || !previewResult.can_commit) return;
    setCommitting(true);
    setFeedback(null);

    const rows = parseCsvToRows(csvContent);
    try {
      const res = await apiFetch('/api/v1/heats/import/commit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rows,
          source_filename: 'Batch_Heat_Import.csv',
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setFeedback({ 
          type: 'success', 
          message: `Successfully imported ${data.heats_created_count} heats (${data.total_rows_imported} rows). Zero stock movements created.` 
        });
        setPreviewResult(null);
        setCsvContent('');
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Import commit failed.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error committing import.' });
    } finally {
      setCommitting(false);
    }
  };

  return (
    <div className="erp-module">
      <div className="module-header">
        <div>
          <h2 className="module-title">Induction Furnace Heat Log Excel Import</h2>
          <p className="module-subtitle">
            Bulk ingest induction furnace heat records, charge detail mixes, and castings cast with atomic preview validation.
          </p>
        </div>
      </div>

      {feedback && (
        <div className={`notification-banner ${feedback.type === 'success' ? 'banner-success' : 'banner-error'}`}>
          {feedback.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Isolation Info Card */}
      <div className="info-banner mb-4">
        <strong>Strict Accounting Boundary:</strong> Importing heat charge rows creates heat master records and charge details, but 
        <strong> NEVER creates stock ledger movements or updates warehouse inventory balances</strong>.
      </div>

      <div className="erp-card mb-4">
        <div className="card-header flex-between">
          <h3>Paste Heat Log CSV Data</h3>
          <button 
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
            <button 
              className="erp-btn btn-primary"
              onClick={handlePreview}
              disabled={validating || !csvContent.trim()}
            >
              <Upload size={14} className="btn-icon" /> {validating ? 'Validating Batch...' : 'Preview Validation'}
            </button>
          </div>
        </div>
      </div>

      {/* Preview Validation Findings */}
      {previewResult && (
        <div className="erp-card">
          <div className="card-header flex-between">
            <h3>Preview Validation Results</h3>
            <div className="badge-group">
              <span className="badge badge-secondary">Total: {previewResult.total_rows}</span>
              <span className="badge badge-success">Valid: {previewResult.valid_rows}</span>
              {previewResult.error_rows > 0 && (
                <span className="badge badge-danger">Errors: {previewResult.error_rows}</span>
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

            <div className="mt-4 flex-between">
              <div>
                {!previewResult.can_commit && (
                  <p className="text-danger text-sm">
                    Atomic commit is blocked until all errors are fixed. Zero partial writes permitted.
                  </p>
                )}
              </div>
              <button 
                className="erp-btn btn-success"
                onClick={handleCommit}
                disabled={!previewResult.can_commit || committing}
              >
                <Database size={14} className="btn-icon" /> {committing ? 'Committing...' : 'Commit Heat Batch Atomically'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
