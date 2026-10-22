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
import type { HeatHeader, MaterialItem, UOM, UserRole } from '../types';
import { apiFetch } from '../api/client';

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
  const [items, setItems] = useState<MaterialItem[]>([]);
  const [uoms, setUoms] = useState<UOM[]>([]);

  // Form state
  const [heatNumber, setHeatNumber] = useState<string>('');
  const [heatDate, setHeatDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [furnaceId, setFurnaceId] = useState<string>('FURNACE-1');
  const [shift, setShift] = useState<string>('SHIFT_A');
  const [metalTappedWeight, setMetalTappedWeight] = useState<string>('');
  const [notes, setNotes] = useState<string>('');

  // Charge lines builder
  const [chargeLines, setChargeLines] = useState<Array<{
    original_material_description: string;
    charged_quantity: string;
    uom_id: number | '';
    remarks: string;
  }>>([
    { original_material_description: '', charged_quantity: '', uom_id: '', remarks: '' }
  ]);

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
        setHeats(data);
      }
    } catch {
      // fallback
    } finally {
      setLoading(false);
    }
  };

  const fetchReferences = async () => {
    try {
      const [itemsRes, uomsRes] = await Promise.all([
        apiFetch('/api/v1/items?limit=200'),
        apiFetch('/api/v1/uoms')
      ]);
      if (itemsRes.ok) setItems(await itemsRes.json());
      if (uomsRes.ok) setUoms(await uomsRes.json());
    } catch {
      // fallback
    }
  };

  useEffect(() => {
    fetchHeats();
    fetchReferences();
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
              <th>Normalized Ref</th>
              <th>Date</th>
              <th>Furnace</th>
              <th>Shift</th>
              <th>Metal Tapped</th>
              <th>Charge Items</th>
              <th>Parts Cast</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={10} className="text-center py-4">Loading furnace heat logs...</td></tr>
            ) : heats.length === 0 ? (
              <tr><td colSpan={10} className="text-center py-4 text-muted">No furnace heats recorded for this criteria.</td></tr>
            ) : (
              heats.map((h) => (
                <tr key={h.id}>
                  <td><strong>{h.heat_number}</strong></td>
                  <td><code className="code-badge">{h.normalized_heat_number}</code></td>
                  <td>{h.heat_date}</td>
                  <td>{h.furnace_id || '-'}</td>
                  <td>{h.shift || '-'}</td>
                  <td>{h.metal_tapped_weight ? `${Number(h.metal_tapped_weight).toLocaleString()} KG` : '-'}</td>
                  <td><span className="badge badge-secondary">{h.charge_lines?.length || 0} materials</span></td>
                  <td><span className="badge badge-secondary">{h.parts_produced?.length || 0} types</span></td>
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
              ))
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
                    <label>Notes / Metallurgy Remarks</label>
                    <input 
                      type="text" 
                      placeholder="Optional remarks" 
                      value={notes} 
                      onChange={(e) => setNotes(e.target.value)} 
                    />
                  </div>
                </div>

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
                <button type="submit" className="erp-btn btn-primary" disabled={submitting}>
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
