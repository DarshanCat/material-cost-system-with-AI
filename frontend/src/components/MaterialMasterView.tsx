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
  X
} from 'lucide-react';
import type { MaterialItem, Department, PaginatedResponse, UserRole } from '../types';
import { apiFetch } from '../api/client';

interface MaterialMasterViewProps {
  currentRole: UserRole;
  onRequestNewItem: () => void;
}

export const MaterialMasterView: React.FC<MaterialMasterViewProps> = ({
  currentRole: _currentRole,
  onRequestNewItem,
}) => {
  const [items, setItems] = useState<MaterialItem[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
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

  // Load departments for filter dropdown
  useEffect(() => {
    apiFetch('/api/v1/departments')
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setDepartments(data))
      .catch(() => {});
  }, []);

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
        const data: PaginatedResponse<MaterialItem> = await res.json();
        setItems(data.items);
        setTotal(data.total);
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
            Code convention: <code>DEPT-CATEGORY-SERIAL</code> (e.g. <code>FDY-RM-016</code>).
          </p>
        </div>
        <div>
          <button className="primary-btn" onClick={onRequestNewItem}>
            <PlusCircle size={16} />
            <span>Request New Material Item</span>
          </button>
        </div>
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
            <option value="RAW_MATERIAL">Raw Material (RM)</option>
            <option value="ALLOY">Ferro Alloy (FA)</option>
            <option value="CONSUMABLE">Consumable (CON)</option>
            <option value="RETURN">Return Scrap (RET)</option>
            <option value="BORING">Machine Boring (BOR)</option>
            <option value="GATING">Gatings / Runners (GAT)</option>
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
            <button className="secondary-btn mt-3" onClick={onRequestNewItem}>
              <PlusCircle size={15} />
              <span>Initiate First Item Creation Request</span>
            </button>
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
                  <tr key={item.id} onClick={() => setSelectedItem(item)} className="cursor-pointer">
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
                          setSelectedItem(item);
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
            </div>

            <div className="modal-footer">
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
