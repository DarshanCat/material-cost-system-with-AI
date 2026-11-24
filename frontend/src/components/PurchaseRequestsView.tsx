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
  ShoppingCart,
  ArrowRight,
  ShieldCheck,
  Clock,
  Trash2,
} from 'lucide-react';
import type { PurchaseRequest, UserRole } from '../types';
import { apiFetch, readApiError } from '../api/client';
import { useReferenceData } from '../hooks/useReferenceData';
import { ReferenceDataNotice } from './ReferenceDataNotice';

interface PurchaseRequestsViewProps {
  currentRole: UserRole;
  currentUserId: string;
  onNavigateToPO?: (pr?: PurchaseRequest) => void;
}

export const PurchaseRequestsView: React.FC<PurchaseRequestsViewProps> = ({
  currentRole,
  currentUserId: _currentUserId,
  onNavigateToPO,
}) => {
  const isPlantHeadOrMgmt = currentRole === 'Management' || currentRole === 'Admin';
  const canCreatePR =
    currentRole === 'Purchase' ||
    currentRole === 'Stores' ||
    currentRole === 'Management' ||
    currentRole === 'Admin';

  const [prs, setPrs] = useState<PurchaseRequest[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedPR, setSelectedPR] = useState<PurchaseRequest | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [successToast, setSuccessToast] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const refs = useReferenceData(['items', 'departments']);
  const { items, departments } = refs;

  // New PR Modal State
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [departmentId, setDepartmentId] = useState<number>(1);
  const [targetDate, setTargetDate] = useState<string>(
    new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10)
  );
  const [justification, setJustification] = useState<string>('');
  const [itemSearchFilter, setItemSearchFilter] = useState<string>('');
  const [lines, setLines] = useState<
    Array<{
      material_item_id: number | '';
      uom_id: number | '';
      quantity: string;
      estimated_rate: string;
      remarks: string;
    }>
  >([
    {
      material_item_id: '',
      uom_id: '',
      quantity: '100',
      estimated_rate: '45.00',
      remarks: '',
    },
  ]);
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Approval / Rejection Modal State
  const [showRejectModal, setShowRejectModal] = useState<boolean>(false);
  const [rejectionComments, setRejectionComments] = useState<string>('');
  const [approving, setApproving] = useState<boolean>(false);

  const fetchPRs = async () => {
    setLoading(true);
    setActionError(null);
    try {
      const res = await apiFetch('/api/v1/purchase-requests/');
      if (res.ok) {
        const data = await res.json();
        const list = Array.isArray(data) ? data : data.items || [];
        setPrs(list);
        if (selectedPR) {
          const refreshed = list.find((p: PurchaseRequest) => p.id === selectedPR.id);
          if (refreshed) setSelectedPR(refreshed);
        }
      }
    } catch (err) {
      console.error('Failed to load purchase requests:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPRs();
  }, []);

  const handleAddLine = () => {
    setLines([
      ...lines,
      {
        material_item_id: '',
        uom_id: '',
        quantity: '1',
        estimated_rate: '',
        remarks: '',
      },
    ]);
  };

  const handleRemoveLine = (idx: number) => {
    if (lines.length === 1) return;
    setLines(lines.filter((_, i) => i !== idx));
  };

  const handleLineChange = (idx: number, field: string, val: any) => {
    const updated = [...lines];
    if (field === 'material_item_id') {
      const item = items.find((i) => i.id === Number(val));
      updated[idx] = {
        ...updated[idx],
        material_item_id: Number(val),
        uom_id: item?.base_uom_id || updated[idx].uom_id || 1,
      };
    } else {
      updated[idx] = { ...updated[idx], [field]: val };
    }
    setLines(updated);
  };

  const handleCreatePR = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);

    if (!justification.trim() || justification.trim().length < 5) {
      setActionError('Justification is mandatory under Financial Control Audit rules (minimum 5 characters).');
      return;
    }

    const validLines = lines.filter((l) => l.material_item_id && Number(l.quantity) > 0);
    if (validLines.length === 0) {
      setActionError('At least one valid material line item with positive quantity is required.');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        department_id: departmentId,
        target_date: targetDate,
        justification: justification.trim(),
        lines: validLines.map((l, idx) => ({
          line_number: idx + 1,
          material_item_id: Number(l.material_item_id),
          uom_id: Number(l.uom_id) || 1,
          quantity: parseFloat(l.quantity),
          estimated_rate: l.estimated_rate ? parseFloat(l.estimated_rate) : null,
          remarks: l.remarks || null,
        })),
      };

      const res = await apiFetch('/api/v1/purchase-requests/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const msg = await readApiError(res, 'Failed to create Purchase Request');
        throw new Error(msg);
      }

      setSuccessToast('Purchase Request submitted successfully. Awaiting Plant Head Layer-1 review.');
      setShowCreateModal(false);
      setJustification('');
      setLines([
        {
          material_item_id: '',
          uom_id: '',
          quantity: '100',
          estimated_rate: '45.00',
          remarks: '',
        },
      ]);
      await fetchPRs();
    } catch (err: any) {
      setActionError(err.message || 'Error creating Purchase Request');
    } finally {
      setSubmitting(false);
    }
  };

  const handleApprovePR = async (prId: number) => {
    setActionError(null);
    setApproving(true);
    try {
      const res = await apiFetch(`/api/v1/purchase-requests/${prId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comments: 'Approved by Plant Head. Authorized for PO creation.' }),
      });

      if (!res.ok) {
        const msg = await readApiError(res, 'Failed to approve Purchase Request');
        throw new Error(msg);
      }

      setSuccessToast(`PR approved by Plant Head. Authorized for PO creation.`);
      await fetchPRs();
    } catch (err: any) {
      setActionError(err.message || 'Error approving Purchase Request');
    } finally {
      setApproving(false);
    }
  };

  const handleRejectPR = async () => {
    if (!selectedPR) return;
    setActionError(null);
    setApproving(true);
    try {
      const res = await apiFetch(`/api/v1/purchase-requests/${selectedPR.id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comments: rejectionComments || 'Rejected by Plant Head' }),
      });

      if (!res.ok) {
        const msg = await readApiError(res, 'Failed to reject Purchase Request');
        throw new Error(msg);
      }

      setSuccessToast(`PR #${selectedPR.pr_number} rejected.`);
      setShowRejectModal(false);
      setRejectionComments('');
      await fetchPRs();
    } catch (err: any) {
      setActionError(err.message || 'Error rejecting Purchase Request');
    } finally {
      setApproving(false);
    }
  };

  const filteredPRs = prs.filter((p) => {
    const matchesStatus =
      statusFilter === 'ALL'
        ? true
        : statusFilter === 'PENDING'
        ? p.status === 'SUBMITTED' || p.status === 'DRAFT'
        : p.status === statusFilter;

    const matchesSearch =
      !searchTerm ||
      p.pr_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.department_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.justification.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.requisitioner_id.toLowerCase().includes(searchTerm.toLowerCase());

    return matchesStatus && matchesSearch;
  });

  const pendingCount = prs.filter((p) => p.status === 'SUBMITTED' || p.status === 'DRAFT').length;
  const approvedCount = prs.filter((p) => p.status === 'APPROVED').length;
  const convertedCount = prs.filter((p) => p.status === 'CONVERTED_TO_PO').length;
  const rejectedCount = prs.filter((p) => p.status === 'REJECTED').length;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return (
          <span className="badge badge-success">
            <ShieldCheck size={12} className="btn-icon" /> Approved
          </span>
        );
      case 'SUBMITTED':
      case 'DRAFT':
        return (
          <span className="badge badge-warning">
            <Clock size={12} className="btn-icon" /> Pending Review
          </span>
        );
      case 'CONVERTED_TO_PO':
        return (
          <span className="badge badge-primary">
            <ShoppingCart size={12} className="btn-icon" /> Converted to PO
          </span>
        );
      case 'REJECTED':
        return (
          <span className="badge badge-danger">
            <XCircle size={12} className="btn-icon" /> Rejected
          </span>
        );
      default:
        return <span className="badge badge-secondary">{status}</span>;
    }
  };

  return (
    <div className="erp-view">
      <ReferenceDataNotice refs={refs} />

      {/* Header Bar */}
      <div className="view-header flex-between">
        <div className="header-title-group">
          <div className="flex-align-center gap-2 mb-1">
            <span className="badge badge-primary text-xs">P2P Step 1 of 5</span>
            <span className="badge badge-info text-xs">Layer-1 Procurement Governance</span>
          </div>
          <h2>Purchase Requests (PR)</h2>
          <p className="subtitle">
            Raised by SCM / Planning with mandatory operational justification. Authorized strictly by Plant Head before PO creation.
          </p>
        </div>
        <div className="header-actions">
          <button className="erp-btn btn-secondary" onClick={fetchPRs} disabled={loading}>
            <RefreshCw size={14} className={`btn-icon ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
          {canCreatePR && (
            <button
              className="erp-btn btn-primary"
              onClick={() => {
                setShowCreateModal(true);
                setActionError(null);
              }}
            >
              <Plus size={16} className="btn-icon" /> Raise New PR
            </button>
          )}
        </div>
      </div>

      {/* P2P Flow Visualizer Strip */}
      <div className="erp-card p-3" style={{ backgroundColor: '#f8fafc', padding: '0.75rem 1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px', fontSize: '12px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '4px 10px',
              borderRadius: '4px',
              background: '#eff6ff',
              border: '1px solid #bfdbfe',
              color: '#1d4ed8',
              fontWeight: 700,
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: '#2563eb',
                marginRight: '6px',
                display: 'inline-block',
              }}
            />
            1. PR (SCM / Planning)
          </div>
          <ArrowRight size={14} color="#94a3b8" />
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '4px 10px',
              borderRadius: '4px',
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              color: '#334155',
              fontWeight: 600,
            }}
          >
            <ShieldCheck size={14} style={{ marginRight: '6px', color: '#10b981' }} />
            2. Plant Head Approval
          </div>
          <ArrowRight size={14} color="#94a3b8" />
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '4px 10px',
              borderRadius: '4px',
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              color: '#334155',
              fontWeight: 600,
            }}
          >
            <ShoppingCart size={14} style={{ marginRight: '6px', color: '#6366f1' }} />
            3. Purchase Order (CEO/MD)
          </div>
          <ArrowRight size={14} color="#94a3b8" />
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '4px 10px',
              borderRadius: '4px',
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              color: '#334155',
              fontWeight: 600,
            }}
          >
            <Clock size={14} style={{ marginRight: '6px', color: '#d97706' }} />
            4. Order Placed
          </div>
          <ArrowRight size={14} color="#94a3b8" />
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '4px 10px',
              borderRadius: '4px',
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              color: '#334155',
              fontWeight: 600,
            }}
          >
            5. GRN Inward & QA
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-title">Total Requisitions</div>
          <div className="stat-value">{prs.length}</div>
          <div className="stat-desc">Recorded PRs in ledger</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">Pending Plant Head Review</div>
          <div className="stat-value text-warning">{pendingCount}</div>
          <div className="stat-desc">Awaiting Layer-1 sign-off</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">Approved (Ready for PO)</div>
          <div className="stat-value text-success">{approvedCount}</div>
          <div className="stat-desc">Plant Head authorized</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">Converted to PO</div>
          <div className="stat-value text-primary">{convertedCount}</div>
          <div className="stat-desc">Active PO generated</div>
        </div>
      </div>

      {/* Notifications */}
      {successToast && (
        <div className="notification-banner banner-success">
          <CheckCircle size={16} className="btn-icon" />
          <span style={{ flex: 1 }}>{successToast}</span>
          <button
            onClick={() => setSuccessToast(null)}
            className="close-btn"
            style={{ width: '20px', height: '20px' }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {actionError && (
        <div className="notification-banner banner-error">
          <AlertTriangle size={16} className="btn-icon" />
          <span style={{ flex: 1 }}>{actionError}</span>
          <button
            onClick={() => setActionError(null)}
            className="close-btn"
            style={{ width: '20px', height: '20px' }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Search & Filter Controls */}
      <div className="table-controls-bar flex-between">
        <div className="search-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search PR #, department, justification, requisitioner..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <button
            className={`filter-chip ${statusFilter === 'ALL' ? 'active' : ''}`}
            onClick={() => setStatusFilter('ALL')}
          >
            All ({prs.length})
          </button>
          <button
            className={`filter-chip ${statusFilter === 'PENDING' ? 'active' : ''}`}
            onClick={() => setStatusFilter('PENDING')}
          >
            Pending Review ({pendingCount})
          </button>
          <button
            className={`filter-chip ${statusFilter === 'APPROVED' ? 'active' : ''}`}
            onClick={() => setStatusFilter('APPROVED')}
          >
            Approved ({approvedCount})
          </button>
          <button
            className={`filter-chip ${statusFilter === 'CONVERTED_TO_PO' ? 'active' : ''}`}
            onClick={() => setStatusFilter('CONVERTED_TO_PO')}
          >
            Converted to PO ({convertedCount})
          </button>
          <button
            className={`filter-chip ${statusFilter === 'REJECTED' ? 'active' : ''}`}
            onClick={() => setStatusFilter('REJECTED')}
          >
            Rejected ({rejectedCount})
          </button>
        </div>
      </div>

      {/* Main PR Table */}
      <div className="erp-card">
        <div className="erp-table-container">
          <table className="erp-table">
            <thead>
              <tr>
                <th style={{ width: '140px' }}>PR Number</th>
                <th style={{ width: '110px' }}>Req. Date</th>
                <th style={{ width: '130px' }}>Department</th>
                <th style={{ width: '150px' }}>Raised By</th>
                <th style={{ width: '110px' }}>Target Date</th>
                <th>Operational Justification</th>
                <th style={{ width: '90px', textAlign: 'center' }}>Items</th>
                <th style={{ width: '150px' }}>Status</th>
                <th style={{ width: '200px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: '2rem' }}>
                    <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 8px', color: '#64748b' }} />
                    <div style={{ color: '#64748b', fontSize: '13px' }}>Loading Purchase Requests...</div>
                  </td>
                </tr>
              ) : filteredPRs.length === 0 ? (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: '2.5rem' }}>
                    <FileText size={36} style={{ margin: '0 auto 8px', color: '#cbd5e1' }} />
                    <div style={{ fontWeight: 600, color: '#334155' }}>No Purchase Requests found</div>
                    <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
                      Try adjusting the search query or status filter.
                    </div>
                  </td>
                </tr>
              ) : (
                filteredPRs.map((pr) => {
                  const isApproved = pr.status === 'APPROVED';
                  const isPending = pr.status === 'SUBMITTED' || pr.status === 'DRAFT';

                  return (
                    <tr
                      key={pr.id}
                      onClick={() => setSelectedPR(pr)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td style={{ fontWeight: 700, fontFamily: 'monospace', color: '#2563eb' }}>
                        {pr.pr_number}
                      </td>
                      <td style={{ color: '#475569', whiteSpace: 'nowrap' }}>
                        {pr.request_date}
                      </td>
                      <td style={{ fontWeight: 600, color: '#0f172a' }}>
                        {pr.department_name}
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, color: '#0f172a', fontSize: '13px' }}>
                          {pr.requisitioner_id}
                        </div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>
                          {pr.requisitioner_role}
                        </div>
                      </td>
                      <td style={{ color: '#475569', whiteSpace: 'nowrap' }}>
                        {pr.target_date}
                      </td>
                      <td style={{ maxWidth: '300px' }} title={pr.justification}>
                        <div
                          style={{
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            color: '#334155',
                            fontSize: '13px',
                          }}
                        >
                          {pr.justification}
                        </div>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span className="badge badge-secondary" style={{ fontWeight: 700 }}>
                          {pr.lines?.length || 0} line(s)
                        </span>
                      </td>
                      <td>{getStatusBadge(pr.status)}</td>
                      <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }} onClick={(e) => e.stopPropagation()}>
                        <div style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
                          {isPending && isPlantHeadOrMgmt && (
                            <>
                              <button
                                type="button"
                                onClick={() => handleApprovePR(pr.id)}
                                disabled={approving}
                                className="erp-btn btn-xs btn-success"
                                title="Approve as Plant Head"
                              >
                                <Check size={12} className="btn-icon" /> Approve
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedPR(pr);
                                  setShowRejectModal(true);
                                }}
                                disabled={approving}
                                className="erp-btn btn-xs btn-danger"
                                title="Reject PR"
                              >
                                <X size={12} className="btn-icon" /> Reject
                              </button>
                            </>
                          )}
                          {isApproved && (
                            <button
                              type="button"
                              onClick={() => {
                                if (onNavigateToPO) {
                                  onNavigateToPO(pr);
                                } else {
                                  setSelectedPR(pr);
                                }
                              }}
                              className="erp-btn btn-xs btn-primary"
                              title="Generate PO from this approved PR"
                            >
                              <ShoppingCart size={12} className="btn-icon" /> Generate PO
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => setSelectedPR(pr)}
                            className="erp-btn btn-xs btn-secondary"
                            title="Inspect PR Details"
                          >
                            View
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* PR Detail Modal */}
      {selectedPR && !showRejectModal && (
        <div className="modal-backdrop" onClick={() => setSelectedPR(null)}>
          <div
            className="modal-content modal-large"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '850px', width: '95vw', maxHeight: '90vh' }}
          >
            <div className="modal-header">
              <div className="modal-title-group">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FileText size={20} style={{ color: '#2563eb' }} />
                  <h3 className="modal-title" style={{ margin: 0 }}>
                    Purchase Request: {selectedPR.pr_number}
                  </h3>
                  {getStatusBadge(selectedPR.status)}
                </div>
                <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                  Originating Requisition for Department: <strong>{selectedPR.department_name}</strong>
                </p>
              </div>
              <button
                type="button"
                className="close-btn"
                onClick={() => setSelectedPR(null)}
                title="Close"
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body" style={{ padding: '1.25rem', overflowY: 'auto' }}>
              {/* Summary Metadata Row */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                  gap: '12px',
                  background: '#f8fafc',
                  padding: '12px 16px',
                  borderRadius: '8px',
                  border: '1px solid #e2e8f0',
                  marginBottom: '16px',
                }}
              >
                <div>
                  <div style={{ fontSize: '11px', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>
                    Requisition Date
                  </div>
                  <div style={{ fontWeight: 700, color: '#0f172a', marginTop: '2px' }}>
                    {selectedPR.request_date}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '11px', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>
                    Target Required Date
                  </div>
                  <div style={{ fontWeight: 700, color: '#0f172a', marginTop: '2px' }}>
                    {selectedPR.target_date}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '11px', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>
                    Raised By
                  </div>
                  <div style={{ fontWeight: 700, color: '#0f172a', marginTop: '2px' }}>
                    {selectedPR.requisitioner_id} ({selectedPR.requisitioner_role})
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '11px', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>
                    Department
                  </div>
                  <div style={{ fontWeight: 700, color: '#0f172a', marginTop: '2px' }}>
                    {selectedPR.department_name}
                  </div>
                </div>
              </div>

              {/* Justification Box */}
              <div
                style={{
                  background: '#fffbeb',
                  border: '1px solid #fef3c7',
                  borderLeft: '4px solid #f59e0b',
                  padding: '12px 16px',
                  borderRadius: '6px',
                  marginBottom: '16px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontWeight: 700,
                    fontSize: '12px',
                    color: '#92400e',
                    marginBottom: '4px',
                  }}
                >
                  <AlertTriangle size={14} /> Mandatory Operational Justification (Financial Control Audit Requirement)
                </div>
                <div style={{ fontStyle: 'italic', fontSize: '13px', color: '#78350f', lineHeight: 1.5 }}>
                  "{selectedPR.justification}"
                </div>
              </div>

              {/* Plant Head Approval Verification */}
              {selectedPR.plant_head_approved_by && (
                <div
                  style={{
                    background: '#f0fdf4',
                    border: '1px solid #bbf7d0',
                    borderLeft: '4px solid #16a34a',
                    padding: '12px 16px',
                    borderRadius: '6px',
                    marginBottom: '16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                  }}
                >
                  <ShieldCheck size={24} style={{ color: '#16a34a', flexShrink: 0 }} />
                  <div style={{ fontSize: '12px', color: '#166534' }}>
                    <strong>Layer-1 Plant Head Authorized:</strong> Approved by{' '}
                    <span style={{ fontFamily: 'monospace', fontWeight: 700 }}>
                      {selectedPR.plant_head_approved_by}
                    </span>{' '}
                    on{' '}
                    <span>
                      {selectedPR.plant_head_approved_at
                        ? new Date(selectedPR.plant_head_approved_at).toLocaleString()
                        : 'Recorded in Ledger'}
                    </span>
                    . Validated for Purchase Order creation under Financial Control standard.
                  </div>
                </div>
              )}

              {/* Rejection notice */}
              {selectedPR.rejection_reason && (
                <div
                  style={{
                    background: '#fef2f2',
                    border: '1px solid #fecaca',
                    borderLeft: '4px solid #dc2626',
                    padding: '12px 16px',
                    borderRadius: '6px',
                    marginBottom: '16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                  }}
                >
                  <XCircle size={24} style={{ color: '#dc2626', flexShrink: 0 }} />
                  <div style={{ fontSize: '12px', color: '#991b1b' }}>
                    <strong>Rejection Reason:</strong> {selectedPR.rejection_reason}
                  </div>
                </div>
              )}

              {/* Line Items Table */}
              <div style={{ marginBottom: '16px' }}>
                <h4 style={{ fontSize: '13px', fontWeight: 700, color: '#334155', textTransform: 'uppercase', marginBottom: '8px' }}>
                  Requested Material Items ({selectedPR.lines?.length || 0})
                </h4>
                <div className="erp-table-container">
                  <table className="erp-table">
                    <thead>
                      <tr>
                        <th style={{ width: '40px' }}>#</th>
                        <th>Material Code & Name</th>
                        <th style={{ width: '80px' }}>UOM</th>
                        <th style={{ width: '120px', textAlign: 'right' }}>Requested Qty</th>
                        <th style={{ width: '120px', textAlign: 'right' }}>Est. Rate (₹)</th>
                        <th>Remarks / Purpose</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selectedPR.lines || []).map((line, idx) => (
                        <tr key={idx}>
                          <td style={{ color: '#94a3b8' }}>{line.line_number}</td>
                          <td style={{ fontWeight: 600, color: '#0f172a' }}>
                            {line.item_name}{' '}
                            <span style={{ color: '#64748b', fontFamily: 'monospace', fontWeight: 400 }}>
                              ({line.item_code})
                            </span>
                          </td>
                          <td style={{ color: '#475569' }}>{line.uom_code}</td>
                          <td style={{ textAlign: 'right', fontWeight: 700, color: '#0f172a' }}>
                            {line.quantity}
                          </td>
                          <td style={{ textAlign: 'right', fontFamily: 'monospace', color: '#475569' }}>
                            {line.estimated_rate ? `₹${parseFloat(String(line.estimated_rate)).toFixed(2)}` : '—'}
                          </td>
                          <td style={{ color: '#64748b', fontSize: '12px' }}>
                            {line.remarks || '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Audit Trail */}
              {selectedPR.audit_logs && selectedPR.audit_logs.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '13px', fontWeight: 700, color: '#334155', textTransform: 'uppercase', marginBottom: '8px' }}>
                    Audit History & Governance Trail
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {selectedPR.audit_logs.map((log: any, idx: number) => (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          padding: '8px 12px',
                          background: '#f8fafc',
                          borderRadius: '4px',
                          border: '1px solid #e2e8f0',
                          fontSize: '12px',
                        }}
                      >
                        <span style={{ fontWeight: 600, color: '#0f172a' }}>{log.action}</span>
                        <span style={{ color: '#475569' }}>{log.comments || 'Status transition'}</span>
                        <span style={{ color: '#94a3b8', fontFamily: 'monospace' }}>
                          {log.timestamp ? new Date(log.timestamp).toLocaleString() : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer Actions */}
            <div className="modal-footer flex-between" style={{ padding: '0.85rem 1.25rem', borderTop: '1px solid #e2e8f0' }}>
              <button
                type="button"
                onClick={() => setSelectedPR(null)}
                className="erp-btn btn-secondary"
              >
                Close Dossier
              </button>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {(selectedPR.status === 'SUBMITTED' || selectedPR.status === 'DRAFT') && isPlantHeadOrMgmt && (
                  <>
                    <button
                      type="button"
                      onClick={() => setShowRejectModal(true)}
                      className="erp-btn btn-danger"
                    >
                      <X size={14} className="btn-icon" /> Reject PR
                    </button>
                    <button
                      type="button"
                      onClick={() => handleApprovePR(selectedPR.id)}
                      disabled={approving}
                      className="erp-btn btn-success"
                    >
                      <Check size={14} className="btn-icon" />
                      {approving ? 'Approving...' : 'Approve as Plant Head'}
                    </button>
                  </>
                )}
                {selectedPR.status === 'APPROVED' && onNavigateToPO && (
                  <button
                    type="button"
                    onClick={() => {
                      onNavigateToPO(selectedPR);
                      setSelectedPR(null);
                    }}
                    className="erp-btn btn-primary"
                  >
                    <ShoppingCart size={14} className="btn-icon" /> Generate Purchase Order (PO)
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {showRejectModal && selectedPR && (
        <div className="modal-backdrop" onClick={() => setShowRejectModal(false)}>
          <div
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '480px' }}
          >
            <div className="modal-header">
              <div className="modal-title-group">
                <h3 className="modal-title" style={{ color: '#dc2626' }}>
                  Reject Purchase Request
                </h3>
                <p>Provide mandatory reason for rejection</p>
              </div>
              <button
                type="button"
                className="close-btn"
                onClick={() => setShowRejectModal(false)}
                title="Close"
              >
                <X size={18} />
              </button>
            </div>
            <div className="modal-body" style={{ padding: '1.25rem' }}>
              <p style={{ fontSize: '13px', color: '#475569', marginBottom: '12px' }}>
                Please specify the reason for rejecting PR #{selectedPR.pr_number}. This will be logged in the immutable audit trail.
              </p>
              <div className="form-group">
                <label className="form-label required">Rejection Reason</label>
                <textarea
                  rows={3}
                  value={rejectionComments}
                  onChange={(e) => setRejectionComments(e.target.value)}
                  placeholder="e.g. Existing buffer inventory sufficient, defer to next melting campaign..."
                  className="form-control"
                  required
                />
              </div>
            </div>
            <div className="modal-footer flex-between" style={{ padding: '0.85rem 1.25rem', borderTop: '1px solid #e2e8f0' }}>
              <button
                type="button"
                onClick={() => setShowRejectModal(false)}
                className="erp-btn btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRejectPR}
                disabled={approving || !rejectionComments.trim()}
                className="erp-btn btn-danger"
              >
                {approving ? 'Rejecting...' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create PR Modal */}
      {showCreateModal && (
        <div className="modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div
            className="modal-content modal-large"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '850px', width: '95vw', maxHeight: '90vh' }}
          >
            <div className="modal-header">
              <div className="modal-title-group">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Plus size={20} style={{ color: '#2563eb' }} />
                  <h3 className="modal-title" style={{ margin: 0 }}>
                    Raise New Purchase Request (PR)
                  </h3>
                </div>
                <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                  Step 1 of P2P: SCM / Planning Requisition with Mandatory Operational Justification
                </p>
              </div>
              <button
                type="button"
                className="close-btn"
                onClick={() => setShowCreateModal(false)}
                title="Close"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreatePR} style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
              <div className="modal-body" style={{ padding: '1.25rem', overflowY: 'auto' }}>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                    gap: '1rem',
                    marginBottom: '1rem',
                  }}
                >
                  <div className="form-group">
                    <label className="form-label required">Requisitioning Department</label>
                    <select
                      className="form-control"
                      value={departmentId}
                      onChange={(e) => setDepartmentId(Number(e.target.value))}
                      required
                    >
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name} ({d.code})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label required">Target Required Date</label>
                    <input
                      type="date"
                      className="form-control"
                      value={targetDate}
                      onChange={(e) => setTargetDate(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                  <label className="form-label required">
                    Operational Justification (Financial Control Audit Requirement)
                  </label>
                  <textarea
                    rows={2}
                    className="form-control"
                    value={justification}
                    onChange={(e) => setJustification(e.target.value)}
                    placeholder="Specify operational necessity (e.g. Monthly safety stock replenishment for induction furnace melting campaign, emergency refractory nozzle replacement)..."
                    required
                  />
                  <span style={{ fontSize: '11px', color: '#64748b', marginTop: '4px', display: 'block' }}>
                    Audit Rule: All PRs require valid justification before the Plant Head can approve Layer-1 procurement.
                  </span>
                </div>

                {/* Material Line Items */}
                <div style={{ marginTop: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <label className="form-label required" style={{ margin: 0 }}>
                      Material Line Items
                    </label>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <input
                        type="text"
                        placeholder="Filter catalog..."
                        value={itemSearchFilter}
                        onChange={(e) => setItemSearchFilter(e.target.value)}
                        className="form-control"
                        style={{ width: '150px', padding: '0.25rem 0.5rem', fontSize: '11px' }}
                      />
                      <button
                        type="button"
                        onClick={handleAddLine}
                        className="erp-btn btn-xs btn-secondary"
                      >
                        <Plus size={12} className="btn-icon" /> Add Item
                      </button>
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {lines.map((line, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '5fr 2fr 2fr 3fr auto',
                          gap: '8px',
                          alignItems: 'center',
                          padding: '10px',
                          background: '#f8fafc',
                          border: '1px solid #e2e8f0',
                          borderRadius: '6px',
                        }}
                      >
                        <div>
                          <label style={{ fontSize: '10px', textTransform: 'uppercase', color: '#64748b', fontWeight: 600, display: 'block', marginBottom: '2px' }}>
                            Material Item *
                          </label>
                          <select
                            className="form-control"
                            value={line.material_item_id}
                            onChange={(e) => handleLineChange(idx, 'material_item_id', e.target.value)}
                            style={{ fontSize: '12px', padding: '0.35rem 0.5rem' }}
                            required
                          >
                            <option value="">-- Select Material --</option>
                            {items
                              .filter(
                                (it) =>
                                  !itemSearchFilter ||
                                  it.name.toLowerCase().includes(itemSearchFilter.toLowerCase()) ||
                                  it.item_code.toLowerCase().includes(itemSearchFilter.toLowerCase())
                              )
                              .map((it) => (
                                <option key={it.id} value={it.id}>
                                  {it.item_code} - {it.name}
                                </option>
                              ))}
                          </select>
                        </div>

                        <div>
                          <label style={{ fontSize: '10px', textTransform: 'uppercase', color: '#64748b', fontWeight: 600, display: 'block', marginBottom: '2px' }}>
                            Quantity *
                          </label>
                          <input
                            type="number"
                            step="any"
                            min="0.001"
                            className="form-control"
                            value={line.quantity}
                            onChange={(e) => handleLineChange(idx, 'quantity', e.target.value)}
                            style={{ fontSize: '12px', padding: '0.35rem 0.5rem' }}
                            required
                          />
                        </div>

                        <div>
                          <label style={{ fontSize: '10px', textTransform: 'uppercase', color: '#64748b', fontWeight: 600, display: 'block', marginBottom: '2px' }}>
                            Est. Rate (₹)
                          </label>
                          <input
                            type="number"
                            step="0.01"
                            className="form-control"
                            value={line.estimated_rate}
                            onChange={(e) => handleLineChange(idx, 'estimated_rate', e.target.value)}
                            placeholder="Optional"
                            style={{ fontSize: '12px', padding: '0.35rem 0.5rem' }}
                          />
                        </div>

                        <div>
                          <label style={{ fontSize: '10px', textTransform: 'uppercase', color: '#64748b', fontWeight: 600, display: 'block', marginBottom: '2px' }}>
                            Remarks
                          </label>
                          <input
                            type="text"
                            className="form-control"
                            value={line.remarks}
                            onChange={(e) => handleLineChange(idx, 'remarks', e.target.value)}
                            placeholder="Purpose / Spec"
                            style={{ fontSize: '12px', padding: '0.35rem 0.5rem' }}
                          />
                        </div>

                        <div style={{ paddingTop: '16px' }}>
                          {lines.length > 1 && (
                            <button
                              type="button"
                              onClick={() => handleRemoveLine(idx)}
                              className="close-btn"
                              title="Remove item"
                              style={{ color: '#ef4444' }}
                            >
                              <Trash2 size={16} />
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="modal-footer flex-between" style={{ padding: '0.85rem 1.25rem', borderTop: '1px solid #e2e8f0' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="erp-btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="erp-btn btn-primary"
                >
                  <Send size={14} className="btn-icon" />
                  {submitting ? 'Submitting PR...' : 'Submit PR for Plant Head Approval'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
