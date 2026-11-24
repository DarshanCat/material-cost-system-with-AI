import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  CheckCircle, 
  Send, 
  X, 
  Search,
  RefreshCw,
  RotateCcw,
  Trash2,
  Image as ImageIcon
} from 'lucide-react';
import type { WasteDisposition, UserRole } from '../types';
import { apiFetch, readApiError } from '../api/client';
import { useReferenceData } from '../hooks/useReferenceData';
import { ReferenceDataNotice } from './ReferenceDataNotice';
import { hasPermission } from '../auth/permissions';

interface WasteDispositionViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const WasteDispositionView: React.FC<WasteDispositionViewProps> = ({ currentRole }) => {
  const canLogWaste = hasPermission(currentRole, 'waste:log');
  const canApproveWaste = hasPermission(currentRole, 'waste:approve');
  const [actionError, setActionError] = useState<string | null>(null);
  const [wastes, setWastes] = useState<WasteDisposition[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const refs = useReferenceData(['items', 'uoms', 'departments']);
  const { items, uoms, departments } = refs;
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
  const [successToast, setSuccessToast] = useState<string | null>(null);

  // Foundry Re-inward vs External Disposal Stream
  const [dispStream, setDispStream] = useState<'RE_INWARD_TO_RM' | 'EXTERNAL_DISPOSAL'>('RE_INWARD_TO_RM');
  const [targetItemId, setTargetItemId] = useState<number | ''>('');
  const [valuationRate, setValuationRate] = useState<string>('32.00');
  const [disposalCost, setDisposalCost] = useState<string>('0.00');
  const [disposalContractor, setDisposalContractor] = useState<string>('');
  const [gatePassNo, setGatePassNo] = useState<string>('');
  const [photoUrl, setPhotoUrl] = useState<string>('');
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
      const res = await apiFetch('/api/v1/waste/');
      if (res.ok) {
        const data = await res.json();
        setWastes(Array.isArray(data) ? data : (data?.items || []));
      }
    } catch (err) {
      console.error('Error fetching waste disposition records:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWastes();
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

      const targetItem = targetItemId ? items.find(i => i.id === Number(targetItemId)) : null;
      const payload = {
        disposition_date: dispDate,
        waste_type: wasteType,
        disposition_type: dispType,
        disposition_stream: dispStream,
        source_department_id: Number(sourceDeptId),
        destination_notes: destinationNotes || null,
        notes: notes || null,
        target_item_id: targetItemId ? Number(targetItemId) : null,
        target_item_code: targetItem?.item_code || null,
        valuation_rate: dispStream === 'RE_INWARD_TO_RM' ? valuationRate : null,
        disposal_cost: dispStream === 'EXTERNAL_DISPOSAL' ? disposalCost : null,
        disposal_contractor: dispStream === 'EXTERNAL_DISPOSAL' ? disposalContractor : null,
        gate_pass_number: dispStream === 'EXTERNAL_DISPOSAL' ? gatePassNo : null,
        photo_url: dispStream === 'EXTERNAL_DISPOSAL' ? photoUrl : null,
        lines: payloadLines,
      };

      const res = await apiFetch(`/api/v1/waste/`, {
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
        setSuccessToast(`Disposition ${data.waste_number || 'record'} logged successfully.`);
        setTimeout(() => setSuccessToast(null), 4000);
      }
    } catch (err: any) {
      setFormError(err.message || 'Error occurred while saving waste disposition');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAction = async (wasteId: number, action: 'submit' | 'approve' | 'reject') => {
    setActionError(null);
    try {
      const res = await apiFetch(`/api/v1/waste/${wasteId}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comments: `Action ${action}` }),
      });
      if (res.ok) {
        const updated = await res.json();
        fetchWastes();
        if (selectedWaste && selectedWaste.id === wasteId) {
          setSelectedWaste(updated);
        }
        if (action === 'approve') {
          setSuccessToast(updated.disposition_stream === 'RE_INWARD_TO_RM' 
            ? `Approved! Material inward successfully posted back to Raw Material inventory under ${updated.target_item_code || 'RM'}.`
            : `Approved! Material disposed externally with gate pass & cost recorded.`
          );
        } else {
          setSuccessToast(`Waste record ${action === 'submit' ? 'submitted for approval' : 'rejected'}.`);
        }
        setTimeout(() => setSuccessToast(null), 4000);
      } else {
        setActionError(await readApiError(res, 'Could not '+action+' the waste record'));
      }
    } catch (err) {
      console.error(`Failed to ${action} waste record:`, err);
      setActionError('Network error: the request could not be completed.');
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
      {successToast && (
        <div className="notification-banner banner-success mb-3">
          <CheckCircle size={16} />
          <span>{successToast}</span>
        </div>
      )}
      {actionError && (
        <div className="erp-alert alert-danger" role="alert">
          {actionError}
        </div>
      )}
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
          {canLogWaste && (
            <button className="erp-btn btn-primary" onClick={() => setShowModal(true)}>
              <Plus size={14} className="btn-icon" /> New Waste Entry
            </button>
          )}
        </div>
      </div>

      <ReferenceDataNotice refs={refs} />

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
              <th>Disposition Stream</th>
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
                    {waste.disposition_stream === 'RE_INWARD_TO_RM' ? (
                      <span className="badge badge-success flex items-center gap-1 text-xs" title="Credited to Raw Material inventory">
                        <RotateCcw size={11} /> Re-Inward ({waste.target_item_code || 'RM'})
                      </span>
                    ) : (
                      <span className="badge badge-outline flex items-center gap-1 text-xs" title={`Disposal cost: ₹${waste.disposal_cost || 0}`}>
                        <Trash2 size={11} /> Disposed (₹{waste.disposal_cost || '0'})
                      </span>
                    )}
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
                      {waste.status === 'DRAFT' && canLogWaste && (
                        <button
                          className="erp-btn btn-sm btn-outline"
                          onClick={() => handleAction(waste.id, 'submit')}
                        >
                          <Send size={12} /> Submit
                        </button>
                      )}
                      {waste.status === 'SUBMITTED' && canApproveWaste && (
                        <>
                          <button
                            className="erp-btn btn-sm btn-success flex items-center gap-1"
                            onClick={() => handleAction(waste.id, 'approve')}
                            title={waste.disposition_stream === 'RE_INWARD_TO_RM' ? 'Approve & Credit to Inventory' : 'Approve Disposal'}
                          >
                            <CheckCircle size={12} /> Approve
                          </button>
                          <button
                            className="erp-btn btn-sm btn-danger flex items-center gap-1"
                            onClick={() => handleAction(waste.id, 'reject')}
                            title="Reject waste disposition"
                          >
                            <X size={12} /> Reject
                          </button>
                        </>
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

              {/* Stream Dossier */}
              {selectedWaste.disposition_stream === 'RE_INWARD_TO_RM' ? (
                <div className="audit-card p-3 mb-4 bg-emerald-50 border border-emerald-200 rounded">
                  <div className="flex justify-between items-center mb-1">
                    <h4 className="font-semibold text-sm flex items-center gap-1 text-emerald-800">
                      <RotateCcw size={16} /> Re-Inward to Raw Material Inventory (Remelt Recovery)
                    </h4>
                    <span className="badge badge-success font-mono font-bold">{selectedWaste.target_item_code || 'RM CREDITED'}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs text-slate-600 mt-2">
                    <div><strong>Valuation Rate:</strong> ₹{selectedWaste.valuation_rate || '32.00'} / KG</div>
                    <div><strong>Live Stock Ledger:</strong> {selectedWaste.status === 'APPROVED' ? 'Stock Credited ✅' : 'Pending Approval'}</div>
                    <div><strong>Destination:</strong> Foundry Storage Bin / Charge Yard</div>
                  </div>
                </div>
              ) : (
                <div className="audit-card p-3 mb-4 bg-amber-50 border border-amber-200 rounded">
                  <div className="flex justify-between items-center mb-1">
                    <h4 className="font-semibold text-sm flex items-center gap-1 text-amber-800">
                      <Trash2 size={16} /> External Scrap Disposal Record
                    </h4>
                    <span className="badge badge-warning font-mono font-bold">Cost: ₹{selectedWaste.disposal_cost || '0'}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs text-slate-600 mt-2">
                    <div><strong>Contractor / Buyer:</strong> {selectedWaste.disposal_contractor || 'External Scrap Dealer'}</div>
                    <div><strong>Gate Pass #:</strong> {selectedWaste.gate_pass_number || 'N/A'}</div>
                    <div><strong>Disposal Evidence:</strong> {selectedWaste.photo_url ? 'Photo Attached 📷' : 'Documented on Weighbridge'}</div>
                  </div>
                  {selectedWaste.photo_url && (
                    <div className="mt-2 text-xs bg-white p-2 rounded border border-amber-100 flex items-center gap-2">
                      <ImageIcon size={14} className="text-amber-600" />
                      <span>Evidence Reference / Photo: <a href={selectedWaste.photo_url} target="_blank" rel="noreferrer" className="text-blue-600 underline">{selectedWaste.photo_url}</a></span>
                    </div>
                  )}
                </div>
              )}

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
                <div className="mb-3">
                  <ReferenceDataNotice refs={refs} />
                </div>
                {formError && (
                  <div className="alert-error p-3 mb-3 bg-red-50 text-red-700 text-sm rounded">
                    {formError}
                  </div>
                )}

                {/* Disposition Stream Selector */}
                <div className="audit-card p-3 mb-4 bg-slate-50 border rounded">
                  <label className="form-label font-bold mb-2 block">Disposition Stream / Policy Action *</label>
                  <div className="grid grid-cols-2 gap-3">
                    <label className={`p-3 rounded border cursor-pointer flex items-start gap-2 ${dispStream === 'RE_INWARD_TO_RM' ? 'bg-emerald-50 border-emerald-500' : 'bg-white'}`}>
                      <input
                        type="radio"
                        name="dispStream"
                        checked={dispStream === 'RE_INWARD_TO_RM'}
                        onChange={() => {
                          setDispStream('RE_INWARD_TO_RM');
                          setDispType('INTERNAL_RECOVERY');
                        }}
                        className="mt-1"
                      />
                      <div>
                        <strong className="text-emerald-800 text-sm block">Re-Inward to Raw Material (Recycle)</strong>
                        <span className="text-xs text-slate-500">For reusable Foundry Borings, Runners, Risers, Gatings & Returns. Adds directly back to available inventory upon approval.</span>
                      </div>
                    </label>

                    <label className={`p-3 rounded border cursor-pointer flex items-start gap-2 ${dispStream === 'EXTERNAL_DISPOSAL' ? 'bg-amber-50 border-amber-500' : 'bg-white'}`}>
                      <input
                        type="radio"
                        name="dispStream"
                        checked={dispStream === 'EXTERNAL_DISPOSAL'}
                        onChange={() => {
                          setDispStream('EXTERNAL_DISPOSAL');
                          setDispType('SCRAP_OUTWARD');
                        }}
                        className="mt-1"
                      />
                      <div>
                        <strong className="text-amber-800 text-sm block">External Disposal / Scrap Sale</strong>
                        <span className="text-xs text-slate-500">For non-reusable dross/slag or external scrap sales. Captures contractor, gate pass, disposal cost & photo.</span>
                      </div>
                    </label>
                  </div>
                </div>

                {dispStream === 'RE_INWARD_TO_RM' ? (
                  <div className="grid grid-cols-2 gap-3 mb-4 p-3 bg-emerald-50/50 border border-emerald-200 rounded">
                    <div>
                      <label className="form-label">Matching Inward Raw Material Code *</label>
                      <select
                        className="form-control"
                        value={targetItemId}
                        onChange={(e) => setTargetItemId(e.target.value ? Number(e.target.value) : '')}
                        required
                      >
                        <option value="">-- Select Target RM Code to Credit Stock --</option>
                        {items
                          .filter(i => i.item_code?.includes('RM') || i.category?.includes('Raw') || i.name?.toLowerCase().includes('scrap') || i.name?.toLowerCase().includes('return'))
                          .map((i) => (
                            <option key={i.id} value={i.id}>{i.item_code} - {i.name}</option>
                          ))
                        }
                        {items.slice(0, 10).map((i) => (
                          <option key={'all-'+i.id} value={i.id}>{i.item_code} - {i.name}</option>
                        ))}
                      </select>
                      <small className="text-xs text-emerald-700">Stock will be credited to this Raw Material item upon approval.</small>
                    </div>
                    <div>
                      <label className="form-label">Internal Recovery Rate (₹ / KG)</label>
                      <input
                        type="number"
                        step="0.01"
                        className="form-control font-mono"
                        value={valuationRate}
                        onChange={(e) => setValuationRate(e.target.value)}
                        placeholder="32.00"
                      />
                      <small className="text-xs text-slate-500">Accounting valuation for internal remelt inventory.</small>
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-3 gap-3 mb-4 p-3 bg-amber-50/50 border border-amber-200 rounded">
                    <div>
                      <label className="form-label">Disposal Cost / Realized Sale (₹) *</label>
                      <input
                        type="number"
                        step="0.01"
                        className="form-control font-mono"
                        value={disposalCost}
                        onChange={(e) => setDisposalCost(e.target.value)}
                        placeholder="0.00"
                        required
                      />
                      <small className="text-xs text-slate-500">Cost paid to haul off, or revenue from scrap sale.</small>
                    </div>
                    <div>
                      <label className="form-label">Disposal Contractor / Scrap Buyer</label>
                      <input
                        type="text"
                        className="form-control"
                        value={disposalContractor}
                        onChange={(e) => setDisposalContractor(e.target.value)}
                        placeholder="e.g. Mahalakshmi Metal Recyclers"
                      />
                    </div>
                    <div>
                      <label className="form-label">Gate Pass / Weighment Slip #</label>
                      <input
                        type="text"
                        className="form-control font-mono"
                        value={gatePassNo}
                        onChange={(e) => setGatePassNo(e.target.value)}
                        placeholder="GP-2026-1049"
                      />
                    </div>
                    <div className="col-span-3">
                      <label className="form-label">Disposal Evidence Image / Photo Reference URL</label>
                      <input
                        type="text"
                        className="form-control"
                        value={photoUrl}
                        onChange={(e) => setPhotoUrl(e.target.value)}
                        placeholder="https://... or photo file note / weighbridge scale photo"
                      />
                    </div>
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
                      <option value="">{refs.placeholder('departments', '-- Source Dept --')}</option>
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
                          <option value="">{refs.placeholder('items', '-- Select Material Item --')}</option>
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
                          <option value="">{refs.placeholder('uoms', '-- UOM --')}</option>
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
                <button type="submit" className="erp-btn btn-primary" disabled={submitting || refs.unavailable}>
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
