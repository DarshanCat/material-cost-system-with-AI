import React, { useState, useEffect } from 'react';
import {
  RotateCcw,
  Plus,
  CheckCircle,
  AlertTriangle,
  Search,
  RefreshCw,
  X,
  Check,
  XCircle,
  Trash2,
} from 'lucide-react';
import type {
  MaterialReturn,
  ReturnCondition,
  UserRole,
} from '../types';
import { apiFetch, readApiError } from '../api/client';
import { useReferenceData } from '../hooks/useReferenceData';
import { ReferenceDataNotice } from './ReferenceDataNotice';

interface ReturnToStoreViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

const CONDITION_METADATA: Record<
  ReturnCondition,
  { label: string; badgeClass: string; description: string; icon: string }
> = {
  UNUSED_GOOD: {
    label: 'Unused / Prime Material',
    badgeClass: 'badge-success',
    description: 'Virgin raw material or alloy returned unused in clean original condition.',
    icon: '✨',
  },
  MACHINE_SHOP_BORINGS: {
    label: 'Machine Shop Borings',
    badgeClass: 'badge-primary',
    description: 'Clean SG iron or steel turnings/chips collected from machining operations.',
    icon: '⚙️',
  },
  FOUNDRY_RETURNS: {
    label: 'Foundry Returns (Runners/Risers)',
    badgeClass: 'badge-warning',
    description: 'Internal scrap: gating systems, runners, risers, and poured metal returns.',
    icon: '🔥',
  },
  REJECTED_CASTINGS: {
    label: 'Rejected Castings (Foundry Scrap)',
    badgeClass: 'badge-danger',
    description: 'Castings rejected in visual inspection or testing suitable for re-melting.',
    icon: '🚫',
  },
  DAMAGED_CONTAMINATED: {
    label: 'Damaged / Contaminated',
    badgeClass: 'badge-secondary',
    description: 'Material degraded, contaminated with sand, oil, or rust. Requires inspection.',
    icon: '⚠️',
  },
};

export const ReturnToStoreView: React.FC<ReturnToStoreViewProps> = ({
  currentRole,
  currentUserId: _currentUserId,
}) => {
  const isStoresOrAdmin = currentRole === 'Stores' || currentRole === 'Management' || currentRole === 'Admin';
  const canCreateReturn = true; // Any shop floor role can return material to store

  const [returns, setReturns] = useState<MaterialReturn[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedReturn, setSelectedReturn] = useState<MaterialReturn | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [conditionFilter, setConditionFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [successToast, setSuccessToast] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Active heats for reference
  const [activeHeats, setActiveHeats] = useState<any[]>([]);

  const refs = useReferenceData(['items', 'departments', 'uoms']);
  const { items, departments, uoms } = refs;

  // New RTS Modal State
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [returningDeptId, setReturningDeptId] = useState<number>(1); // Foundry default
  const [returnDate, setReturnDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [condition, setCondition] = useState<ReturnCondition>('UNUSED_GOOD');
  const [heatReference, setHeatReference] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [lines, setLines] = useState<Array<{
    material_item_id: number | '';
    uom_id: number | '';
    quantity: string;
    condition: ReturnCondition;
    remarks: string;
  }>>([
    {
      material_item_id: '',
      uom_id: '',
      quantity: '',
      condition: 'UNUSED_GOOD',
      remarks: '',
    },
  ]);
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Rejection modal
  const [showRejectModal, setShowRejectModal] = useState<boolean>(false);
  const [rejectionComments, setRejectionComments] = useState<string>('');
  const [processingAction, setProcessingAction] = useState<boolean>(false);

  const fetchReturns = async () => {
    setLoading(true);
    try {
      let url = '/api/v1/material-returns/';
      const params: string[] = [];
      if (statusFilter && statusFilter !== 'ALL') {
        params.push(`status_filter=${encodeURIComponent(statusFilter)}`);
      }
      if (conditionFilter && conditionFilter !== 'ALL') {
        params.push(`condition_filter=${encodeURIComponent(conditionFilter)}`);
      }
      if (params.length > 0) {
        url += `?${params.join('&')}`;
      }
      const res = await apiFetch(url);
      if (res.ok) {
        const data = await res.json();
        setReturns(Array.isArray(data) ? data : []);
      }
    } catch {
      // offline / mock fallback
    } finally {
      setLoading(false);
    }
  };

  const fetchActiveHeats = async () => {
    try {
      const res = await apiFetch('/api/v1/heats/active');
      if (res.ok) {
        const data = await res.json();
        setActiveHeats(Array.isArray(data) ? data : []);
      }
    } catch {
      // fallback
    }
  };

  useEffect(() => {
    fetchReturns();
    fetchActiveHeats();
  }, [statusFilter, conditionFilter]);

  const handleAddLine = () => {
    setLines((prev) => [
      ...prev,
      {
        material_item_id: '',
        uom_id: '',
        quantity: '',
        condition: condition,
        remarks: '',
      },
    ]);
  };

  const handleRemoveLine = (idx: number) => {
    if (lines.length > 1) {
      setLines((prev) => prev.filter((_, i) => i !== idx));
    }
  };

  const handleItemSelect = (index: number, itemId: number) => {
    const item = items.find((i) => i.id === itemId);
    setLines((prev) =>
      prev.map((l, i) => {
        if (i === index) {
          return {
            ...l,
            material_item_id: itemId,
            uom_id: item?.base_uom_id || l.uom_id,
          };
        }
        return l;
      })
    );
  };

  const handleCreateRTS = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);

    const validLines = lines.filter(
      (l) => l.material_item_id !== '' && Number(l.quantity) > 0
    );
    if (validLines.length === 0) {
      setActionError('Please specify at least one valid material line with quantity > 0.');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        returning_department_id: Number(returningDeptId),
        return_date: returnDate,
        heat_reference_number: heatReference.trim() || null,
        condition: condition,
        notes: notes.trim() || null,
        lines: validLines.map((l) => ({
          material_item_id: Number(l.material_item_id),
          uom_id: l.uom_id ? Number(l.uom_id) : undefined,
          quantity: Number(l.quantity),
          condition: l.condition || condition,
          remarks: l.remarks || undefined,
        })),
      };

      const res = await apiFetch('/api/v1/material-returns/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const msg = await readApiError(res, 'Failed to create Return to Store voucher');
        throw new Error(msg);
      }

      const created = await res.json();
      setSuccessToast(`Return to Store voucher #${created.return_number} submitted successfully!`);
      setShowCreateModal(false);
      setNotes('');
      setHeatReference('');
      setLines([
        {
          material_item_id: '',
          uom_id: '',
          quantity: '',
          condition: 'UNUSED_GOOD',
          remarks: '',
        },
      ]);
      await fetchReturns();
    } catch (err: any) {
      setActionError(err.message || 'Error submitting Return to Store voucher');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAcceptReturn = async (returnId: number) => {
    setActionError(null);
    setProcessingAction(true);
    try {
      const res = await apiFetch(`/api/v1/material-returns/${returnId}/accept`, {
        method: 'POST',
      });

      if (!res.ok) {
        const msg = await readApiError(res, 'Failed to accept Return to Store voucher');
        throw new Error(msg);
      }

      setSuccessToast(`Material return accepted by Stores. Stock ledger updated with positive inward balance!`);
      if (selectedReturn?.id === returnId) {
        const updated = await res.json();
        setSelectedReturn(updated);
      }
      await fetchReturns();
    } catch (err: any) {
      setActionError(err.message || 'Error accepting Return to Store voucher');
    } finally {
      setProcessingAction(false);
    }
  };

  const handleRejectReturn = async () => {
    if (!selectedReturn) return;
    setActionError(null);
    setProcessingAction(true);
    try {
      const res = await apiFetch(`/api/v1/material-returns/${selectedReturn.id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: rejectionComments || 'Rejected by Stores Operator during physical inspection' }),
      });

      if (!res.ok) {
        const msg = await readApiError(res, 'Failed to reject Return to Store voucher');
        throw new Error(msg);
      }

      setSuccessToast(`Return voucher #${selectedReturn.return_number} rejected.`);
      setShowRejectModal(false);
      setRejectionComments('');
      const updated = await res.json();
      setSelectedReturn(updated);
      await fetchReturns();
    } catch (err: any) {
      setActionError(err.message || 'Error rejecting Return to Store voucher');
    } finally {
      setProcessingAction(false);
    }
  };

  // Filtered returns
  const filteredReturns = returns.filter((r) => {
    const term = searchTerm.toLowerCase();
    const num = (r.return_number || '').toLowerCase();
    const dept = (r.returning_department_name || '').toLowerCase();
    const heat = (r.heat_reference_number || '').toLowerCase();
    const n = (r.notes || '').toLowerCase();
    return num.includes(term) || dept.includes(term) || heat.includes(term) || n.includes(term);
  });

  const pendingCount = returns.filter((r) => r.status === 'SUBMITTED').length;
  const acceptedCount = returns.filter((r) => r.status === 'ACCEPTED').length;

  return (
    <div className="erp-view">
      <div className="view-header">
        <div>
          <h2 className="module-title">Return to Store (RTS)</h2>
          <p className="module-subtitle">
            Controlled physical material returns from shop floor (Foundry, Machine Shop) back to Stores inventory with mandatory condition grading.
          </p>
        </div>
        <div className="header-actions">
          {canCreateReturn && (
            <button
              className="erp-btn btn-primary"
              onClick={() => setShowCreateModal(true)}
            >
              <Plus size={16} className="btn-icon" /> + New Return to Store
            </button>
          )}
          <button className="erp-btn btn-secondary" onClick={fetchReturns}>
            <RefreshCw size={14} className="btn-icon" /> Refresh
          </button>
        </div>
      </div>

      {successToast && (
        <div className="notification-banner banner-success">
          <CheckCircle size={16} />
          <span>{successToast}</span>
          <button className="close-banner" onClick={() => setSuccessToast(null)}>
            <X size={14} />
          </button>
        </div>
      )}

      {actionError && (
        <div className="notification-banner banner-error">
          <AlertTriangle size={16} />
          <span>{actionError}</span>
          <button className="close-banner" onClick={() => setActionError(null)}>
            <X size={14} />
          </button>
        </div>
      )}

      <ReferenceDataNotice refs={refs} />

      {/* KPI Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total RTS Vouchers</div>
          <div className="stat-value">{returns.length}</div>
          <div className="stat-subtext">All returns logged</div>
        </div>
        <div className="stat-card" style={{ borderLeft: '4px solid #f59e0b' }}>
          <div className="stat-label">Pending Stores Receipt</div>
          <div className="stat-value" style={{ color: '#d97706' }}>
            {pendingCount}
          </div>
          <div className="stat-subtext">Awaiting physical verification</div>
        </div>
        <div className="stat-card" style={{ borderLeft: '4px solid #10b981' }}>
          <div className="stat-label">Accepted into Stock</div>
          <div className="stat-value" style={{ color: '#059669' }}>
            {acceptedCount}
          </div>
          <div className="stat-subtext">Positively added to stock ledger</div>
        </div>
        <div className="stat-card" style={{ borderLeft: '4px solid #3b82f6' }}>
          <div className="stat-label">Active Foundry Heats</div>
          <div className="stat-value" style={{ color: '#2563eb' }}>
            {activeHeats.length}
          </div>
          <div className="stat-subtext">Eligible for return reference</div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="filter-toolbar" style={{ flexWrap: 'wrap', gap: '8px' }}>
        <div className="search-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search RTS #, department, heat number, notes..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <span className="filter-label">Status:</span>
          {['ALL', 'SUBMITTED', 'ACCEPTED', 'REJECTED'].map((st) => (
            <button
              key={st}
              className={`filter-chip ${statusFilter === st ? 'active' : ''}`}
              onClick={() => setStatusFilter(st)}
            >
              {st === 'ALL'
                ? 'All'
                : st === 'SUBMITTED'
                ? 'Pending Acceptance'
                : st === 'ACCEPTED'
                ? 'Accepted'
                : 'Rejected'}
            </button>
          ))}
        </div>

        <div className="filter-group">
          <span className="filter-label">Condition:</span>
          {['ALL', 'UNUSED_GOOD', 'MACHINE_SHOP_BORINGS', 'FOUNDRY_RETURNS', 'REJECTED_CASTINGS', 'DAMAGED_CONTAMINATED'].map((c) => (
            <button
              key={c}
              className={`filter-chip ${conditionFilter === c ? 'active' : ''}`}
              onClick={() => setConditionFilter(c)}
            >
              {c === 'ALL' ? 'All Conditions' : CONDITION_METADATA[c as ReturnCondition]?.label || c}
            </button>
          ))}
        </div>
      </div>

      {/* Returns Table */}
      <div className="erp-table-container">
        <table className="erp-table">
          <thead>
            <tr>
              <th>RTS Voucher #</th>
              <th>Return Date</th>
              <th>From Dept</th>
              <th>Condition Grade</th>
              <th>Heat Ref</th>
              <th>Materials Count</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className="text-center py-4">
                  Loading Return to Store vouchers...
                </td>
              </tr>
            ) : filteredReturns.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-center py-4 text-muted">
                  No Return to Store vouchers found.
                </td>
              </tr>
            ) : (
              filteredReturns.map((r) => {
                const condMeta = CONDITION_METADATA[r.condition] || {
                  label: r.condition,
                  badgeClass: 'badge-secondary',
                  icon: '📦',
                };
                return (
                  <tr key={r.id}>
                    <td>
                      <div>
                        <strong>{r.return_number}</strong>
                      </div>
                      <small className="text-muted">By {r.created_by}</small>
                    </td>
                    <td>{r.return_date}</td>
                    <td>
                      <span className="badge badge-secondary">
                        {r.returning_department_name || `Dept #${r.returning_department_id}`}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${condMeta.badgeClass}`} style={{ fontWeight: 600 }}>
                        {condMeta.icon} {condMeta.label}
                      </span>
                    </td>
                    <td>
                      {r.heat_reference_number ? (
                        <code className="code-badge">{r.heat_reference_number}</code>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td>
                      <strong>{r.lines?.length || 0}</strong> line(s)
                      {r.lines && r.lines[0] && (
                        <div style={{ fontSize: '11px', color: '#64748b' }}>
                          {r.lines[0].item_name || r.lines[0].item_code}: {r.lines[0].quantity} {r.lines[0].uom_code || 'KG'}
                          {r.lines.length > 1 ? ` (+${r.lines.length - 1} more)` : ''}
                        </div>
                      )}
                    </td>
                    <td>
                      {r.status === 'SUBMITTED' ? (
                        <span className="badge badge-warning">Pending Stores Receipt</span>
                      ) : r.status === 'ACCEPTED' ? (
                        <span className="badge badge-success">Accepted into Stock</span>
                      ) : (
                        <span className="badge badge-danger">Rejected</span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button
                          className="erp-btn btn-sm btn-outline"
                          onClick={() => setSelectedReturn(r)}
                        >
                          View Dossier
                        </button>
                        {isStoresOrAdmin && r.status === 'SUBMITTED' && (
                          <button
                            className="erp-btn btn-sm btn-success"
                            onClick={() => handleAcceptReturn(r.id)}
                            disabled={processingAction}
                            title="Verify and Accept into Store inventory"
                          >
                            <Check size={12} className="btn-icon" /> Accept
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* New Return to Store Modal */}
      {showCreateModal && (
        <div className="modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div
            className="modal-content modal-large"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '850px' }}
          >
            <div className="modal-header">
              <div className="modal-title-group">
                <RotateCcw size={20} className="text-primary" />
                <h3>Log Return to Store (RTS) Voucher</h3>
              </div>
              <button
                className="close-btn"
                onClick={() => setShowCreateModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateRTS} className="modal-form">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label>Returning Department *</label>
                  <select
                    value={returningDeptId}
                    onChange={(e) => setReturningDeptId(Number(e.target.value))}
                    required
                  >
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name} ({d.code})
                      </option>
                    ))}
                  </select>
                  <small className="text-muted">Shop-floor department returning materials.</small>
                </div>

                <div className="form-group">
                  <label>Return Date *</label>
                  <input
                    type="date"
                    value={returnDate}
                    onChange={(e) => setReturnDate(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label>Condition Classification *</label>
                  <select
                    value={condition}
                    onChange={(e) => setCondition(e.target.value as ReturnCondition)}
                    required
                  >
                    <option value="UNUSED_GOOD">✨ Unused / Prime Material (Clean)</option>
                    <option value="MACHINE_SHOP_BORINGS">⚙️ Machine Shop Borings (Chips/Turnings)</option>
                    <option value="FOUNDRY_RETURNS">🔥 Foundry Returns (Runners/Risers)</option>
                    <option value="REJECTED_CASTINGS">🚫 Rejected Castings (Foundry Scrap)</option>
                    <option value="DAMAGED_CONTAMINATED">⚠️ Damaged / Contaminated Material</option>
                  </select>
                  <small className="text-muted">
                    {CONDITION_METADATA[condition]?.description}
                  </small>
                </div>

                <div className="form-group" style={{ background: '#fffbeb', padding: '10px 12px', borderRadius: '6px', border: '1px solid #fde68a' }}>
                  <label style={{ fontWeight: 700, color: '#78350f', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    🔥 Furnace Heat Reference (Credit Back to Heat)
                  </label>
                  {activeHeats.length > 0 ? (
                    <select
                      value={heatReference}
                      onChange={(e) => setHeatReference(e.target.value)}
                      style={{ marginTop: '4px', fontFamily: 'monospace', fontWeight: 600 }}
                    >
                      <option value="">-- None / General Department Return --</option>
                      {activeHeats.map((h) => (
                        <option key={h.id} value={h.normalized_heat_number || h.heat_number}>
                          🟢 {h.normalized_heat_number || h.heat_number} · (Furnace: {h.furnace_id || 'F1'})
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      placeholder="e.g. H-202611-0012"
                      value={heatReference}
                      onChange={(e) => setHeatReference(e.target.value)}
                      style={{ marginTop: '4px', fontFamily: 'monospace' }}
                    />
                  )}
                  <small style={{ color: '#92400e', fontSize: '11px', marginTop: '4px', display: 'block' }}>
                    Returned material will be accepted directly into store stock and deducted from this heat's net batch consumption & cost.
                  </small>
                </div>
              </div>

              <div className="form-group">
                <label>Operational Return Reason / Notes</label>
                <textarea
                  rows={2}
                  placeholder="Specify why materials are being returned (e.g., End of shift surplus, excess borings from CNC-04, cold runner scrap)..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>

              {/* Line items section */}
              <div style={{ marginTop: '16px', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>Material Line Items *</h4>
                <button
                  type="button"
                  className="erp-btn btn-sm btn-secondary"
                  onClick={handleAddLine}
                >
                  <Plus size={14} className="btn-icon" /> Add Material
                </button>
              </div>

              <div className="erp-table-container" style={{ maxHeight: '250px', overflowY: 'auto' }}>
                <table className="erp-table">
                  <thead>
                    <tr>
                      <th style={{ width: '40%' }}>Material Item</th>
                      <th style={{ width: '20%' }}>Quantity</th>
                      <th style={{ width: '15%' }}>UOM</th>
                      <th style={{ width: '20%' }}>Remarks</th>
                      <th style={{ width: '5%' }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map((l, idx) => {
                      return (
                        <tr key={idx}>
                          <td>
                            <select
                              value={l.material_item_id}
                              onChange={(e) => handleItemSelect(idx, Number(e.target.value))}
                              required
                              style={{ width: '100%' }}
                            >
                              <option value="">-- Select Material Item --</option>
                              {items.map((it) => (
                                <option key={it.id} value={it.id}>
                                  {it.item_code} - {it.name} ({it.category})
                                </option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <input
                              type="number"
                              step="0.01"
                              placeholder="Quantity"
                              value={l.quantity}
                              onChange={(e) => {
                                const val = e.target.value;
                                setLines((prev) =>
                                  prev.map((item, i) =>
                                    i === idx ? { ...item, quantity: val } : item
                                  )
                                );
                              }}
                              required
                              style={{ width: '100%' }}
                            />
                          </td>
                          <td>
                            <select
                              value={l.uom_id}
                              onChange={(e) => {
                                const val = e.target.value;
                                setLines((prev) =>
                                  prev.map((item, i) =>
                                    i === idx ? { ...item, uom_id: val ? Number(val) : '' } : item
                                  )
                                );
                              }}
                              style={{ width: '100%' }}
                            >
                              {uoms.map((u) => (
                                <option key={u.id} value={u.id}>
                                  {u.code}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <input
                              type="text"
                              placeholder="Notes / drum #"
                              value={l.remarks}
                              onChange={(e) => {
                                const val = e.target.value;
                                setLines((prev) =>
                                  prev.map((item, i) =>
                                    i === idx ? { ...item, remarks: val } : item
                                  )
                                );
                              }}
                              style={{ width: '100%' }}
                            />
                          </td>
                          <td>
                            {lines.length > 1 && (
                              <button
                                type="button"
                                className="erp-btn btn-xs btn-outline"
                                onClick={() => handleRemoveLine(idx)}
                                title="Remove row"
                              >
                                <Trash2 size={13} style={{ color: '#ef4444' }} />
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="modal-actions" style={{ marginTop: '20px' }}>
                <button
                  type="button"
                  className="erp-btn btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="erp-btn btn-primary"
                  disabled={submitting}
                >
                  {submitting ? 'Submitting...' : 'Submit Return Voucher to Stores'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Selected Return Dossier Modal */}
      {selectedReturn && (
        <div className="modal-backdrop" onClick={() => setSelectedReturn(null)}>
          <div
            className="modal-content modal-large"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '800px' }}
          >
            <div className="modal-header">
              <div className="modal-title-group">
                <RotateCcw size={20} className="text-primary" />
                <h3>Return to Store Voucher: {selectedReturn.return_number}</h3>
              </div>
              <button
                className="close-btn"
                onClick={() => setSelectedReturn(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', padding: '16px', background: '#f8fafc', borderRadius: '6px', marginBottom: '16px' }}>
              <div>
                <small className="text-muted" style={{ display: 'block' }}>Returning Dept</small>
                <strong>{selectedReturn.returning_department_name || `Dept #${selectedReturn.returning_department_id}`}</strong>
              </div>
              <div>
                <small className="text-muted" style={{ display: 'block' }}>Receiving Dept</small>
                <strong>Stores (Central Warehouse)</strong>
              </div>
              <div>
                <small className="text-muted" style={{ display: 'block' }}>Return Date</small>
                <strong>{selectedReturn.return_date}</strong>
              </div>
              <div>
                <small className="text-muted" style={{ display: 'block' }}>Current Status</small>
                {selectedReturn.status === 'SUBMITTED' ? (
                  <span className="badge badge-warning">Pending Stores Receipt</span>
                ) : selectedReturn.status === 'ACCEPTED' ? (
                  <span className="badge badge-success">Accepted into Stock</span>
                ) : (
                  <span className="badge badge-danger">Rejected</span>
                )}
              </div>
            </div>

            <div style={{ marginBottom: '16px', padding: '12px 16px', borderRadius: '6px', border: '1px solid #e2e8f0', background: '#ffffff' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <span style={{ fontSize: '18px' }}>{CONDITION_METADATA[selectedReturn.condition]?.icon}</span>
                <strong style={{ fontSize: '14px' }}>Condition: {CONDITION_METADATA[selectedReturn.condition]?.label || selectedReturn.condition}</strong>
              </div>
              <p style={{ margin: 0, fontSize: '13px', color: '#475569' }}>
                {CONDITION_METADATA[selectedReturn.condition]?.description}
              </p>
              {selectedReturn.heat_reference_number && (
                <div style={{ marginTop: '8px', fontSize: '13px' }}>
                  <span className="text-muted">Linked Heat Number:</span>{' '}
                  <code className="code-badge">{selectedReturn.heat_reference_number}</code>
                </div>
              )}
              {selectedReturn.notes && (
                <div style={{ marginTop: '8px', fontSize: '13px', color: '#334155' }}>
                  <strong>Notes / Remarks:</strong> {selectedReturn.notes}
                </div>
              )}
            </div>

            {selectedReturn.status === 'ACCEPTED' && (
              <div className="notification-banner banner-success" style={{ marginBottom: '16px' }}>
                <CheckCircle size={16} />
                <div>
                  <strong>Accepted into Store Inventory</strong>
                  <div style={{ fontSize: '12px' }}>
                    Accepted by <code>{selectedReturn.accepted_by}</code> on {selectedReturn.accepted_at}. Positive stock movement posted into stock ledger.
                  </div>
                </div>
              </div>
            )}

            {selectedReturn.status === 'REJECTED' && (
              <div className="notification-banner banner-error" style={{ marginBottom: '16px' }}>
                <XCircle size={16} />
                <div>
                  <strong>Return Rejected by Stores</strong>
                  <div style={{ fontSize: '12px' }}>
                    Reason: {selectedReturn.rejection_reason || 'Material failed physical receipt criteria.'}
                  </div>
                </div>
              </div>
            )}

            <h4 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '8px' }}>Returned Line Items</h4>
            <div className="erp-table-container">
              <table className="erp-table">
                <thead>
                  <tr>
                    <th>Item Code</th>
                    <th>Material Description</th>
                    <th className="text-right">Quantity</th>
                    <th>UOM</th>
                    <th>Condition</th>
                    <th>Remarks</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedReturn.lines.map((l) => (
                    <tr key={l.id || l.line_number}>
                      <td><strong>{l.item_code || `Item #${l.material_item_id}`}</strong></td>
                      <td>{l.item_name || 'Material Item'}</td>
                      <td className="text-right"><strong>{l.quantity}</strong></td>
                      <td>{l.uom_code || 'KG'}</td>
                      <td>
                        <span className={`badge ${CONDITION_METADATA[l.condition]?.badgeClass || 'badge-secondary'}`}>
                          {l.condition}
                        </span>
                      </td>
                      <td>{l.remarks || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Audit Logs */}
            {selectedReturn.audit_logs && selectedReturn.audit_logs.length > 0 && (
              <div style={{ marginTop: '16px' }}>
                <h4 style={{ fontSize: '13px', fontWeight: 600, color: '#64748b', marginBottom: '6px' }}>Audit Trail</h4>
                <div style={{ fontSize: '12px', background: '#f8fafc', padding: '10px', borderRadius: '6px' }}>
                  {selectedReturn.audit_logs.map((a) => (
                    <div key={a.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #f1f5f9' }}>
                      <span>
                        <strong>{a.action}</strong> by <code>{a.actor_id}</code>: {a.comments}
                      </span>
                      <span className="text-muted">{new Date(a.timestamp).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Modal Actions */}
            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <button
                type="button"
                className="erp-btn btn-secondary"
                onClick={() => setSelectedReturn(null)}
              >
                Close
              </button>

              {isStoresOrAdmin && selectedReturn.status === 'SUBMITTED' && (
                <>
                  <button
                    type="button"
                    className="erp-btn btn-danger"
                    onClick={() => setShowRejectModal(true)}
                    disabled={processingAction}
                  >
                    <XCircle size={14} className="btn-icon" /> Reject Return
                  </button>
                  <button
                    type="button"
                    className="erp-btn btn-success"
                    onClick={() => handleAcceptReturn(selectedReturn.id)}
                    disabled={processingAction}
                  >
                    <Check size={14} className="btn-icon" /> Accept into Store Inventory
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="modal-backdrop" onClick={() => setShowRejectModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '480px' }}>
            <div className="modal-header">
              <div className="modal-title-group">
                <XCircle size={18} className="text-danger" />
                <h3>Reject Return Voucher</h3>
              </div>
              <button className="close-btn" onClick={() => setShowRejectModal(false)}>
                <X size={16} />
              </button>
            </div>
            <div className="modal-form">
              <p style={{ fontSize: '13px', color: '#64748b', margin: 0 }}>
                Please specify the reason for rejecting this material return (e.g. Unidentified alloy grade, excessive sand contamination, unapproved scrap stream).
              </p>
              <div className="form-group" style={{ marginTop: '12px' }}>
                <label>Rejection Reason *</label>
                <textarea
                  rows={3}
                  value={rejectionComments}
                  onChange={(e) => setRejectionComments(e.target.value)}
                  placeholder="Mandatory rejection notes..."
                  required
                />
              </div>
              <div className="modal-actions" style={{ marginTop: '16px' }}>
                <button
                  className="erp-btn btn-secondary"
                  onClick={() => setShowRejectModal(false)}
                >
                  Cancel
                </button>
                <button
                  className="erp-btn btn-danger"
                  onClick={handleRejectReturn}
                  disabled={processingAction || !rejectionComments.trim()}
                >
                  Confirm Rejection
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
