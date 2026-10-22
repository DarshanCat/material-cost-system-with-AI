import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  CheckCircle, 
  AlertTriangle, 
  Send, 
  X, 
  Search,
  RefreshCw
} from 'lucide-react';
import type { GRN, MaterialItem, UOM, Vendor, UserRole } from '../types';
import { apiFetch, readApiError } from '../api/client';

interface GRNManagementViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const GRNManagementView: React.FC<GRNManagementViewProps> = () => {
  const [actionError, setActionError] = useState<string | null>(null);
  const [grns, setGrns] = useState<GRN[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [items, setItems] = useState<MaterialItem[]>([]);
  const [uoms, setUoms] = useState<UOM[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [showModal, setShowModal] = useState<boolean>(false);
  const [selectedGRN, setSelectedGRN] = useState<GRN | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Form State
  const [sourceType, setSourceType] = useState<'EXTERNAL_VENDOR' | 'INTERNAL_VSPL' | 'SEGREGATION_YARD'>('EXTERNAL_VENDOR');
  const [vendorId, setVendorId] = useState<number | ''>('');
  const [receiptDate, setReceiptDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [invoiceNo, setInvoiceNo] = useState<string>('');
  const [invoiceDate, setInvoiceDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState<string>('');
  const [lines, setLines] = useState<Array<{
    material_item_id: number | '';
    uom_id: number | '';
    quantity: string;
    rate_ex_gst: string;
    gst_percent: string;
    remarks: string;
  }>>([
    { material_item_id: '', uom_id: '', quantity: '', rate_ex_gst: '', gst_percent: '18', remarks: '' }
  ]);
  const [formError, setFormError] = useState<string | null>(null);
  const [formWarnings, setFormWarnings] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState<boolean>(false);

  const fetchGRNs = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/v1/grn/');
      if (res.ok) {
        const data = await res.json();
        setGrns(data);
      }
    } catch (err) {
      console.error('Error fetching GRNs:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchReferences = async () => {
    try {
      const [iRes, uRes, vRes] = await Promise.all([
        apiFetch('/api/v1/items?limit=500'),
        apiFetch('/api/v1/uoms'),
        apiFetch('/api/v1/vendors?size=200'),
      ]);
      if (iRes.ok) setItems(await iRes.json());
      if (uRes.ok) setUoms(await uRes.json());
      if (vRes.ok) {
        const vData = await vRes.json();
        setVendors(vData.items || []);
      }
    } catch (err) {
      console.error('Error fetching references:', err);
    }
  };

  useEffect(() => {
    fetchGRNs();
    fetchReferences();
  }, []);

  const handleAddLine = () => {
    setLines([...lines, { material_item_id: '', uom_id: '', quantity: '', rate_ex_gst: '', gst_percent: '18', remarks: '' }]);
  };

  const handleRemoveLine = (idx: number) => {
    if (lines.length > 1) {
      setLines(lines.filter((_, i) => i !== idx));
    }
  };

  const handleLineChange = (idx: number, field: string, value: any) => {
    const updated = [...lines];
    updated[idx] = { ...updated[idx], [field]: value };
    
    // Auto-populate UOM if material item selected
    if (field === 'material_item_id' && value) {
      const selectedItem = items.find(i => i.id === Number(value));
      if (selectedItem) {
        updated[idx].uom_id = selectedItem.base_uom_id;
      }
    }
    setLines(updated);
  };

  const handleCreateGRN = async (e: React.FormEvent) => {
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
        rate_ex_gst: l.rate_ex_gst ? l.rate_ex_gst : null,
        gst_percent: l.gst_percent ? l.gst_percent : null,
        remarks: l.remarks || null,
      }));

      const payload = {
        receipt_date: receiptDate,
        source_type: sourceType,
        vendor_id: vendorId ? Number(vendorId) : null,
        vendor_invoice_no: invoiceNo || null,
        invoice_date: invoiceDate || null,
        notes: notes || null,
        lines: payloadLines,
      };

      const res = await apiFetch(`/api/v1/grn/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        setFormError(data.detail || 'Failed to create GRN');
      } else {
        if (data.validation_warnings && data.validation_warnings.length > 0) {
          setFormWarnings(data.validation_warnings);
        }
        fetchGRNs();
        setShowModal(false);
        // Reset form
        setLines([{ material_item_id: '', uom_id: '', quantity: '', rate_ex_gst: '', gst_percent: '18', remarks: '' }]);
      }
    } catch (err: any) {
      setFormError(err.message || 'Error occurred while saving GRN');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAction = async (grnId: number, action: 'submit' | 'approve' | 'cancel') => {
    setActionError(null);
    try {
      const res = await apiFetch(`/api/v1/grn/${grnId}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comments: `Action ${action}` }),
      });
      if (res.ok) {
        fetchGRNs();
        if (selectedGRN && selectedGRN.id === grnId) {
          const updated = await res.json();
          setSelectedGRN(updated);
        }
      } else {
        setActionError(await readApiError(res, 'Could not '+action+' the GRN'));
      }
    } catch (err) {
      console.error(`Failed to ${action} GRN:`, err);
      setActionError('Network error: the request could not be completed.');
    }
  };

  const filteredGRNs = grns.filter(g => {
    const matchesStatus = statusFilter === 'ALL' || g.status === statusFilter;
    const matchesSearch = 
      g.grn_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (g.vendor_name && g.vendor_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (g.vendor_invoice_no && g.vendor_invoice_no.toLowerCase().includes(searchTerm.toLowerCase()));
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
          <h2>Goods Receipt Notes (GRN)</h2>
          <p className="subtitle">
            Record material inward from External Vendors, Internal VSPL, and Segregation Yard.
          </p>
        </div>
        <div className="header-actions">
          <button className="erp-btn btn-secondary" onClick={fetchGRNs}>
            <RefreshCw size={14} className="btn-icon" /> Refresh
          </button>
          <button className="erp-btn btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={14} className="btn-icon" /> New GRN Entry
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
            placeholder="Search by GRN #, Vendor, Invoice #..."
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

      {/* GRN Table */}
      <div className="erp-table-container">
        <table className="erp-table">
          <thead>
            <tr>
              <th>GRN Document #</th>
              <th>Receipt Date</th>
              <th>Source Type</th>
              <th>Vendor / Inward Entity</th>
              <th>Invoice #</th>
              <th>Items</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="text-center p-4">Loading GRN records...</td></tr>
            ) : filteredGRNs.length === 0 ? (
              <tr><td colSpan={8} className="text-center p-4">No GRNs match current criteria.</td></tr>
            ) : (
              filteredGRNs.map((grn) => (
                <tr key={grn.id} onClick={() => setSelectedGRN(grn)} className="cursor-pointer">
                  <td className="font-mono font-medium">{grn.grn_number}</td>
                  <td>{grn.receipt_date}</td>
                  <td>
                    <span className="badge badge-outline">{grn.source_type}</span>
                  </td>
                  <td>{grn.vendor_name || 'Internal VSPL / Yard'}</td>
                  <td>{grn.vendor_invoice_no || '—'}</td>
                  <td>{grn.lines?.length || 0} line(s)</td>
                  <td>
                    <span className={`status-pill status-${grn.status.toLowerCase()}`}>
                      {grn.status}
                    </span>
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="flex gap-1">
                      {grn.status === 'DRAFT' && (
                        <button
                          className="erp-btn btn-sm btn-outline"
                          onClick={() => handleAction(grn.id, 'submit')}
                        >
                          <Send size={12} /> Submit
                        </button>
                      )}
                      {grn.status === 'SUBMITTED' && (
                        <button
                          className="erp-btn btn-sm btn-success"
                          onClick={() => handleAction(grn.id, 'approve')}
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

      {/* Selected GRN Detail Drawer / Modal */}
      {selectedGRN && (
        <div className="modal-backdrop" onClick={() => setSelectedGRN(null)}>
          <div className="modal-content max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>GRN Details: {selectedGRN.grn_number}</h3>
              <button className="close-btn" onClick={() => setSelectedGRN(null)}><X size={18} /></button>
            </div>
            <div className="modal-body">
              <div className="grid grid-cols-3 gap-4 mb-4 text-sm">
                <div><strong>Receipt Date:</strong> {selectedGRN.receipt_date}</div>
                <div><strong>Source:</strong> {selectedGRN.source_type}</div>
                <div><strong>Status:</strong> {selectedGRN.status}</div>
                <div><strong>Vendor:</strong> {selectedGRN.vendor_name || 'N/A'}</div>
                <div><strong>Invoice #:</strong> {selectedGRN.vendor_invoice_no || 'N/A'}</div>
                <div><strong>Invoice Date:</strong> {selectedGRN.invoice_date || 'N/A'}</div>
              </div>

              <h4 className="font-semibold mb-2">Material Line Items</h4>
              <table className="erp-table mb-4">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Item Code & Name</th>
                    <th>UOM</th>
                    <th>Quantity</th>
                    <th>Rate Ex GST (₹)</th>
                    <th>GST %</th>
                    <th>Remarks</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedGRN.lines.map((l) => (
                    <tr key={l.line_number}>
                      <td>{l.line_number}</td>
                      <td>{l.item_code} - {l.item_name}</td>
                      <td>{l.uom_code}</td>
                      <td className="font-mono">{l.quantity}</td>
                      <td className="font-mono">{l.rate_ex_gst ? `₹${l.rate_ex_gst}` : '—'}</td>
                      <td>{l.gst_percent ? `${l.gst_percent}%` : '—'}</td>
                      <td>{l.remarks || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h4 className="font-semibold mb-2">Audit History</h4>
              <div className="audit-timeline">
                {selectedGRN.audit_logs?.map((log) => (
                  <div key={log.id} className="timeline-item text-xs mb-1">
                    <span className="font-semibold">{log.action}</span> by {log.actor_id} on {new Date(log.timestamp).toLocaleString()}: {log.comments}
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-footer">
              <button className="erp-btn btn-secondary" onClick={() => setSelectedGRN(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="modal-content max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleCreateGRN}>
              <div className="modal-header">
                <h3>New Goods Receipt Note (GRN)</h3>
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
                    <label className="form-label">Receipt Date *</label>
                    <input
                      type="date"
                      className="form-control"
                      value={receiptDate}
                      onChange={(e) => setReceiptDate(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <label className="form-label">Source Type *</label>
                    <select
                      className="form-control"
                      value={sourceType}
                      onChange={(e: any) => setSourceType(e.target.value)}
                    >
                      <option value="EXTERNAL_VENDOR">External Vendor</option>
                      <option value="INTERNAL_VSPL">Internal VSPL Movement</option>
                      <option value="SEGREGATION_YARD">Segregation Yard</option>
                    </select>
                  </div>
                  {sourceType === 'EXTERNAL_VENDOR' && (
                    <div>
                      <label className="form-label">Vendor Reference *</label>
                      <select
                        className="form-control"
                        value={vendorId}
                        onChange={(e) => setVendorId(e.target.value ? Number(e.target.value) : '')}
                        required={sourceType === 'EXTERNAL_VENDOR'}
                      >
                        <option value="">-- Select Vendor --</option>
                        {vendors.map((v) => (
                          <option key={v.id} value={v.id}>{v.name} {v.gstin ? `(${v.gstin})` : ''}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>

                {sourceType === 'EXTERNAL_VENDOR' && (
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div>
                      <label className="form-label">Vendor Invoice Number</label>
                      <input
                        type="text"
                        className="form-control"
                        placeholder="e.g. INV-2026-0982"
                        value={invoiceNo}
                        onChange={(e) => setInvoiceNo(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Invoice Date</label>
                      <input
                        type="date"
                        className="form-control"
                        value={invoiceDate}
                        onChange={(e) => setInvoiceDate(e.target.value)}
                      />
                    </div>
                  </div>
                )}

                {/* Line Items Entry */}
                <div className="mb-4">
                  <div className="flex justify-between items-center mb-2">
                    <h4 className="font-semibold text-sm">Material Line Items</h4>
                    <button type="button" className="erp-btn btn-sm btn-secondary" onClick={handleAddLine}>
                      <Plus size={12} /> Add Item
                    </button>
                  </div>

                  {lines.map((l, idx) => (
                    <div key={idx} className="grid grid-cols-12 gap-2 mb-2 items-end bg-slate-50 p-2 rounded">
                      <div className="col-span-4">
                        <label className="form-label text-xs">Item *</label>
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
                          placeholder="e.g. 1500"
                          value={l.quantity}
                          onChange={(e) => handleLineChange(idx, 'quantity', e.target.value)}
                          required
                        />
                      </div>
                      <div className="col-span-2">
                        <label className="form-label text-xs">Rate Ex GST (₹)</label>
                        <input
                          type="number"
                          step="0.01"
                          className="form-control text-xs"
                          placeholder="Rate"
                          value={l.rate_ex_gst}
                          onChange={(e) => handleLineChange(idx, 'rate_ex_gst', e.target.value)}
                        />
                      </div>
                      <div className="col-span-1">
                        <label className="form-label text-xs">GST %</label>
                        <input
                          type="number"
                          step="0.1"
                          className="form-control text-xs"
                          value={l.gst_percent}
                          onChange={(e) => handleLineChange(idx, 'gst_percent', e.target.value)}
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

                <div className="mb-2">
                  <label className="form-label">Notes / Remarks</label>
                  <textarea
                    className="form-control"
                    rows={2}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Reference gate pass, vehicle number, or inward conditions..."
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="erp-btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="erp-btn btn-primary" disabled={submitting}>
                  {submitting ? 'Creating...' : 'Create Draft GRN'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
