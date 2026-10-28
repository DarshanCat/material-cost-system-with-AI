import React, { useState, useEffect } from 'react';
import { 
  Play, 
  RefreshCw, 
  Eye, 
  CheckCircle, 
  AlertTriangle, 
  Calendar,
  X,
  UserCheck
} from 'lucide-react';
import type { 
  ReconciliationRun, 
  UserRole 
} from '../types';
import { apiFetch } from '../api/client';

interface ReconciliationDashboardProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const ReconciliationDashboard: React.FC<ReconciliationDashboardProps> = ({ currentRole }) => {
  const [runs, setRuns] = useState<ReconciliationRun[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedRun, setSelectedRun] = useState<ReconciliationRun | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'results' | 'candidates' | 'exceptions'>('results');
  
  // New Run Trigger Form State
  const [showRunModal, setShowRunModal] = useState<boolean>(false);
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [runNotes, setRunNotes] = useState<string>('');
  const [triggering, setTriggering] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Candidate action state
  const [candidateActionComment, setCandidateActionComment] = useState<string>('');

  // Exception resolution state
  const [selectedExceptionId, setSelectedExceptionId] = useState<number | null>(null);
  const [exceptionAction, setExceptionAction] = useState<'RESOLVE' | 'ACCEPT_LOSS'>('RESOLVE');
  const [exceptionComment, setExceptionComment] = useState<string>('');

  const fetchRuns = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/v1/reconciliation/runs?limit=50');
      if (res.ok) {
        const data = await res.json();
        const runsList = Array.isArray(data) ? data : (data?.items || []);
        setRuns(runsList);
        if (runsList.length > 0 && !selectedRun) {
          fetchRunDetail(runsList[0].id);
        }
      }
    } catch {
      // fallback
    } finally {
      setLoading(false);
    }
  };

  const fetchRunDetail = async (runId: number) => {
    setLoadingDetail(true);
    try {
      const res = await apiFetch(`/api/v1/reconciliation/runs/${runId}`);
      if (res.ok) {
        setSelectedRun(await res.json());
      }
    } catch {
      // fallback
    } finally {
      setLoadingDetail(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  const handleTriggerRun = async (e: React.FormEvent) => {
    e.preventDefault();
    setTriggering(true);
    setFeedback(null);

    const payload = {
      date_from: dateFrom ? dateFrom : null,
      date_to: dateTo ? dateTo : null,
      notes: runNotes.trim() || null,
    };

    try {
      const res = await apiFetch('/api/v1/reconciliation/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const newRun = await res.json();
        setFeedback({ 
          type: 'success', 
          message: `Reconciliation run ${newRun.run_number} completed. Found ${newRun.exact_matches_count} exact matches, ${newRun.batch_matches_count} batch aggregations, and ${newRun.discrepancies_count} discrepancies.` 
        });
        setShowRunModal(false);
        fetchRuns();
        fetchRunDetail(newRun.id);
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Reconciliation run failed.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error triggering reconciliation run.' });
    } finally {
      setTriggering(false);
    }
  };

  const handleConfirmCandidate = async (candidateId: number) => {
    try {
      const res = await apiFetch(`/api/v1/reconciliation/candidates/${candidateId}/confirm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ comments: candidateActionComment.trim() || 'Confirmed by supervisor' }),
      });
      if (res.ok) {
        setFeedback({ type: 'success', message: 'Fuzzy candidate confirmed and allocated successfully.' });
        setCandidateActionComment('');
        if (selectedRun) fetchRunDetail(selectedRun.id);
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Candidate confirmation failed.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error confirming candidate.' });
    }
  };

  const handleRejectCandidate = async (candidateId: number) => {
    if (!candidateActionComment.trim()) {
      alert('Please provide rejection comments.');
      return;
    }
    try {
      const res = await apiFetch(`/api/v1/reconciliation/candidates/${candidateId}/reject`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ comments: candidateActionComment.trim() }),
      });
      if (res.ok) {
        setFeedback({ type: 'success', message: 'Candidate rejected.' });
        setCandidateActionComment('');
        if (selectedRun) fetchRunDetail(selectedRun.id);
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Rejection failed.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error rejecting candidate.' });
    }
  };

  const handleResolveException = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedExceptionId || !exceptionComment.trim()) return;

    try {
      const res = await apiFetch(`/api/v1/reconciliation/exceptions/${selectedExceptionId}/resolve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: exceptionAction,
          comments: exceptionComment.trim(),
        }),
      });

      if (res.ok) {
        setFeedback({ type: 'success', message: 'Exception updated.' });
        setSelectedExceptionId(null);
        setExceptionComment('');
        if (selectedRun) fetchRunDetail(selectedRun.id);
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Failed to update exception.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error resolving exception.' });
    }
  };

  return (
    <div className="erp-module">
      <div className="module-header">
        <div>
          <h2 className="module-title">Induction Furnace Issue-to-Heat Reconciliation</h2>
          <p className="module-subtitle">
            Deterministic 3-pass comparison between Stores material issues and furnace melt charges.
          </p>
        </div>
        <div className="header-actions">
          {['Foundry', 'Management', 'Admin'].includes(currentRole) && (
            <button className="erp-btn btn-primary" onClick={() => setShowRunModal(true)}>
              <Play size={16} className="btn-icon" /> Run Reconciliation
            </button>
          )}
          <button className="erp-btn btn-secondary" onClick={fetchRuns}>
            <RefreshCw size={14} className="btn-icon" /> Refresh
          </button>
        </div>
      </div>

      {feedback && (
        <div className={`notification-banner ${feedback.type === 'success' ? 'banner-success' : 'banner-error'}`}>
          {feedback.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Isolation Info Card */}
      <div className="info-banner mb-4">
        <strong>Strict Accounting Principle:</strong> Heat Log charges and reconciliation runs are analytical and 
        <strong> NEVER modify inventory ledger balances</strong>. Issue slips remain the sole mechanism for stock movement.
      </div>

      {/* Historical Runs Table */}
      <div className="erp-card mb-4">
        <div className="card-header">
          <h3>Reconciliation Runs History</h3>
        </div>
        <div className="erp-table-container">
          <table className="erp-table">
            <thead>
              <tr>
                <th>Run Number</th>
                <th>Executed At</th>
                <th>Date Range</th>
                <th>Algorithm</th>
                <th>Evaluated</th>
                <th>Exact Matches</th>
                <th>Batch Matches</th>
                <th>Fuzzy Candidates</th>
                <th>Discrepancies</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10} className="text-center py-4">Loading reconciliation history...</td></tr>
              ) : runs.length === 0 ? (
                <tr><td colSpan={10} className="text-center py-4 text-muted">No reconciliation runs recorded yet. Click 'Run Reconciliation' to evaluate issues vs charges.</td></tr>
              ) : (
                runs.map((r) => (
                  <tr key={r.id} className={selectedRun?.id === r.id ? 'row-selected' : ''}>
                    <td><strong>{r.run_number}</strong></td>
                    <td>{new Date(r.created_at).toLocaleString()}</td>
                    <td>{r.date_from ? `${r.date_from} to ${r.date_to || 'Now'}` : 'All Dates'}</td>
                    <td><code className="code-badge">{r.algorithm_version}</code></td>
                    <td><strong>{r.total_evaluated_count}</strong></td>
                    <td><span className="badge badge-success">{r.exact_matches_count}</span></td>
                    <td><span className="badge badge-secondary">{r.batch_matches_count}</span></td>
                    <td><span className="badge badge-warning">{r.fuzzy_candidates_count}</span></td>
                    <td>
                      <span className={`badge ${r.discrepancies_count === 0 ? 'badge-success' : 'badge-danger'}`}>
                        {r.discrepancies_count}
                      </span>
                    </td>
                    <td>
                      <button 
                        className="erp-btn btn-sm btn-outline"
                        onClick={() => fetchRunDetail(r.id)}
                      >
                        <Eye size={12} className="btn-icon" /> Inspect Run
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Selected Run Details View */}
      {selectedRun && (
        <div className="erp-card mt-4">
          <div className="card-header flex-between">
            <div className="header-title-group">
              <h3>Run Details: {selectedRun.run_number}</h3>
              <p className="text-muted">Executed by {selectedRun.created_by} at {new Date(selectedRun.created_at).toLocaleString()}</p>
            </div>
            <div className="nav-tab-group">
              <button 
                className={`tab-btn ${activeTab === 'results' ? 'active' : ''}`}
                onClick={() => setActiveTab('results')}
              >
                Item Comparisons ({selectedRun.results?.length || 0})
              </button>
              <button 
                className={`tab-btn ${activeTab === 'candidates' ? 'active' : ''}`}
                onClick={() => setActiveTab('candidates')}
              >
                Advisory Fuzzy Matches ({selectedRun.candidate_matches?.length || 0})
              </button>
              <button 
                className={`tab-btn ${activeTab === 'exceptions' ? 'active' : ''}`}
                onClick={() => setActiveTab('exceptions')}
              >
                Exceptions Queue ({selectedRun.exceptions?.length || 0})
              </button>
            </div>
          </div>

          <div className="card-body">
            {loadingDetail ? (
              <div className="text-center py-4">Loading run details...</div>
            ) : activeTab === 'results' ? (
              <div className="erp-table-container">
                <table className="erp-table">
                  <thead>
                    <tr>
                      <th>Material Item</th>
                      <th>Heat Number</th>
                      <th>Match Method</th>
                      <th>Issued Qty (A)</th>
                      <th>Charged Qty (B)</th>
                      <th>Variance (A - B)</th>
                      <th>Tolerance Limit</th>
                      <th>Variance Class</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedRun.results?.map((res) => (
                      <tr key={res.id}>
                        <td>
                          <strong>{res.material_item ? res.material_item.name : `Item #${res.material_item_id}`}</strong>
                          <br /><small className="text-muted">{res.material_item?.item_code}</small>
                        </td>
                        <td>{res.heat?.heat_number || 'Batch Aggregation'}</td>
                        <td><span className="badge badge-secondary">{res.match_method}</span></td>
                        <td>{Number(res.issued_quantity).toLocaleString()}</td>
                        <td>{Number(res.charged_quantity).toLocaleString()}</td>
                        <td className={Number(res.variance_quantity) === 0 ? '' : Number(res.variance_quantity) > 0 ? 'text-primary' : 'text-danger'}>
                          <strong>{Number(res.variance_quantity) > 0 ? `+${Number(res.variance_quantity).toFixed(4)}` : Number(res.variance_quantity).toFixed(4)}</strong>
                          {res.variance_percentage && <small className="text-muted block">({Number(res.variance_percentage).toFixed(2)}%)</small>}
                        </td>
                        <td>
                          <small title={res.tolerance_basis}>{Number(res.applied_tolerance).toFixed(4)}</small>
                        </td>
                        <td>
                          <span className={`badge ${
                            res.variance_class === 'OK' ? 'badge-success' :
                            res.variance_class === 'SHORT_ISSUE' ? 'badge-danger' :
                            res.variance_class === 'EXCESS_ISSUE' ? 'badge-warning' :
                            res.variance_class === 'DECIMAL_SUSPECT' ? 'badge-danger' :
                            'badge-secondary'
                          }`}>
                            {res.variance_class}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : activeTab === 'candidates' ? (
              <div>
                <p className="text-muted mb-3">
                  Pass 3 generates advisory candidate suggestions based on typographical similarity and adjacent date shift crossovers. 
                  <strong> Human confirmation is strictly required.</strong>
                </p>
                {selectedRun.candidate_matches?.length === 0 ? (
                  <p className="text-muted py-4 text-center">No fuzzy candidate matches proposed for this run.</p>
                ) : (
                  <table className="erp-table">
                    <thead>
                      <tr>
                        <th>Confidence</th>
                        <th>Suggestion Reason</th>
                        <th>Issue Line ID</th>
                        <th>Charge Line ID</th>
                        <th>Status</th>
                        <th>Reviewer Decision</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedRun.candidate_matches?.map((c) => (
                        <tr key={c.id}>
                          <td><strong>{Number(c.confidence_score).toFixed(1)}%</strong></td>
                          <td>{c.suggestion_reason}</td>
                          <td>Line #{c.issue_line_id}</td>
                          <td>Charge #{c.heat_charge_line_id}</td>
                          <td>
                            <span className={`badge ${
                              c.status === 'CONFIRMED' ? 'badge-success' :
                              c.status === 'REJECTED' ? 'badge-danger' : 'badge-warning'
                            }`}>
                              {c.status}
                            </span>
                          </td>
                          <td>
                            {c.reviewed_by ? (
                              <span>{c.reviewed_by} ({c.review_comments})</span>
                            ) : '-'}
                          </td>
                          <td>
                            {c.status === 'SUGGESTED' && ['Foundry', 'Management', 'Admin'].includes(currentRole) && (
                              <div className="action-button-group">
                                <button className="erp-btn btn-sm btn-success" onClick={() => handleConfirmCandidate(c.id)}>
                                  Confirm
                                </button>
                                <button className="erp-btn btn-sm btn-danger" onClick={() => handleRejectCandidate(c.id)}>
                                  Reject
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <div className="mt-3 form-group max-w-md">
                  <label>Review Notes (for Candidate Confirm / Reject)</label>
                  <input 
                    type="text" 
                    placeholder="Enter justification remarks..." 
                    value={candidateActionComment}
                    onChange={(e) => setCandidateActionComment(e.target.value)}
                  />
                </div>
              </div>
            ) : (
              <div>
                <p className="text-muted mb-3">
                  Reconciliation exceptions track discrepancies (Short issues, Excess issues, Unmatched slips, Unmapped materials) for human follow-up.
                </p>
                {selectedRun.exceptions?.length === 0 ? (
                  <p className="text-muted py-4 text-center">Zero exceptions generated in this run. Full reconciliation achieved.</p>
                ) : (
                  <table className="erp-table">
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Source Reference</th>
                        <th>Description</th>
                        <th>Assigned Role</th>
                        <th>Priority</th>
                        <th>Status</th>
                        <th>Resolution</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedRun.exceptions?.map((exc) => (
                        <tr key={exc.id}>
                          <td><span className="badge badge-warning">{exc.exception_type}</span></td>
                          <td><strong>{exc.source_reference}</strong></td>
                          <td>{exc.description}</td>
                          <td>{exc.assigned_role}</td>
                          <td><span className="badge badge-secondary">{exc.priority}</span></td>
                          <td>
                            <span className={`badge ${exc.status === 'RESOLVED' ? 'badge-success' : 'badge-danger'}`}>
                              {exc.status}
                            </span>
                          </td>
                          <td>
                            {exc.resolved_by ? (
                              <span>{exc.resolved_by}: {exc.resolution_comments}</span>
                            ) : '-'}
                          </td>
                          <td>
                            {exc.status === 'OPEN' && ['Management', 'Admin', 'Foundry'].includes(currentRole) && (
                              <button 
                                className="erp-btn btn-sm btn-outline"
                                onClick={() => setSelectedExceptionId(exc.id)}
                              >
                                <UserCheck size={12} className="btn-icon" /> Resolve
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Trigger Reconciliation Modal */}
      {showRunModal && (
        <div className="modal-backdrop" onClick={() => setShowRunModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <Play size={18} className="text-primary" />
                <h3>Trigger Issue-to-Heat Reconciliation</h3>
              </div>
              <button className="close-btn" onClick={() => setShowRunModal(false)}><X size={18} /></button>
            </div>
            <form onSubmit={handleTriggerRun}>
              <div className="modal-body">
                <p className="text-muted mb-4">
                  Runs the deterministic 3-pass reconciliation algorithm against approved Stores issue slips and furnace heat charge logs.
                </p>
                <div className="form-group mb-3">
                  <label><Calendar size={14} className="inline-icon" /> Date From (Optional)</label>
                  <input 
                    type="date" 
                    value={dateFrom} 
                    onChange={(e) => setDateFrom(e.target.value)} 
                  />
                  <small className="form-help">Leave empty to evaluate all historical records from baseline (12 Oct 2026).</small>
                </div>
                <div className="form-group mb-3">
                  <label><Calendar size={14} className="inline-icon" /> Date To (Optional)</label>
                  <input 
                    type="date" 
                    value={dateTo} 
                    onChange={(e) => setDateTo(e.target.value)} 
                  />
                </div>
                <div className="form-group mb-3">
                  <label>Run Notes / Reason</label>
                  <input 
                    type="text" 
                    placeholder="e.g. End of shift melt deck audit" 
                    value={runNotes} 
                    onChange={(e) => setRunNotes(e.target.value)} 
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="erp-btn btn-secondary" onClick={() => setShowRunModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="erp-btn btn-primary" disabled={triggering}>
                  {triggering ? 'Executing Algorithm...' : 'Start Reconciliation Run'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Resolve Exception Modal */}
      {selectedExceptionId && (
        <div className="modal-backdrop" onClick={() => setSelectedExceptionId(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <UserCheck size={18} className="text-primary" />
                <h3>Resolve Reconciliation Exception</h3>
              </div>
              <button className="close-btn" onClick={() => setSelectedExceptionId(null)}><X size={18} /></button>
            </div>
            <form onSubmit={handleResolveException}>
              <div className="modal-body">
                <div className="form-group mb-3">
                  <label>Resolution Action *</label>
                  <select 
                    value={exceptionAction} 
                    onChange={(e) => setExceptionAction(e.target.value as any)}
                  >
                    <option value="RESOLVE">RESOLVE (Floor adjustment investigated)</option>
                    <option value="ACCEPT_LOSS">ACCEPT_LOSS (Melting / Spillage loss confirmed)</option>
                  </select>
                </div>
                <div className="form-group mb-3">
                  <label>Justification Comments *</label>
                  <textarea 
                    rows={3} 
                    placeholder="Enter metallurgical / stores investigation finding..."
                    value={exceptionComment} 
                    onChange={(e) => setExceptionComment(e.target.value)} 
                    required 
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="erp-btn btn-secondary" onClick={() => setSelectedExceptionId(null)}>
                  Cancel
                </button>
                <button type="submit" className="erp-btn btn-primary">
                  Save Resolution
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
