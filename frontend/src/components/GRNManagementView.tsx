import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  CheckCircle, 
  AlertTriangle, 
  Send, 
  X, 
  Search,
  RefreshCw,
  ShieldCheck,
  XCircle,
  CreditCard,
  FileCheck
} from 'lucide-react';
import type { GRN, UserRole } from '../types';
import { apiFetch, readApiError } from '../api/client';
import { useReferenceData } from '../hooks/useReferenceData';
import { ReferenceDataNotice } from './ReferenceDataNotice';

interface GRNManagementViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const GRNManagementView: React.FC<GRNManagementViewProps> = () => {
  const [actionError, setActionError] = useState<string | null>(null);
  const [grns, setGrns] = useState<GRN[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const refs = useReferenceData(['items', 'uoms', 'vendors']);
  const { items, uoms, vendors } = refs;
  const [showModal, setShowModal] = useState<boolean>(false);
  const [selectedGRN, setSelectedGRN] = useState<GRN | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [successToast, setSuccessToast] = useState<string | null>(null);

  // Quality Inspection Modal State (Approve / Reject with Quality Certificate)
  const [showQualityModal, setShowQualityModal] = useState<boolean>(false);
  const [qualityGrn, setQualityGrn] = useState<GRN | null>(null);
  const [qualityAction, setQualityAction] = useState<'approve' | 'reject'>('approve');
  const [qualityDocNo, setQualityDocNo] = useState<string>('');
  const [qualityStatus, setQualityStatus] = useState<'PASSED' | 'CONDITIONALLY_ACCEPTED' | 'REJECTED'>('PASSED');
  const [qualityNotes, setQualityNotes] = useState<string>('');
  const [heatLotNo, setHeatLotNo] = useState<string>('');
  const [qualitySubmitting, setQualitySubmitting] = useState<boolean>(false);

  // P2P Payment Settlement Modal State
  const [showPaymentModal, setShowPaymentModal] = useState<boolean>(false);
  const [paymentGrn, setPaymentGrn] = useState<GRN | null>(null);
  const [amountPaid, setAmountPaid] = useState<string>('');
  const [paymentRef, setPaymentRef] = useState<string>('');
  const [paymentDate, setPaymentDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [paymentMode, setPaymentMode] = useState<'NEFT_RTGS' | 'CHEQUE' | 'BANK_TRANSFER' | 'UPI'>('NEFT_RTGS');
  const [paymentNotes, setPaymentNotes] = useState<string>('');
  const [paymentSubmitting, setPaymentSubmitting] = useState<boolean>(false);

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
  const [approvedPOs, setApprovedPOs] = useState<any[]>([]);
  const [selectedPOId, setSelectedPOId] = useState<number | ''>('');

  const fetchApprovedPOs = async () => {
    try {
      const res = await apiFetch('/api/v1/purchase-orders/');
      if (res.ok) {
        const data = await res.json();
        const list = Array.isArray(data) ? data : (data.items || []);
        setApprovedPOs(list.filter((p: any) => p.status === 'APPROVED'));
      }
    } catch {}
  };

  const fetchGRNs = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/v1/grn/');
      if (res.ok) {
        const data = await res.json();
        setGrns(Array.isArray(data) ? data : (data?.items || []));
      }
    } catch (err) {
      console.error('Error fetching GRNs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGRNs();
    fetchApprovedPOs();
  }, []);

  const handleSelectPO = (poIdStr: string) => {
    if (!poIdStr) {
      setSelectedPOId('');
      return;
    }
    const pid = Number(poIdStr);
    setSelectedPOId(pid);
    const po = approvedPOs.find((p) => p.id === pid);
    if (po) {
      setVendorId(po.vendor_id);
      setNotes((prev) => (prev ? `${prev} | Linked PO: ${po.po_number}` : `Linked PO: ${po.po_number}`));
      if (po.lines && po.lines.length > 0) {
        setLines(
          po.lines.map((l: any) => ({
            material_item_id: l.material_item_id,
            uom_id: l.uom_id,
            quantity: String(l.quantity),
            rate_ex_gst: String(l.unit_rate_ex_gst),
            gst_percent: String(l.gst_percent || '18'),
            remarks: `From PO line #${l.line_number}: ${l.remarks || ''}`.trim(),
          }))
        );
      }
    }
  };

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

  const openQualityDecision = (grn: GRN, action: 'approve' | 'reject') => {
    setQualityGrn(grn);
    setQualityAction(action);
    setQualityDocNo(grn.quality_document_number || `TC-${new Date().getFullYear()}-${String(grn.id).padStart(4, '0')}`);
    setQualityStatus(action === 'approve' ? 'PASSED' : 'REJECTED');
    setQualityNotes('');
    setHeatLotNo('');
    setShowQualityModal(true);
  };

  const submitQualityDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!qualityGrn) return;
    if (qualityAction === 'reject' && !qualityNotes.trim()) {
      setActionError('Quality rejection comments are mandatory.');
      return;
    }
    setQualitySubmitting(true);
    setActionError(null);
    try {
      const res = await apiFetch(`/api/v1/grn/${qualityGrn.id}/${qualityAction}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          comments: qualityNotes,
          quality_document_number: qualityDocNo.trim() || null,
          quality_inspection_status: qualityStatus,
          quality_inspection_notes: qualityNotes.trim() || null,
          heat_lot_verified: heatLotNo.trim() || null,
        }),
      });
      if (res.ok) {
        setShowQualityModal(false);
        fetchGRNs();
        setSuccessToast(`GRN ${qualityGrn.grn_number} successfully ${qualityAction === 'approve' ? 'approved with Quality Certificate attached' : 'rejected and quarantined'}.`);
        setTimeout(() => setSuccessToast(null), 4000);
      } else {
        setActionError(await readApiError(res, `Could not ${qualityAction} the GRN`));
      }
    } catch (err: any) {
      setActionError(`Network error: ${err.message}`);
    } finally {
      setQualitySubmitting(false);
    }
  };

  const openPaymentModal = (grn: GRN) => {
    setPaymentGrn(grn);
    const totalWithGst = (grn.lines || []).reduce((sum, l) => {
      const lineEx = Number(l.quantity || 0) * Number(l.rate_ex_gst || 0);
      const gst = lineEx * (Number(l.gst_percent || 0) / 100);
      return sum + lineEx + gst;
    }, 0);
    setAmountPaid(totalWithGst > 0 ? totalWithGst.toFixed(2) : '54000.00');
    setPaymentRef(`UTR-${Date.now().toString().slice(-8)}`);
    setPaymentDate(new Date().toISOString().slice(0, 10));
    setPaymentMode('NEFT_RTGS');
    setPaymentNotes('Settled via HDFC Bank Corporate NetBanking');
    setShowPaymentModal(true);
  };

  const submitPaymentRecord = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!paymentGrn) return;
    setPaymentSubmitting(true);
    setActionError(null);
    try {
      const res = await apiFetch(`/api/v1/grn/${paymentGrn.id}/payment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          payment_status: 'PAID',
          amount_paid: amountPaid,
          payment_reference: paymentRef,
          payment_date: paymentDate,
          payment_mode: paymentMode,
          payment_notes: paymentNotes,
        }),
      });
      if (res.ok) {
        setShowPaymentModal(false);
        fetchGRNs();
        setSuccessToast(`Payment of ₹${amountPaid} for GRN ${paymentGrn.grn_number} recorded successfully (UTR: ${paymentRef}).`);
        setTimeout(() => setSuccessToast(null), 4000);
      } else {
        setActionError(await readApiError(res, 'Could not record payment'));
      }
    } catch (err: any) {
      setActionError(`Network error: ${err.message}`);
    } finally {
      setPaymentSubmitting(false);
    }
  };

  const handleAction = async (grnId: number, action: 'submit' | 'approve' | 'reject' | 'cancel') => {
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
      {successToast && (
        <div className="erp-alert alert-success" role="alert">
          <CheckCircle size={16} className="inline mr-2" />
          {successToast}
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

      <ReferenceDataNotice refs={refs} />

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
              <th>Quality Doc (TC / MTC)</th>
              <th>Status</th>
              <th>P2P Payment</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={10} className="text-center p-4">Loading GRN records...</td></tr>
            ) : filteredGRNs.length === 0 ? (
              <tr><td colSpan={10} className="text-center p-4">No GRNs match current criteria.</td></tr>
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
                    {grn.quality_document_number ? (
                      <span className="flex items-center gap-1 text-xs text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                        <FileCheck size={12} /> {grn.quality_document_number}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400 italic">Pending Inspection</span>
                    )}
                  </td>
                  <td>
                    <span className={`status-pill status-${grn.status.toLowerCase()}`}>
                      {grn.status}
                    </span>
                  </td>
                  <td>
                    {grn.payment_status === 'PAID' ? (
                      <span className="status-pill status-approved text-xs" title={`UTR: ${grn.payment_reference || 'N/A'}`}>
                        PAID ({grn.payment_reference ? grn.payment_reference.slice(-6) : 'SETTLED'})
                      </span>
                    ) : grn.status === 'APPROVED' ? (
                      <span className="status-pill status-draft text-xs">UNPAID</span>
                    ) : (
                      <span className="text-muted text-xs">—</span>
                    )}
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="flex gap-1 flex-wrap">
                      {grn.status === 'DRAFT' && (
                        <button
                          className="erp-btn btn-sm btn-outline"
                          onClick={() => handleAction(grn.id, 'submit')}
                        >
                          <Send size={12} /> Submit
                        </button>
                      )}
                      {grn.status === 'SUBMITTED' && (
                        <>
                          <button
                            className="erp-btn btn-sm btn-success flex items-center gap-1"
                            onClick={() => openQualityDecision(grn, 'approve')}
                            title="Approve GRN with Mill Test Certificate / Quality Document"
                          >
                            <ShieldCheck size={12} /> Approve (QA)
                          </button>
                          <button
                            className="erp-btn btn-sm btn-danger flex items-center gap-1"
                            onClick={() => openQualityDecision(grn, 'reject')}
                            title="Reject GRN on quality failure"
                          >
                            <XCircle size={12} /> Reject
                          </button>
                        </>
                      )}
                      {grn.status === 'APPROVED' && grn.payment_status !== 'PAID' && (
                        <button
                          className="erp-btn btn-sm btn-secondary flex items-center gap-1 text-xs py-1 px-2"
                          onClick={() => openPaymentModal(grn)}
                          title="Record Bank Payment / UTR for this GRN"
                        >
                          <CreditCard size={12} /> Pay
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

              {/* Quality Inspection Dossier */}
              <div className="audit-card p-3 mb-4 bg-slate-50 border border-slate-200 rounded">
                <div className="flex justify-between items-center mb-2">
                  <h4 className="font-semibold text-sm flex items-center gap-1 text-slate-800">
                    <ShieldCheck size={16} className="text-emerald-600" /> Quality Inspection & Mill Test Certificate (TC/MTC)
                  </h4>
                  {selectedGRN.quality_document_number && (
                    <span className="badge badge-success font-mono">{selectedGRN.quality_document_number}</span>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-slate-500 font-medium">Inspection Status: </span>
                    <strong className={selectedGRN.quality_inspection_status === 'REJECTED' ? 'text-rose-600' : 'text-emerald-600'}>
                      {selectedGRN.quality_inspection_status || 'Pending QA Verification'}
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 font-medium">Inspected By: </span>
                    <span>{selectedGRN.quality_inspected_by || 'QA Metallurgist'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 font-medium">Verified On: </span>
                    <span>{selectedGRN.quality_inspected_at ? new Date(selectedGRN.quality_inspected_at).toLocaleDateString() : '—'}</span>
                  </div>
                </div>
                {selectedGRN.quality_inspection_notes && (
                  <p className="text-xs text-slate-600 mt-2 bg-white p-2 rounded border border-slate-100">
                    <strong>QA Notes:</strong> {selectedGRN.quality_inspection_notes}
                  </p>
                )}
              </div>

              {/* P2P Payment Settlement Dossier */}
              <div className="audit-card p-3 mb-4 bg-slate-50 border border-slate-200 rounded">
                <div className="flex justify-between items-center mb-2">
                  <h4 className="font-semibold text-sm flex items-center gap-1 text-slate-800">
                    <CreditCard size={16} className="text-blue-600" /> Procure-to-Pay (P2P) Payment Settlement
                  </h4>
                  <span className={`status-pill ${selectedGRN.payment_status === 'PAID' ? 'status-approved' : 'status-draft'}`}>
                    {selectedGRN.payment_status || 'UNPAID'}
                  </span>
                </div>
                {selectedGRN.payment_status === 'PAID' ? (
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <span className="text-slate-500 font-medium">Bank UTR / Ref: </span>
                      <strong className="font-mono">{selectedGRN.payment_reference || 'N/A'}</strong>
                    </div>
                    <div>
                      <span className="text-slate-500 font-medium">Amount Paid: </span>
                      <strong>₹{selectedGRN.amount_paid || '—'}</strong>
                    </div>
                    <div>
                      <span className="text-slate-500 font-medium">Settlement Date: </span>
                      <span>{selectedGRN.payment_date || '—'} ({selectedGRN.payment_mode || 'NEFT'})</span>
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-between items-center text-xs text-slate-500">
                    <span>Payment pending commercial invoice verification and credit terms clearance.</span>
                    {selectedGRN.status === 'APPROVED' && (
                      <button
                        className="erp-btn btn-sm btn-primary text-xs"
                        onClick={() => {
                          const g = selectedGRN;
                          setSelectedGRN(null);
                          openPaymentModal(g);
                        }}
                      >
                        Record Payment Settlement
                      </button>
                    )}
                  </div>
                )}
              </div>

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
                <div className="mb-3">
                  <ReferenceDataNotice refs={refs} />
                </div>
                {formError && (
                  <div className="alert-error p-3 mb-3 bg-red-50 text-red-700 text-sm rounded">
                    {formError}
                  </div>
                )}

                {/* P2P PO Inward Integration */}
                <div className="p-3 mb-4 bg-blue-50 border border-blue-200 rounded">
                  <div className="flex justify-between items-center gap-3">
                    <div>
                      <strong className="text-sm text-blue-900">Procure-to-Pay (P2P): Link Approved Purchase Order</strong>
                      <p className="text-xs text-blue-700 m-0">
                        Optionally select an authorized PO to auto-populate vendor details and ordered material line items.
                      </p>
                    </div>
                    <div style={{ minWidth: '240px' }}>
                      <select
                        className="form-control text-sm"
                        value={selectedPOId}
                        onChange={(e) => handleSelectPO(e.target.value)}
                      >
                        <option value="">-- Manual Inward / No PO --</option>
                        {approvedPOs.map((po) => (
                          <option key={po.id} value={po.id}>
                            {po.po_number} ({po.vendor_name}) - ₹{Number(po.grand_total).toLocaleString('en-IN')}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

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
                        <option value="">{refs.placeholder('vendors', '-- Select Vendor --')}</option>
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
                <button type="submit" className="erp-btn btn-primary" disabled={submitting || refs.unavailable}>
                  {submitting ? 'Creating...' : 'Create Draft GRN'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Quality Inspection & Approval/Rejection Modal */}
      {showQualityModal && qualityGrn && (
        <div className="modal-backdrop" onClick={() => !qualitySubmitting && setShowQualityModal(false)}>
          <div className="modal-content max-w-2xl" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={submitQualityDecision}>
              <div className="modal-header">
                <div className="flex items-center gap-2">
                  <ShieldCheck size={20} className={qualityAction === 'approve' ? 'text-emerald-600' : 'text-rose-600'} />
                  <h3>Quality Inspection & {qualityAction === 'approve' ? 'Inward Approval' : 'Rejection'}: {qualityGrn.grn_number}</h3>
                </div>
                <button type="button" className="close-btn" onClick={() => setShowQualityModal(false)} disabled={qualitySubmitting}>
                  <X size={18} />
                </button>
              </div>

              <div className="modal-body space-y-4">
                <div className="p-3 bg-slate-50 border rounded text-xs space-y-1">
                  <div><strong>Vendor:</strong> {qualityGrn.vendor_name || 'Internal Entity'} | <strong>Invoice #:</strong> {qualityGrn.vendor_invoice_no || 'N/A'}</div>
                  <div><strong>Items to Inspect:</strong> {qualityGrn.lines?.length || 0} line item(s) awaiting metallurgical/quality clearance.</div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="form-group">
                    <label className="form-label">Quality Test Certificate (TC / MTC #) *</label>
                    <input
                      type="text"
                      className="form-control font-mono"
                      value={qualityDocNo}
                      onChange={(e) => setQualityDocNo(e.target.value)}
                      placeholder="e.g. TC-2026-SAIL-0841"
                      required
                    />
                    <small className="text-muted text-xs">Mill Test Certificate / Manufacturer Lab Report identifier.</small>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Heat Lot / Melt Identification #</label>
                    <input
                      type="text"
                      className="form-control font-mono"
                      value={heatLotNo}
                      onChange={(e) => setHeatLotNo(e.target.value)}
                      placeholder="e.g. LOT-F88-2026"
                    />
                    <small className="text-muted text-xs">Matching heat number stamped on ingot / bundle tags.</small>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Quality Inspection Verdict *</label>
                  <select
                    className="form-control"
                    value={qualityStatus}
                    onChange={(e) => setQualityStatus(e.target.value as any)}
                  >
                    <option value="PASSED">PASSED — Conforms fully to ASTM/IS chemistry & visual spec</option>
                    <option value="CONDITIONALLY_ACCEPTED">CONDITIONALLY ACCEPTED — Minor deviation, usable with foundry concession</option>
                    <option value="REJECTED">REJECTED — Chemical non-conformance, porosity, or severe rust</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Metallurgical & Inspection Notes {qualityAction === 'reject' ? '*' : ''}</label>
                  <textarea
                    className="form-control"
                    rows={3}
                    value={qualityNotes}
                    onChange={(e) => setQualityNotes(e.target.value)}
                    placeholder={qualityAction === 'reject' ? 'Mandatory reason for rejection (e.g. Si content low, physical contamination)...' : 'Remarks on hardness, spectrometry readings, or dimensional checks...'}
                    required={qualityAction === 'reject'}
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="erp-btn btn-secondary" onClick={() => setShowQualityModal(false)} disabled={qualitySubmitting}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className={`erp-btn ${qualityAction === 'approve' ? 'btn-success' : 'btn-danger'}`}
                  disabled={qualitySubmitting}
                >
                  {qualitySubmitting ? 'Recording Decision...' : qualityAction === 'approve' ? 'Approve & Post to Stock Ledger' : 'Confirm Rejection'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* P2P Payment Settlement Modal */}
      {showPaymentModal && paymentGrn && (
        <div className="modal-backdrop" onClick={() => !paymentSubmitting && setShowPaymentModal(false)}>
          <div className="modal-content max-w-lg" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={submitPaymentRecord}>
              <div className="modal-header">
                <div className="flex items-center gap-2">
                  <CreditCard size={20} className="text-blue-600" />
                  <h3>Record Vendor Payment: {paymentGrn.grn_number}</h3>
                </div>
                <button type="button" className="close-btn" onClick={() => setShowPaymentModal(false)} disabled={paymentSubmitting}>
                  <X size={18} />
                </button>
              </div>

              <div className="modal-body space-y-4">
                <div className="p-3 bg-blue-50 border border-blue-200 rounded text-xs space-y-1">
                  <div><strong>Vendor:</strong> {paymentGrn.vendor_name || 'N/A'}</div>
                  <div><strong>Invoice #:</strong> {paymentGrn.vendor_invoice_no || 'N/A'} | <strong>Invoice Date:</strong> {paymentGrn.invoice_date || 'N/A'}</div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="form-group">
                    <label className="form-label">Amount Paid (₹ with GST) *</label>
                    <input
                      type="number"
                      step="0.01"
                      className="form-control font-mono font-bold"
                      value={amountPaid}
                      onChange={(e) => setAmountPaid(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Payment Date *</label>
                    <input
                      type="date"
                      className="form-control"
                      value={paymentDate}
                      onChange={(e) => setPaymentDate(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="form-group">
                    <label className="form-label">Bank UTR / Ref Number *</label>
                    <input
                      type="text"
                      className="form-control font-mono"
                      value={paymentRef}
                      onChange={(e) => setPaymentRef(e.target.value)}
                      placeholder="e.g. UTR-HDFC-994821"
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Payment Mode *</label>
                    <select
                      className="form-control"
                      value={paymentMode}
                      onChange={(e) => setPaymentMode(e.target.value as any)}
                    >
                      <option value="NEFT_RTGS">NEFT / RTGS</option>
                      <option value="BANK_TRANSFER">Direct Account Transfer</option>
                      <option value="CHEQUE">Bank Cheque</option>
                      <option value="UPI">UPI Corporate</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Settlement Notes</label>
                  <input
                    type="text"
                    className="form-control"
                    value={paymentNotes}
                    onChange={(e) => setPaymentNotes(e.target.value)}
                    placeholder="Reference bank voucher, TDS deduction, or invoice clearance..."
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="erp-btn btn-secondary" onClick={() => setShowPaymentModal(false)} disabled={paymentSubmitting}>
                  Cancel
                </button>
                <button type="submit" className="erp-btn btn-primary" disabled={paymentSubmitting}>
                  {paymentSubmitting ? 'Recording Settlement...' : 'Save Payment Record'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
