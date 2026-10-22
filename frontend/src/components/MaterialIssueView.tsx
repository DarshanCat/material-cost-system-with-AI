import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  CheckCircle, 
  AlertTriangle, 
  Send, 
  X, 
  Search,
  Flame,
  RefreshCw
} from 'lucide-react';
import type { MaterialIssue, MaterialItem, UOM, Department, UserRole } from '../types';
import { apiFetch, readApiError } from '../api/client';

interface MaterialIssueViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const MaterialIssueView: React.FC<MaterialIssueViewProps> = () => {
  const [actionError, setActionError] = useState<string | null>(null);
  const [issues, setIssues] = useState<MaterialIssue[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [items, setItems] = useState<MaterialItem[]>([]);
  const [uoms, setUoms] = useState<UOM[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [showModal, setShowModal] = useState<boolean>(false);
  const [selectedIssue, setSelectedIssue] = useState<MaterialIssue | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Form State
  const [issueDate, setIssueDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [issuingDeptId, setIssuingDeptId] = useState<number | ''>('');
  const [receivingDeptId, setReceivingDeptId] = useState<number | ''>('');
  const [heatRefNo, setHeatRefNo] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [lines, setLines] = useState<Array<{
    material_item_id: number | '';
    uom_id: number | '';
    quantity: string;
    remarks: string;
  }>>([
    { material_item_id: '', uom_id: '', quantity: '', remarks: '' }
  ]);
  const [formError, setFormError] = useState<string | null>(null);
  const [formWarnings, setFormWarnings] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState<boolean>(false);

  const fetchIssues = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/v1/issues/');
      if (res.ok) {
        const data = await res.json();
        setIssues(data);
      }
    } catch (err) {
      console.error('Error fetching issue slips:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchReferences = async () => {
    try {
      const [iRes, uRes, dRes] = await Promise.all([
        apiFetch('/api/v1/items?limit=500'),
        apiFetch('/api/v1/uoms'),
        apiFetch('/api/v1/departments'),
      ]);
      if (iRes.ok) setItems(await iRes.json());
      if (uRes.ok) setUoms(await uRes.json());
      if (dRes.ok) setDepartments(await dRes.json());
    } catch (err) {
      console.error('Error fetching references:', err);
    }
  };

  useEffect(() => {
    fetchIssues();
    fetchReferences();
  }, []);

  const handleAddLine = () => {
    setLines([...lines, { material_item_id: '', uom_id: '', quantity: '', remarks: '' }]);
  };

  const handleRemoveLine = (idx: number) => {
    if (lines.length > 1) {
      setLines(lines.filter((_, i) => i !== idx));
    }
  };

  const handleLineChange = (idx: number, field: string, value: any) => {
    const updated = [...lines];
    updated[idx] = { ...updated[idx], [field]: value };
    if (field === 'material_item_id' && value) {
      const selectedItem = items.find(i => i.id === Number(value));
      if (selectedItem) {
        updated[idx].uom_id = selectedItem.base_uom_id;
      }
    }
    setLines(updated);
  };

  const handleCreateIssue = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setFormWarnings([]);
    setSubmitting(true);

    try {
      const payloadLines = lines.map((l, index) => ({
        line_number: index + 1,
        material_item_id: Number(l.material_item_id),
        uom_id: Number(l.uom_id),
        quantity: l.quantity,
        remarks: l.remarks || null,
      }));

      const payload = {
        issue_date: issueDate,
        issuing_department_id: Number(issuingDeptId),
        receiving_department_id: Number(receivingDeptId),
        heat_reference_number: heatRefNo ? heatRefNo.trim() : null,
        notes: notes || null,
        lines: payloadLines,
      };

      const res = await apiFetch(`/api/v1/issues/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        setFormError(data.detail || 'Failed to create Issue Slip');
      } else {
        if (data.validation_warnings && data.validation_warnings.length > 0) {
          setFormWarnings(data.validation_warnings);
        }
        fetchIssues();
        setShowModal(false);
        setLines([{ material_item_id: '', uom_id: '', quantity: '', remarks: '' }]);
      }
    } catch (err: any) {
      setFormError(err.message || 'Error occurred while saving issue slip');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAction = async (issueId: number, action: 'submit' | 'approve' | 'cancel') => {
    setActionError(null);
    try {
      const res = await apiFetch(`/api/v1/issues/${issueId}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comments: `Action ${action}` }),
      });
      if (res.ok) {
        fetchIssues();
        if (selectedIssue && selectedIssue.id === issueId) {
          const updated = await res.json();
          setSelectedIssue(updated);
        }
      } else {
        setActionError(await readApiError(res, 'Could not '+action+' the issue slip'));
      }
    } catch (err) {
      console.error(`Failed to ${action} issue slip:`, err);
      setActionError('Network error: the request could not be completed.');
    }
  };

  const filteredIssues = issues.filter(i => {
    const matchesStatus = statusFilter === 'ALL' || i.status === statusFilter;
    const matchesSearch = 
      i.issue_slip_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (i.heat_reference_number && i.heat_reference_number.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (i.receiving_department_name && i.receiving_department_name.toLowerCase().includes(searchTerm.toLowerCase()));
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="erp-view">
      {actionError && (
        <div className="erp-alert alert-danger" role="alert">
          {actionError}
        </div>
      )}
      <div className="view-header">
        <div>
          <h2>Material Issue Slips</h2>
          <p className="subtitle">
            Authorize and trace material issues across plant departments and furnace heat numbers.
          </p>
        </div>
        <div className="header-actions">
          <button className="erp-btn btn-secondary" onClick={fetchIssues}>
            <RefreshCw size={14} className="btn-icon" /> Refresh
          </button>
          <button className="erp-btn btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={14} className="btn-icon" /> Create Issue Slip
          </button>
        </div>
      </div>

      {formWarnings.length > 0 && (
        <div className="audit-card p-3 mb-3 bg-amber-50 border-amber-200">
          <div className="flex items-center gap-2 text-amber-800 font-medium">
            <AlertTriangle size={18} /> Traceability Notice / Warnings:
          </div>
          <ul className="list-disc ml-5 mt-1 text-sm text-amber-700">
            {formWarnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="filter-toolbar">
        <div className="search-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search by Slip #, Heat Ref (H-XXXX), Receiving Dept..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <span className="filter-label">Status:</span>
          {['ALL', 'DRAFT', 'SUBMITTED', 'APPROVED', 'CANCELLED'].map((st) => (
            <button
              key={st}
              className={`filter-btn ${statusFilter === st ? 'active' : ''}`}
              onClick={() => setStatusFilter(st)}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Issue Slips Table */}
      <div className="erp-table-container">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Issue Slip #</th>
              <th>Issue Date</th>
              <th>Issuing Dept</th>
              <th>Receiving Dept</th>
              <th>Furnace Heat Ref</th>
              <th>Items</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="text-center p-4">Loading issue slips...</td></tr>
            ) : filteredIssues.length === 0 ? (
              <tr><td colSpan={8} className="text-center p-4">No issue slips match current criteria.</td></tr>
            ) : (
              filteredIssues.map((issue) => (
                <tr key={issue.id} onClick={() => setSelectedIssue(issue)} className="cursor-pointer">
                  <td className="font-mono font-medium">{issue.issue_slip_number}</td>
                  <td>{issue.issue_date}</td>
                  <td>{issue.issuing_department_name}</td>
                  <td><strong>{issue.receiving_department_name}</strong></td>
                  <td>
                    {issue.heat_reference_number ? (
                      <span className="badge badge-primary flex items-center gap-1 w-fit">
                        <Flame size={12} /> {issue.heat_reference_number}
                      </span>
                    ) : '—'}
                  </td>
                  <td>{issue.lines?.length || 0} item(s)</td>
                  <td>
                    <span className={`status-pill status-${issue.status.toLowerCase()}`}>
                      {issue.status}
                    </span>
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="flex gap-1">
                      {issue.status === 'DRAFT' && (
                        <button
                          className="erp-btn btn-sm btn-outline"
                          onClick={() => handleAction(issue.id, 'submit')}
                        >
                          <Send size={12} /> Submit
                        </button>
                      )}
                      {issue.status === 'SUBMITTED' && (
                        <button
                          className="erp-btn btn-sm btn-success"
                          onClick={() => handleAction(issue.id, 'approve')}
                        >
                          <CheckCircle size={12} /> Approve
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Detail Modal */}
      {selectedIssue && (
        <div className="modal-backdrop" onClick={() => setSelectedIssue(null)}>
          <div className="modal-content max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Issue Slip Details: {selectedIssue.issue_slip_number}</h3>
              <button className="close-btn" onClick={() => setSelectedIssue(null)}><X size={18} /></button>
            </div>
            <div className="modal-body">
              <div className="grid grid-cols-3 gap-4 mb-4 text-sm">
                <div><strong>Issue Date:</strong> {selectedIssue.issue_date}</div>
                <div><strong>Issuing Dept:</strong> {selectedIssue.issuing_department_name}</div>
                <div><strong>Receiving Dept:</strong> {selectedIssue.receiving_department_name}</div>
                <div><strong>Furnace Heat Ref:</strong> {selectedIssue.heat_reference_number || 'N/A'}</div>
                <div><strong>Status:</strong> {selectedIssue.status}</div>
                <div><strong>Created By:</strong> {selectedIssue.created_by}</div>
              </div>

              <h4 className="font-semibold mb-2">Issued Material Lines</h4>
              <table className="erp-table mb-4">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Item Code & Name</th>
                    <th>UOM</th>
                    <th>Issued Quantity</th>
                    <th>Remarks</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedIssue.lines.map((l) => (
                    <tr key={l.line_number}>
                      <td>{l.line_number}</td>
                      <td>{l.item_code} - {l.item_name}</td>
                      <td>{l.uom_code}</td>
                      <td className="font-mono font-medium">{l.quantity}</td>
                      <td>{l.remarks || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h4 className="font-semibold mb-2">Audit History</h4>
              <div className="audit-timeline">
                {selectedIssue.audit_logs?.map((log) => (
                  <div key={log.id} className="timeline-item text-xs mb-1">
                    <span className="font-semibold">{log.action}</span> by {log.actor_id} on {new Date(log.timestamp).toLocaleString()}: {log.comments}
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-footer">
              <button className="erp-btn btn-secondary" onClick={() => setSelectedIssue(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="modal-content max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleCreateIssue}>
              <div className="modal-header">
                <h3>New Material Issue Slip</h3>
                <button type="button" className="close-btn" onClick={() => setShowModal(false)}><X size={18} /></button>
              </div>
              <div className="modal-body">
                {formError && (
                  <div className="alert-error p-3 mb-3 bg-red-50 text-red-700 text-sm rounded">
                    {formError}
                  </div>
                )}

                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div>
                    <label className="form-label">Issue Date *</label>
                    <input
                      type="date"
                      className="form-control"
                      value={issueDate}
                      onChange={(e) => setIssueDate(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <label className="form-label">Issuing Department *</label>
                    <select
                      className="form-control"
                      value={issuingDeptId}
                      onChange={(e) => setIssuingDeptId(e.target.value ? Number(e.target.value) : '')}
                      required
                    >
                      <option value="">-- Select Issuing Dept --</option>
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>{d.name} ({d.code})</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="form-label">Receiving Department *</label>
                    <select
                      className="form-control"
                      value={receivingDeptId}
                      onChange={(e) => setReceivingDeptId(e.target.value ? Number(e.target.value) : '')}
                      required
                    >
                      <option value="">-- Select Receiving Dept --</option>
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>{d.name} ({d.code})</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div>
                    <label className="form-label">Heat Reference Number (e.g. 102603-3721)</label>
                    <input
                      type="text"
                      className="form-control"
                      placeholder="Normalizes automatically to H-102603-3721"
                      value={heatRefNo}
                      onChange={(e) => setHeatRefNo(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="form-label">Notes / Justification</label>
                    <input
                      type="text"
                      className="form-control"
                      placeholder="Furnace charge, maintenance work order, etc."
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>
                </div>

                {/* Lines */}
                <div className="mb-4">
                  <div className="flex justify-between items-center mb-2">
                    <h4 className="font-semibold text-sm">Issued Items</h4>
                    <button type="button" className="erp-btn btn-sm btn-secondary" onClick={handleAddLine}>
                      <Plus size={12} /> Add Item
                    </button>
                  </div>

                  {lines.map((l, idx) => (
                    <div key={idx} className="grid grid-cols-12 gap-2 mb-2 items-end bg-slate-50 p-2 rounded">
                      <div className="col-span-6">
                        <label className="form-label text-xs">Material Item *</label>
                        <select
                          className="form-control text-xs"
                          value={l.material_item_id}
                          onChange={(e) => handleLineChange(idx, 'material_item_id', e.target.value)}
                          required
                        >
                          <option value="">-- Select Material Item --</option>
                          {items.map((it) => (
                            <option key={it.id} value={it.id}>{it.item_code} - {it.name}</option>
                          ))}
                        </select>
                      </div>
                      <div className="col-span-2">
                        <label className="form-label text-xs">UOM *</label>
                        <select
                          className="form-control text-xs"
                          value={l.uom_id}
                          onChange={(e) => handleLineChange(idx, 'uom_id', e.target.value)}
                          required
                        >
                          <option value="">-- UOM --</option>
                          {uoms.map((u) => (
                            <option key={u.id} value={u.id}>{u.code}</option>
                          ))}
                        </select>
                      </div>
                      <div className="col-span-3">
                        <label className="form-label text-xs">Quantity *</label>
                        <input
                          type="number"
                          step="any"
                          className="form-control text-xs"
                          placeholder="e.g. 25.5"
                          value={l.quantity}
                          onChange={(e) => handleLineChange(idx, 'quantity', e.target.value)}
                          required
                        />
                      </div>
                      <div className="col-span-1 text-center">
                        {lines.length > 1 && (
                          <button
                            type="button"
                            className="erp-btn btn-sm btn-danger p-1"
                            onClick={() => handleRemoveLine(idx)}
                          >
                            <X size={14} />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="erp-btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="erp-btn btn-primary" disabled={submitting}>
                  {submitting ? 'Creating...' : 'Create Draft Issue Slip'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
