import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  CheckCircle, 
  Send, 
  X, 
  Search,
  RefreshCw
} from 'lucide-react';
import type { WasteDisposition, MaterialItem, UOM, Department, UserRole } from '../types';

interface WasteDispositionViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const WasteDispositionView: React.FC<WasteDispositionViewProps> = ({ currentRole, currentUserId }) => {
  const [wastes, setWastes] = useState<WasteDisposition[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [items, setItems] = useState<MaterialItem[]>([]);
  const [uoms, setUoms] = useState<UOM[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [showModal, setShowModal] = useState<boolean>(false);
  const [selectedWaste, setSelectedWaste] = useState<WasteDisposition | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Form State
  const [dispDate, setDispDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [wasteType, setWasteType] = useState<string>('BORINGS');
  const [dispType, setDispType] = useState<string>('INTERNAL_RECOVERY');
  const [sourceDeptId, setSourceDeptId] = useState<number | ''>('');
  const [destinationNotes, setDestinationNotes] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [lines, setLines] = useState<Array<{
    material_item_id: number | '';
    uom_id: number | '';
    quantity: string;
    reason: string;
  }>>([
    { material_item_id: '', uom_id: '', quantity: '', reason: '' }
  ]);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  const fetchWastes = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/waste');
      if (res.ok) {
        const data = await res.json();
        setWastes(data);
      }
    } catch (err) {
      console.error('Error fetching waste disposition records:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchReferences = async () => {
    try {
      const [iRes, uRes, dRes] = await Promise.all([
        fetch('/api/v1/items?limit=500'),
        fetch('/api/v1/uoms'),
        fetch('/api/v1/departments'),
      ]);
      if (iRes.ok) setItems(await iRes.json());
      if (uRes.ok) setUoms(await uRes.json());
      if (dRes.ok) setDepartments(await dRes.json());
    } catch (err) {
      console.error('Error fetching references:', err);
    }
  };

  useEffect(() => {
    fetchWastes();
    fetchReferences();
  }, []);

  const handleAddLine = () => {
    setLines([...lines, { material_item_id: '', uom_id: '', quantity: '', reason: '' }]);
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

  const handleCreateWaste = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);

    try {
      const payloadLines = lines.map((l, index) => ({
        line_number: index + 1,
        material_item_id: Number(l.material_item_id),
        uom_id: Number(l.uom_id),
        quantity: l.quantity,
        reason: l.reason || 'Foundry generation',
      }));

      const payload = {
        disposition_date: dispDate,
        waste_type: wasteType,
        disposition_type: dispType,
        source_department_id: Number(sourceDeptId),
        destination_notes: destinationNotes || null,
        notes: notes || null,
        lines: payloadLines,
      };

      const res = await fetch(`/api/v1/waste/?created_by=${currentRole}%20(${currentUserId})`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        setFormError(data.detail || 'Failed to create waste disposition record');
      } else {
        fetchWastes();
        setShowModal(false);
        setLines([{ material_item_id: '', uom_id: '', quantity: '', reason: '' }]);
      }
    } catch (err: any) {
      setFormError(err.message || 'Error occurred while saving waste disposition');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAction = async (wasteId: number, action: 'submit' | 'approve') => {
    try {
      const res = await fetch(`/api/v1/waste/${wasteId}/${action}?actor_id=${currentRole}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comments: `Action ${action} by ${currentRole}` }),
      });
      if (res.ok) {
        fetchWastes();
        if (selectedWaste && selectedWaste.id === wasteId) {
          const updated = await res.json();
          setSelectedWaste(updated);
        }
      }
    } catch (err) {
      console.error(`Failed to ${action} waste record:`, err);
    }
  };

  const filteredWastes = wastes.filter(w => {
    const matchesStatus = statusFilter === 'ALL' || w.status === statusFilter;
    const matchesSearch = 
      w.waste_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      w.waste_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (w.source_department_name && w.source_department_name.toLowerCase().includes(searchTerm.toLowerCase()));
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="erp-view">
      <div className="view-header">
        <div>
          <h2>Scrap & Waste Disposition</h2>
          <p className="subtitle">
            Track and classify foundry returns, machining borings, runners, risers, and rejected castings.
          </p>
        </div>
        <div className="header-actions">
          <button className="erp-btn btn-secondary" onClick={fetchWastes}>
            <RefreshCw size={14} className="btn-icon" /> Refresh
          </button>
          <button className="erp-btn btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={14} className="btn-icon" /> New Waste Entry
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="filter-toolbar">
        <div className="search-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search by Waste #, Type, Department..."
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

      {/* Table */}
      <div className="erp-table-container">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Disposition #</th>
              <th>Date</th>
              <th>Waste Type</th>
              <th>Disposition Type</th>
              <th>Source Dept</th>
              <th>Items</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="text-center p-4">Loading waste records...</td></tr>
            ) : filteredWastes.length === 0 ? (
              <tr><td colSpan={8} className="text-center p-4">No waste records match criteria.</td></tr>
            ) : (
              filteredWastes.map((waste) => (
                <tr key={waste.id} onClick={() => setSelectedWaste(waste)} className="cursor-pointer">
                  <td className="font-mono font-medium">{waste.waste_number}</td>
                  <td>{waste.disposition_date}</td>
                  <td>
                    <span className="badge badge-warning">{waste.waste_type}</span>
                  </td>
                  <td>
                    <span className="badge badge-outline">{waste.disposition_type}</span>
                  </td>
                  <td>{waste.source_department_name}</td>
                  <td>{waste.lines?.length || 0} line(s)</td>
                  <td>
                    <span className={`status-pill status-${waste.status.toLowerCase()}`}>
                      {waste.status}
                    </span>
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="flex gap-1">
                      {waste.status === 'DRAFT' && (
                        <button
                          className="erp-btn btn-sm btn-outline"
                          onClick={() => handleAction(waste.id, 'submit')}
                        >
                          <Send size={12} /> Submit
                        </button>
                      )}
                      {waste.status === 'SUBMITTED' && (
                        <button
                          className="erp-btn btn-sm btn-success"
                          onClick={() => handleAction(waste.id, 'approve')}
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
      {selectedWaste && (
        <div className="modal-backdrop" onClick={() => setSelectedWaste(null)}>
          <div className="modal-content max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Waste Record: {selectedWaste.waste_number}</h3>
              <button className="close-btn" onClick={() => setSelectedWaste(null)}><X size={18} /></button>
            </div>
            <div className="modal-body">
              <div className="grid grid-cols-3 gap-4 mb-4 text-sm">
                <div><strong>Date:</strong> {selectedWaste.disposition_date}</div>
                <div><strong>Waste Type:</strong> {selectedWaste.waste_type}</div>
                <div><strong>Disposition Type:</strong> {selectedWaste.disposition_type}</div>
                <div><strong>Source Dept:</strong> {selectedWaste.source_department_name}</div>
                <div><strong>Destination / Handling:</strong> {selectedWaste.destination_notes || 'Internal'}</div>
                <div><strong>Status:</strong> {selectedWaste.status}</div>
              </div>

              <h4 className="font-semibold mb-2">Line Items</h4>
              <table className="erp-table mb-4">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Item Code & Name</th>
                    <th>UOM</th>
                    <th>Quantity</th>
                    <th>Reason / Generation</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedWaste.lines.map((l) => (
                    <tr key={l.line_number}>
                      <td>{l.line_number}</td>
                      <td>{l.item_code} - {l.item_name}</td>
                      <td>{l.uom_code}</td>
                      <td className="font-mono font-medium">{l.quantity}</td>
                      <td>{l.reason || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h4 className="font-semibold mb-2">Audit History</h4>
              <div className="audit-timeline">
                {selectedWaste.audit_logs?.map((log) => (
                  <div key={log.id} className="timeline-item text-xs mb-1">
                    <span className="font-semibold">{log.action}</span> by {log.actor_id} on {new Date(log.timestamp).toLocaleString()}: {log.comments}
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-footer">
              <button className="erp-btn btn-secondary" onClick={() => setSelectedWaste(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="modal-content max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleCreateWaste}>
              <div className="modal-header">
                <h3>New Scrap / Waste Disposition</h3>
                <button type="button" className="close-btn" onClick={() => setShowModal(false)}><X size={18} /></button>
              </div>
              <div className="modal-body">
                {formError && (
                  <div className="alert-error p-3 mb-3 bg-red-50 text-red-700 text-sm rounded">
                    {formError}
                  </div>
                )}

                <div className="grid grid-cols-4 gap-3 mb-4">
                  <div>
                    <label className="form-label">Disposition Date *</label>
                    <input
                      type="date"
                      className="form-control"
                      value={dispDate}
                      onChange={(e) => setDispDate(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <label className="form-label">Waste Type *</label>
                    <select
                      className="form-control"
                      value={wasteType}
                      onChange={(e) => setWasteType(e.target.value)}
                    >
                      <option value="BORINGS">Machining Borings</option>
                      <option value="GATINGS_RUNNERS">Gatings & Runners</option>
                      <option value="RETURNS">Foundry Returns</option>
                      <option value="REJECTED_CASTINGS">Rejected Castings</option>
                      <option value="SLAG">Furnace Slag</option>
                      <option value="OTHER_SCRAP">Other Scrap</option>
                    </select>
                  </div>
                  <div>
                    <label className="form-label">Disposition Type *</label>
                    <select
                      className="form-control"
                      value={dispType}
                      onChange={(e) => setDispType(e.target.value)}
                    >
                      <option value="INTERNAL_RECOVERY">Internal Recovery (Remelt)</option>
                      <option value="SCRAP_OUTWARD">Scrap Outward (Sale)</option>
                      <option value="INSPECTION_HOLD">Inspection Hold (QA Review)</option>
                    </select>
                  </div>
                  <div>
                    <label className="form-label">Source Dept *</label>
                    <select
                      className="form-control"
                      value={sourceDeptId}
                      onChange={(e) => setSourceDeptId(e.target.value ? Number(e.target.value) : '')}
                      required
                    >
                      <option value="">-- Source Dept --</option>
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div>
                    <label className="form-label">Destination / Handling Notes</label>
                    <input
                      type="text"
                      className="form-control"
                      placeholder="e.g. Moved to scrap yard bin 4, re-melting batch"
                      value={destinationNotes}
                      onChange={(e) => setDestinationNotes(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="form-label">General Remarks</label>
                    <input
                      type="text"
                      className="form-control"
                      placeholder="Batch observations, reason for scrap"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>
                </div>

                {/* Lines */}
                <div className="mb-4">
                  <div className="flex justify-between items-center mb-2">
                    <h4 className="font-semibold text-sm">Waste Material Items</h4>
                    <button type="button" className="erp-btn btn-sm btn-secondary" onClick={handleAddLine}>
                      <Plus size={12} /> Add Item
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
                        <label className="form-label text-xs">Quantity *</label>
                        <input
                          type="number"
                          step="any"
                          className="form-control text-xs"
                          placeholder="e.g. 500"
                          value={l.quantity}
                          onChange={(e) => handleLineChange(idx, 'quantity', e.target.value)}
                          required
                        />
                      </div>
                      <div className="col-span-2">
                        <label className="form-label text-xs">Generation Reason</label>
                        <input
                          type="text"
                          className="form-control text-xs"
                          placeholder="e.g. Tool chatter"
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
                  {submitting ? 'Creating...' : 'Create Draft Waste Record'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
