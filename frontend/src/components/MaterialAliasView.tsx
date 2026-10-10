import React, { useState, useEffect } from 'react';
import { 
  Search, 
  Plus, 
  RefreshCw, 
  CheckCircle, 
  XCircle, 
  AlertTriangle, 
  X,
  Link
} from 'lucide-react';
import type { MaterialAlias, MaterialItem, UserRole } from '../types';

interface MaterialAliasViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const MaterialAliasView: React.FC<MaterialAliasViewProps> = ({ currentRole }) => {
  const [aliases, setAliases] = useState<MaterialAlias[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [items, setItems] = useState<MaterialItem[]>([]);
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [showRejectModal, setShowRejectModal] = useState<boolean>(false);
  const [selectedAlias, setSelectedAlias] = useState<MaterialAlias | null>(null);
  const [rejectionComments, setRejectionComments] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Form State
  const [aliasText, setAliasText] = useState<string>('');
  const [targetItemId, setTargetItemId] = useState<number | ''>('');

  const fetchAliases = async () => {
    setLoading(true);
    try {
      let url = '/api/v1/material-aliases?limit=100';
      if (statusFilter !== 'ALL') url += `&status_filter=${statusFilter}`;
      if (searchTerm) url += `&search=${encodeURIComponent(searchTerm)}`;
      const res = await fetch(url);
      if (res.ok) {
        setAliases(await res.json());
      }
    } catch {
      // fallback
    } finally {
      setLoading(false);
    }
  };

  const fetchItems = async () => {
    try {
      const res = await fetch('/api/v1/items?limit=500');
      if (res.ok) setItems(await res.json());
    } catch {
      // fallback
    }
  };

  useEffect(() => {
    fetchAliases();
    fetchItems();
  }, [statusFilter]);

  const handleCreateAlias = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetItemId) return;
    setSubmitting(true);
    setFeedback(null);

    try {
      const res = await fetch('/api/v1/material-aliases', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': currentRole,
        },
        body: JSON.stringify({
          alias_text: aliasText.trim(),
          material_item_id: Number(targetItemId),
          status: 'APPROVED',
        }),
      });

      if (res.ok) {
        setFeedback({ type: 'success', message: `Alias '${aliasText}' mapped successfully.` });
        setShowCreateModal(false);
        setAliasText('');
        setTargetItemId('');
        fetchAliases();
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Failed to create alias mapping.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error mapping alias.' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleApprove = async (aliasId: number) => {
    try {
      const res = await fetch(`/api/v1/material-aliases/${aliasId}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': currentRole,
        },
        body: JSON.stringify({ decision_notes: 'Approved by supervisor' }),
      });
      if (res.ok) {
        setFeedback({ type: 'success', message: 'Alias approved successfully.' });
        fetchAliases();
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Approval failed.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error during approval.' });
    }
  };

  const handleReject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAlias || !rejectionComments.trim()) return;
    setSubmitting(true);

    try {
      const res = await fetch(`/api/v1/material-aliases/${selectedAlias.id}/reject`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': currentRole,
        },
        body: JSON.stringify({ decision_notes: rejectionComments.trim() }),
      });
      if (res.ok) {
        setFeedback({ type: 'success', message: 'Alias rejected.' });
        setShowRejectModal(false);
        setSelectedAlias(null);
        setRejectionComments('');
        fetchAliases();
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Rejection failed.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error during rejection.' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivate = async (aliasId: number) => {
    if (!window.confirm('Deactivate this alias mapping?')) return;
    try {
      const res = await fetch(`/api/v1/material-aliases/${aliasId}/deactivate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': currentRole,
        },
      });
      if (res.ok) {
        setFeedback({ type: 'success', message: 'Alias deactivated.' });
        fetchAliases();
      }
    } catch {
      // fallback
    }
  };

  return (
    <div className="erp-module">
      <div className="module-header">
        <div>
          <h2 className="module-title">Material Description Alias Master</h2>
          <p className="module-subtitle">
            Controls dictionary mappings between raw heat-log descriptions and official item codes without modifying source files.
          </p>
        </div>
        <div className="header-actions">
          {['Stores', 'Foundry', 'Management', 'Admin'].includes(currentRole) && (
            <button className="erp-btn btn-primary" onClick={() => setShowCreateModal(true)}>
              <Plus size={16} className="btn-icon" /> Map New Alias
            </button>
          )}
          <button className="erp-btn btn-secondary" onClick={fetchAliases}>
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

      {/* Filter Toolbar */}
      <div className="filter-toolbar">
        <div className="search-box">
          <Search size={16} className="search-icon" />
          <input 
            type="text" 
            placeholder="Search by alias text or normalized key..." 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <span className="filter-label">Status:</span>
          {['ALL', 'APPROVED', 'PENDING', 'REJECTED'].map((st) => (
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

      {/* Alias Table */}
      <div className="erp-table-container">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Raw Alias Text</th>
              <th>Normalized Lookup Key</th>
              <th>Target Material Master</th>
              <th>Active</th>
              <th>Approval Status</th>
              <th>Created By</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="text-center py-4">Loading alias dictionary...</td></tr>
            ) : aliases.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-4 text-muted">No material aliases registered.</td></tr>
            ) : (
              aliases.map((a) => {
                const targetItem = items.find(i => i.id === a.material_item_id);
                return (
                  <tr key={a.id}>
                    <td><strong>{a.alias_text}</strong></td>
                    <td><code className="code-badge">{a.normalized_alias_key}</code></td>
                    <td>
                      {targetItem ? (
                        <span><Link size={12} className="inline-icon" /> <strong>{targetItem.item_code}</strong> - {targetItem.name}</span>
                      ) : (
                        `Item ID #${a.material_item_id}`
                      )}
                    </td>
                    <td>
                      <span className={`badge ${a.is_active ? 'badge-success' : 'badge-secondary'}`}>
                        {a.is_active ? 'ACTIVE' : 'INACTIVE'}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${
                        a.status === 'APPROVED' ? 'badge-success' : a.status === 'PENDING' ? 'badge-warning' : 'badge-danger'
                      }`}>
                        {a.status}
                      </span>
                    </td>
                    <td>{a.created_by}</td>
                    <td>
                      <div className="action-button-group">
                        {a.status === 'PENDING' && ['Management', 'Admin'].includes(currentRole) && (
                          <>
                            <button className="erp-btn btn-sm btn-success" onClick={() => handleApprove(a.id)}>
                              Approve
                            </button>
                            <button 
                              className="erp-btn btn-sm btn-danger" 
                              onClick={() => { setSelectedAlias(a); setShowRejectModal(true); }}
                            >
                              Reject
                            </button>
                          </>
                        )}
                        {a.is_active && (
                          <button className="erp-btn btn-sm btn-secondary" onClick={() => handleDeactivate(a.id)}>
                            Deactivate
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

      {/* Map New Alias Modal */}
      {showCreateModal && (
        <div className="modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <Link size={18} className="text-primary" />
                <h3>Map Material Description Alias</h3>
              </div>
              <button className="close-btn" onClick={() => setShowCreateModal(false)}><X size={18} /></button>
            </div>
            <form onSubmit={handleCreateAlias}>
              <div className="modal-body">
                <div className="form-group mb-3">
                  <label>Raw Source Description *</label>
                  <input 
                    type="text" 
                    placeholder="e.g. CRC Scrap-Low High MN, Pig Iron Gr A..." 
                    value={aliasText} 
                    onChange={(e) => setAliasText(e.target.value)} 
                    required 
                  />
                  <small className="form-help">Exact spelling or description as found in induction furnace heat logs.</small>
                </div>
                <div className="form-group mb-3">
                  <label>Official Material Master Item *</label>
                  <select 
                    value={targetItemId} 
                    onChange={(e) => setTargetItemId(Number(e.target.value))} 
                    required
                  >
                    <option value="">-- Select Material Master --</option>
                    {items.map(it => (
                      <option key={it.id} value={it.id}>{it.item_code} - {it.name} ({it.category})</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="erp-btn btn-secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="erp-btn btn-primary" disabled={submitting}>
                  {submitting ? 'Mapping...' : 'Save Alias Mapping'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reject Alias Modal */}
      {showRejectModal && selectedAlias && (
        <div className="modal-backdrop" onClick={() => setShowRejectModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <XCircle size={18} className="text-danger" />
                <h3>Reject Alias Mapping</h3>
              </div>
              <button className="close-btn" onClick={() => setShowRejectModal(false)}><X size={18} /></button>
            </div>
            <form onSubmit={handleReject}>
              <div className="modal-body">
                <p>Rejecting alias: <strong>{selectedAlias.alias_text}</strong></p>
                <div className="form-group">
                  <label>Justification Reason *</label>
                  <textarea 
                    rows={3} 
                    placeholder="Provide reason for rejecting this alias mapping..." 
                    value={rejectionComments} 
                    onChange={(e) => setRejectionComments(e.target.value)} 
                    required 
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="erp-btn btn-secondary" onClick={() => setShowRejectModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="erp-btn btn-danger" disabled={submitting}>
                  {submitting ? 'Rejecting...' : 'Confirm Rejection'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
