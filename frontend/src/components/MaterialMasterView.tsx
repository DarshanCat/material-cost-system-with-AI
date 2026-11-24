import React, { useState, useEffect, useCallback } from 'react';
import { 
  Package, 
  Search, 
  Filter, 
  PlusCircle, 
  ChevronLeft, 
  ChevronRight, 
  AlertCircle,
  Building2,
  Tag,
  Info,
  History,
  X
} from 'lucide-react';
import type { MaterialItem, Department, ItemHistory, UserRole } from '../types';
import { apiFetch, readApiError } from '../api/client';
import { hasPermission } from '../auth/permissions';

interface ItemCategoryOption {
  category: string;
  code: string;
  name: string;
  department_code?: string;
  cost_head?: string;
}

interface MaterialMasterViewProps {
  currentRole: UserRole;
  onRequestNewItem: () => void;
}

export const MaterialMasterView: React.FC<MaterialMasterViewProps> = ({
  currentRole,
  onRequestNewItem,
}) => {
  const [items, setItems] = useState<MaterialItem[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [categories, setCategories] = useState<ItemCategoryOption[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedDept, setSelectedDept] = useState<string>('');
  const [selectedCat, setSelectedCat] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [total, setTotal] = useState<number>(0);
  const pageSize = 15;

  // Selected item modal
  const [selectedItem, setSelectedItem] = useState<MaterialItem | null>(null);
  const [history, setHistory] = useState<ItemHistory | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [statusReason, setStatusReason] = useState<string>('');
  const [statusError, setStatusError] = useState<string | null>(null);
  const [statusSaving, setStatusSaving] = useState<boolean>(false);

  // Retire / reactivate is limited to roles with item:update; requesting new items requires item_request:create.
  const canChangeStatus = hasPermission(currentRole, 'item:update');
  const canRequestNewItem = hasPermission(currentRole, 'item_request:create');

  // Load departments and the Nomenclature Standard v1.0 categories for the filter dropdowns
  useEffect(() => {
    apiFetch('/api/v1/departments')
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setDepartments(data))
      .catch(() => {});
    apiFetch('/api/v1/items/categories')
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setCategories(data))
      .catch(() => {});
  }, []);

  const loadHistory = (itemId: number) => {
    setHistory(null);
    setHistoryError(null);
    apiFetch(`/api/v1/items/${itemId}/history`)
      .then(async (res) => {
        if (res.ok) setHistory(await res.json());
        else setHistoryError(await readApiError(res, 'Unable to load item history'));
      })
      .catch((err: Error) => setHistoryError(`Network error: ${err.message}`));
  };

  const openItem = (item: MaterialItem) => {
    setSelectedItem(item);
    setStatusReason('');
    setStatusError(null);
    loadHistory(item.id);
  };

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (searchQuery.trim()) params.append('q', searchQuery.trim());
      if (selectedDept) params.append('department_id', selectedDept);
      if (selectedCat) params.append('category', selectedCat);
      params.append('page', String(page));
      params.append('size', String(pageSize));

      const res = await apiFetch(`/api/v1/items?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        const itemsList = Array.isArray(data) ? data : (data?.items || []);
        setItems(itemsList);
        setTotal(typeof data?.total === 'number' ? data.total : itemsList.length);
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || 'Unable to load items from backend.');
        setItems([]);
        setTotal(0);
      }
    } catch (err: any) {
      setError(`Network error: ${err.message}. Ensure backend is running.`);
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, selectedDept, selectedCat, page]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  const handleStatusChange = async () => {
    if (!selectedItem) return;
    setStatusError(null);
    if (statusReason.trim().length < 5) {
      setStatusError('Give a reason (at least 5 characters); it is recorded permanently in the item history.');
      return;
    }
    setStatusSaving(true);
    try {
      const res = await apiFetch(`/api/v1/items/${selectedItem.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !selectedItem.is_active, change_reason: statusReason.trim() }),
      });
      if (res.ok) {
        const updated: MaterialItem = await res.json();
        setSelectedItem(updated);
        setStatusReason('');
        loadHistory(updated.id);
        fetchItems();
      } else {
        setStatusError(await readApiError(res, 'Status change failed'));
      }
    } catch (err: any) {
      setStatusError(`Network error: ${err.message}`);
    } finally {
      setStatusSaving(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="module-container">
      {/* View Header */}
      <div className="view-header-row">
        <div>
          <span className="phase-pill">Phase 2: Master Data</span>
          <h2 className="view-title">Material Item Master Catalog</h2>
          <p className="view-subtitle">
            Controlled inventory definitions across ~741 SG Iron foundry materials.
            New codes follow the Item Nomenclature Standard v1.0: <code>DEPT-CAT-###</code> (e.g. <code>MCS-CB-004</code>).
            Existing codes outside v1.0 are kept unchanged. Codes are permanent and never reused.
          </p>
        </div>
        {canRequestNewItem && (
          <div>
            <button className="primary-btn" onClick={onRequestNewItem}>
              <PlusCircle size={16} />
              <span>Request New Material Item</span>
            </button>
          </div>
        )}
      </div>

      {/* Filter Toolbar */}
      <div className="filter-toolbar card">
        <div className="search-box">
          <Search size={16} className="text-muted search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Search by code (e.g. FDY-RM) or name..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
          />
        </div>

        <div className="filter-group">
          <Filter size={16} className="text-muted filter-icon" />
          <select
            className="select-input"
            value={selectedDept}
            onChange={(e) => {
              setSelectedDept(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Departments</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.code})
              </option>
            ))}
          </select>

          <select
            className="select-input"
            value={selectedCat}
            onChange={(e) => {
              setSelectedCat(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Categories</option>
            {categories.map((c) => (
              <option key={c.code} value={c.category}>
                {c.name} ({c.code})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="error-banner card">
          <AlertCircle size={20} className="text-danger flex-shrink-0" />
          <div>
            <div className="error-title">Database / Telemetry Notification</div>
            <p className="error-body">{error}</p>
          </div>
        </div>
      )}

      {/* Data Table */}
      <div className="card table-card">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading material master catalog...</p>
          </div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <Package size={48} className="text-muted mb-2" />
            <h3 className="empty-title">No Material Items Found</h3>
            <p className="empty-desc">
              {searchQuery || selectedDept || selectedCat
                ? 'No items match the selected search filters.'
                : 'Zero synthetic data policy active: ~741 catalog items will be loaded via approved Item Requests or Phase 7 historical spreadsheet migration.'}
            </p>
            {canRequestNewItem && (
              <button className="secondary-btn mt-3" onClick={onRequestNewItem}>
                <PlusCircle size={15} />
                <span>Initiate First Item Creation Request</span>
              </button>
            )}
          </div>
        ) : (
          <>
            <table className="erp-table">
              <thead>
                <tr>
                  <th>Item Code</th>
                  <th>Item Name</th>
                  <th>Department</th>
                  <th>Category</th>
                  <th>Base UOM</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} onClick={() => openItem(item)} className="cursor-pointer">
                    <td>
                      <code className="item-code-badge">{item.item_code}</code>
                    </td>
                    <td className="font-semibold">{item.name}</td>
                    <td>{item.department_name || item.department_id}</td>
                    <td>
                      <span className="cat-tag">{item.category}</span>
                    </td>
                    <td>
                      <span className="uom-tag">{item.uom_code || 'UOM'}</span>
                    </td>
                    <td>
                      <span className={`status-tag ${item.is_active ? 'active-tag' : 'inactive-tag'}`}>
                        {item.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="text-muted text-xs">
                      {new Date(item.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      <button 
                        className="table-action-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          openItem(item);
                        }}
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination footer */}
            <div className="table-pagination-row">
              <span className="pagination-info">
                Showing <strong>{items.length}</strong> of <strong>{total}</strong> catalog items
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
                  Page {page} of {totalPages}
                </span>
                <button
                  className="page-btn"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Item Detail Modal */}
      {selectedItem && (
        <div className="modal-backdrop" onClick={() => setSelectedItem(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="phase-pill">Material Item Detail</span>
                <h3 className="modal-title">{selectedItem.name}</h3>
              </div>
              <button className="modal-close-btn" onClick={() => setSelectedItem(null)}>
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              <div className="modal-info-grid">
                <div className="info-item">
                  <span className="info-label">Standard Item Code</span>
                  <code className="info-code">{selectedItem.item_code}</code>
                </div>
                <div className="info-item">
                  <span className="info-label">Assigned Department</span>
                  <span className="info-val flex items-center gap-1">
                    <Building2 size={14} className="text-muted" />
                    {selectedItem.department_name || `Dept #${selectedItem.department_id}`}
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">Category / Subcategory</span>
                  <span className="info-val">
                    <Tag size={14} className="text-muted inline mr-1" />
                    {selectedItem.category} {selectedItem.subcategory ? `(${selectedItem.subcategory})` : ''}
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">Base Unit of Measurement</span>
                  <span className="info-val font-semibold">{selectedItem.uom_code || selectedItem.base_uom_id}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Status</span>
                  <span className={`status-tag ${selectedItem.is_active ? 'active-tag' : 'inactive-tag'}`}>
                    {selectedItem.is_active ? 'Active Master Item' : 'Inactive'}
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">Catalog Registration</span>
                  <span className="info-val text-xs text-muted">
                    {new Date(selectedItem.created_at).toLocaleString()}
                  </span>
                </div>
              </div>

              {selectedItem.description && (
                <div className="info-desc-box mt-3">
                  <div className="info-label mb-1">
                    <Info size={14} className="inline mr-1" /> Technical Description & Business Justification
                  </div>
                  <p className="text-sm text-muted">{selectedItem.description}</p>
                </div>
              )}

              {/* Permanent code registry and item history */}
              <div className="audit-timeline-container mt-3">
                <h4 className="card-title text-sm mb-2">
                  <History size={16} className="text-primary inline mr-1" />
                  Item Code History
                </h4>
                {historyError && <p className="text-xs text-danger">{historyError}</p>}
                {!history && !historyError && <p className="text-xs text-muted">Loading history…</p>}
                {history && !history.registry_installed && (
                  <p className="text-xs text-muted">Code registry not installed (migration 008 pending); no history recorded yet.</p>
                )}
                {history && history.registry_installed && (
                  <>
                    <p className="text-xs text-muted mb-2">
                      {history.registry
                        ? `Issued by the generator (standard v${history.registry.standard_version}) on ${new Date(history.registry.issued_at).toLocaleString()} by ${history.registry.issued_by}.`
                        : 'Existing code created before the generator; kept unchanged (grandfathered).'}
                    </p>
                    {(history.events || []).length === 0 ? (
                      <p className="text-xs text-muted">No changes recorded.</p>
                    ) : (
                      <div className="timeline-list">
                        {(history.events || []).map((ev) => (
                          <div key={ev.id} className="timeline-entry">
                            <div className="timeline-marker"></div>
                            <div className="timeline-content">
                              <div className="flex justify-between items-center">
                                <span className="font-semibold text-xs text-main">
                                  {ev.action}{ev.field_name ? ` (${ev.field_name})` : ''}
                                </span>
                                <span className="text-2xs text-muted">{new Date(ev.timestamp).toLocaleString()}</span>
                              </div>
                              <div className="text-2xs text-muted">
                                Actor: <strong>{ev.actor_id}</strong> [{ev.actor_role}]
                              </div>
                              {(ev.old_value || ev.new_value) && (
                                <div className="text-xs">
                                  {ev.old_value ? `${ev.old_value} → ` : ''}{ev.new_value}
                                </div>
                              )}
                              {ev.reason && <div className="text-xs text-slate-700 mt-1 italic">"{ev.reason}"</div>}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>

              {canChangeStatus && (
                <div className="form-group mt-3">
                  <label className="form-label">
                    {selectedItem.is_active ? 'Retire item (mark Inactive)' : 'Reactivate item'} — reason{' '}
                    <span className="text-danger">*</span>
                  </label>
                  <textarea
                    className="form-textarea"
                    rows={2}
                    placeholder={
                      selectedItem.is_active
                        ? 'Why is this item being retired? The code stays reserved and is never reused.'
                        : 'Why is this item being brought back into use?'
                    }
                    value={statusReason}
                    onChange={(e) => setStatusReason(e.target.value)}
                  />
                  {statusError && <span className="text-xs text-danger">{statusError}</span>}
                </div>
              )}
            </div>

            <div className="modal-footer">
              {canChangeStatus && (
                <button
                  className={selectedItem.is_active ? 'action-btn-danger' : 'primary-btn'}
                  onClick={handleStatusChange}
                  disabled={statusSaving}
                >
                  {statusSaving ? 'Saving…' : selectedItem.is_active ? 'Retire Item' : 'Reactivate Item'}
                </button>
              )}
              <button className="secondary-btn" onClick={() => setSelectedItem(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
