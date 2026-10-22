import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  CheckCircle, 
  Send, 
  X, 
  Search, 
  RefreshCw,
  Eye
} from 'lucide-react';
import type { PhysicalAudit, MaterialItem, UOM, Department, UserRole } from '../types';
import { apiFetch } from '../api/client';

interface PhysicalAuditViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const PhysicalAuditView: React.FC<PhysicalAuditViewProps> = () => {
  const [audits, setAudits] = useState<PhysicalAudit[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [items, setItems] = useState<MaterialItem[]>([]);
  const [uoms, setUoms] = useState<UOM[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [showModal, setShowModal] = useState<boolean>(false);
  const [selectedAudit, setSelectedAudit] = useState<PhysicalAudit | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Form State
  const [auditDate, setAuditDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [departmentId, setDepartmentId] = useState<number | ''>('');
  const [notes, setNotes] = useState<string>('');
  const [lines, setLines] = useState<Array<{
    material_item_id: number | '';
    uom_id: number | '';
    physical_quantity: string;
    reason: string;
    remarks: string;
  }>>([
    { material_item_id: '', uom_id: '', physical_quantity: '', reason: 'Monthly verification', remarks: '' }
  ]);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  const fetchAudits = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/v1/physical-audits');
      if (res.ok) {
        const data = await res.json();
        setAudits(data);
      }
    } catch (err) {
      console.error('Error fetching physical audits:', err);
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
    fetchAudits();
    fetchReferences();
  }, []);

  const handleAddLine = () => {
    setLines([...lines, { material_item_id: '', uom_id: '', physical_quantity: '', reason: 'Monthly verification', remarks: '' }]);
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

  const handleCreateAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);

    try {
      const payloadLines = lines.map(l => ({
        material_item_id: Number(l.material_item_id),
        uom_id: Number(l.uom_id),
        physical_quantity: l.physical_quantity,
        reason: l.reason || null,
        remarks: l.remarks || null,
      }));

      const payload = {
        audit_date: auditDate,
        department_id: departmentId ? Number(departmentId) : null,
        notes: notes || null,
        lines: payloadLines,
      };

      const res = await apiFetch(`/api/v1/physical-audits/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        setFormError(data.detail || 'Failed to create physical audit');
      } else {
        fetchAudits();
        setShowModal(false);
        setLines([{ material_item_id: '', uom_id: '', physical_quantity: '', reason: 'Monthly verification', remarks: '' }]);
      }
    } catch (err: any) {
      setFormError(err.message || 'Error occurred while saving audit');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAction = async (auditId: number, action: 'submit' | 'approve') => {
    try {
      const res = await apiFetch(`/api/v1/physical-audits/${auditId}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comments: `Action ${action}` }),
      });
      if (res.ok) {
        fetchAudits();
        if (selectedAudit && selectedAudit.id === auditId) {
          const updated = await res.json();
          setSelectedAudit(updated);
        }
      }
    } catch (err) {
      console.error(`Failed to ${action} physical audit:`, err);
    }
  };

  const filteredAudits = audits.filter(a => {
    const matchesStatus = statusFilter === 'ALL' || a.status === statusFilter;
    const matchesSearch = 
      a.audit_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (a.department_name && a.department_name.toLowerCase().includes(searchTerm.toLowerCase()));
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="erp-view">
      <div className="view-header">
        <div>
          <h2>Physical Stock Audits & Adjustments</h2>
          <p className="subtitle">
            Perform physical counts, calculate cutoff variance against ledger balances, and post approved adjustment entries.
          </p>
        </div>
        <div className="header-actions">
          <button className="erp-btn btn-secondary" onClick={fetchAudits}>
            <RefreshCw size={14} className="btn-icon" /> Refresh
          </button>
          <button className="erp-btn btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={14} className="btn-icon" /> Record Physical Count
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="filter-toolbar">
        <div className="search-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search by Audit Document #, Department..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <span className="filter-label">Status:</span>
          {['ALL', 'DRAFT', 'SUBMITTED', 'APPROVED'].map((st) => (
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

      {/* Audits Table */}
      <div className="erp-table-container">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Audit Document #</th>
              <th>Audit Cutoff Date</th>
              <th>Department</th>
              <th>Counted Items</th>
              <th>Status</th>
              <th>Created By</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="text-center p-4">Loading physical audit records...</td></tr>
            ) : filteredAudits.length === 0 ? (
              <tr><td colSpan={7} className="text-center p-4">No audit records match criteria.</td></tr>
            ) : (
              filteredAudits.map((a) => (
                <tr key={a.id} onClick={() => setSelectedAudit(a)} className="cursor-pointer">
                  <td className="font-mono font-medium">{a.audit_number}</td>
                  <td>{a.audit_date}</td>
                  <td>{a.department_name || 'Plant-Wide'}</td>
                  <td>{a.lines?.length || 0} item(s)</td>
                  <td>
                    <span className={`status-pill status-${a.status.toLowerCase()}`}>
                      {a.status}
                    </span>
                  </td>
                  <td>{a.created_by}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="flex gap-1">
                      {a.status === 'DRAFT' && (
                        <button
                          className="erp-btn btn-sm btn-outline"
                          onClick={() => handleAction(a.id, 'submit')}
                        >
                          <Send size={12} /> Submit
                        </button>
                      )}
                      {a.status === 'SUBMITTED' && (
                        <button
                          className="erp-btn btn-sm btn-success"
                          onClick={() => handleAction(a.id, 'approve')}
                        >
                          <CheckCircle size={12} /> Approve & Post
                        </button>
                      )}
                      <button
                        className="erp-btn btn-sm btn-secondary"
                        onClick={() => setSelectedAudit(a)}
                      >
                        <Eye size={12} /> View
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Audit Detail Modal */}
      {selectedAudit && (
        <div className="modal-backdrop" onClick={() => setSelectedAudit(null)}>
          <div className="modal-content max-w-5xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Physical Audit: {selectedAudit.audit_number}</h3>
              <button className="close-btn" onClick={() => setSelectedAudit(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="grid grid-cols-4 gap-4 mb-4 text-sm bg-slate-50 p-3 rounded">
                <div><strong>Cutoff Date:</strong> {selectedAudit.audit_date}</div>
                <div><strong>Department:</strong> {selectedAudit.department_name || 'Plant-Wide'}</div>
                <div><strong>Status:</strong> {selectedAudit.status}</div>
                <div><strong>Created By:</strong> {selectedAudit.created_by}</div>
              </div>

              <h4 className="font-semibold mb-2">Count Comparison & Variance Breakdown</h4>
              <p className="text-xs text-slate-500 mb-2">
                Variance = Physical Count - System Quantity at Cutoff Date. Approved variances are posted as signed adjustments.
              </p>
              <div className="erp-table-container mb-4">
                <table className="erp-table text-xs">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Item Code & Name</th>
                      <th>UOM</th>
                      <th>System Qty at Cutoff</th>
                      <th>Physical Count</th>
                      <th>Calculated Variance</th>
                      <th>Reason / Explanation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedAudit.lines.map((l) => (
                      <tr key={l.line_number}>
                        <td>{l.line_number}</td>
                        <td className="font-medium">{l.item_code} - {l.item_name}</td>
                        <td>{l.uom_code}</td>
                        <td className="font-mono">{l.system_quantity}</td>
                        <td className="font-mono font-semibold">{l.physical_quantity}</td>
                        <td className="font-mono font-bold">
                          <span className={Number(l.variance) > 0 ? 'text-emerald-700' : Number(l.variance) < 0 ? 'text-red-700' : 'text-slate-600'}>
                            {Number(l.variance) > 0 ? `+${l.variance}` : l.variance}
                          </span>
                        </td>
                        <td>{l.reason || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <h4 className="font-semibold mb-2">Audit History</h4>
              <div className="audit-timeline">
                {selectedAudit.audit_logs?.map((log) => (
                  <div key={log.id} className="timeline-item text-xs mb-1">
                    <span className="font-semibold">{log.action}</span> by {log.actor_id} on {new Date(log.timestamp).toLocaleString()}: {log.comments}
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-footer">
              <button className="erp-btn btn-secondary" onClick={() => setSelectedAudit(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="modal-content max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleCreateAudit}>
              <div className="modal-header">
                <h3>Record Physical Inventory Count</h3>
                <button type="button" className="close-btn" onClick={() => setShowModal(false)}>✕</button>
              </div>
              <div className="modal-body">
                {formError && (
                  <div className="alert-error p-3 mb-3 bg-red-50 text-red-700 text-sm rounded">
                    {formError}
                  </div>
                )}

                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div>
                    <label className="form-label">Audit Cutoff Date *</label>
                    <input
                      type="date"
                      className="form-control"
                      value={auditDate}
                      onChange={(e) => setAuditDate(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <label className="form-label">Audited Department</label>
                    <select
                      className="form-control"
                      value={departmentId}
                      onChange={(e) => setDepartmentId(e.target.value ? Number(e.target.value) : '')}
                    >
                      <option value="">-- Plant-Wide Count --</option>
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="form-label">General Audit Notes</label>
                    <input
                      type="text"
                      className="form-control"
                      placeholder="e.g. Q4 Physical stock count"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>
                </div>

                {/* Lines */}
                <div className="mb-4">
                  <div className="flex justify-between items-center mb-2">
                    <h4 className="font-semibold text-sm">Physically Counted Items</h4>
                    <button type="button" className="erp-btn btn-sm btn-secondary" onClick={handleAddLine}>
                      <Plus size={12} /> Add Count Item
                    </button>
                  </div>

                  {lines.map((l, idx) => (
                    <div key={idx} className="grid grid-cols-12 gap-2 mb-2 items-end bg-slate-50 p-2 rounded">
                      <div className="col-span-5">
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
                      <div className="col-span-2">
                        <label className="form-label text-xs">Physical Count *</label>
                        <input
                          type="number"
                          step="any"
                          className="form-control text-xs"
                          placeholder="Measured count"
                          value={l.physical_quantity}
                          onChange={(e) => handleLineChange(idx, 'physical_quantity', e.target.value)}
                          required
                        />
                      </div>
                      <div className="col-span-2">
                        <label className="form-label text-xs">Reason</label>
                        <input
                          type="text"
                          className="form-control text-xs"
                          placeholder="Shrinkage, scrap, etc."
                          value={l.reason}
                          onChange={(e) => handleLineChange(idx, 'reason', e.target.value)}
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
                  {submitting ? 'Calculating Variances...' : 'Create Draft Audit Record'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
