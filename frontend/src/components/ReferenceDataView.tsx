import React, { useState, useEffect } from 'react';
import { Building2, Ruler, ShieldCheck, AlertCircle, Plus, CheckCircle2, X } from 'lucide-react';
import type { Department, UOM, UserRole } from '../types';
import { apiFetch, readApiError } from '../api/client';
import { hasPermission } from '../auth/permissions';

interface ReferenceDataViewProps {
  currentRole?: UserRole | null;
}

export const ReferenceDataView: React.FC<ReferenceDataViewProps> = ({ currentRole }) => {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [uoms, setUoms] = useState<UOM[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState<string | null>(null);

  // Add Department Modal State
  const [showDeptModal, setShowDeptModal] = useState<boolean>(false);
  const [deptCode, setDeptCode] = useState<string>('');
  const [deptName, setDeptName] = useState<string>('');
  const [deptSubmitting, setDeptSubmitting] = useState<boolean>(false);
  const [deptError, setDeptError] = useState<string | null>(null);

  // Add UOM Modal State
  const [showUomModal, setShowUomModal] = useState<boolean>(false);
  const [uomCode, setUomCode] = useState<string>('');
  const [uomName, setUomName] = useState<string>('');
  const [uomPrecision, setUomPrecision] = useState<number>(0);
  const [uomSubmitting, setUomSubmitting] = useState<boolean>(false);
  const [uomError, setUomError] = useState<string | null>(null);

  const canManageDepartments = hasPermission(currentRole, 'department:manage');
  const canManageUoms = hasPermission(currentRole, 'uom:manage');

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [deptRes, uomRes] = await Promise.all([
        apiFetch('/api/v1/departments'),
        apiFetch('/api/v1/uoms'),
      ]);
      if (deptRes.ok) {
        const d = await deptRes.json();
        setDepartments(Array.isArray(d) ? d : []);
      }
      if (uomRes.ok) {
        const u = await uomRes.json();
        setUoms(Array.isArray(u) ? u : []);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load reference data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateDepartment = async (e: React.FormEvent) => {
    e.preventDefault();
    setDeptError(null);
    const cleanCode = deptCode.trim().toUpperCase();
    const cleanName = deptName.trim();

    if (!cleanCode || !cleanName) {
      setDeptError('Department code and name are required.');
      return;
    }

    setDeptSubmitting(true);
    try {
      const res = await apiFetch('/api/v1/departments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: cleanCode, name: cleanName }),
      });

      if (!res.ok) {
        const errDetail = await readApiError(res, 'Failed to create department');
        setDeptError(errDetail);
        return;
      }

      const created = await res.json();
      setDepartments((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
      setShowDeptModal(false);
      setDeptCode('');
      setDeptName('');
      setSuccessToast(`Department '${created.name}' (${created.code}) created successfully.`);
      setTimeout(() => setSuccessToast(null), 4000);
    } catch (err: any) {
      setDeptError(err?.message || 'Network error while creating department');
    } finally {
      setDeptSubmitting(false);
    }
  };

  const handleCreateUOM = async (e: React.FormEvent) => {
    e.preventDefault();
    setUomError(null);
    const cleanCode = uomCode.trim().toUpperCase();
    const cleanName = uomName.trim();

    if (!cleanCode || !cleanName) {
      setUomError('UOM code and unit name are required.');
      return;
    }

    setUomSubmitting(true);
    try {
      const res = await apiFetch('/api/v1/uoms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: cleanCode,
          name: cleanName,
          decimal_precision: Number(uomPrecision),
        }),
      });

      if (!res.ok) {
        const errDetail = await readApiError(res, 'Failed to create UOM');
        setUomError(errDetail);
        return;
      }

      const created = await res.json();
      setUoms((prev) => [...prev, created].sort((a, b) => a.code.localeCompare(b.code)));
      setShowUomModal(false);
      setUomCode('');
      setUomName('');
      setUomPrecision(0);
      setSuccessToast(`UOM '${created.code}' (${created.name}) created successfully.`);
      setTimeout(() => setSuccessToast(null), 4000);
    } catch (err: any) {
      setUomError(err?.message || 'Network error while creating UOM');
    } finally {
      setUomSubmitting(false);
    }
  };

  return (
    <div className="module-container">
      <div className="view-header-row">
        <div>
          <span className="phase-pill">Phase 2: Reference Architecture</span>
          <h2 className="view-title">Departments & Measurement Units (UOM) Foundation</h2>
          <p className="view-subtitle">
            Controlled organizational hierarchy and precision rules governing all inventory, procurement, and heat logs.
          </p>
        </div>
      </div>

      {successToast && (
        <div className="success-banner card mb-3" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: '#ecfdf5', border: '1px solid #a7f3d0', color: '#065f46', borderRadius: '8px' }}>
          <CheckCircle2 size={18} className="text-success flex-shrink-0" />
          <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{successToast}</span>
        </div>
      )}

      {error && (
        <div className="error-banner card mb-3">
          <AlertCircle size={20} className="text-danger flex-shrink-0" />
          <span>Error loading reference data: {error}</span>
        </div>
      )}

      {/* Precision Notice Banner */}
      <div className="audit-policy-card mb-4">
        <div className="policy-icon-col">
          <ShieldCheck size={28} className="text-primary" />
        </div>
        <div className="policy-content">
          <h4 className="policy-title">Non-Negotiable Quantity Precision Standard</h4>
          <p className="policy-text">
            VSPL strictly enforces <strong>Decimal/Numeric</strong> precision. IEEE 754 binary floating-point 
            (FLOAT/DOUBLE) is prohibited in database schemas and costing services to eliminate mathematical drift. 
            Decimal entries (e.g., 5014 kg vs 5.014 kg) are validated against defined UOM limits without automatic truncation.
          </p>
        </div>
      </div>

      <div className="grid-2-col">
        {/* Departments Master */}
        <div className="card table-card">
          <div className="card-header-row mb-3" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h3 className="card-title" style={{ margin: 0 }}>
                <Building2 size={18} className="text-primary inline-icon" />
                Plant Department Master ({departments.length} Units)
              </h3>
              <span className="scope-tag">{departments.length} Active</span>
            </div>
            {canManageDepartments && (
              <button
                type="button"
                className="erp-btn btn-sm btn-primary"
                onClick={() => {
                  setDeptError(null);
                  setShowDeptModal(true);
                }}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '6px 12px', fontSize: '0.78rem' }}
              >
                <Plus size={14} /> Add Department
              </button>
            )}
          </div>

          {loading ? (
            <div className="loading-state"><div className="spinner"></div></div>
          ) : (
            <table className="erp-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Department Name</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {departments.map((d) => (
                  <tr key={d.id}>
                    <td><code className="item-code-badge">{d.code}</code></td>
                    <td className="font-semibold">{d.name}</td>
                    <td><span className="status-tag active-tag">Active</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* UOM Master */}
        <div className="card table-card">
          <div className="card-header-row mb-3" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h3 className="card-title" style={{ margin: 0 }}>
                <Ruler size={18} className="text-primary inline-icon" />
                Controlled Units of Measurement (UOM)
              </h3>
              <span className="scope-tag">{uoms.length} Controlled</span>
            </div>
            {canManageUoms && (
              <button
                type="button"
                className="erp-btn btn-sm btn-primary"
                onClick={() => {
                  setUomError(null);
                  setShowUomModal(true);
                }}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '6px 12px', fontSize: '0.78rem' }}
              >
                <Plus size={14} /> Add UOM
              </button>
            )}
          </div>

          {loading ? (
            <div className="loading-state"><div className="spinner"></div></div>
          ) : (
            <table className="erp-table">
              <thead>
                <tr>
                  <th>UOM Code</th>
                  <th>Unit Name</th>
                  <th>Decimal Precision</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {uoms.map((u) => (
                  <tr key={u.id}>
                    <td><code className="uom-tag">{u.code}</code></td>
                    <td className="font-semibold">{u.name}</td>
                    <td>
                      <span className="font-mono font-bold text-xs bg-slate-100 px-2 py-0.5 rounded">
                        {u.decimal_precision} {u.decimal_precision === 1 ? 'decimal' : 'decimals'}
                      </span>
                    </td>
                    <td><span className="status-tag active-tag">Active</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Modal: Add Department */}
      {showDeptModal && (
        <div className="modal-backdrop" onClick={() => setShowDeptModal(false)}>
          <div
            className="modal-card"
            style={{ maxWidth: '480px', width: '95vw' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div className="modal-title-group">
                <h3 className="modal-title">Register Plant Department</h3>
                <p>Add a new operational department to the organizational hierarchy</p>
              </div>
              <button
                type="button"
                className="close-btn"
                onClick={() => setShowDeptModal(false)}
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleCreateDepartment}>
              <div className="modal-body">
                {deptError && (
                  <div className="form-error-box mb-3" style={{ marginBottom: '1rem' }}>
                    <AlertCircle size={16} className="flex-shrink-0" />
                    <span>{deptError}</span>
                  </div>
                )}
                <div className="form-group mb-3" style={{ marginBottom: '1rem' }}>
                  <label className="form-label required">Department Code</label>
                  <input
                    type="text"
                    className="form-input"
                    value={deptCode}
                    onChange={(e) => setDeptCode(e.target.value.toUpperCase())}
                    placeholder="e.g. PAT, LAB, PND"
                    maxLength={10}
                    required
                  />
                  <span className="form-hint">Standard 2-4 letter uppercase abbreviation (e.g. FDY, MCS, STR)</span>
                </div>
                <div className="form-group mb-3">
                  <label className="form-label required">Department Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={deptName}
                    onChange={(e) => setDeptName(e.target.value)}
                    placeholder="e.g. Pattern Shop, Metallurgical Lab"
                    required
                  />
                  <span className="form-hint">Official plant unit designation for requisitions and issues</span>
                </div>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="erp-btn btn-secondary"
                  onClick={() => setShowDeptModal(false)}
                  disabled={deptSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="erp-btn btn-primary"
                  disabled={deptSubmitting}
                >
                  {deptSubmitting ? 'Creating...' : 'Create Department'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Add UOM */}
      {showUomModal && (
        <div className="modal-backdrop" onClick={() => setShowUomModal(false)}>
          <div
            className="modal-card"
            style={{ maxWidth: '480px', width: '95vw' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div className="modal-title-group">
                <h3 className="modal-title">Register Unit of Measurement (UOM)</h3>
                <p>Define a controlled measurement unit with precision rules</p>
              </div>
              <button
                type="button"
                className="close-btn"
                onClick={() => setShowUomModal(false)}
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleCreateUOM}>
              <div className="modal-body">
                {uomError && (
                  <div className="form-error-box mb-3" style={{ marginBottom: '1rem' }}>
                    <AlertCircle size={16} className="flex-shrink-0" />
                    <span>{uomError}</span>
                  </div>
                )}
                <div className="form-group mb-3" style={{ marginBottom: '1rem' }}>
                  <label className="form-label required">UOM Code</label>
                  <input
                    type="text"
                    className="form-input"
                    value={uomCode}
                    onChange={(e) => setUomCode(e.target.value.toUpperCase())}
                    placeholder="e.g. PCS, DRUM, M3, SET"
                    maxLength={10}
                    required
                  />
                  <span className="form-hint">Standard uppercase abbreviation (e.g. KG, MT, LTR, NOS, BAG)</span>
                </div>
                <div className="form-group mb-3" style={{ marginBottom: '1rem' }}>
                  <label className="form-label required">Unit Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={uomName}
                    onChange={(e) => setUomName(e.target.value)}
                    placeholder="e.g. Pieces, 200L Drums, Cubic Meters"
                    required
                  />
                </div>
                <div className="form-group mb-3">
                  <label className="form-label required">Decimal Precision</label>
                  <select
                    className="form-input"
                    value={uomPrecision}
                    onChange={(e) => setUomPrecision(Number(e.target.value))}
                    required
                  >
                    <option value={0}>0 Decimals (Whole integers only: NOS, PCS, BAG, BOX)</option>
                    <option value={1}>1 Decimal (0.1: e.g. MTR, FT)</option>
                    <option value={2}>2 Decimals (0.01: e.g. MTR, SQM, LTR)</option>
                    <option value={3}>3 Decimals (0.001: e.g. LTR, KG precision)</option>
                    <option value={4}>4 Decimals (0.0001: e.g. MT, KG, high precision alloys)</option>
                  </select>
                  <span className="form-hint">Non-negotiable accounting precision for weight and quantity calculations</span>
                </div>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="erp-btn btn-secondary"
                  onClick={() => setShowUomModal(false)}
                  disabled={uomSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="erp-btn btn-primary"
                  disabled={uomSubmitting}
                >
                  {uomSubmitting ? 'Creating...' : 'Create UOM'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
