import React, { useState, useEffect } from 'react';
import { 
  Flame, 
  Search, 
  Plus, 
  RefreshCw, 
  Eye, 
  CheckCircle, 
  AlertTriangle, 
  X,
  Layers,
  Calendar
} from 'lucide-react';
import type { HeatHeader, UserRole } from '../types';
import { apiFetch } from '../api/client';
import { useReferenceData } from '../hooks/useReferenceData';
import { ReferenceDataNotice } from './ReferenceDataNotice';

interface HeatLogManagementViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const HeatLogManagementView: React.FC<HeatLogManagementViewProps> = ({ currentRole }) => {
  const [heats, setHeats] = useState<HeatHeader[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [dateFilter, setDateFilter] = useState<string>('');
  const [selectedHeat, setSelectedHeat] = useState<HeatHeader | null>(null);
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Master references
  const refs = useReferenceData(['items', 'uoms']);
  const { items, uoms } = refs;
  // Items only feed the description suggestions; UOMs are written into the heat payload.
  const uomsUnavailable = refs.loading || Boolean(refs.errors.uoms) || (uoms?.length ?? 0) === 0;

  // Form state
  const [heatNumber, setHeatNumber] = useState<string>('');
  const [heatDate, setHeatDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [furnaceId, setFurnaceId] = useState<string>('FURNACE-1');
  const [shift, setShift] = useState<string>('SHIFT_A');
  const [metalTappedWeight, setMetalTappedWeight] = useState<string>('');
  const [powerKwh, setPowerKwh] = useState<string>('');
  const [notes, setNotes] = useState<string>('');

  // Configurable Costing & Yield Policy Parameters
  const [showConfigPolicy, setShowConfigPolicy] = useState<boolean>(false);
  const [powerTariff, setPowerTariff] = useState<number>(8.50);
  const [consumableOverheadPerMt, setConsumableOverheadPerMt] = useState<number>(1200.00);
  const [warningMeltLossPct, setWarningMeltLossPct] = useState<number>(6.5);
  const [criticalMeltLossPct, setCriticalMeltLossPct] = useState<number>(8.0);

  // Charge lines builder
  const [chargeLines, setChargeLines] = useState<Array<{
    original_material_description: string;
    charged_quantity: string;
    uom_id: number | '';
    remarks: string;
  }>>([
    { original_material_description: '', charged_quantity: '', uom_id: '', remarks: '' }
  ]);

  // Stores Issue Linking State
  const [linkedIssues, setLinkedIssues] = useState<any[]>([]);
  const [loadingLinkedIssues, setLoadingLinkedIssues] = useState<boolean>(false);
  const [selectedHeatIssues, setSelectedHeatIssues] = useState<any[]>([]);
  const [loadingSelectedHeatIssues, setLoadingSelectedHeatIssues] = useState<boolean>(false);

  // Auto-query approved Stores Issues when Heat Number is typed in the modal
  useEffect(() => {
    const trimmed = heatNumber.trim();
    if (!trimmed || trimmed.length < 3) {
      setLinkedIssues([]);
      return;
    }
    const norm = trimmed.toUpperCase().startsWith('H-') ? trimmed.toUpperCase() : `H-${trimmed.toUpperCase()}`;
    const timer = setTimeout(async () => {
      setLoadingLinkedIssues(true);
      try {
        const res = await apiFetch(`/api/v1/issues?status=APPROVED&heat_reference_number=${encodeURIComponent(norm)}`);
        if (res.ok) {
          const data = await res.json();
          setLinkedIssues(Array.isArray(data) ? data : (data?.items || []));
        }
      } catch {
        setLinkedIssues([]);
      } finally {
        setLoadingLinkedIssues(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [heatNumber]);

  // Query linked Stores Issues when inspecting an existing heat
  useEffect(() => {
    if (!selectedHeat) {
      setSelectedHeatIssues([]);
      return;
    }
    const heatRef = selectedHeat.normalized_heat_number || selectedHeat.heat_number;
    if (!heatRef) return;
    setLoadingSelectedHeatIssues(true);
    apiFetch(`/api/v1/issues?status=APPROVED&heat_reference_number=${encodeURIComponent(heatRef)}`)
      .then(async (res) => {
        if (res.ok) {
          const data = await res.json();
          setSelectedHeatIssues(Array.isArray(data) ? data : (data?.items || []));
        }
      })
      .catch(() => setSelectedHeatIssues([]))
      .finally(() => setLoadingSelectedHeatIssues(false));
  }, [selectedHeat]);

  const handleImportFromIssue = (issue: any) => {
    if (!issue.lines || issue.lines.length === 0) return;
    const defaultUom = uoms.find(u => u.code === 'KG') || uoms[0];
    const newLines = issue.lines.map((l: any) => ({
      original_material_description: l.item_name || l.item_code || 'Furnace Raw Material',
      charged_quantity: String(Number(l.quantity) || ''),
      uom_id: l.uom_id || defaultUom?.id || '',
      remarks: `Imported from Stores Issue Slip #${issue.issue_slip_number}`,
    }));
    setChargeLines(newLines);
    setFeedback({
      type: 'success',
      message: `Imported ${newLines.length} materials from Stores Issue ${issue.issue_slip_number} directly into Crucible Charge lines!`,
    });
  };

  // Parts produced builder
  const [partsProduced, setPartsProduced] = useState<Array<{
    original_part_description: string;
    quantity_produced: string;
    unit_cast_weight: string;
    classification: string;
  }>>([
    { original_part_description: '', quantity_produced: '', unit_cast_weight: '', classification: 'GOOD' }
  ]);

  const fetchHeats = async () => {
    setLoading(true);
    try {
      let url = '/api/v1/heats?limit=100';
      if (dateFilter) url += `&date_from=${dateFilter}&date_to=${dateFilter}`;
      if (searchTerm) url += `&search=${encodeURIComponent(searchTerm)}`;
      const res = await apiFetch(url);
      if (res.ok) {
        const data = await res.json();
        setHeats(Array.isArray(data) ? data : (data?.items || []));
      }
    } catch {
      // fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHeats();
  }, []);

  const addChargeRow = () => {
    setChargeLines(prev => [
      ...prev,
      { original_material_description: '', charged_quantity: '', uom_id: uoms[0]?.id || '', remarks: '' }
    ]);
  };

  const removeChargeRow = (idx: number) => {
    if (chargeLines.length > 1) {
      setChargeLines(prev => prev.filter((_, i) => i !== idx));
    }
  };

  const addPartRow = () => {
    setPartsProduced(prev => [
      ...prev,
      { original_part_description: '', quantity_produced: '', unit_cast_weight: '', classification: 'GOOD' }
    ]);
  };

  const removePartRow = (idx: number) => {
    if (partsProduced.length > 1) {
      setPartsProduced(prev => prev.filter((_, i) => i !== idx));
    }
  };

  // Helper to compute metrics for a heat
  const computeHeatMetrics = (h: HeatHeader) => {
    const grossCharged = h.charge_lines?.reduce((sum, cl) => sum + (Number(cl.charged_quantity) || 0), 0) || 0;
    const tapped = Number(h.metal_tapped_weight) || 0;
    const meltLossKg = (grossCharged > 0 && tapped > 0) ? Math.max(0, grossCharged - tapped) : null;
    const meltLossPct = (grossCharged > 0 && meltLossKg !== null) ? (meltLossKg / grossCharged) * 100 : null;
    const yieldPct = meltLossPct !== null ? 100 - meltLossPct : null;
    
    // Status classification based on configurable policy
    let yieldStatus: 'NORMAL' | 'WARNING' | 'CRITICAL' = 'NORMAL';
    if (meltLossPct !== null) {
      if (meltLossPct > criticalMeltLossPct) yieldStatus = 'CRITICAL';
      else if (meltLossPct > warningMeltLossPct) yieldStatus = 'WARNING';
    }

    // Power & Consumable estimations
    // Standard induction furnace energy: 550 KWH / MT tapped if not recorded
    const estKwh = (tapped / 1000) * 550;
    const powerCost = estKwh * powerTariff;
    const overheadCost = (tapped / 1000) * consumableOverheadPerMt;
    
    // Estimated material cost using ₹42/kg average for metallic charge
    const estMaterialCost = grossCharged * 42.0;
    const totalEstCost = estMaterialCost + powerCost + overheadCost;
    const costPerKg = tapped > 0 ? (totalEstCost / tapped) : null;

    return {
      grossCharged,
      tapped,
      meltLossKg,
      meltLossPct,
      yieldPct,
      yieldStatus,
      powerCost,
      overheadCost,
      totalEstCost,
      costPerKg,
    };
  };

  const handleCreateHeat = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFeedback(null);

    const defaultUom = uoms.find(u => u.code === 'KG') || uoms[0];

    const payload = {
      heat_number: heatNumber.trim(),
      heat_date: heatDate,
      furnace_id: furnaceId,
      shift: shift,
      metal_tapped_weight: metalTappedWeight ? metalTappedWeight : null,
      metal_tapped_uom_id: metalTappedWeight ? defaultUom?.id : null,
      production_status: 'COMPLETED',
      notes: notes.trim() || null,
      charge_lines: chargeLines
        .filter(c => c.original_material_description.trim() && Number(c.charged_quantity) > 0)
        .map(c => ({
          original_material_description: c.original_material_description.trim(),
          charged_quantity: c.charged_quantity,
          uom_id: c.uom_id || defaultUom?.id,
          remarks: c.remarks.trim() || null,
        })),
      parts_produced: partsProduced
        .filter(p => p.original_part_description.trim() && Number(p.quantity_produced) > 0)
        .map(p => ({
          original_part_description: p.original_part_description.trim(),
          quantity_produced: p.quantity_produced,
          unit_cast_weight: p.unit_cast_weight ? p.unit_cast_weight : null,
          weight_uom_id: defaultUom?.id,
          classification: p.classification,
        }))
    };

    try {
      const res = await apiFetch('/api/v1/heats', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setFeedback({ type: 'success', message: `Heat ${heatNumber} recorded successfully.` });
        setShowCreateModal(false);
        setHeatNumber('');
        setMetalTappedWeight('');
        setNotes('');
        fetchHeats();
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Failed to record heat.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error communicating with heat service.' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="erp-module">
      <div className="module-header">
        <div>
          <h2 className="module-title">Induction Furnace Heat Log</h2>
          <p className="module-subtitle">
            Records furnace melting heats, charge detail mixes, and castings produced. Heat data never moves inventory.
          </p>
        </div>
        <div className="header-actions">
          <button 
            className={`erp-btn ${showConfigPolicy ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setShowConfigPolicy(!showConfigPolicy)}
          >
            ⚡ Cost & Yield Policy
          </button>
          {['Foundry', 'Management', 'Admin'].includes(currentRole) && (
            <button className="erp-btn btn-primary" onClick={() => setShowCreateModal(true)}>
              <Plus size={16} className="btn-icon" /> Log New Heat
            </button>
          )}
          <button className="erp-btn btn-secondary" onClick={fetchHeats}>
            <RefreshCw size={14} className="btn-icon" /> Refresh
          </button>
        </div>
      </div>

      {/* Configurable Costing & Yield Policy Panel */}
      {showConfigPolicy && (
        <div style={{
          background: '#ffffff',
          border: '1.5px solid #bfdbfe',
          borderRadius: '8px',
          padding: '16px 20px',
          marginBottom: '16px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.04)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h4 style={{ margin: 0, fontSize: '14px', color: '#1e3a8a', fontWeight: 700 }}>
              ⚡ Costing & Melt Loss Policy Parameters
            </h4>
            <span style={{ fontSize: '12px', color: '#64748b' }}>
              Used for live furnace heat valuation & yield tolerance checking
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 600, color: '#475569', display: 'block', marginBottom: '4px' }}>
                Electric Power Tariff (₹/KWH)
              </label>
              <input 
                type="number" 
                step="0.1" 
                value={powerTariff} 
                onChange={(e) => setPowerTariff(Number(e.target.value) || 0)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '13px' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 600, color: '#475569', display: 'block', marginBottom: '4px' }}>
                Consumables Overhead (₹/MT Tapped)
              </label>
              <input 
                type="number" 
                step="50" 
                value={consumableOverheadPerMt} 
                onChange={(e) => setConsumableOverheadPerMt(Number(e.target.value) || 0)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '13px' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 600, color: '#475569', display: 'block', marginBottom: '4px' }}>
                Melt Loss Warning Threshold (%)
              </label>
              <input 
                type="number" 
                step="0.1" 
                value={warningMeltLossPct} 
                onChange={(e) => setWarningMeltLossPct(Number(e.target.value) || 0)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '13px' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 600, color: '#475569', display: 'block', marginBottom: '4px' }}>
                Critical Hold Threshold (%)
              </label>
              <input 
                type="number" 
                step="0.1" 
                value={criticalMeltLossPct} 
                onChange={(e) => setCriticalMeltLossPct(Number(e.target.value) || 0)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '13px' }}
              />
            </div>
          </div>
        </div>
      )}

      {feedback && (
        <div className={`notification-banner ${feedback.type === 'success' ? 'banner-success' : 'banner-error'}`}>
          {feedback.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          <span>{feedback.message}</span>
        </div>
      )}

      <ReferenceDataNotice refs={refs} />

      {/* Filter Toolbar */}
      <div className="filter-toolbar">
        <div className="search-box">
          <Search size={16} className="search-icon" />
          <input 
            type="text" 
            placeholder="Search by Heat Number (e.g. 102603-3721), Furnace..." 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <span className="filter-label"><Calendar size={14} className="inline-icon" /> Date:</span>
          <input 
            type="date" 
            className="filter-date-input" 
            value={dateFilter} 
            onChange={(e) => setDateFilter(e.target.value)}
          />
          {dateFilter && (
            <button className="erp-btn btn-sm" onClick={() => setDateFilter('')}>Clear Date</button>
          )}
        </div>
      </div>

      {/* Heats Table */}
      <div className="erp-table-container">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Heat Number</th>
              <th>Date & Furnace</th>
              <th>Shift</th>
              <th>Charged Qty</th>
              <th>Metal Tapped</th>
              <th>Melt Loss / Yield</th>
              <th>Est. Direct Cost</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9} className="text-center py-4">Loading furnace heat logs...</td></tr>
            ) : heats.length === 0 ? (
              <tr><td colSpan={9} className="text-center py-4 text-muted">No furnace heats recorded for this criteria.</td></tr>
            ) : (
              heats.map((h) => {
                const m = computeHeatMetrics(h);
                return (
                  <tr key={h.id}>
                    <td>
                      <div><strong>{h.heat_number}</strong></div>
                      <div><code className="code-badge" style={{ fontSize: '10px' }}>{h.normalized_heat_number}</code></div>
                    </td>
                    <td>
                      <div>{h.heat_date}</div>
                      <small className="text-muted">{h.furnace_id || 'F-01'}</small>
                    </td>
                    <td><span className="badge badge-secondary">{h.shift || 'A'}</span></td>
                    <td className="text-right">
                      <strong>{m.grossCharged > 0 ? `${m.grossCharged.toLocaleString()} KG` : '—'}</strong>
                      <div><small className="text-muted">{h.charge_lines?.length || 0} items</small></div>
                    </td>
                    <td className="text-right">
                      <strong>{m.tapped > 0 ? `${m.tapped.toLocaleString()} KG` : '—'}</strong>
                    </td>
                    <td>
                      {m.meltLossPct !== null ? (
                        <div>
                          <span className={`badge ${
                            m.yieldStatus === 'CRITICAL' ? 'badge-danger' :
                            m.yieldStatus === 'WARNING' ? 'badge-warning' : 'badge-success'
                          }`} style={{ fontWeight: 700 }}>
                            {m.meltLossPct.toFixed(2)}% Loss ({m.yieldPct?.toFixed(1)}% Yield)
                          </span>
                          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                            {m.meltLossKg?.toFixed(1)} KG unrecovered
                          </div>
                        </div>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="text-right">
                      {m.costPerKg !== null ? (
                        <div>
                          <strong style={{ color: '#1e3a8a' }}>₹{m.costPerKg.toFixed(2)} / kg</strong>
                          <div style={{ fontSize: '10px', color: '#64748b' }}>
                            ₹{(m.totalEstCost).toLocaleString('en-IN', { maximumFractionDigits: 0 })} total
                          </div>
                        </div>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td>
                      <span className="badge badge-success">{h.production_status}</span>
                    </td>
                    <td>
                      <button 
                        className="erp-btn btn-sm btn-outline"
                        onClick={() => setSelectedHeat(h)}
                      >
                        <Eye size={12} className="btn-icon" /> Details
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Heat Details Drawer / Modal */}
      {selectedHeat && (
        <div className="modal-backdrop" onClick={() => setSelectedHeat(null)}>
          <div className="modal-card modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <Flame size={20} className="text-primary" />
                <h3>Heat Details: {selectedHeat.heat_number} ({selectedHeat.normalized_heat_number})</h3>
              </div>
              <button className="close-btn" onClick={() => setSelectedHeat(null)}><X size={18} /></button>
            </div>
            <div className="modal-body">
              <div className="metric-strip mb-4">
                <div className="metric-cell">
                  <div className="metric-label">Date</div>
                  <div className="metric-val">{selectedHeat.heat_date}</div>
                </div>
                <div className="metric-cell">
                  <div className="metric-label">Furnace & Shift</div>
                  <div className="metric-val">{selectedHeat.furnace_id || 'F-01'} / {selectedHeat.shift || 'A'}</div>
                </div>
                <div className="metric-cell">
                  <div className="metric-label">Metal Tapped</div>
                  <div className="metric-val">
                    {selectedHeat.metal_tapped_weight ? `${Number(selectedHeat.metal_tapped_weight).toLocaleString()} KG` : 'N/A'}
                  </div>
                </div>
                <div className="metric-cell">
                  <div className="metric-label">Created By</div>
                  <div className="metric-val">{selectedHeat.created_by}</div>
                </div>
              </div>

              {/* Melt Yield & Costing Breakdown Panel */}
              {(() => {
                const m = computeHeatMetrics(selectedHeat);
                return (
                  <div style={{
                    background: '#f8fafc',
                    border: '1.5px solid #e2e8f0',
                    borderRadius: '8px',
                    padding: '14px 18px',
                    marginBottom: '18px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                      <span style={{ fontSize: '13px', fontWeight: 700, color: '#1e3a8a' }}>
                        🔥 Melt Loss, Yield & Cost Breakdown (Policy Applied)
                      </span>
                      <span className={`badge ${
                        m.yieldStatus === 'CRITICAL' ? 'badge-danger' :
                        m.yieldStatus === 'WARNING' ? 'badge-warning' : 'badge-success'
                      }`} style={{ fontWeight: 700 }}>
                        {m.meltLossPct !== null ? `${m.meltLossPct.toFixed(2)}% Loss (${m.yieldPct?.toFixed(1)}% Yield)` : 'Pending Weighment'}
                      </span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px' }}>
                      <div style={{ background: '#fff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>Charged Weight</div>
                        <div style={{ fontSize: '14px', fontWeight: 700 }}>{m.grossCharged.toLocaleString()} KG</div>
                      </div>
                      <div style={{ background: '#fff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>Tapped Metal</div>
                        <div style={{ fontSize: '14px', fontWeight: 700 }}>{m.tapped > 0 ? `${m.tapped.toLocaleString()} KG` : '—'}</div>
                      </div>
                      <div style={{ background: '#fff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>Power Cost (@₹{powerTariff}/KWH)</div>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: '#d97706' }}>
                          ₹{m.powerCost.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </div>
                      </div>
                      <div style={{ background: '#fff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>Overhead (@₹{consumableOverheadPerMt}/MT)</div>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: '#475569' }}>
                          ₹{m.overheadCost.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </div>
                      </div>
                      <div style={{ background: '#ecfdf5', padding: '10px', borderRadius: '6px', border: '1.5px solid #a7f3d0' }}>
                        <div style={{ fontSize: '11px', color: '#065f46', fontWeight: 700 }}>Net Cost / Kg</div>
                        <div style={{ fontSize: '15px', fontWeight: 800, color: '#065f46' }}>
                          {m.costPerKg ? `₹${m.costPerKg.toFixed(2)} / kg` : '—'}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* Linked Stores Issues Section */}
              <div style={{
                background: '#f8fafc',
                border: '1px solid #cbd5e1',
                borderRadius: '8px',
                padding: '12px 16px',
                marginBottom: '18px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Layers size={16} className="text-steel" />
                    <strong style={{ fontSize: '13px', color: '#1e293b' }}>
                      Stores Material Issue Slips (Traceability Reflection)
                    </strong>
                  </div>
                  <span className="pill p-steel" style={{ fontSize: '11px' }}>
                    {selectedHeatIssues.length} Slip(s) Linked
                  </span>
                </div>

                {loadingSelectedHeatIssues ? (
                  <div style={{ fontSize: '12px', color: '#64748b' }}>Checking linked stores issues...</div>
                ) : selectedHeatIssues.length === 0 ? (
                  <div style={{ fontSize: '12px', color: '#64748b' }}>
                    No Stores Issue slips explicitly tagged with Heat Ref <code>{selectedHeat.normalized_heat_number || selectedHeat.heat_number}</code> yet.
                  </div>
                ) : (
                  <div>
                    {selectedHeatIssues.map((iss) => {
                      const totalIssuedKg = iss.lines?.reduce((s: number, l: any) => s + (Number(l.quantity) || 0), 0) || 0;
                      return (
                        <div key={iss.id} style={{ 
                          background: '#fff', 
                          border: '1px solid #e2e8f0', 
                          borderRadius: '6px', 
                          padding: '10px 12px',
                          marginBottom: '8px'
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                            <span style={{ fontSize: '13px', fontWeight: 600 }}>
                              {iss.issue_slip_number} · {iss.issue_date}
                            </span>
                            <span className="pill p-posted" style={{ fontSize: '11px' }}>
                              Issued: {totalIssuedKg.toLocaleString()} KG
                            </span>
                          </div>
                          <div style={{ fontSize: '12px', color: '#475569' }}>
                            {iss.lines?.map((l: any) => `${l.item_name}: ${Number(l.quantity).toLocaleString()} ${l.uom_code || 'KG'}`).join(' | ')}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <h4>Furnace Charge Mix Breakdown</h4>
              <table className="erp-table mb-4">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Material Description</th>
                    <th>Mapped Master Item</th>
                    <th>Charged Qty</th>
                    <th>Alias Status</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedHeat.charge_lines?.map((cl) => (
                    <tr key={cl.line_number}>
                      <td>{cl.line_number}</td>
                      <td><strong>{cl.original_material_description}</strong></td>
                      <td>{cl.material_item ? `${cl.material_item.item_code} - ${cl.material_item.name}` : <span className="text-muted">Unmapped Description</span>}</td>
                      <td>{Number(cl.charged_quantity).toLocaleString()}</td>
                      <td>
                        <span className={`badge ${cl.validation_status === 'VALID' ? 'badge-success' : 'badge-warning'}`}>
                          {cl.validation_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h4>Parts & Castings Produced</h4>
              <table className="erp-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Part Description</th>
                    <th>Quantity Cast</th>
                    <th>Unit Weight (kg)</th>
                    <th>Classification</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedHeat.parts_produced?.length === 0 ? (
                    <tr><td colSpan={5} className="text-center text-muted">No casting parts recorded for this heat.</td></tr>
                  ) : (
                    selectedHeat.parts_produced?.map((p) => (
                      <tr key={p.line_number}>
                        <td>{p.line_number}</td>
                        <td><strong>{p.original_part_description}</strong></td>
                        <td>{Number(p.quantity_produced).toLocaleString()}</td>
                        <td>{p.unit_cast_weight ? `${Number(p.unit_cast_weight)} kg` : '-'}</td>
                        <td><span className="badge badge-success">{p.classification}</span></td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="modal-footer">
              <button className="erp-btn btn-secondary" onClick={() => setSelectedHeat(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Log New Heat Modal */}
      {showCreateModal && (
        <div className="modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="modal-card modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <Flame size={20} className="text-primary" />
                <h3>Log Induction Furnace Heat</h3>
              </div>
              <button className="close-btn" onClick={() => setShowCreateModal(false)}><X size={18} /></button>
            </div>
            <form onSubmit={handleCreateHeat}>
              <div className="modal-body">
                <div className="mb-3">
                  <ReferenceDataNotice refs={refs} />
                </div>
                <div className="form-grid-3">
                  <div className="form-group">
                    <label>Heat Number *</label>
                    <input 
                      type="text" 
                      placeholder="e.g. 102603-3721 or H-102603-3721" 
                      value={heatNumber} 
                      onChange={(e) => setHeatNumber(e.target.value)} 
                      required 
                    />
                  </div>
                  <div className="form-group">
                    <label>Heat Date *</label>
                    <input 
                      type="date" 
                      value={heatDate} 
                      onChange={(e) => setHeatDate(e.target.value)} 
                      required 
                    />
                  </div>
                  <div className="form-group">
                    <label>Furnace ID</label>
                    <input 
                      type="text" 
                      value={furnaceId} 
                      onChange={(e) => setFurnaceId(e.target.value)} 
                    />
                  </div>
                </div>

                <div className="form-grid-3">
                  <div className="form-group">
                    <label>Shift</label>
                    <select value={shift} onChange={(e) => setShift(e.target.value)}>
                      <option value="SHIFT_A">Shift A (Morning)</option>
                      <option value="SHIFT_B">Shift B (Evening)</option>
                      <option value="SHIFT_C">Shift C (Night)</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Metal Tapped Weight (kg)</label>
                    <input 
                      type="number" 
                      step="0.0001" 
                      placeholder="e.g. 5000.00" 
                      value={metalTappedWeight} 
                      onChange={(e) => setMetalTappedWeight(e.target.value)} 
                    />
                  </div>
                  <div className="form-group">
                    <label>Melting Power Consumed (KWH)</label>
                    <input 
                      type="number" 
                      step="0.1" 
                      placeholder="e.g. 295 (calc at ₹8.50/KWH)" 
                      value={powerKwh} 
                      onChange={(e) => setPowerKwh(e.target.value)} 
                    />
                  </div>
                </div>

                <div className="form-group mb-2">
                  <label>Notes / Metallurgy Remarks</label>
                  <input 
                    type="text" 
                    placeholder="Optional remarks" 
                    value={notes} 
                    onChange={(e) => setNotes(e.target.value)} 
                  />
                </div>

                {/* Linked Stores Issues Detection & 1-Click Import */}
                {loadingLinkedIssues && (
                  <div style={{ fontSize: '12px', color: '#64748b', margin: '8px 0' }}>
                    Checking Stores Material Issue slips for heat {heatNumber}...
                  </div>
                )}
                {linkedIssues.length > 0 && (
                  <div style={{ 
                    background: '#f0fdf4', 
                    border: '1.5px solid #86efac', 
                    borderRadius: '8px', 
                    padding: '12px 14px', 
                    margin: '10px 0 14px 0' 
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <CheckCircle size={18} style={{ color: '#16a34a' }} />
                        <strong style={{ fontSize: '13px', color: '#166534' }}>
                          Stores Issue Found for this Heat ({linkedIssues.length} slip)
                        </strong>
                      </div>
                      <span className="pill p-posted" style={{ fontSize: '11px' }}>Approved in Stores</span>
                    </div>

                    {linkedIssues.map((issue) => (
                      <div key={issue.id} style={{ 
                        background: '#ffffff', 
                        border: '1px solid #bbf7d0', 
                        borderRadius: '6px', 
                        padding: '10px 12px',
                        marginTop: '6px' 
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#14532d' }}>
                            {issue.issue_slip_number} ({issue.issue_date})
                          </span>
                          <button
                            type="button"
                            className="erp-btn btn-sm btn-primary"
                            onClick={() => handleImportFromIssue(issue)}
                            style={{ fontSize: '12px', padding: '4px 10px', background: '#16a34a', borderColor: '#16a34a' }}
                          >
                            📥 Copy Issued Materials to Crucible Charges
                          </button>
                        </div>
                        <div style={{ fontSize: '12px', color: '#374151' }}>
                          {issue.lines?.map((l: any) => (
                            <span key={l.id || l.line_number} style={{ display: 'inline-block', marginRight: '10px' }}>
                              <strong>{l.item_name}</strong>: {Number(l.quantity).toLocaleString()} {l.uom_code || 'KG'}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Live Yield & Melt Loss Simulator */}
                {(() => {
                  const modalGrossCharged = chargeLines.reduce((acc, row) => acc + (Number(row.charged_quantity) || 0), 0);
                  const modalTapped = Number(metalTappedWeight) || 0;
                  const modalLossKg = (modalGrossCharged > 0 && modalTapped > 0) ? Math.max(0, modalGrossCharged - modalTapped) : 0;
                  const modalLossPct = modalGrossCharged > 0 ? (modalLossKg / modalGrossCharged) * 100 : 0;
                  const modalYieldPct = 100 - modalLossPct;
                  const modalKwh = Number(powerKwh) || (modalTapped > 0 ? (modalTapped / 1000) * 550 : 0);
                  const modalPowerCost = modalKwh * powerTariff;
                  const modalOverhead = (modalTapped / 1000) * consumableOverheadPerMt;
                  const modalMatCost = modalGrossCharged * 42;
                  const modalTotalCost = modalMatCost + modalPowerCost + modalOverhead;
                  const modalCostPerKg = modalTapped > 0 ? modalTotalCost / modalTapped : 0;

                  return (
                    <div style={{
                      background: modalLossPct > criticalMeltLossPct ? '#fef2f2' : modalLossPct > warningMeltLossPct ? '#fffbeb' : '#f0fdf4',
                      border: `1.5px solid ${modalLossPct > criticalMeltLossPct ? '#fca5a5' : modalLossPct > warningMeltLossPct ? '#fde68a' : '#bbf7d0'}`,
                      borderRadius: '8px',
                      padding: '12px 16px',
                      marginTop: '10px',
                      marginBottom: '14px'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <span style={{ fontSize: '12px', fontWeight: 700, color: '#0f172a' }}>
                          ⚡ Live Heat Yield & Cost Estimation Preview
                        </span>
                        {modalGrossCharged > 0 && modalTapped > 0 && (
                          <span className={`badge ${
                            modalLossPct > criticalMeltLossPct ? 'badge-danger' :
                            modalLossPct > warningMeltLossPct ? 'badge-warning' : 'badge-success'
                          }`} style={{ fontWeight: 700 }}>
                            {modalLossPct.toFixed(2)}% Melt Loss • {modalYieldPct.toFixed(2)}% Yield
                          </span>
                        )}
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px', fontSize: '11px' }}>
                        <div>Gross Charge: <strong>{modalGrossCharged.toLocaleString()} kg</strong></div>
                        <div>Tapped Metal: <strong>{modalTapped.toLocaleString()} kg</strong></div>
                        <div>Melt Loss: <strong>{modalLossKg.toFixed(1)} kg</strong></div>
                        <div>Est. Power: <strong>₹{modalPowerCost.toFixed(0)}</strong></div>
                        <div>Est. Net Cost: <strong style={{ color: '#065f46' }}>{modalCostPerKg > 0 ? `₹${modalCostPerKg.toFixed(2)}/kg` : '—'}</strong></div>
                      </div>
                    </div>
                  );
                })()}

                <div className="section-divider mt-4 mb-2">
                  <span className="section-title"><Layers size={14} className="inline-icon" /> Charge Materials</span>
                </div>
                {chargeLines.map((c, idx) => (
                  <div key={idx} className="charge-row form-grid-4 mb-2">
                    <div className="form-group">
                      <label>Material Description *</label>
                      <input 
                        type="text" 
                        placeholder="e.g. Pig Iron Grade A, Returns, FeSi..." 
                        value={c.original_material_description} 
                        onChange={(e) => {
                          const val = e.target.value;
                          setChargeLines(prev => prev.map((row, i) => i === idx ? { ...row, original_material_description: val } : row));
                        }}
                        list="material-suggestions"
                        required
                      />
                    </div>
                    <div className="form-group">
                      <label>Charged Quantity (kg) *</label>
                      <input 
                        type="number" 
                        step="0.0001" 
                        placeholder="Qty" 
                        value={c.charged_quantity} 
                        onChange={(e) => {
                          const val = e.target.value;
                          setChargeLines(prev => prev.map((row, i) => i === idx ? { ...row, charged_quantity: val } : row));
                        }}
                        required
                      />
                    </div>
                    <div className="form-group">
                      <label>Remarks</label>
                      <input 
                        type="text" 
                        placeholder="e.g. Bucket 1" 
                        value={c.remarks} 
                        onChange={(e) => {
                          const val = e.target.value;
                          setChargeLines(prev => prev.map((row, i) => i === idx ? { ...row, remarks: val } : row));
                        }}
                      />
                    </div>
                    <div className="form-group pt-4">
                      {chargeLines.length > 1 && (
                        <button type="button" className="erp-btn btn-danger btn-sm" onClick={() => removeChargeRow(idx)}>
                          Remove
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                <button type="button" className="erp-btn btn-secondary btn-sm mb-4" onClick={addChargeRow}>
                  + Add Charge Item
                </button>

                <div className="section-divider mt-2 mb-2">
                  <span className="section-title">Parts Cast</span>
                </div>
                {partsProduced.map((p, idx) => (
                  <div key={idx} className="part-row form-grid-4 mb-2">
                    <div className="form-group">
                      <label>Part Description</label>
                      <input 
                        type="text" 
                        placeholder="e.g. Differential Case" 
                        value={p.original_part_description} 
                        onChange={(e) => {
                          const val = e.target.value;
                          setPartsProduced(prev => prev.map((row, i) => i === idx ? { ...row, original_part_description: val } : row));
                        }}
                      />
                    </div>
                    <div className="form-group">
                      <label>Quantity Cast</label>
                      <input 
                        type="number" 
                        placeholder="Count" 
                        value={p.quantity_produced} 
                        onChange={(e) => {
                          const val = e.target.value;
                          setPartsProduced(prev => prev.map((row, i) => i === idx ? { ...row, quantity_produced: val } : row));
                        }}
                      />
                    </div>
                    <div className="form-group">
                      <label>Unit Weight (kg)</label>
                      <input 
                        type="number" 
                        step="0.01" 
                        placeholder="Unit kg" 
                        value={p.unit_cast_weight} 
                        onChange={(e) => {
                          const val = e.target.value;
                          setPartsProduced(prev => prev.map((row, i) => i === idx ? { ...row, unit_cast_weight: val } : row));
                        }}
                      />
                    </div>
                    <div className="form-group pt-4">
                      {partsProduced.length > 1 && (
                        <button type="button" className="erp-btn btn-danger btn-sm" onClick={() => removePartRow(idx)}>
                          Remove
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                <button type="button" className="erp-btn btn-secondary btn-sm mb-2" onClick={addPartRow}>
                  + Add Part Row
                </button>

                <datalist id="material-suggestions">
                  {items.map(it => (
                    <option key={it.id} value={it.name}>{it.item_code}</option>
                  ))}
                </datalist>
              </div>

              <div className="modal-footer">
                <button type="button" className="erp-btn btn-secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="erp-btn btn-primary" disabled={submitting || uomsUnavailable}>
                  {submitting ? 'Recording Heat...' : 'Commit Heat Record'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
