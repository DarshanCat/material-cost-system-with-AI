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
  ItemCodePreview,
  ItemCodeRules,
  MaterialItem,
  PaginatedResponse,
  UserRole
} from '../types';
import { apiFetch, readApiError } from '../api/client';
import { hasPermission } from '../auth/permissions';
import {
  canSubmitPreview,
  categoriesForDepartment,
  categoryLabel,
  describeDuplicate,
  issuesForField,
  parseItemCodeError,
  type ItemCodeApiError,
} from '../api/itemCodes';
import '../item-codes.css';

interface ItemRequestsViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

async function errorFromResponse(res: Response, fallback: string): Promise<ItemCodeApiError> {
  const body = await res.json().catch(() => null);
  return parseItemCodeError(body, `${fallback} (HTTP ${res.status})`);
}

async function fetchPreview(body: Record<string, unknown>): Promise<ItemCodePreview> {
  const res = await apiFetch('/api/v1/item-codes/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readApiError(res, 'Code preview failed'));
  return res.json();
}

/** Validation errors, warnings, duplicates and the provisional code returned by the preview endpoint. */
const PreviewPanel: React.FC<{ preview: ItemCodePreview | null; loading: boolean; error: string | null }> = ({
  preview,
  loading,
  error,
}) => {
  if (error) {
    return (
      <div className="form-error-box">
        <AlertCircle size={16} className="text-danger flex-shrink-0" />
        <span>{error}</span>
      </div>
    );
  }
  if (!preview) {
    return <p className="text-xs text-muted">{loading ? 'Checking against the standard…' : 'Complete the steps above to preview the code.'}</p>;
  }
  return (
    <div className={`icg-preview ${preview.valid ? '' : 'icg-preview-invalid'}`}>
      <div className="flex justify-between items-center">
        <div>
          <div className="info-label">Provisional item code</div>
          <div className="icg-code">{preview.proposed_code ?? '—'}</div>
        </div>
        <span className={`status-pill ${preview.valid ? 'status-pill-ok' : 'status-pill-danger'}`}>
          {preview.valid ? 'Meets standard' : 'Cannot submit'}
        </span>
      </div>
      <div className="icg-meta-grid">
        <div className="info-item">
          <span className="info-label">Category</span>
          <span className="info-val">{preview.category_code ? `${preview.category_code} · ${preview.category_name}` : '—'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Cost head (derived)</span>
          <span className="info-val">{preview.cost_head ?? '—'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Serials remaining</span>
          <span className="info-val">{preview.serials_remaining ?? '—'}</span>
        </div>
      </div>
      <p className="text-2xs text-muted">{preview.note} Standard v{preview.standard_version}.</p>
      {((preview.errors || []).length > 0 || (preview.warnings || []).length > 0) && (
        <ul className="icg-issue-list">
          {(preview.errors || []).map((e, i) => (
            <li key={`e${i}`} className="icg-issue-error"><strong>{e.field}:</strong> {e.message}</li>
          ))}
          {(preview.warnings || []).map((w, i) => (
            <li key={`w${i}`} className="icg-issue-warning"><strong>{w.field}:</strong> {w.message}</li>
          ))}
        </ul>
      )}
      {(preview.duplicates || []).length > 0 && (
        <>
          <div className="info-label mt-2">Possible duplicates</div>
          <ul className="icg-issue-list">
            {(preview.duplicates || []).map((d, i) => (
              <li key={`d${i}`} className={d.blocking ? 'icg-issue-error' : 'icg-issue-warning'}>
                {d.blocking ? 'Blocking — ' : 'Similar — '}
                {describeDuplicate(d)}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
};

export const ItemRequestsView: React.FC<ItemRequestsViewProps> = ({
  currentRole,
  currentUserId,
}) => {
  const [activeTab, setActiveTab] = useState<'all' | 'pending' | 'new'>('all');
  const [requests, setRequests] = useState<ItemRequest[]>([]);
  const [pendingRequests, setPendingRequests] = useState<ItemRequest[]>([]);
  const [rules, setRules] = useState<ItemCodeRules | null>(null);
  const [rulesError, setRulesError] = useState<string | null>(null);
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
  const [decisionError, setDecisionError] = useState<ItemCodeApiError | null>(null);
  const [processingDecision, setProcessingDecision] = useState<boolean>(false);
  const [decisionPreview, setDecisionPreview] = useState<ItemCodePreview | null>(null);
  const [decisionPreviewError, setDecisionPreviewError] = useState<string | null>(null);

  // Guided registration form state
  const [masterSearch, setMasterSearch] = useState<string>('');
  const [masterResults, setMasterResults] = useState<MaterialItem[] | null>(null);
  const [masterSearchError, setMasterSearchError] = useState<string | null>(null);
  const [formDeptCode, setFormDeptCode] = useState<string>('');
  const [formCategory, setFormCategory] = useState<string>('');
  const [formName, setFormName] = useState<string>('');
  const [formSubcategory, setFormSubcategory] = useState<string>('');
  const [formUomId, setFormUomId] = useState<string>('');
  const [formJustification, setFormJustification] = useState<string>('');
  const [formSubmitting, setFormSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<ItemCodeApiError | null>(null);
  const [preview, setPreview] = useState<ItemCodePreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Load the Item Nomenclature Standard rules (departments, categories, UOMs with database IDs)
  useEffect(() => {
    apiFetch('/api/v1/item-codes/rules')
      .then(async (res) => {
        if (res.ok) {
          setRules(await res.json());
        } else {
          setRulesError(await readApiError(res, 'Unable to load the Item Nomenclature Standard rules'));
        }
      })
      .catch((err: Error) => setRulesError(`Network error: ${err.message}`));
  }, []);

  const selectedDept = rules?.departments.find((d) => d.code === formDeptCode);
  const deptCategories = categoriesForDepartment(rules, formDeptCode);
  const selectedCategory = deptCategories.find((c) => c.code === formCategory);
  const approvedUoms = rules?.uoms.filter((u) => u.provisioned) ?? [];

  // Live, non-reserving preview while the form is filled in (debounced)
  useEffect(() => {
    if (activeTab !== 'new') return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (cancelled) return;
      setPreviewLoading(true);
      fetchPreview({
        department_id: selectedDept?.department_id ?? null,
        category: formCategory || null,
        description: formName || null,
        uom_id: formUomId ? Number(formUomId) : null,
      })
        .then((data) => {
          if (cancelled) return;
          setPreview(data);
          setPreviewError(null);
        })
        .catch((err: Error) => {
          if (!cancelled) setPreviewError(err.message);
        })
        .finally(() => {
          if (!cancelled) setPreviewLoading(false);
        });
    }, 350);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [activeTab, selectedDept?.department_id, formCategory, formName, formUomId]);

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
        const data = await res.json();
        const itemsList = Array.isArray(data) ? data : (data?.items || []);
        setRequests(itemsList);
        setTotal(typeof data?.total === 'number' ? data.total : itemsList.length);
      } else {
        setError(await readApiError(res, 'Unable to load requests.'));
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
  }, [statusFilter, searchQuery, page, pageSize]);

  const fetchPendingQueue = useCallback(async () => {
    if (!hasPermission(currentRole, 'item:approve') && currentRole !== 'Admin') return;
    try {
      const res = await apiFetch('/api/v1/item-requests/pending');
      if (res.ok) {
        const data = await res.json();
        const pendingList = Array.isArray(data) ? data : (data?.items || []);
        setPendingRequests(pendingList);
      } else {
        setPendingRequests([]);
      }
    } catch (_) {
      setPendingRequests([]);
    }
  }, [currentRole]);

  useEffect(() => {
    if (activeTab === 'all') fetchRequests();
    if (activeTab === 'pending') fetchPendingQueue();
  }, [activeTab, fetchRequests, fetchPendingQueue]);

  // Step 1: search the master (active and retired items) before requesting a new code
  const handleMasterSearch = async () => {
    const term = masterSearch.trim();
    setMasterSearchError(null);
    if (term.length < 2) {
      setMasterSearchError('Enter at least 2 characters to search the item master.');
      return;
    }
    try {
      const responses = await Promise.all(
        ['true', 'false'].map((active) =>
          apiFetch(`/api/v1/items?${new URLSearchParams({ q: term, is_active: active, size: '50' }).toString()}`),
        ),
      );
      const found: MaterialItem[] = [];
      for (const res of responses) {
        if (!res.ok) {
          setMasterSearchError(await readApiError(res, 'Item master search failed'));
          return;
        }
        const data: PaginatedResponse<MaterialItem> = await res.json();
        found.push(...data.items);
      }
      setMasterResults(found);
    } catch (err: any) {
      setMasterSearchError(`Network error: ${err.message}`);
    }
  };

  const resetForm = () => {
    setFormName('');
    setFormSubcategory('');
    setFormJustification('');
    setFormCategory('');
    setFormError(null);
    setPreview(null);
  };

  // Form Submission (Create Draft)
  const handleCreateRequest = async (e: React.FormEvent, submitImmediately: boolean = false) => {
    e.preventDefault();
    setFormError(null);

    if (!selectedDept?.department_id) {
      setFormError({ message: 'Select a provisioned v1.0 owning department.', errors: [], duplicates: [] });
      return;
    }
    if (formJustification.trim().length < 5) {
      setFormError({ message: 'Please provide a business justification (minimum 5 characters).', errors: [], duplicates: [] });
      return;
    }

    setFormSubmitting(true);
    try {
      const payload = {
        requested_name: formName,
        proposed_department_id: selectedDept.department_id,
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
            const submitErr = await errorFromResponse(submitRes, 'Submission failed');
            setSuccessMsg(`Request ${createdReq.request_number} saved as DRAFT. Not submitted: ${submitErr.message}`);
          }
        } else {
          setSuccessMsg(`Draft request ${createdReq.request_number} created.`);
        }

        resetForm();
        setActiveTab('all');
        fetchRequests();
        setTimeout(() => setSuccessMsg(null), 6000);
      } else {
        setFormError(await errorFromResponse(res, 'Failed to create item request'));
      }
    } catch (err: any) {
      setFormError({ message: `Network error: ${err.message}`, errors: [], duplicates: [] });
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
        const err = await errorFromResponse(res, 'Submit failed');
        alert([err.message, ...err.errors.map((i) => `• ${i.message}`)].join('\n'));
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
        alert(`Cancel failed: ${(await errorFromResponse(res, 'Unknown error')).message}`);
      }
    } catch (err: any) {
      alert(`Network error: ${err.message}`);
    }
  };

  // Open the decision modal; for approvals, re-check the request against the standard and show the provisional code
  const openDecision = (r: ItemRequest, action: 'approve' | 'reject') => {
    setDecisionReq(r);
    setDecisionAction(action);
    setDecisionComments('');
    setDecisionError(null);
    setDecisionPreview(null);
    setDecisionPreviewError(null);
    if (action !== 'approve') return;
    fetchPreview({
      department_id: r.proposed_department_id,
      category: r.proposed_category,
      description: r.requested_name,
      uom_id: r.proposed_uom_id,
      exclude_request_id: r.id,
    })
      .then(setDecisionPreview)
      .catch((err: Error) => setDecisionPreviewError(err.message));
  };

  // Decision Execution (Approve / Reject)
  const handleExecuteDecision = async () => {
    if (!decisionReq || !decisionAction) return;
    setDecisionError(null);

    if (decisionAction === 'reject' && (!decisionComments || !decisionComments.trim())) {
      setDecisionError({ message: 'Rejection requires mandatory explanation in decision comments.', errors: [], duplicates: [] });
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
        setDecisionError(await errorFromResponse(res, 'Action failed'));
      }
    } catch (err: any) {
      setDecisionError({ message: `Network error: ${err.message}`, errors: [], duplicates: [] });
    } finally {
      setProcessingDecision(false);
    }
  };

  const canApprove = hasPermission(currentRole, 'item:approve');
  const canCreate = hasPermission(currentRole, 'item_request:create');
  const canSubmit = hasPermission(currentRole, 'item_request:submit');
  const canCancel = hasPermission(currentRole, 'item_request:cancel');
  const approvalBlocked = decisionAction === 'approve' && decisionPreview !== null && !canSubmitPreview(decisionPreview);

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

  const fieldErrors = (field: string) =>
    issuesForField([...(preview?.errors ?? []), ...(formError?.errors ?? [])], field).map((i, idx) => (
      <span key={idx} className="icg-field-error">{i.message}</span>
    ));

  return (
    <div className="module-container">
      {/* Header */}
      <div className="view-header-row">
        <div>
          <span className="phase-pill">Phase 2: Approval Workflows</span>
          <h2 className="view-title">New Item Registration & Approval</h2>
          <p className="view-subtitle">
            Item codes follow the VSPL Item Nomenclature Standard
            {rules ? ` v${rules.version} (${rules.code_format})` : ''}. Stores raises the request; Management approves it, and the
            code is allocated only at approval.
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
              {(pendingRequests || []).length > 0 && (
                <span className="count-pill">{(pendingRequests || []).length}</span>
              )}
            </button>
          )}
          {canCreate && (
            <button
              className={`tab-btn ${activeTab === 'new' ? 'tab-btn-active' : ''}`}
              onClick={() => setActiveTab('new')}
            >
              <PlusCircle size={16} /> New Request
            </button>
          )}
        </div>
      </div>

      {successMsg && (
        <div className="success-banner card">
          <CheckCircle size={18} className="text-success" />
          <span>{successMsg}</span>
        </div>
      )}

      {rulesError && (
        <div className="error-banner card">
          <AlertCircle size={20} className="text-danger flex-shrink-0" />
          <div>
            <div className="error-title">Item Nomenclature Standard unavailable</div>
            <p className="error-body">{rulesError}</p>
          </div>
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
            ) : (requests || []).length === 0 ? (
              <div className="empty-state">
                <FileText size={48} className="text-muted mb-2" />
                <h3 className="empty-title">No Item Requests Found</h3>
                <p className="empty-desc">
                  No requests match the current filters.{canCreate ? ' Click "New Request" to initiate a material item creation proposal.' : ''}
                </p>
                {canCreate && (
                  <button className="primary-btn mt-3" onClick={() => setActiveTab('new')}>
                    <PlusCircle size={16} /> Initiate Item Request
                  </button>
                )}
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
                  {(requests || []).map((r) => (
                    <tr key={r.id} onClick={() => setSelectedReq(r)} className="cursor-pointer">
                      <td><code className="text-xs font-semibold">{r.request_number}</code></td>
                      <td className="font-semibold text-main">{r.requested_name}</td>
                      <td>{r.department_name || `Dept #${r.proposed_department_id}`}</td>
                      <td><span className="cat-tag">{categoryLabel(rules, r.proposed_category)}</span></td>
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
                          {r.status === 'DRAFT' && canSubmit && (
                            <button
                              className="action-btn-small btn-primary-small"
                              onClick={() => handleSubmitDraft(r.id)}
                            >
                              Submit
                            </button>
                          )}
                          {(r.status === 'DRAFT' || r.status === 'SUBMITTED') && canCancel && (
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
                              onClick={() => openDecision(r, 'approve')}
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
                  Showing <strong>{(requests || []).length}</strong> of <strong>{total}</strong> requests
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
            <span className="scope-tag">{(pendingRequests || []).length} Awaiting Decision</span>
          </div>

          {(pendingRequests || []).length === 0 ? (
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
                {(pendingRequests || []).map((r) => {
                  const isSelf = r.requester_id === currentUserId;
                  return (
                    <tr key={r.id}>
                      <td><code>{r.request_number}</code></td>
                      <td className="font-semibold">{r.requested_name}</td>
                      <td>{r.department_name || r.proposed_department_id}</td>
                      <td><span className="cat-tag">{categoryLabel(rules, r.proposed_category)}</span></td>
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
                            onClick={() => openDecision(r, 'approve')}
                          >
                            Approve
                          </button>
                          <button
                            className="action-btn-small btn-danger-small"
                            disabled={isSelf}
                            title={isSelf ? 'Self-decision not allowed' : 'Reject request'}
                            onClick={() => openDecision(r, 'reject')}
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

      {/* TAB 3: GUIDED NEW ITEM REGISTRATION */}
      {activeTab === 'new' && canCreate && (
        <div className="card" style={{ maxWidth: '860px', margin: '0 auto' }}>
          <div className="card-header-row mb-3">
            <h3 className="card-title">
              <PlusCircle size={18} className="text-primary inline-icon" />
              Register a New Item (Nomenclature Standard{rules ? ` v${rules.version}` : ''})
            </h3>
            <span className="scope-tag">Initiator: {currentUserId} ({currentRole})</span>
          </div>

          {rules && !rules.registry_installed && (
            <div className="notice-banner mb-3">
              <div>
                <strong>Code registry not installed.</strong> Requests can be drafted and submitted, but approval is refused until
                database migration <code>008_item_code_registry</code> is applied.
              </div>
            </div>
          )}

          <form onSubmit={(e) => handleCreateRequest(e, false)}>
            {formError && (
              <div className="form-error-box mb-3">
                <AlertCircle size={16} className="text-danger flex-shrink-0" />
                <div>
                  <div>{formError.message}</div>
                  {formError.errors.map((i, idx) => (
                    <div key={idx}>• {i.message}</div>
                  ))}
                  {formError.duplicates.map((d, idx) => (
                    <div key={`d${idx}`}>• {describeDuplicate(d)}</div>
                  ))}
                </div>
              </div>
            )}

            {/* Step 1 */}
            <div className="icg-step">
              <div className="icg-step-header">
                <span className="icg-step-number">1</span>
                <span className="icg-step-title">Search the master first — never create a duplicate</span>
              </div>
              <div className="icg-search-row">
                <input
                  type="text"
                  className="form-input"
                  placeholder="Search by description or code (active and retired items)"
                  value={masterSearch}
                  onChange={(e) => setMasterSearch(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleMasterSearch();
                    }
                  }}
                />
                <button type="button" className="secondary-btn" onClick={handleMasterSearch}>
                  <Search size={15} /> <span>Search</span>
                </button>
              </div>
              {masterSearchError && <span className="icg-field-error">{masterSearchError}</span>}
              {masterResults && (
                (masterResults || []).length === 0 ? (
                  <p className="text-xs text-muted mt-2">No existing item matches "{masterSearch.trim()}".</p>
                ) : (
                  <table className="erp-table mt-2">
                    <thead>
                      <tr>
                        <th>Code</th>
                        <th>Description</th>
                        <th>Department</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {masterResults.map((it) => (
                        <tr key={it.id}>
                          <td><code className="item-code-badge">{it.item_code}</code></td>
                          <td>{it.name}</td>
                          <td>{it.department_name || it.department_id}</td>
                          <td>
                            <span className={`status-tag ${it.is_active ? 'active-tag' : 'inactive-tag'}`}>
                              {it.is_active ? 'Active' : 'Retired'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )
              )}
              <p className="form-hint">If the item already exists, use its code. Retired codes are never reissued.</p>
            </div>

            {/* Step 2 */}
            <div className="icg-step">
              <div className="icg-step-header">
                <span className="icg-step-number">2</span>
                <span className="icg-step-title">Owning department and category</span>
              </div>
              <div className="grid-2-col">
                <div className="form-group">
                  <label className="form-label">
                    Owning Department <span className="text-danger">*</span>
                  </label>
                  <select
                    className="form-input"
                    value={formDeptCode}
                    onChange={(e) => {
                      setFormDeptCode(e.target.value);
                      setFormCategory('');
                    }}
                    required
                  >
                    <option value="">{rules ? 'Select department…' : 'Loading standard…'}</option>
                    {rules?.departments.map((d) => (
                      <option key={d.code} value={d.code} disabled={!d.provisioned}>
                        {d.code} — {d.name}{d.provisioned ? '' : ' (not set up in database)'}
                      </option>
                    ))}
                  </select>
                  {fieldErrors('department')}
                </div>

                <div className="form-group">
                  <label className="form-label">
                    Category <span className="text-danger">*</span>
                  </label>
                  <select
                    className="form-input"
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                    disabled={!formDeptCode}
                    required
                  >
                    <option value="">{formDeptCode ? 'Select category…' : 'Select a department first'}</option>
                    {deptCategories.map((c) => (
                      <option key={c.code} value={c.code}>
                        {c.code} — {c.name}
                      </option>
                    ))}
                  </select>
                  {selectedCategory && (
                    <span className="form-hint">Cost head (derived, not entered): {selectedCategory.cost_head}</span>
                  )}
                  {fieldErrors('category')}
                </div>
              </div>
              {rules && (rules.unprovisioned_departments || []).length > 0 && (
                <p className="form-hint">
                  Standard departments not yet set up in the database: {(rules.unprovisioned_departments || []).join(', ')}. New
                  departments or categories need an approved update to the standard.
                </p>
              )}
            </div>

            {/* Step 3 */}
            <div className={`icg-step ${formCategory ? '' : 'icg-step-disabled'}`}>
              <div className="icg-step-header">
                <span className="icg-step-number">3</span>
                <span className="icg-step-title">Item description and unit</span>
              </div>
              <div className="form-group mb-3">
                <label className="form-label">
                  Item Description <span className="text-danger">*</span>
                </label>
                <input
                  type="text"
                  className="form-input"
                  placeholder={selectedCategory ? `e.g. ${selectedCategory.example}` : 'Select a category first'}
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  disabled={!formCategory}
                  required
                />
                {selectedCategory && (
                  <span className="form-hint">
                    Pattern for {selectedCategory.name}: <strong>{selectedCategory.pattern}</strong>
                    {selectedCategory.verbatim_description
                      ? ' — enter the ISO designation exactly as printed.'
                      : `. ${rules?.naming_formula ?? ''}. Title Case, single spaces, no department, supplier or price.`}
                  </span>
                )}
                {fieldErrors('description')}
                {rules && (
                  <ul className="icg-hint-list">
                    <li>
                      Standard abbreviations:{' '}
                      {rules.abbreviations.map((a) => `${a.abbreviation} (${a.meaning})`).join(', ')}
                    </li>
                  </ul>
                )}
              </div>

              <div className="grid-2-col">
                <div className="form-group">
                  <label className="form-label">
                    Unit of Measure <span className="text-danger">*</span>
                  </label>
                  <select
                    className="form-input"
                    value={formUomId}
                    onChange={(e) => setFormUomId(e.target.value)}
                    disabled={!formCategory}
                    required
                  >
                    <option value="">Select UOM…</option>
                    {approvedUoms.map((u) => (
                      <option key={u.code} value={String(u.uom_id)}>
                        {u.label} — {u.meaning}
                      </option>
                    ))}
                  </select>
                  {rules && (rules.unprovisioned_uoms || []).length > 0 && (
                    <span className="form-hint">Approved but not set up in the database: {(rules.unprovisioned_uoms || []).join(', ')}</span>
                  )}
                  {fieldErrors('uom')}
                </div>
                <div className="form-group">
                  <label className="form-label">Subcategory / Grade (Optional)</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. INOCULANT"
                    value={formSubcategory}
                    onChange={(e) => setFormSubcategory(e.target.value)}
                    disabled={!formCategory}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">
                  Business Justification <span className="text-danger">*</span>
                </label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  placeholder="Why the item is needed and where it will be used..."
                  value={formJustification}
                  onChange={(e) => setFormJustification(e.target.value)}
                  disabled={!formCategory}
                  required
                />
              </div>
            </div>

            {/* Step 4 */}
            <div className="icg-step">
              <div className="icg-step-header">
                <span className="icg-step-number">4</span>
                <span className="icg-step-title">Check, duplicates and provisional code</span>
              </div>
              <PreviewPanel preview={preview} loading={previewLoading} error={previewError} />
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
                disabled={formSubmitting || !canSubmitPreview(preview)}
              >
                {formSubmitting ? 'Saving...' : 'Save as Draft'}
              </button>
              <button
                type="button"
                className="primary-btn"
                disabled={formSubmitting || !canSubmitPreview(preview)}
                onClick={(e) => handleCreateRequest(e, true)}
              >
                <Send size={15} />
                <span>Save & Submit for Approval</span>
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
                  <div>
                    <div>{decisionError.message}</div>
                    {decisionError.errors.map((i, idx) => (
                      <div key={idx}>• {i.message}</div>
                    ))}
                    {decisionError.duplicates.map((d, idx) => (
                      <div key={`d${idx}`}>• {describeDuplicate(d)}</div>
                    ))}
                  </div>
                </div>
              )}

              <div className="notice-banner mb-3">
                {decisionAction === 'approve' ? (
                  <div>
                    <strong>Approval Policy:</strong> Approving creates exactly <strong>one</strong> material item. The code is
                    allocated now from the next serial ever issued for the department and category (gaps are never filled, retired
                    codes are never reused) and is recorded permanently.
                  </div>
                ) : (
                  <div>
                    <strong>Rejection Policy:</strong> Rejection requires a mandatory explanatory reason. No material item will be created.
                  </div>
                )}
              </div>

              {decisionAction === 'approve' && (
                <div className="mb-3">
                  <PreviewPanel preview={decisionPreview} loading={!decisionPreview && !decisionPreviewError} error={decisionPreviewError} />
                  {approvalBlocked && (
                    <p className="text-xs text-danger mt-2">
                      This request does not meet the standard or duplicates an existing item. Reject it with a reason so it can be
                      raised again correctly.
                    </p>
                  )}
                </div>
              )}

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
                disabled={processingDecision || approvalBlocked}
              >
                {processingDecision
                  ? 'Processing Decision...'
                  : decisionAction === 'approve'
                  ? 'Confirm Approval & Allocate Code'
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
                  <span className="info-val">{categoryLabel(rules, selectedReq.proposed_category)} {selectedReq.proposed_subcategory ? `(${selectedReq.proposed_subcategory})` : ''}</span>
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
                {(selectedReq.audit_logs || []).length > 0 ? (
                  <div className="timeline-list">
                    {(selectedReq.audit_logs || []).map((log) => (
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
