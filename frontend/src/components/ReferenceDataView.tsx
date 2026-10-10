import React, { useState, useEffect } from 'react';
import { Building2, Ruler, ShieldCheck, AlertCircle } from 'lucide-react';
import type { Department, UOM } from '../types';

export const ReferenceDataView: React.FC = () => {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [uoms, setUoms] = useState<UOM[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch('/api/v1/departments').then((r) => r.json()),
      fetch('/api/v1/uoms').then((r) => r.json()),
    ])
      .then(([deptData, uomData]) => {
        setDepartments(Array.isArray(deptData) ? deptData : []);
        setUoms(Array.isArray(uomData) ? uomData : []);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="module-container">
      <div className="view-header-row">
        <div>
          <span className="phase-pill">Phase 2: Reference Architecture</span>
          <h2 className="view-title">Departments & Measurement Units (UOM) Foundation</h2>
          <p className="view-subtitle">
            Controlled organizational hierarchy and precision rules governing all inventory and heat logs.
          </p>
        </div>
      </div>

      {error && (
        <div className="error-banner card">
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
          <div className="card-header-row mb-3">
            <h3 className="card-title">
              <Building2 size={18} className="text-primary inline-icon" />
              Plant Department Master (8 Units)
            </h3>
            <span className="scope-tag">{departments.length} Active</span>
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
          <div className="card-header-row mb-3">
            <h3 className="card-title">
              <Ruler size={18} className="text-primary inline-icon" />
              Controlled Units of Measurement (UOM)
            </h3>
            <span className="scope-tag">{uoms.length} Controlled</span>
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
    </div>
  );
};
