import React, { useState, useEffect, useCallback } from 'react';
import { 
  FileText, 
  PlusCircle, 
  Clock, 
  CheckCircle, 
  AlertCircle, 
  Search, 
  Send, 
  History, 
  X,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import type { 
  ItemRequest, 
  Department, 
  UOM, 
  PaginatedResponse, 
  UserRole 
} from '../types';
import { apiFetch } from '../api/client';

interface ItemRequestsViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const ItemRequestsView: React.FC<ItemRequestsViewProps> = ({
  currentRole,
  currentUserId,
}) => {
  const [activeTab, setActiveTab] = useState<'all' | 'pending' | 'new'>('all');
  const [requests, setRequests] = useState<ItemRequest[]>([]);
  const [pendingRequests, setPendingRequests] = useState<ItemRequest[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [uoms, setUoms] = useState<UOM[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [total, setTotal] = useState<number>(0);
  const pageSize = 15;

  // Selected request modal
  const [selectedReq, setSelectedReq] = useState<ItemRequest | null>(null);

  // Decision Modal State (Approve / Reject)
  const [decisionReq, setDecisionReq] = useState<ItemRequest | null>(null);
  const [decisionAction, setDecisionAction] = useState<'approve' | 'reject' | null>(null);
  const [decisionComments, setDecisionComments] = useState<string>('');
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [processingDecision, setProcessingDecision] = useState<boolean>(false);

  // New Request Form State
  const [formName, setFormName] = useState<string>('');
  const [formDeptId, setFormDeptId] = useState<string>('');
  const [formCategory, setFormCategory] = useState<string>('RAW_MATERIAL');
  const [formSubcategory, setFormSubcategory] = useState<string>('');
  const [formUomId, setFormUomId] = useState<string>('');
  const [formJustification, setFormJustification] = useState<string>('');
  const [formSubmitting, setFormSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Load Reference Data (Departments and UOMs)
  useEffect(() => {
    apiFetch('/api/v1/departments')
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        setDepartments(data);
        if (data.length > 0) setFormDeptId(String(data[0].id));
      })
      .catch(() => {});

    apiFetch('/api/v1/uoms')
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        setUoms(data);
        if (data.length > 0) setFormUomId(String(data[0].id));
      })
      .catch(() => {});
  }, []);

  const fetchRequests = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      if (searchQuery.trim()) params.append('q', searchQuery.trim());
      params.append('page', String(page));
      params.append('size', String(pageSize));

      const res = await apiFetch(`/api/v1/item-requests?${params.toString()}`);
      if (res.ok) {
        const data: PaginatedResponse<ItemRequest> = await res.json();
        setRequests(data.items);
        setTotal(data.total);
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || 'Unable to load requests.');
        setRequests([]);
        setTotal(0);
      }
    } catch (err: any) {
      setError(`Network error: ${err.message}`);
      setRequests([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, searchQuery, page]);

  const fetchPendingQueue = useCallback(async () => {
    if (currentRole !== 'Management' && currentRole !== 'Admin') return;
    try {
      const res = await apiFetch('/api/v1/item-requests/pending', {
      });
      if (res.ok) {
        const data: PaginatedResponse<ItemRequest> = await res.json();
        setPendingRequests(data.items);
      }
    } catch (_) {}
  }, [currentRole]);

  useEffect(() => {
    if (activeTab === 'all') fetchRequests();
    if (activeTab === 'pending') fetchPendingQueue();
  }, [activeTab, fetchRequests, fetchPendingQueue]);

  // Form Submission (Create Draft)
  const handleCreateRequest = async (e: React.FormEvent, submitImmediately: boolean = false) => {
    e.preventDefault();
    setFormError(null);

    if (!formName.trim() || formName.trim().length < 2) {
      setFormError('Item name must be at least 2 characters.');
      return;
    }
    if (!formDeptId) {
      setFormError('Please select a department.');
      return;
    }
    if (!formUomId) {
      setFormError('Please select a base UOM.');
      return;
    }
    if (!formJustification.trim() || formJustification.trim().length < 5) {
      setFormError('Please provide a business justification (minimum 5 characters).');
      return;
    }

    setFormSubmitting(true);
    try {
      const payload = {
        requested_name: formName.trim(),
        proposed_department_id: Number(formDeptId),
        proposed_category: formCategory,
        proposed_subcategory: formSubcategory.trim() || null,
        proposed_uom_id: Number(formUomId),
        justification: formJustification.trim(),
      };

      const res = await apiFetch('/api/v1/item-requests', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const createdReq: ItemRequest = await res.json();

        if (submitImmediately) {
          // Submit for review right away
          const submitRes = await apiFetch(`/api/v1/item-requests/${createdReq.id}/submit`, {
            method: 'POST',
          });
          if (submitRes.ok) {
            setSuccessMsg(`Request ${createdReq.request_number} created and submitted for review.`);
          } else {
            setSuccessMsg(`Request ${createdReq.request_number} created in DRAFT status.`);
          }
        } else {
          setSuccessMsg(`Draft request ${createdReq.request_number} created.`);
        }

        // Reset Form
        setFormName('');
        setFormSubcategory('');
        setFormJustification('');
        setActiveTab('all');
        fetchRequests();
        setTimeout(() => setSuccessMsg(null), 4000);
      } else {
        const errData = await res.json().catch(() => ({}));
        setFormError(errData.detail || 'Failed to create item request.');
      }
    } catch (err: any) {
      setFormError(`Network error: ${err.message}`);
    } finally {
      setFormSubmitting(false);
    }
  };

  // Submit Draft Action
  const handleSubmitDraft = async (reqId: number) => {
    try {
      const res = await apiFetch(`/api/v1/item-requests/${reqId}/submit`, {
        method: 'POST',
      });
      if (res.ok) {
        setSuccessMsg('Request submitted for management review.');
        fetchRequests();
        setTimeout(() => setSuccessMsg(null), 4000);
      } else {
        const errData = await res.json().catch(() => ({}));
        alert(`Submit failed: ${errData.detail || 'Unknown error'}`);
      }
    } catch (err: any) {
      alert(`Network error: ${err.message}`);
    }
  };

  // Cancel Request Action
  const handleCancelRequest = async (reqId: number) => {
    if (!window.confirm('Are you sure you want to cancel this item request?')) return;
    try {
      const res = await apiFetch(`/api/v1/item-requests/${reqId}/cancel`, {
        method: 'POST',
      });
      if (res.ok) {
        setSuccessMsg('Request cancelled.');
        fetchRequests();
        setTimeout(() => setSuccessMsg(null), 4000);
      } else {
        const errData = await res.json().catch(() => ({}));
        alert(`Cancel failed: ${errData.detail || 'Unknown error'}`);
      }
    } catch (err: any) {
      alert(`Network error: ${err.message}`);
    }
  };

  // Decision Execution (Approve / Reject)
  const handleExecuteDecision = async () => {
    if (!decisionReq || !decisionAction) return;
    setDecisionError(null);

    if (decisionAction === 'reject' && (!decisionComments || !decisionComments.trim())) {
      setDecisionError('Rejection requires mandatory explanation in decision comments.');
      return;
    }

    setProcessingDecision(true);
    try {
      const endpoint = `/api/v1/item-requests/${decisionReq.id}/${decisionAction}`;
      const res = await apiFetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ comments: decisionComments.trim() }),
      });

      if (res.ok) {
        const updated: ItemRequest = await res.json();
        setDecisionReq(null);
        setDecisionAction(null);
        setDecisionComments('');
        setSuccessMsg(
          decisionAction === 'approve'
            ? `Request ${updated.request_number} approved! Material item created with code ${updated.linked_item_code || ''}.`
            : `Request ${updated.request_number} rejected.`
        );
        fetchRequests();
        fetchPendingQueue();
        setTimeout(() => setSuccessMsg(null), 5000);
      } else {
        const errData = await res.json().catch(() => ({}));
        setDecisionError(errData.detail || `Action failed with HTTP status ${res.status}`);
      }
    } catch (err: any) {
      setDecisionError(`Network error: ${err.message}`);
    } finally {
      setProcessingDecision(false);
    }
  };

  const canApprove = currentRole === 'Management' || currentRole === 'Admin';

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'DRAFT':
        return <span className="status-pill status-pill-wait">DRAFT</span>;
      case 'SUBMITTED':
        return <span className="status-pill status-pill-warn">SUBMITTED</span>;
      case 'APPROVED':
        return <span className="status-pill status-pill-ok">APPROVED</span>;
      case 'REJECTED':
        return <span className="status-pill status-pill-danger">REJECTED</span>;
      case 'CANCELLED':
        return <span className="status-pill status-pill-muted">CANCELLED</span>;
      default:
        return <span className="status-pill">{status}</span>;
    }
  };

  return (
    <div className="module-container">
      {/* Header */}
      <div className="view-header-row">
        <div>
          <span className="phase-pill">Phase 2: Approval Workflows</span>
          <h2 className="view-title">New Item Creation & Approval Workflows</h2>
          <p className="view-subtitle">
            Controlled procurement requisition pipeline. Every material item requires authorized approval before ledger entry.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className={`tab-btn ${activeTab === 'all' ? 'tab-btn-active' : ''}`}
            onClick={() => setActiveTab('all')}
          >
            <FileText size={16} /> All Requests
          </button>
          {canApprove && (
            <button
              className={`tab-btn ${activeTab === 'pending' ? 'tab-btn-active' : ''}`}
              onClick={() => setActiveTab('pending')}
            >
              <Clock size={16} /> Pending Review
              {pendingRequests.length > 0 && (
                <span className="count-pill">{pendingRequests.length}</span>
              )}
            </button>
          )}
          <button
            className={`tab-btn ${activeTab === 'new' ? 'tab-btn-active' : ''}`}
            onClick={() => setActiveTab('new')}
          >
            <PlusCircle size={16} /> New Request
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="success-banner card">
          <CheckCircle size={18} className="text-success" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* TAB 1: ALL REQUESTS */}
      {activeTab === 'all' && (
        <>
          <div className="filter-toolbar card">
            <div className="search-box">
              <Search size={16} className="text-muted search-icon" />
              <input
                type="text"
                className="search-input"
                placeholder="Search request # or item name..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
              />
            </div>
            <div className="filter-group">
              <select
                className="select-input"
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All Statuses</option>
                <option value="DRAFT">DRAFT</option>
                <option value="SUBMITTED">SUBMITTED</option>
                <option value="APPROVED">APPROVED</option>
                <option value="REJECTED">REJECTED</option>
                <option value="CANCELLED">CANCELLED</option>
              </select>
            </div>
          </div>

          {error && (
            <div className="error-banner card">
              <AlertCircle size={20} className="text-danger flex-shrink-0" />
              <div>
                <div className="error-title">Database / Telemetry Notification</div>
                <p className="error-body">{error}</p>
              </div>
            </div>
          )}

          <div className="card table-card">
            {loading ? (
              <div className="loading-state">
                <div className="spinner"></div>
                <p>Loading item requests...</p>
              </div>
            ) : requests.length === 0 ? (
              <div className="empty-state">
                <FileText size={48} className="text-muted mb-2" />
                <h3 className="empty-title">No Item Requests Found</h3>
                <p className="empty-desc">
                  No requests match the current filters. Click "New Request" to initiate a material item creation proposal.
                </p>
                <button className="primary-btn mt-3" onClick={() => setActiveTab('new')}>
                  <PlusCircle size={16} /> Initiate Item Request
                </button>
              </div>
            ) : (
              <>
                <table className="erp-table">
                <thead>
                  <tr>
                    <th>Request #</th>
                    <th>Requested Name</th>
                    <th>Proposed Dept</th>
                    <th>Category</th>
                    <th>Status</th>
                    <th>Requester</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map((r) => (
                    <tr key={r.id} onClick={() => setSelectedReq(r)} className="cursor-pointer">
                      <td><code className="text-xs font-semibold">{r.request_number}</code></td>
                      <td className="font-semibold text-main">{r.requested_name}</td>
                      <td>{r.department_name || `Dept #${r.proposed_department_id}`}</td>
                      <td><span className="cat-tag">{r.proposed_category}</span></td>
                      <td>{getStatusBadge(r.status)}</td>
                      <td className="text-xs">
                        <div>{r.requester_id}</div>
                        <div className="text-muted">{r.requester_role}</div>
                      </td>
                      <td className="text-muted text-xs">
                        {new Date(r.created_at).toLocaleDateString()}
                      </td>
                      <td>
                        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                          <button
                            className="table-action-btn"
                            onClick={() => setSelectedReq(r)}
                          >
                            View
                          </button>
                          {r.status === 'DRAFT' && (
                            <button
                              className="action-btn-small btn-primary-small"
                              onClick={() => handleSubmitDraft(r.id)}
                            >
                              Submit
                            </button>
                          )}
                          {(r.status === 'DRAFT' || r.status === 'SUBMITTED') && (
                            <button
                              className="action-btn-small btn-danger-small"
                              onClick={() => handleCancelRequest(r.id)}
                            >
                              Cancel
                            </button>
                          )}
                          {r.status === 'SUBMITTED' && canApprove && (
                            <button
                              className="action-btn-small btn-success-small"
                              onClick={() => {
                                setDecisionReq(r);
                                setDecisionAction('approve');
                                setDecisionComments('');
                                setDecisionError(null);
                              }}
                            >
                              Decide
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="table-pagination-row">
                <span className="pagination-info">
                  Showing <strong>{requests.length}</strong> of <strong>{total}</strong> requests
                </span>
                <div className="pagination-controls">
                  <button
                    className="page-btn"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <span className="page-current">
                    Page {page} of {Math.ceil(total / pageSize) || 1}
                  </span>
                  <button
                    className="page-btn"
                    disabled={page >= (Math.ceil(total / pageSize) || 1)}
                    onClick={() => setPage((p) => Math.min(Math.ceil(total / pageSize) || 1, p + 1))}
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            </>
          )}
          </div>
        </>
      )}

      {/* TAB 2: PENDING APPROVALS QUEUE */}
      {activeTab === 'pending' && (
        <div className="card table-card">
          <div className="card-header-row mb-3">
            <h3 className="card-title">
              <Clock size={18} className="text-amber inline-icon" />
              Pending Requisition Review Queue (Management / Admin)
            </h3>
            <span className="scope-tag">{pendingRequests.length} Awaiting Decision</span>
          </div>

          {pendingRequests.length === 0 ? (
            <div className="empty-state">
              <CheckCircle size={48} className="text-success mb-2" />
              <h3 className="empty-title">Queue Clear</h3>
              <p className="empty-desc">No item requests currently pending review.</p>
            </div>
          ) : (
            <table className="erp-table">
              <thead>
                <tr>
                  <th>Request #</th>
                  <th>Requested Name</th>
                  <th>Proposed Dept</th>
                  <th>Category</th>
                  <th>UOM</th>
                  <th>Requester</th>
                  <th>Submitted At</th>
                  <th>Decision</th>
                </tr>
              </thead>
              <tbody>
                {pendingRequests.map((r) => {
                  const isSelf = r.requester_id === currentUserId;
                  return (
                    <tr key={r.id}>
                      <td><code>{r.request_number}</code></td>
                      <td className="font-semibold">{r.requested_name}</td>
                      <td>{r.department_name || r.proposed_department_id}</td>
                      <td><span className="cat-tag">{r.proposed_category}</span></td>
                      <td><span className="uom-tag">{r.uom_code || r.proposed_uom_id}</span></td>
                      <td className="text-xs">
                        <strong>{r.requester_id}</strong> ({r.requester_role})
                        {isSelf && <div className="text-amber text-2xs font-bold">[Self-Requested]</div>}
                      </td>
                      <td className="text-xs text-muted">
                        {r.submitted_at ? new Date(r.submitted_at).toLocaleString() : 'N/A'}
                      </td>
                      <td>
                        <div className="flex gap-1">
                          <button
                            className="table-action-btn"
                            onClick={() => setSelectedReq(r)}
                          >
                            Details
                          </button>
                          <button
                            className="action-btn-small btn-success-small"
                            disabled={isSelf}
                            title={isSelf ? 'Self-approval not allowed' : 'Approve request'}
                            onClick={() => {
                              setDecisionReq(r);
                              setDecisionAction('approve');
                              setDecisionComments('');
                              setDecisionError(null);
                            }}
                          >
                            Approve
                          </button>
                          <button
                            className="action-btn-small btn-danger-small"
                            disabled={isSelf}
                            title={isSelf ? 'Self-decision not allowed' : 'Reject request'}
                            onClick={() => {
                              setDecisionReq(r);
                              setDecisionAction('reject');
                              setDecisionComments('');
                              setDecisionError(null);
                            }}
                          >
                            Reject
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* TAB 3: CREATE NEW REQUEST FORM */}
      {activeTab === 'new' && (
        <div className="card" style={{ maxWidth: '800px', margin: '0 auto' }}>
          <div className="card-header-row mb-3">
            <h3 className="card-title">
              <PlusCircle size={18} className="text-primary inline-icon" />
              New Material Item Creation Request
            </h3>
            <span className="scope-tag">Initiator: {currentUserId} ({currentRole})</span>
          </div>

          <form onSubmit={(e) => handleCreateRequest(e, false)}>
            {formError && (
              <div className="form-error-box mb-3">
                <AlertCircle size={16} className="text-danger flex-shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <div className="form-group mb-3">
              <label className="form-label">
                Proposed Item Name <span className="text-danger">*</span>
              </label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Spheroidal Graphite Pig Iron Grade A"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                required
              />
              <span className="form-hint">
                Standard technical nomenclature. Checks for existing conflicts in target department.
              </span>
            </div>

            <div className="grid-2-col mb-3">
              <div className="form-group">
                <label className="form-label">
                  Proposed Department <span className="text-danger">*</span>
                </label>
                <select
                  className="form-input"
                  value={formDeptId}
                  onChange={(e) => setFormDeptId(e.target.value)}
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
                <label className="form-label">
                  Material Category <span className="text-danger">*</span>
                </label>
                <select
                  className="form-input"
                  value={formCategory}
                  onChange={(e) => setFormCategory(e.target.value)}
                  required
                >
                  <option value="RAW_MATERIAL">Raw Material (RM)</option>
                  <option value="ALLOY">Ferro Alloy (FA)</option>
                  <option value="CONSUMABLE">Consumable (CON)</option>
                  <option value="RETURN">Return Scrap (RET)</option>
                  <option value="BORING">Machine Boring (BOR)</option>
                  <option value="GATING">Gatings / Runners (GAT)</option>
                </select>
              </div>
            </div>

            <div className="grid-2-col mb-3">
              <div className="form-group">
                <label className="form-label">Subcategory / Grade (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. INOCULANT, SILICON, BINDER"
                  value={formSubcategory}
                  onChange={(e) => setFormSubcategory(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">
                  Base Unit of Measurement (UOM) <span className="text-danger">*</span>
                </label>
                <select
                  className="form-input"
                  value={formUomId}
                  onChange={(e) => setFormUomId(e.target.value)}
                  required
                >
                  {uoms.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.code} — {u.name} (Precision: {u.decimal_precision} decimals)
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-group mb-4">
              <label className="form-label">
                Business Justification & Specifications <span className="text-danger">*</span>
              </label>
              <textarea
                className="form-textarea"
                rows={3}
                placeholder="Explain necessity, metallurgical application, or procurement justification..."
                value={formJustification}
                onChange={(e) => setFormJustification(e.target.value)}
                required
              />
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="secondary-btn"
                disabled={formSubmitting}
                onClick={() => setActiveTab('all')}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="secondary-btn"
                disabled={formSubmitting}
              >
                {formSubmitting ? 'Saving...' : 'Save as Draft'}
              </button>
              <button
                type="button"
                className="primary-btn"
                disabled={formSubmitting}
                onClick={(e) => handleCreateRequest(e, true)}
              >
                <Send size={15} />
                <span>Save & Submit Immediately</span>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Decision Modal (Approve / Reject) */}
      {decisionReq && decisionAction && (
        <div className="modal-backdrop" onClick={() => setDecisionReq(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className={`phase-pill ${decisionAction === 'approve' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                  {decisionAction === 'approve' ? 'Approve Requisition' : 'Reject Requisition'}
                </span>
                <h3 className="modal-title">{decisionReq.requested_name}</h3>
              </div>
              <button className="modal-close-btn" onClick={() => setDecisionReq(null)}>
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              {decisionError && (
                <div className="form-error-box mb-3">
                  <AlertCircle size={16} className="text-danger flex-shrink-0" />
                  <span>{decisionError}</span>
                </div>
              )}

              <div className="notice-banner mb-3">
                {decisionAction === 'approve' ? (
                  <div>
                    <strong>Approval Policy:</strong> Approving this request creates exactly <strong>one</strong> material item in the master catalog with an auto-generated code (e.g. <code>FDY-RM-XXX</code>). This action is permanent and logged in the immutable audit trail.
                  </div>
                ) : (
                  <div>
                    <strong>Rejection Policy:</strong> Rejection requires a mandatory explanatory reason. No material item will be created.
                  </div>
                )}
              </div>

              <div className="form-group">
                <label className="form-label">
                  Decision Comments {decisionAction === 'reject' && <span className="text-danger">* (Required)</span>}
                </label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  placeholder={
                    decisionAction === 'approve'
                      ? 'Add approval notes or specifications (optional)...'
                      : 'Provide explicit reason for rejecting this material requisition...'
                  }
                  value={decisionComments}
                  onChange={(e) => setDecisionComments(e.target.value)}
                  required={decisionAction === 'reject'}
                />
              </div>
            </div>

            <div className="modal-footer">
              <button
                className="secondary-btn"
                onClick={() => setDecisionReq(null)}
                disabled={processingDecision}
              >
                Cancel
              </button>
              <button
                className={decisionAction === 'approve' ? 'primary-btn' : 'action-btn-danger'}
                onClick={handleExecuteDecision}
                disabled={processingDecision}
              >
                {processingDecision
                  ? 'Processing Decision...'
                  : decisionAction === 'approve'
                  ? 'Confirm Approval & Generate Item'
                  : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Request Details & Audit Trail Modal */}
      {selectedReq && (
        <div className="modal-backdrop" onClick={() => setSelectedReq(null)}>
          <div className="modal-card" style={{ maxWidth: '750px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="phase-pill">Request Audit Dossier</span>
                <h3 className="modal-title">{selectedReq.request_number}: {selectedReq.requested_name}</h3>
              </div>
              <button className="modal-close-btn" onClick={() => setSelectedReq(null)}>
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              <div className="modal-info-grid mb-3">
                <div className="info-item">
                  <span className="info-label">Current Status</span>
                  {getStatusBadge(selectedReq.status)}
                </div>
                <div className="info-item">
                  <span className="info-label">Target Department</span>
                  <span className="info-val">{selectedReq.department_name || selectedReq.proposed_department_id}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Category / Subcategory</span>
                  <span className="info-val">{selectedReq.proposed_category} {selectedReq.proposed_subcategory ? `(${selectedReq.proposed_subcategory})` : ''}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Base UOM</span>
                  <span className="info-val font-semibold">{selectedReq.uom_code || selectedReq.proposed_uom_id}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Requester</span>
                  <span className="info-val text-xs">
                    {selectedReq.requester_id} ({selectedReq.requester_role})
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">Linked Master Code</span>
                  {selectedReq.linked_item_code ? (
                    <code className="info-code">{selectedReq.linked_item_code}</code>
                  ) : (
                    <span className="text-muted text-xs italic">Not Created</span>
                  )}
                </div>
              </div>

              <div className="info-desc-box mb-3">
                <div className="info-label mb-1">Business Justification</div>
                <p className="text-sm">{selectedReq.justification}</p>
              </div>

              {selectedReq.decision_comments && (
                <div className="info-desc-box mb-3 bg-slate-50">
                  <div className="info-label mb-1">Reviewer Decision Comments ({selectedReq.reviewer_id})</div>
                  <p className="text-sm">{selectedReq.decision_comments}</p>
                </div>
              )}

              {/* Immutable Audit Trail Timeline */}
              <div className="audit-timeline-container">
                <h4 className="card-title text-sm mb-2">
                  <History size={16} className="text-primary inline mr-1" />
                  Immutable State Transition Audit Log
                </h4>
                {selectedReq.audit_logs && selectedReq.audit_logs.length > 0 ? (
                  <div className="timeline-list">
                    {selectedReq.audit_logs.map((log) => (
                      <div key={log.id} className="timeline-entry">
                        <div className="timeline-marker"></div>
                        <div className="timeline-content">
                          <div className="flex justify-between items-center">
                            <span className="font-semibold text-xs text-main">
                              {log.action} ({log.to_status})
                            </span>
                            <span className="text-2xs text-muted">
                              {new Date(log.timestamp).toLocaleString()}
                            </span>
                          </div>
                          <div className="text-2xs text-muted">
                            Actor: <strong>{log.actor_id}</strong> [{log.actor_role}]
                          </div>
                          {log.comments && (
                            <div className="text-xs text-slate-700 mt-1 italic">
                              "{log.comments}"
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted">No audit history recorded.</p>
                )}
              </div>
            </div>

            <div className="modal-footer">
              <button className="secondary-btn" onClick={() => setSelectedReq(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
