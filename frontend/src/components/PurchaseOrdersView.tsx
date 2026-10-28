import React, { useState, useEffect } from 'react';
import {
  FileText,
  Plus,
  CheckCircle,
  AlertTriangle,
  Search,
  RefreshCw,
  Send,
  X,
  Check,
  XCircle,
  Printer,
} from 'lucide-react';
import type { PurchaseOrder, UserRole } from '../types';
import { apiFetch, readApiError } from '../api/client';
import { useReferenceData } from '../hooks/useReferenceData';
import { ReferenceDataNotice } from './ReferenceDataNotice';

interface PurchaseOrdersViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const PurchaseOrdersView: React.FC<PurchaseOrdersViewProps> = ({ currentRole }) => {
  const [pos, setPos] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedPO, setSelectedPO] = useState<PurchaseOrder | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [successToast, setSuccessToast] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const refs = useReferenceData(['items', 'uoms', 'vendors']);
  const { items, vendors } = refs;

  // New PO Modal State
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [vendorId, setVendorId] = useState<number | ''>('');
  const [departmentId, setDepartmentId] = useState<number>(1);
  const [poDate, setPoDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [expectedDate, setExpectedDate] = useState<string>(
    new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10)
  );
  const [paymentTerms, setPaymentTerms] = useState<string>('Net 30 Days');
  const [deliveryTerms, setDeliveryTerms] = useState<string>('Door Delivery to VSPL Works, Shimoga');
  const [notes, setNotes] = useState<string>('');
  const [lines, setLines] = useState<Array<{
    material_item_id: number | '';
    uom_id: number | '';
    quantity: string;
    unit_rate_ex_gst: string;
    gst_percent: string;
    remarks: string;
  }>>([
    { material_item_id: '', uom_id: '', quantity: '100', unit_rate_ex_gst: '45.00', gst_percent: '18', remarks: '' }
  ]);
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Approval/Rejection action state
  const [showRejectModal, setShowRejectModal] = useState<boolean>(false);
  const [rejectionComments, setRejectionComments] = useState<string>('');
  const [approving, setApproving] = useState<boolean>(false);

  const fetchPOs = async () => {
    setLoading(true);
    setActionError(null);
    try {
      const res = await apiFetch('/api/v1/purchase-orders/');
      if (res.ok) {
        const data = await res.json();
        const list = Array.isArray(data) ? data : (data.items || []);
        setPos(list);
        if (selectedPO) {
          const refreshed = list.find((p: PurchaseOrder) => p.id === selectedPO.id);
          if (refreshed) setSelectedPO(refreshed);
        }
      }
    } catch (err) {
      console.error('Failed to load purchase orders:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPOs();
  }, []);

  const handleAddLine = () => {
    setLines([
      ...lines,
      { material_item_id: '', uom_id: '', quantity: '1', unit_rate_ex_gst: '0.00', gst_percent: '18', remarks: '' }
    ]);
  };

  const handleRemoveLine = (idx: number) => {
    if (lines.length > 1) {
      setLines(lines.filter((_, i) => i !== idx));
    }
  };

  const handleLineChange = (idx: number, field: string, value: any) => {
    const updated = [...lines];
    updated[idx] = { ...updated[idx], [field]: value };

    // Auto-fill UOM if item changed
    if (field === 'material_item_id' && value) {
      const item = items.find(i => i.id === Number(value));
      if (item && item.base_uom_id) {
        updated[idx].uom_id = item.base_uom_id;
      }
    }
    setLines(updated);
  };

  // Calculations for PO modal summary
  const subtotal = lines.reduce((acc, l) => {
    const q = parseFloat(l.quantity) || 0;
    const r = parseFloat(l.unit_rate_ex_gst) || 0;
    return acc + q * r;
  }, 0);

  const totalGst = lines.reduce((acc, l) => {
    const q = parseFloat(l.quantity) || 0;
    const r = parseFloat(l.unit_rate_ex_gst) || 0;
    const g = parseFloat(l.gst_percent) || 0;
    return acc + (q * r * g) / 100;
  }, 0);

  const grandTotal = subtotal + totalGst;

  const handleCreatePO = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vendorId) {
      setActionError('Please select a vendor.');
      return;
    }
    for (const l of lines) {
      if (!l.material_item_id || !l.quantity || parseFloat(l.quantity) <= 0) {
        setActionError('Please ensure all lines have a valid material and quantity.');
        return;
      }
    }

    setSubmitting(true);
    setActionError(null);

    const payload = {
      vendor_id: Number(vendorId),
      department_id: departmentId,
      po_date: poDate,
      expected_delivery_date: expectedDate,
      payment_terms: paymentTerms,
      delivery_terms: deliveryTerms,
      notes: notes.trim() || undefined,
      lines: lines.map((l, idx) => {
        const qty = parseFloat(l.quantity) || 0;
        const rate = parseFloat(l.unit_rate_ex_gst) || 0;
        const gst = parseFloat(l.gst_percent) || 0;
        const total = qty * rate * (1 + gst / 100);
        return {
          line_number: idx + 1,
          material_item_id: Number(l.material_item_id),
          uom_id: Number(l.uom_id) || 1,
          quantity: qty,
          unit_rate_ex_gst: rate,
          gst_percent: gst,
          line_total: total.toFixed(2),
          remarks: l.remarks || undefined,
        };
      }),
    };

    try {
      const res = await apiFetch('/api/v1/purchase-orders/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const created: PurchaseOrder = await res.json();
        setShowCreateModal(false);
        setSuccessToast(`Purchase Order ${created.po_number} created successfully.`);
        setTimeout(() => setSuccessToast(null), 4000);
        fetchPOs();
        setSelectedPO(created);
      } else {
        const err = await readApiError(res, 'Failed to create purchase order.');
        setActionError(err || 'Failed to create purchase order.');
      }
    } catch (err) {
      setActionError('Network error while creating purchase order.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleWorkflowAction = async (
    action: 'submit' | 'approve-dept' | 'approve-scm' | 'approve-mgmt' | 'reject',
    comments?: string
  ) => {
    if (!selectedPO) return;
    setApproving(true);
    setActionError(null);

    try {
      const res = await apiFetch(`/api/v1/purchase-orders/${selectedPO.id}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comments: comments || `${action.toUpperCase()} completed by ${currentRole}` }),
      });

      if (res.ok) {
        const updated = await res.json();
        setSelectedPO(updated);
        setShowRejectModal(false);
        setRejectionComments('');
        setSuccessToast(`PO ${updated.po_number}: status updated to ${updated.status}.`);
        setTimeout(() => setSuccessToast(null), 4000);
        fetchPOs();
      } else {
        const err = await readApiError(res, 'Failed to create purchase order.');
        setActionError(err || `Failed to execute ${action}.`);
      }
    } catch (err) {
      setActionError(`Network error executing ${action}.`);
    } finally {
      setApproving(false);
    }
  };

  // Filtered list
  const filteredPOs = pos.filter((po) => {
    const matchStatus = statusFilter === 'ALL' || po.status === statusFilter;
    const term = searchTerm.toLowerCase();
    const matchSearch =
      !searchTerm ||
      po.po_number.toLowerCase().includes(term) ||
      po.vendor_name.toLowerCase().includes(term) ||
      po.department_name.toLowerCase().includes(term);
    return matchStatus && matchSearch;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'DRAFT':
        return <span className="badge badge-secondary">Draft</span>;
      case 'SUBMITTED':
        return <span className="badge badge-warning">Pending Dept Approval</span>;
      case 'DEPT_APPROVED':
        return <span className="badge badge-info">Pending SCM Approval</span>;
      case 'SCM_APPROVED':
        return <span className="badge badge-primary">Pending Mgmt Approval</span>;
      case 'APPROVED':
        return <span className="badge badge-success">Fully Approved</span>;
      case 'REJECTED':
        return <span className="badge badge-danger">Rejected</span>;
      case 'CANCELLED':
        return <span className="badge badge-secondary">Cancelled</span>;
      default:
        return <span className="badge">{status}</span>;
    }
  };

  return (
    <div className="view-container">
      <ReferenceDataNotice refs={refs} />

      {/* Header Bar */}
      <div className="view-header flex-between">
        <div>
          <h2>Purchase Orders (PO) & P2P Cycle</h2>
          <p className="text-muted">
            3-Tier Procurement Governance: Department HOD &rarr; Supply Chain Head &rarr; Management Approval.
          </p>
        </div>
        <div className="header-actions">
          <button className="erp-btn btn-secondary mr-2" onClick={fetchPOs}>
            <RefreshCw size={14} className="btn-icon" /> Refresh
          </button>
          <button className="erp-btn btn-primary" onClick={() => setShowCreateModal(true)}>
            <Plus size={16} className="btn-icon" /> Create Purchase Order
          </button>
        </div>
      </div>

      {/* Notifications */}
      {successToast && (
        <div className="notification-banner banner-success mb-3">
          <CheckCircle size={16} />
          <span>{successToast}</span>
        </div>
      )}
      {actionError && (
        <div className="notification-banner banner-error mb-3">
          <AlertTriangle size={16} />
          <span>{actionError}</span>
        </div>
      )}

      {/* Stats Summary Cards */}
      <div className="stats-grid mb-4">
        <div className="stat-card">
          <div className="stat-title">Total POs</div>
          <div className="stat-value">{pos.length}</div>
          <div className="stat-desc">Lifetime recorded orders</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">Pending Dept Review</div>
          <div className="stat-value text-warning">
            {pos.filter((p) => p.status === 'SUBMITTED').length}
          </div>
          <div className="stat-desc">Awaiting Requisitioner HOD</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">Pending Supply Chain</div>
          <div className="stat-value text-info">
            {pos.filter((p) => p.status === 'DEPT_APPROVED').length}
          </div>
          <div className="stat-desc">Awaiting SCM Commercial Check</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">Pending Management</div>
          <div className="stat-value text-primary">
            {pos.filter((p) => p.status === 'SCM_APPROVED').length}
          </div>
          <div className="stat-desc">Awaiting Director Sign-off</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">Fully Approved (Ready for GRN)</div>
          <div className="stat-value text-success">
            {pos.filter((p) => p.status === 'APPROVED').length}
          </div>
          <div className="stat-desc">Authorized for goods receipt</div>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="table-controls-bar flex-between mb-3">
        <div className="search-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search by PO number, vendor, department..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <button
            className={`filter-chip ${statusFilter === 'ALL' ? 'active' : ''}`}
            onClick={() => setStatusFilter('ALL')}
          >
            All ({pos.length})
          </button>
          <button
            className={`filter-chip ${statusFilter === 'SUBMITTED' ? 'active' : ''}`}
            onClick={() => setStatusFilter('SUBMITTED')}
          >
            Dept Approval ({pos.filter((p) => p.status === 'SUBMITTED').length})
          </button>
          <button
            className={`filter-chip ${statusFilter === 'DEPT_APPROVED' ? 'active' : ''}`}
            onClick={() => setStatusFilter('DEPT_APPROVED')}
          >
            SCM Approval ({pos.filter((p) => p.status === 'DEPT_APPROVED').length})
          </button>
          <button
            className={`filter-chip ${statusFilter === 'SCM_APPROVED' ? 'active' : ''}`}
            onClick={() => setStatusFilter('SCM_APPROVED')}
          >
            Mgmt Approval ({pos.filter((p) => p.status === 'SCM_APPROVED').length})
          </button>
          <button
            className={`filter-chip ${statusFilter === 'APPROVED' ? 'active' : ''}`}
            onClick={() => setStatusFilter('APPROVED')}
          >
            Approved ({pos.filter((p) => p.status === 'APPROVED').length})
          </button>
        </div>
      </div>

      {/* PO Table */}
      <div className="erp-card">
        <div className="erp-table-container">
          <table className="erp-table">
            <thead>
              <tr>
                <th>PO Number</th>
                <th>PO Date</th>
                <th>Vendor</th>
                <th>Department</th>
                <th>Grand Total (₹)</th>
                <th>Current Level</th>
                <th>Status</th>
                <th>GRN Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={9} className="text-center py-4">
                    Loading purchase orders...
                  </td>
                </tr>
              ) : filteredPOs.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center py-4 text-muted">
                    No purchase orders match criteria.
                  </td>
                </tr>
              ) : (
                filteredPOs.map((po) => (
                  <tr
                    key={po.id}
                    className={selectedPO?.id === po.id ? 'row-selected' : ''}
                    onClick={() => setSelectedPO(po)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <strong className="text-primary">{po.po_number}</strong>
                    </td>
                    <td>{po.po_date}</td>
                    <td>
                      <div>
                        <strong>{po.vendor_name}</strong>
                        {po.vendor_gstin && (
                          <div className="text-xs text-muted">GST: {po.vendor_gstin}</div>
                        )}
                      </div>
                    </td>
                    <td>{po.department_name}</td>
                    <td>
                      <strong>₹{Number(po.grand_total).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong>
                    </td>
                    <td>
                      <span className="text-xs font-semibold text-muted">
                        {po.current_approval_level.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td>{getStatusBadge(po.status)}</td>
                    <td>
                      {po.status === 'APPROVED' ? (
                        <span className="badge badge-success">
                          {po.grn_count && po.grn_count > 0 ? `${po.grn_count} GRNs Issued` : 'Ready for Inward'}
                        </span>
                      ) : (
                        <span className="text-xs text-muted">Inward Blocked</span>
                      )}
                    </td>
                    <td>
                      <button
                        className="erp-btn btn-sm btn-outline"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedPO(po);
                        }}
                      >
                        Inspect Dossier
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Selected PO Dossier / Detail Drawer */}
      {selectedPO && (
        <div className="erp-card mt-4 border-primary">
          <div className="card-header flex-between bg-light">
            <div className="header-title-group">
              <div className="flex-align-center gap-2">
                <FileText size={20} className="text-primary" />
                <h3 className="m-0">Purchase Order: {selectedPO.po_number}</h3>
                {getStatusBadge(selectedPO.status)}
              </div>
              <p className="text-muted text-xs mt-1">
                Created by {selectedPO.created_by} on {new Date(selectedPO.created_at).toLocaleString()}
              </p>
            </div>
            <div className="flex-align-center gap-2">
              <button
                className="erp-btn btn-secondary btn-sm"
                onClick={() => window.print()}
              >
                <Printer size={14} className="btn-icon" /> Print PO
              </button>
              <button
                className="erp-btn btn-outline btn-sm"
                onClick={() => setSelectedPO(null)}
              >
                <X size={14} /> Close
              </button>
            </div>
          </div>

          <div className="card-body">
            {/* 3-Tier Approval Workflow Visualizer */}
            <div className="workflow-stepper-container mb-4 p-3 bg-white rounded border">
              <h4 className="text-xs font-bold text-uppercase text-muted mb-3">
                3-Tier Authorization Governance
              </h4>
              <div className="workflow-stepper">
                {/* Step 1: Department Approval */}
                <div
                  className={`step-item ${
                    selectedPO.dept_approved_by
                      ? 'step-completed'
                      : selectedPO.status === 'SUBMITTED'
                      ? 'step-active'
                      : ''
                  }`}
                >
                  <div className="step-circle">
                    {selectedPO.dept_approved_by ? <Check size={14} /> : '1'}
                  </div>
                  <div className="step-content">
                    <div className="step-title">1. Department HOD</div>
                    <div className="step-subtitle">
                      {selectedPO.dept_approved_by ? (
                        <span className="text-success">
                          Approved by {selectedPO.dept_approved_by} (
                          {selectedPO.dept_approved_at
                            ? new Date(selectedPO.dept_approved_at).toLocaleDateString()
                            : 'OK'}
                          )
                        </span>
                      ) : selectedPO.status === 'SUBMITTED' ? (
                        <span className="text-warning">Pending Review</span>
                      ) : (
                        <span className="text-muted">Awaiting Submission</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="step-line" />

                {/* Step 2: Supply Chain Approval */}
                <div
                  className={`step-item ${
                    selectedPO.scm_approved_by
                      ? 'step-completed'
                      : selectedPO.status === 'DEPT_APPROVED'
                      ? 'step-active'
                      : ''
                  }`}
                >
                  <div className="step-circle">
                    {selectedPO.scm_approved_by ? <Check size={14} /> : '2'}
                  </div>
                  <div className="step-content">
                    <div className="step-title">2. Supply Chain Head</div>
                    <div className="step-subtitle">
                      {selectedPO.scm_approved_by ? (
                        <span className="text-success">
                          Approved by {selectedPO.scm_approved_by} (
                          {selectedPO.scm_approved_at
                            ? new Date(selectedPO.scm_approved_at).toLocaleDateString()
                            : 'OK'}
                          )
                        </span>
                      ) : selectedPO.status === 'DEPT_APPROVED' ? (
                        <span className="text-warning">Pending Commercial Check</span>
                      ) : (
                        <span className="text-muted">Awaiting Level 1</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="step-line" />

                {/* Step 3: Management Approval */}
                <div
                  className={`step-item ${
                    selectedPO.mgmt_approved_by
                      ? 'step-completed'
                      : selectedPO.status === 'SCM_APPROVED'
                      ? 'step-active'
                      : ''
                  }`}
                >
                  <div className="step-circle">
                    {selectedPO.mgmt_approved_by ? <Check size={14} /> : '3'}
                  </div>
                  <div className="step-content">
                    <div className="step-title">3. Management Authorization</div>
                    <div className="step-subtitle">
                      {selectedPO.mgmt_approved_by ? (
                        <span className="text-success">
                          Approved by {selectedPO.mgmt_approved_by} (
                          {selectedPO.mgmt_approved_at
                            ? new Date(selectedPO.mgmt_approved_at).toLocaleDateString()
                            : 'OK'}
                          )
                        </span>
                      ) : selectedPO.status === 'SCM_APPROVED' ? (
                        <span className="text-primary font-bold">Awaiting MD Approval</span>
                      ) : (
                        <span className="text-muted">Awaiting Level 2</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Buttons Bar based on workflow state */}
              <div className="workflow-actions-bar mt-3 pt-3 border-top flex-between">
                <div>
                  {selectedPO.status === 'REJECTED' && (
                    <div className="text-danger text-sm">
                      <strong>Rejection Reason:</strong> {selectedPO.rejection_reason || 'Rejected by approver'}
                    </div>
                  )}
                  {selectedPO.status === 'APPROVED' && (
                    <div className="text-success text-sm flex-align-center gap-1">
                      <CheckCircle size={14} />
                      <strong>Fully Authorized:</strong> Available in GRN screen for Goods Receipt & Quality Verification.
                    </div>
                  )}
                </div>

                <div className="flex-align-center gap-2">
                  {/* Draft -> Submit */}
                  {selectedPO.status === 'DRAFT' && (
                    <button
                      className="erp-btn btn-primary"
                      disabled={approving}
                      onClick={() => handleWorkflowAction('submit')}
                    >
                      <Send size={14} className="btn-icon" /> Submit for Department Approval
                    </button>
                  )}

                  {/* Level 1: Department Approval */}
                  {selectedPO.status === 'SUBMITTED' && (
                    <>
                      <button
                        className="erp-btn btn-danger"
                        disabled={approving}
                        onClick={() => setShowRejectModal(true)}
                      >
                        <XCircle size={14} className="btn-icon" /> Reject PO
                      </button>
                      <button
                        className="erp-btn btn-primary"
                        disabled={approving}
                        onClick={() => handleWorkflowAction('approve-dept')}
                      >
                        <Check size={14} className="btn-icon" /> Approve (Department Level)
                      </button>
                    </>
                  )}

                  {/* Level 2: SCM Approval */}
                  {selectedPO.status === 'DEPT_APPROVED' && (
                    <>
                      <button
                        className="erp-btn btn-danger"
                        disabled={approving}
                        onClick={() => setShowRejectModal(true)}
                      >
                        <XCircle size={14} className="btn-icon" /> Reject PO
                      </button>
                      <button
                        className="erp-btn btn-primary"
                        disabled={approving}
                        onClick={() => handleWorkflowAction('approve-scm')}
                      >
                        <Check size={14} className="btn-icon" /> Approve (Supply Chain Level)
                      </button>
                    </>
                  )}

                  {/* Level 3: Management Approval */}
                  {selectedPO.status === 'SCM_APPROVED' && (
                    <>
                      <button
                        className="erp-btn btn-danger"
                        disabled={approving}
                        onClick={() => setShowRejectModal(true)}
                      >
                        <XCircle size={14} className="btn-icon" /> Reject PO
                      </button>
                      <button
                        className="erp-btn btn-success"
                        disabled={approving}
                        onClick={() => handleWorkflowAction('approve-mgmt')}
                      >
                        <CheckCircle size={14} className="btn-icon" /> Final Authorization (Management Level)
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* PO Details Grid */}
            <div className="grid-2-col gap-4 mb-4">
              <div className="p-3 bg-light rounded">
                <h4 className="text-xs font-bold text-muted text-uppercase mb-2">Vendor Information</h4>
                <div className="font-bold text-lg">{selectedPO.vendor_name}</div>
                {selectedPO.vendor_gstin && (
                  <div className="text-sm text-muted">GSTIN: {selectedPO.vendor_gstin}</div>
                )}
                <div className="text-sm mt-1">Payment Terms: <strong>{selectedPO.payment_terms}</strong></div>
                {selectedPO.delivery_terms && (
                  <div className="text-sm">Delivery: {selectedPO.delivery_terms}</div>
                )}
              </div>

              <div className="p-3 bg-light rounded">
                <h4 className="text-xs font-bold text-muted text-uppercase mb-2">Order Particulars</h4>
                <div className="text-sm">Requisitioning Dept: <strong>{selectedPO.department_name}</strong></div>
                <div className="text-sm">PO Date: <strong>{selectedPO.po_date}</strong></div>
                <div className="text-sm">Expected Delivery: <strong>{selectedPO.expected_delivery_date}</strong></div>
                {selectedPO.notes && (
                  <div className="text-sm mt-1 text-muted">Instructions: {selectedPO.notes}</div>
                )}
              </div>
            </div>

            {/* Line Items Table */}
            <h4 className="text-xs font-bold text-muted text-uppercase mb-2">Ordered Materials & Commercials</h4>
            <div className="erp-table-container mb-3">
              <table className="erp-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Item Code</th>
                    <th>Material Description</th>
                    <th>Quantity</th>
                    <th>Unit Rate (ex-GST)</th>
                    <th>GST %</th>
                    <th>Line Total (₹)</th>
                    <th>Remarks</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedPO.lines.map((l) => (
                    <tr key={l.line_number}>
                      <td>{l.line_number}</td>
                      <td><code>{l.item_code}</code></td>
                      <td><strong>{l.item_name}</strong></td>
                      <td>{Number(l.quantity).toLocaleString()} {l.uom_code}</td>
                      <td>₹{Number(l.unit_rate_ex_gst).toFixed(2)}</td>
                      <td>{l.gst_percent}%</td>
                      <td><strong>₹{Number(l.line_total).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></td>
                      <td className="text-muted text-xs">{l.remarks || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Financial Summary */}
            <div className="flex-end">
              <div className="summary-box p-3 bg-light rounded" style={{ minWidth: '280px' }}>
                <div className="flex-between text-sm py-1">
                  <span>Subtotal (ex-GST):</span>
                  <strong>₹{Number(selectedPO.total_amount_ex_gst).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong>
                </div>
                <div className="flex-between text-sm py-1">
                  <span>Total GST:</span>
                  <strong>₹{Number(selectedPO.total_gst_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong>
                </div>
                <div className="flex-between text-base py-1 border-top mt-1 font-bold text-primary">
                  <span>Grand Total:</span>
                  <span>₹{Number(selectedPO.grand_total).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Purchase Order Modal */}
      {showCreateModal && (
        <div className="modal-backdrop">
          <div className="modal-content modal-lg">
            <div className="modal-header">
              <h3>Create Purchase Order (P2P Procurement)</h3>
              <button className="close-btn" onClick={() => setShowCreateModal(false)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleCreatePO}>
              <div className="modal-body">
                <div className="form-grid grid-2-col gap-3 mb-3">
                  <div className="form-group">
                    <label className="required">Vendor (Approved Master)</label>
                    <select
                      value={vendorId}
                      onChange={(e) => setVendorId(e.target.value ? Number(e.target.value) : '')}
                      required
                    >
                      <option value="">-- Select Vendor --</option>
                      {vendors.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.name} (ID: {v.id})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="required">Requisitioning Department</label>
                    <select
                      value={departmentId}
                      onChange={(e) => setDepartmentId(Number(e.target.value))}
                      required
                    >
                      <option value={1}>Foundry (FDY)</option>
                      <option value={2}>Machine Shop (MCS)</option>
                      <option value={3}>Stores (STR)</option>
                      <option value={4}>Maintenance (MNT)</option>
                      <option value={5}>Quality Assurance (QLY)</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="required">PO Date</label>
                    <input
                      type="date"
                      value={poDate}
                      onChange={(e) => setPoDate(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="required">Expected Delivery Date</label>
                    <input
                      type="date"
                      value={expectedDate}
                      onChange={(e) => setExpectedDate(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="required">Payment Terms</label>
                    <input
                      type="text"
                      value={paymentTerms}
                      onChange={(e) => setPaymentTerms(e.target.value)}
                      placeholder="e.g. Net 30 Days / 100% Against PI"
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label>Delivery Terms</label>
                    <input
                      type="text"
                      value={deliveryTerms}
                      onChange={(e) => setDeliveryTerms(e.target.value)}
                      placeholder="e.g. Door Delivery to VSPL Works"
                    />
                  </div>
                </div>

                <div className="form-group mb-3">
                  <label>Special Instructions / Notes</label>
                  <textarea
                    rows={2}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Enter inspection requirements, test certificates needed, or packing details..."
                  />
                </div>

                {/* Line Items Builder */}
                <div className="flex-between mb-2">
                  <h4 className="text-xs font-bold text-uppercase text-muted">Purchase Order Line Items</h4>
                  <button type="button" className="erp-btn btn-sm btn-secondary" onClick={handleAddLine}>
                    <Plus size={14} className="btn-icon" /> Add Line
                  </button>
                </div>

                <div className="erp-table-container mb-3">
                  <table className="erp-table">
                    <thead>
                      <tr>
                        <th style={{ width: '40%' }}>Material Item</th>
                        <th style={{ width: '15%' }}>Quantity</th>
                        <th style={{ width: '15%' }}>Rate (ex-GST)</th>
                        <th style={{ width: '12%' }}>GST %</th>
                        <th style={{ width: '18%' }}>Line Total</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {lines.map((line, idx) => {
                        const qty = parseFloat(line.quantity) || 0;
                        const rate = parseFloat(line.unit_rate_ex_gst) || 0;
                        const gst = parseFloat(line.gst_percent) || 0;
                        const total = qty * rate * (1 + gst / 100);
                        return (
                          <tr key={idx}>
                            <td>
                              <select
                                value={line.material_item_id}
                                onChange={(e) =>
                                  handleLineChange(idx, 'material_item_id', e.target.value ? Number(e.target.value) : '')
                                }
                                required
                              >
                                <option value="">-- Select Material --</option>
                                {items.map((i) => (
                                  <option key={i.id} value={i.id}>
                                    {i.item_code} - {i.name}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td>
                              <input
                                type="number"
                                step="any"
                                min="0.01"
                                value={line.quantity}
                                onChange={(e) => handleLineChange(idx, 'quantity', e.target.value)}
                                required
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                step="any"
                                min="0.01"
                                value={line.unit_rate_ex_gst}
                                onChange={(e) => handleLineChange(idx, 'unit_rate_ex_gst', e.target.value)}
                                required
                              />
                            </td>
                            <td>
                              <select
                                value={line.gst_percent}
                                onChange={(e) => handleLineChange(idx, 'gst_percent', e.target.value)}
                              >
                                <option value="0">0%</option>
                                <option value="5">5%</option>
                                <option value="12">12%</option>
                                <option value="18">18%</option>
                                <option value="28">28%</option>
                              </select>
                            </td>
                            <td>
                              <strong>₹{total.toFixed(2)}</strong>
                            </td>
                            <td>
                              {lines.length > 1 && (
                                <button
                                  type="button"
                                  className="btn-icon-danger"
                                  onClick={() => handleRemoveLine(idx)}
                                >
                                  <X size={14} />
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Live Modal Summary */}
                <div className="flex-end mb-3">
                  <div className="summary-box p-3 bg-light rounded text-right" style={{ minWidth: '240px' }}>
                    <div className="text-sm">Subtotal: <strong>₹{subtotal.toFixed(2)}</strong></div>
                    <div className="text-sm">Total GST: <strong>₹{totalGst.toFixed(2)}</strong></div>
                    <div className="text-base font-bold text-primary mt-1 border-top pt-1">
                      Grand Total: ₹{grandTotal.toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="erp-btn btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="erp-btn btn-primary" disabled={submitting}>
                  {submitting ? 'Creating PO...' : 'Create & Save Draft PO'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Rejection Modal with Mandatory Reason */}
      {showRejectModal && selectedPO && (
        <div className="modal-backdrop">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Reject Purchase Order {selectedPO.po_number}</h3>
              <button className="close-btn" onClick={() => setShowRejectModal(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <p className="text-muted text-sm mb-3">
                Please provide a mandatory justification for rejecting this Purchase Order. The requisitioning team will receive this feedback.
              </p>
              <div className="form-group">
                <label className="required">Rejection Comments / Non-conformance Reason</label>
                <textarea
                  rows={3}
                  value={rejectionComments}
                  onChange={(e) => setRejectionComments(e.target.value)}
                  placeholder="e.g. Commercial rate exceeds budget ceiling, or alternative supplier already under contract..."
                  required
                />
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="erp-btn btn-secondary"
                onClick={() => setShowRejectModal(false)}
              >
                Cancel
              </button>
              <button
                className="erp-btn btn-danger"
                disabled={!rejectionComments.trim() || approving}
                onClick={() => handleWorkflowAction('reject', rejectionComments.trim())}
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
