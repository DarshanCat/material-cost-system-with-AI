import React, { useState, useEffect, useCallback } from 'react';
import { 
  Building, 
  Search, 
  PlusCircle, 
  ChevronLeft, 
  ChevronRight, 
  AlertCircle,
  CheckCircle,
  X,
  Phone,
  Mail,
  MapPin,
  UserCheck
} from 'lucide-react';
import type { Vendor, PaginatedResponse, UserRole } from '../types';
import { apiFetch } from '../api/client';

interface VendorMasterViewProps {
  currentRole: UserRole;
}

export const VendorMasterView: React.FC<VendorMasterViewProps> = ({ currentRole }) => {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Search & Pagination
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [total, setTotal] = useState<number>(0);
  const pageSize = 15;

  // Modals
  const [selectedVendor, setSelectedVendor] = useState<Vendor | null>(null);
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);

  // Create Form State
  const [formName, setFormName] = useState<string>('');
  const [formGstin, setFormGstin] = useState<string>('');
  const [formContact, setFormContact] = useState<string>('');
  const [formPhone, setFormPhone] = useState<string>('');
  const [formEmail, setFormEmail] = useState<string>('');
  const [formAddress, setFormAddress] = useState<string>('');
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [createSuccessMsg, setCreateSuccessMsg] = useState<string | null>(null);

  const fetchVendors = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (searchQuery.trim()) params.append('q', searchQuery.trim());
      params.append('page', String(page));
      params.append('size', String(pageSize));

      const res = await apiFetch(`/api/v1/vendors?${params.toString()}`);
      if (res.ok) {
        const data: PaginatedResponse<Vendor> = await res.json();
        setVendors(data.items);
        setTotal(data.total);
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || 'Unable to retrieve vendors.');
        setVendors([]);
        setTotal(0);
      }
    } catch (err: any) {
      setError(`Network error: ${err.message}. Ensure backend is running.`);
      setVendors([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, page]);

  useEffect(() => {
    fetchVendors();
  }, [fetchVendors]);

  // GSTIN Live Syntax Validation (15 alphanumeric characters)
  const isGstinValid = (val: string) => {
    if (!val.trim()) return true; // Optional per rules
    const pattern = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
    return pattern.test(val.trim().toUpperCase());
  };

  const handleCreateVendor = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!formName.trim() || formName.trim().length < 2) {
      setFormError('Legal vendor name must be at least 2 characters long.');
      return;
    }

    if (formGstin.trim() && !isGstinValid(formGstin)) {
      setFormError('Invalid GSTIN format: Must be standard 15-character Indian GSTIN (e.g., 29AABCU9603R1Z2).');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        name: formName.trim(),
        gstin: formGstin.trim() ? formGstin.trim().toUpperCase() : null,
        contact_person: formContact.trim() || null,
        phone: formPhone.trim() || null,
        email: formEmail.trim() || null,
        address: formAddress.trim() || null,
      };

      const res = await apiFetch('/api/v1/vendors', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const createdVendor = await res.json();
        setShowCreateModal(false);
        setFormName('');
        setFormGstin('');
        setFormContact('');
        setFormPhone('');
        setFormEmail('');
        setFormAddress('');
        setCreateSuccessMsg(`Vendor '${createdVendor.name}' registered successfully.`);
        fetchVendors();
        setTimeout(() => setCreateSuccessMsg(null), 4000);
      } else {
        const errData = await res.json().catch(() => ({}));
        setFormError(errData.detail || 'Failed to create vendor record.');
      }
    } catch (err: any) {
      setFormError(`Network error: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;
  const canManageVendors = currentRole === 'Purchase' || currentRole === 'Admin';

  return (
    <div className="module-container">
      {/* Header */}
      <div className="view-header-row">
        <div>
          <span className="phase-pill">Phase 2: Master Data</span>
          <h2 className="view-title">Vendor Master Management</h2>
          <p className="view-subtitle">
            Controlled vendor directory for raw materials, alloys, consumables, and transport contractors.
            Duplicate normalized key detection active.
          </p>
        </div>
        <div>
          {canManageVendors ? (
            <button className="primary-btn" onClick={() => setShowCreateModal(true)}>
              <PlusCircle size={16} />
              <span>Register New Vendor</span>
            </button>
          ) : (
            <div className="text-xs text-muted font-medium bg-gray-100 p-2 rounded">
              Vendor creation requires Purchase or Admin role
            </div>
          )}
        </div>
      </div>

      {createSuccessMsg && (
        <div className="success-banner card">
          <CheckCircle size={18} className="text-success" />
          <span>{createSuccessMsg}</span>
        </div>
      )}

      {/* Toolbar */}
      <div className="filter-toolbar card">
        <div className="search-box">
          <Search size={16} className="text-muted search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Search by vendor name, contact person, or GSTIN..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
          />
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="error-banner card">
          <AlertCircle size={20} className="text-danger flex-shrink-0" />
          <div>
            <div className="error-title">Database / Telemetry Notification</div>
            <p className="error-body">{error}</p>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="card table-card">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading vendor master catalog...</p>
          </div>
        ) : vendors.length === 0 ? (
          <div className="empty-state">
            <Building size={48} className="text-muted mb-2" />
            <h3 className="empty-title">No Vendors Found</h3>
            <p className="empty-desc">
              {searchQuery
                ? 'No vendors match your search query.'
                : 'Zero synthetic data policy active: No fictitious vendors are pre-populated. Register authentic supplier records above.'}
            </p>
            {canManageVendors && (
              <button className="secondary-btn mt-3" onClick={() => setShowCreateModal(true)}>
                <PlusCircle size={15} />
                <span>Register Initial Supplier</span>
              </button>
            )}
          </div>
        ) : (
          <>
            <table className="erp-table">
              <thead>
                <tr>
                  <th>Vendor Name</th>
                  <th>Normalized Search Key</th>
                  <th>GSTIN</th>
                  <th>Contact Person</th>
                  <th>Phone / Email</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {vendors.map((v) => (
                  <tr key={v.id} onClick={() => setSelectedVendor(v)} className="cursor-pointer">
                    <td className="font-semibold text-main">{v.name}</td>
                    <td>
                      <code className="text-xs bg-slate-100 px-1 py-0.5 rounded text-slate-700">
                        {v.normalized_name}
                      </code>
                    </td>
                    <td>
                      {v.gstin ? (
                        <span className="font-mono text-xs font-semibold">{v.gstin}</span>
                      ) : (
                        <span className="text-muted text-xs italic">Not Provided</span>
                      )}
                    </td>
                    <td>{v.contact_person || <span className="text-muted text-xs italic">—</span>}</td>
                    <td className="text-xs">
                      {v.phone && <div>{v.phone}</div>}
                      {v.email && <div className="text-muted">{v.email}</div>}
                      {!v.phone && !v.email && <span className="text-muted italic">—</span>}
                    </td>
                    <td>
                      <span className={`status-tag ${v.is_active ? 'active-tag' : 'inactive-tag'}`}>
                        {v.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <button 
                        className="table-action-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedVendor(v);
                        }}
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            <div className="table-pagination-row">
              <span className="pagination-info">
                Showing <strong>{vendors.length}</strong> of <strong>{total}</strong> vendors
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

      {/* Create Vendor Modal */}
      {showCreateModal && (
        <div className="modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="phase-pill">Supplier Registration</span>
                <h3 className="modal-title">Register New Vendor</h3>
              </div>
              <button className="modal-close-btn" onClick={() => setShowCreateModal(false)}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateVendor}>
              <div className="modal-body">
                {formError && (
                  <div className="form-error-box mb-3">
                    <AlertCircle size={16} className="text-danger flex-shrink-0" />
                    <span>{formError}</span>
                  </div>
                )}

                <div className="form-group mb-3">
                  <label className="form-label">
                    Legal Vendor Name <span className="text-danger">*</span>
                  </label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Tata Steel Limited"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    required
                  />
                  <span className="form-hint">
                    Original legal name is preserved for GST/accounting auditing.
                  </span>
                </div>

                <div className="form-group mb-3">
                  <label className="form-label">
                    GSTIN (Goods and Services Tax ID)
                  </label>
                  <input
                    type="text"
                    className="form-input uppercase font-mono"
                    placeholder="e.g. 27AAACT2727Q1ZW (Optional)"
                    value={formGstin}
                    onChange={(e) => setFormGstin(e.target.value)}
                    maxLength={15}
                  />
                  <span className="form-hint">
                    15-character standard Indian GSTIN syntax validated upon submission.
                  </span>
                </div>

                <div className="grid-2-col mb-3">
                  <div className="form-group">
                    <label className="form-label">Contact Person</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. Mr. Rajesh Sharma"
                      value={formContact}
                      onChange={(e) => setFormContact(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Phone Number</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. +91 9876543210"
                      value={formPhone}
                      onChange={(e) => setFormPhone(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-group mb-3">
                  <label className="form-label">Email Address</label>
                  <input
                    type="email"
                    className="form-input"
                    placeholder="e.g. orders@supplier.com"
                    value={formEmail}
                    onChange={(e) => setFormEmail(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Registered Office / Yard Address</label>
                  <textarea
                    className="form-textarea"
                    rows={2}
                    placeholder="Factory, warehouse, or registered office address..."
                    value={formAddress}
                    onChange={(e) => setFormAddress(e.target.value)}
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="secondary-btn"
                  onClick={() => setShowCreateModal(false)}
                  disabled={submitting}
                >
                  Cancel
                </button>
                <button type="submit" className="primary-btn" disabled={submitting}>
                  {submitting ? 'Registering Vendor...' : 'Save Vendor Master Record'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Vendor Detail Modal */}
      {selectedVendor && (
        <div className="modal-backdrop" onClick={() => setSelectedVendor(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="phase-pill">Vendor Details</span>
                <h3 className="modal-title">{selectedVendor.name}</h3>
              </div>
              <button className="modal-close-btn" onClick={() => setSelectedVendor(null)}>
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              <div className="modal-info-grid">
                <div className="info-item">
                  <span className="info-label">Normalized Search Key</span>
                  <code className="info-code">{selectedVendor.normalized_name}</code>
                </div>
                <div className="info-item">
                  <span className="info-label">GSTIN</span>
                  <span className="info-val font-mono font-bold">
                    {selectedVendor.gstin || 'None Provided'}
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">Contact Person</span>
                  <span className="info-val flex items-center gap-1">
                    <UserCheck size={14} className="text-muted" />
                    {selectedVendor.contact_person || 'N/A'}
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">Phone & Email</span>
                  <span className="info-val text-xs">
                    {selectedVendor.phone && <div className="flex items-center gap-1"><Phone size={12} /> {selectedVendor.phone}</div>}
                    {selectedVendor.email && <div className="flex items-center gap-1 text-muted"><Mail size={12} /> {selectedVendor.email}</div>}
                    {!selectedVendor.phone && !selectedVendor.email && 'N/A'}
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">Status</span>
                  <span className={`status-tag ${selectedVendor.is_active ? 'active-tag' : 'inactive-tag'}`}>
                    {selectedVendor.is_active ? 'Active Vendor' : 'Inactive'}
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">Registered On</span>
                  <span className="info-val text-xs text-muted">
                    {new Date(selectedVendor.created_at).toLocaleString()}
                  </span>
                </div>
              </div>

              {selectedVendor.address && (
                <div className="info-desc-box mt-3">
                  <div className="info-label mb-1">
                    <MapPin size={14} className="inline mr-1" /> Office / Yard Address
                  </div>
                  <p className="text-sm text-muted">{selectedVendor.address}</p>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button className="secondary-btn" onClick={() => setSelectedVendor(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
