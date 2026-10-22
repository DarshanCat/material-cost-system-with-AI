import React, { useState, useEffect } from 'react';
import type {
  UserRole,
  InventoryValuationReport,
  ItemRateJournal,
  HeatCostSummary,
  CostingRunSummary,
  CostingComparisonSummary,
} from '../types';
import { apiFetch } from '../api/client';

interface CostingDashboardProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const CostingDashboard: React.FC<CostingDashboardProps> = ({
  currentRole,
  currentUserId,
}) => {
  const [activeTab, setActiveTab] = useState<
    'valuation' | 'rate-journal' | 'heats' | 'runs' | 'exceptions'
  >('valuation');

  const [asOfDate, setAsOfDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Data states
  const [valuationReport, setValuationReport] = useState<InventoryValuationReport | null>(null);
  const [itemJournal, setItemJournal] = useState<ItemRateJournal | null>(null);

  const [heatCosts, setHeatCosts] = useState<HeatCostSummary[]>([]);
  const [selectedHeat, setSelectedHeat] = useState<HeatCostSummary | null>(null);

  const [runs, setRuns] = useState<CostingRunSummary[]>([]);
  const [comparison, setComparison] = useState<CostingComparisonSummary | null>(null);
  const [compareRun1Id, setCompareRun1Id] = useState<string>('');
  const [compareRun2Id, setCompareRun2Id] = useState<string>('');

  const [exceptions, setExceptions] = useState<{
    missing_rates: any[];
    missing_weights: any[];
    unmapped_descriptions: any[];
    pending_openings: any[];
  }>({
    missing_rates: [],
    missing_weights: [],
    unmapped_descriptions: [],
    pending_openings: [],
  });

  const canRunCosting = currentRole === 'Management' || currentRole === 'Admin';

  // 1. Fetch Inventory Valuation Report
  const fetchValuation = async (dateStr: string) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch(`/api/v1/costing/valuation/historical?as_of_date=${dateStr}`);
      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || 'Failed to fetch inventory valuation');
      }
      const data: InventoryValuationReport = await resp.json();
      setValuationReport(data);
    } catch (err: any) {
      setError(err.message || 'Error loading valuation');
    } finally {
      setLoading(false);
    }
  };

  // 2. Fetch Item Rate Journal
  const fetchItemJournal = async (itemId: number) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch(`/api/v1/costing/rates/history/${itemId}`);
      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || 'Failed to load rate evolution');
      }
      const data: ItemRateJournal = await resp.json();
      setItemJournal(data);
    } catch (err: any) {
      setError(err.message || 'Error loading rate history');
    } finally {
      setLoading(false);
    }
  };

  // 3. Fetch Heat Costs
  const fetchHeatCosts = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch('/api/v1/costing/heats');
      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || 'Failed to fetch heat costs');
      }
      const data: HeatCostSummary[] = await resp.json();
      setHeatCosts(data);
    } catch (err: any) {
      setError(err.message || 'Error loading heat costs');
    } finally {
      setLoading(false);
    }
  };

  // 4. Fetch Costing Runs
  const fetchCostingRuns = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch('/api/v1/costing/runs');
      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || 'Failed to fetch costing runs');
      }
      const data: CostingRunSummary[] = await resp.json();
      setRuns(data);
    } catch (err: any) {
      setError(err.message || 'Error loading costing runs');
    } finally {
      setLoading(false);
    }
  };

  // 5. Fetch Exceptions Queue
  const fetchExceptions = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch('/api/v1/costing/exceptions');
      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || 'Failed to fetch exceptions');
      }
      const data = await resp.json();
      setExceptions(data);
    } catch (err: any) {
      setError(err.message || 'Error loading exceptions queue');
    } finally {
      setLoading(false);
    }
  };

  // Trigger Costing Run
  const handleExecuteRun = async () => {
    if (!canRunCosting) {
      setError('Only Management and Admin roles can execute costing runs.');
      return;
    }
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const resp = await apiFetch('/api/v1/costing/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          period_start: '2026-10-12',
          period_end: asOfDate,
          as_of_date: asOfDate,
          denominator_policy: 'METAL_TAPPED',
          scrap_recovery_policy: 'POLICY_PENDING',
          internal_recovery_policy: 'POLICY_PENDING',
          notes: `Costing run executed from UI by ${currentUserId}`,
        }),
      });
      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || 'Failed to execute costing run');
      }
      const newRun: CostingRunSummary = await resp.json();
      setSuccessMsg(`Costing Run ${newRun.run_number} completed successfully!`);
      fetchCostingRuns();
    } catch (err: any) {
      setError(err.message || 'Error executing costing run');
    } finally {
      setLoading(false);
    }
  };

  // Compare Runs
  const handleCompareRuns = async () => {
    if (!compareRun1Id || !compareRun2Id) {
      setError('Please select both Run 1 and Run 2 to compare.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch(
        `/api/v1/costing/runs/compare?run_id_1=${compareRun1Id}&run_id_2=${compareRun2Id}`
      );
      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || 'Failed to compare costing runs');
      }
      const compData: CostingComparisonSummary = await resp.json();
      setComparison(compData);
    } catch (err: any) {
      setError(err.message || 'Error comparing runs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'valuation') {
      fetchValuation(asOfDate);
    } else if (activeTab === 'heats') {
      fetchHeatCosts();
    } else if (activeTab === 'runs') {
      fetchCostingRuns();
    } else if (activeTab === 'exceptions') {
      fetchExceptions();
    }
  }, [activeTab]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'VALUED':
      case 'COMPLETE':
      case 'COMPLETED':
        return <span className="erp-badge badge-success">{status}</span>;
      case 'ZERO_STOCK':
        return <span className="erp-badge badge-info">{status}</span>;
      case 'OPENING_VALUATION_MISSING':
      case 'POLICY_PENDING':
      case 'PARTIAL_COST':
      case 'MISSING_WEIGHT':
      case 'UNMAPPED_ALIAS':
        return <span className="erp-badge badge-warning">{status}</span>;
      case 'NEGATIVE_STOCK_SUSPENDED':
      case 'UNINITIALIZED':
      case 'INSUFFICIENT_COST_DATA':
        return <span className="erp-badge badge-danger">{status}</span>;
      default:
        return <span className="erp-badge badge-secondary">{status}</span>;
    }
  };

  return (
    <div className="erp-page-container">
      {/* Header bar */}
      <div className="erp-page-header">
        <div>
          <h2>Weighted-Average Costing & Valuation (Phase 6)</h2>
          <p className="erp-subtitle">
            Cost Engine v1.0.0 — Material-Only Scope — Effective Date: 12-Oct-2026
          </p>
        </div>
        <div className="erp-header-actions">
          {canRunCosting && (
            <button
              className="erp-btn btn-primary"
              onClick={handleExecuteRun}
              disabled={loading}
            >
              {loading ? 'Processing...' : '▶ Execute Costing Run'}
            </button>
          )}
        </div>
      </div>

      {/* Policy Governance Banner */}
      <div className="erp-alert alert-info">
        <strong>Cost Accounting Governance:</strong> Valuations and rates strictly cover{' '}
        <strong>Material-Only (ex-GST)</strong> costs. All calculations derive from the
        authoritative append-only stock ledger. Stock quantities and ledger balances are{' '}
        <strong>never mutated</strong> by costing calculations. Internal runner/riser returns and
        borings valuation remain flagged as <code>POLICY_PENDING</code>.
      </div>

      {error && <div className="erp-alert alert-danger">{error}</div>}
      {successMsg && <div className="erp-alert alert-success">{successMsg}</div>}

      {/* Tabs */}
      <div className="erp-tabs">
        <button
          className={`erp-tab-btn ${activeTab === 'valuation' ? 'active' : ''}`}
          onClick={() => setActiveTab('valuation')}
        >
          Inventory Valuation
        </button>
        <button
          className={`erp-tab-btn ${activeTab === 'rate-journal' ? 'active' : ''}`}
          onClick={() => setActiveTab('rate-journal')}
        >
          Item Cost History & Journal
        </button>
        <button
          className={`erp-tab-btn ${activeTab === 'heats' ? 'active' : ''}`}
          onClick={() => setActiveTab('heats')}
        >
          Heat Production Costing
        </button>
        <button
          className={`erp-tab-btn ${activeTab === 'runs' ? 'active' : ''}`}
          onClick={() => setActiveTab('runs')}
        >
          Costing Runs & Comparisons
        </button>
        <button
          className={`erp-tab-btn ${activeTab === 'exceptions' ? 'active' : ''}`}
          onClick={() => setActiveTab('exceptions')}
        >
          Exceptions Queue
        </button>
      </div>

      {/* Tab 1: Inventory Valuation */}
      {activeTab === 'valuation' && (
        <div className="erp-tab-content">
          <div className="erp-filter-bar">
            <div className="erp-form-group">
              <label>As Of Date:</label>
              <input
                type="date"
                value={asOfDate}
                onChange={(e) => setAsOfDate(e.target.value)}
                min="2026-10-12"
              />
            </div>
            <button
              className="erp-btn btn-secondary"
              onClick={() => fetchValuation(asOfDate)}
              disabled={loading}
            >
              Recalculate Valuation
            </button>
          </div>

          {valuationReport && (
            <>
              {/* Summary Metrics Cards */}
              <div className="erp-metrics-row">
                <div className="erp-metric-card">
                  <span className="metric-title">Total Inventory Valuation</span>
                  <span className="metric-value">
                    ₹{Number(valuationReport.total_inventory_valuation).toLocaleString('en-IN', {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </span>
                  <span className="metric-sub">Ex-GST Material Value</span>
                </div>
                <div className="erp-metric-card">
                  <span className="metric-title">Valued Items</span>
                  <span className="metric-value">{valuationReport.valued_items_count}</span>
                  <span className="metric-sub">
                    of {valuationReport.total_active_items} total active items
                  </span>
                </div>
                <div className="erp-metric-card">
                  <span className="metric-title">Zero Stock Items</span>
                  <span className="metric-value">{valuationReport.zero_stock_items_count}</span>
                  <span className="metric-sub">Stock = 0.0000</span>
                </div>
                <div className="erp-metric-card">
                  <span className="metric-title">Unvalued / Exceptions</span>
                  <span className="metric-value text-warning">
                    {valuationReport.unvalued_items_count}
                  </span>
                  <span className="metric-sub">Missing opening or receipt rate</span>
                </div>
              </div>

              {/* Items Table */}
              <div className="erp-table-container">
                <table className="erp-table">
                  <thead>
                    <tr>
                      <th>Item Code</th>
                      <th>Item Name</th>
                      <th>Category</th>
                      <th>Quantity</th>
                      <th>UOM</th>
                      <th>Weighted-Avg Rate (₹)</th>
                      <th>Extended Value (₹)</th>
                      <th>Valuation Status</th>
                      <th>Rate Source</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {valuationReport.items.map((item) => (
                      <tr key={item.material_item_id}>
                        <td>
                          <strong>{item.item_code}</strong>
                        </td>
                        <td>{item.item_name}</td>
                        <td>{item.category}</td>
                        <td className="text-right">
                          {Number(item.inventory_quantity).toFixed(4)}
                        </td>
                        <td>{item.uom_code}</td>
                        <td className="text-right">
                          {item.weighted_average_rate
                            ? `₹${Number(item.weighted_average_rate).toFixed(4)}`
                            : '—'}
                        </td>
                        <td className="text-right">
                          {item.extended_value
                            ? `₹${Number(item.extended_value).toLocaleString('en-IN', {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })}`
                            : '—'}
                        </td>
                        <td>{getStatusBadge(item.valuation_status)}</td>
                        <td>
                          <small>{item.rate_source || '—'}</small>
                        </td>
                        <td>
                          <button
                            className="erp-btn btn-sm btn-outline"
                            onClick={() => {
                              fetchItemJournal(item.material_item_id);
                              setActiveTab('rate-journal');
                            }}
                          >
                            View Journal
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* Tab 2: Item Rate Evolution & Journal */}
      {activeTab === 'rate-journal' && (
        <div className="erp-tab-content">
          <div className="erp-filter-bar">
            <p>
              Inspect the deterministic running average calculation movement-by-movement for an
              item.
            </p>
          </div>

          {itemJournal ? (
            <div>
              <div className="erp-section-header">
                <h3>
                  {itemJournal.item_code} — {itemJournal.item_name}
                </h3>
                <div>
                  Current Quantity: <strong>{itemJournal.current_quantity}</strong> | Weighted-Avg
                  Rate:{' '}
                  <strong>
                    {itemJournal.current_weighted_average_rate
                      ? `₹${itemJournal.current_weighted_average_rate}`
                      : 'N/A'}
                  </strong>{' '}
                  | Status: {getStatusBadge(itemJournal.current_valuation_status)}
                </div>
              </div>

              <div className="erp-table-container">
                <table className="erp-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Date</th>
                      <th>Movement Type</th>
                      <th>Delta Qty</th>
                      <th>Running Qty</th>
                      <th>Receipt Rate (₹)</th>
                      <th>Applied Rate (₹)</th>
                      <th>Resulting Avg Rate (₹)</th>
                      <th>Movement Value (₹)</th>
                      <th>Cumulative Value (₹)</th>
                      <th>Status</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {itemJournal.steps.map((s) => (
                      <tr key={s.step_number}>
                        <td>{s.step_number}</td>
                        <td>{s.transaction_date}</td>
                        <td>
                          <code>{s.movement_type}</code>
                        </td>
                        <td
                          className={`text-right ${
                            Number(s.quantity_delta) >= 0 ? 'text-success' : 'text-danger'
                          }`}
                        >
                          {Number(s.quantity_delta) > 0 ? `+${s.quantity_delta}` : s.quantity_delta}
                        </td>
                        <td className="text-right">{s.running_quantity}</td>
                        <td className="text-right">
                          {s.receipt_rate ? `₹${s.receipt_rate}` : '—'}
                        </td>
                        <td className="text-right">
                          {s.applied_rate ? `₹${s.applied_rate}` : '—'}
                        </td>
                        <td className="text-right font-bold">
                          {s.resulting_average_rate ? `₹${s.resulting_average_rate}` : '—'}
                        </td>
                        <td className="text-right">
                          {s.movement_extended_value ? `₹${s.movement_extended_value}` : '—'}
                        </td>
                        <td className="text-right">
                          {s.cumulative_value ? `₹${s.cumulative_value}` : '—'}
                        </td>
                        <td>{getStatusBadge(s.status)}</td>
                        <td>
                          <small>{s.notes || ''}</small>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="erp-placeholder-box">
              <p>Select an item from the <strong>Inventory Valuation</strong> tab to view its running rate journal.</p>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Heat Production Costing */}
      {activeTab === 'heats' && (
        <div className="erp-tab-content">
          <div className="erp-section-header">
            <h3>Heat Charge Material Cost & Cost Per Kilogram</h3>
            <button className="erp-btn btn-secondary" onClick={fetchHeatCosts}>
              Refresh Heats
            </button>
          </div>

          <div className="erp-table-container">
            <table className="erp-table">
              <thead>
                <tr>
                  <th>Heat No.</th>
                  <th>Heat Date</th>
                  <th>Furnace</th>
                  <th>Charged Qty (kg)</th>
                  <th>Metal Tapped (kg)</th>
                  <th>Total Material Cost (₹)</th>
                  <th>Cost per kg (₹)</th>
                  <th>Valued Lines</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {heatCosts.map((h) => (
                  <tr key={h.heat_id}>
                    <td>
                      <strong>{h.heat_number}</strong>
                    </td>
                    <td>{h.heat_date}</td>
                    <td>{h.furnace_id}</td>
                    <td className="text-right">{h.total_charged_quantity}</td>
                    <td className="text-right">{h.metal_tapped_weight || '—'}</td>
                    <td className="text-right">
                      ₹{Number(h.total_material_cost).toLocaleString('en-IN', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </td>
                    <td className="text-right font-bold">
                      {h.cost_per_kg ? `₹${h.cost_per_kg} / kg` : '—'}
                    </td>
                    <td>
                      {h.valued_lines} / {h.total_lines}
                    </td>
                    <td>{getStatusBadge(h.status)}</td>
                    <td>
                      <button
                        className="erp-btn btn-sm btn-outline"
                        onClick={() => setSelectedHeat(h)}
                      >
                        Inspect Breakdown
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedHeat && (
            <div className="erp-modal-overlay">
              <div className="erp-modal">
                <div className="erp-modal-header">
                  <h3>Heat {selectedHeat.heat_number} — Charge Materials Breakdown</h3>
                  <button
                    className="erp-close-btn"
                    onClick={() => setSelectedHeat(null)}
                  >
                    ✕
                  </button>
                </div>
                <div className="erp-modal-body">
                  <p>
                    Scope: <strong>{selectedHeat.cost_scope}</strong> | Denominator:{' '}
                    <strong>{selectedHeat.denominator_type}</strong> (
                    {selectedHeat.cost_denominator_value} kg)
                  </p>
                  <table className="erp-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Charge Description</th>
                        <th>Mapped Canonical Item</th>
                        <th>Charged Qty</th>
                        <th>Applicable Rate (₹)</th>
                        <th>Line Cost (₹)</th>
                        <th>Status</th>
                        <th>Remarks</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedHeat.lines.map((l) => (
                        <tr key={l.heat_charge_line_id}>
                          <td>{l.line_number}</td>
                          <td>{l.raw_material_description}</td>
                          <td>
                            {l.canonical_item_code
                              ? `${l.canonical_item_code} - ${l.canonical_item_name}`
                              : 'Unmapped'}
                          </td>
                          <td className="text-right">{l.charged_quantity}</td>
                          <td className="text-right">
                            {l.applicable_rate ? `₹${l.applicable_rate}` : '—'}
                          </td>
                          <td className="text-right">
                            {l.line_cost ? `₹${l.line_cost}` : '—'}
                          </td>
                          <td>{getStatusBadge(l.status)}</td>
                          <td>{l.remarks || ''}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Costing Runs & Comparisons */}
      {activeTab === 'runs' && (
        <div className="erp-tab-content">
          <div className="erp-section-header">
            <h3>Immutable Costing Runs Archive</h3>
            <p className="erp-subtitle">
              Every execution creates a permanent, versioned snapshot. Historical runs are
              immutable and never modified by subsequent recalculations.
            </p>
          </div>

          <div className="erp-table-container">
            <table className="erp-table">
              <thead>
                <tr>
                  <th>Run Number</th>
                  <th>Period</th>
                  <th>As Of Date</th>
                  <th>Valuation (₹)</th>
                  <th>Heat Material Cost (₹)</th>
                  <th>Valued Items</th>
                  <th>Costed Heats</th>
                  <th>Executed By</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <strong>{r.run_number}</strong>
                    </td>
                    <td>
                      {r.period_start} to {r.period_end}
                    </td>
                    <td>{r.as_of_date}</td>
                    <td className="text-right">
                      ₹{Number(r.total_inventory_valuation).toLocaleString('en-IN', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </td>
                    <td className="text-right">
                      ₹{Number(r.total_heat_material_cost).toLocaleString('en-IN', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </td>
                    <td>
                      {r.total_items_valued} / {r.total_items_evaluated}
                    </td>
                    <td>
                      {r.total_heats_costed} / {r.total_heats_evaluated}
                    </td>
                    <td>{r.created_by}</td>
                    <td>{getStatusBadge(r.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Run Comparison Form */}
          <div className="erp-card mt-4">
            <h4>Compare Costing Runs Side-by-Side</h4>
            <div className="erp-filter-bar">
              <div className="erp-form-group">
                <label>Run 1 (Baseline):</label>
                <select
                  value={compareRun1Id}
                  onChange={(e) => setCompareRun1Id(e.target.value)}
                >
                  <option value="">Select baseline run...</option>
                  {runs.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.run_number} (As of {r.as_of_date})
                    </option>
                  ))}
                </select>
              </div>
              <div className="erp-form-group">
                <label>Run 2 (Comparison):</label>
                <select
                  value={compareRun2Id}
                  onChange={(e) => setCompareRun2Id(e.target.value)}
                >
                  <option value="">Select comparison run...</option>
                  {runs.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.run_number} (As of {r.as_of_date})
                    </option>
                  ))}
                </select>
              </div>
              <button
                className="erp-btn btn-secondary"
                onClick={handleCompareRuns}
                disabled={!compareRun1Id || !compareRun2Id || loading}
              >
                Compare Runs
              </button>
            </div>

            {comparison && (
              <div className="mt-4">
                <div className="erp-metrics-row">
                  <div className="erp-metric-card">
                    <span className="metric-title">Valuation Delta</span>
                    <span
                      className={`metric-value ${
                        comparison.summary.valuation_delta >= 0 ? 'text-success' : 'text-danger'
                      }`}
                    >
                      ₹{comparison.summary.valuation_delta.toLocaleString('en-IN', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </span>
                    <span className="metric-sub">
                      Run 1: ₹{comparison.summary.valuation_run_1.toLocaleString()} → Run 2: ₹
                      {comparison.summary.valuation_run_2.toLocaleString()}
                    </span>
                  </div>
                  <div className="erp-metric-card">
                    <span className="metric-title">Heat Cost Delta</span>
                    <span className="metric-value">
                      ₹{comparison.summary.heat_cost_delta.toLocaleString('en-IN', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </span>
                  </div>
                </div>

                <h5>Item Rate and Valuation Variances</h5>
                <div className="erp-table-container">
                  <table className="erp-table">
                    <thead>
                      <tr>
                        <th>Item Code</th>
                        <th>Item Name</th>
                        <th>Run 1 Rate (₹)</th>
                        <th>Run 2 Rate (₹)</th>
                        <th>Rate Delta (₹)</th>
                        <th>Run 1 Value (₹)</th>
                        <th>Run 2 Value (₹)</th>
                        <th>Value Delta (₹)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {comparison.item_differences.map((d) => (
                        <tr key={d.material_item_id}>
                          <td><strong>{d.item_code}</strong></td>
                          <td>{d.item_name}</td>
                          <td className="text-right">{d.run_1_rate != null ? `₹${d.run_1_rate.toFixed(4)}` : '—'}</td>
                          <td className="text-right">{d.run_2_rate != null ? `₹${d.run_2_rate.toFixed(4)}` : '—'}</td>
                          <td className={`text-right ${Number(d.rate_delta) > 0 ? 'text-success' : 'text-danger'}`}>
                            {d.rate_delta != null ? `₹${d.rate_delta.toFixed(4)}` : '—'}
                          </td>
                          <td className="text-right">{d.run_1_value != null ? `₹${d.run_1_value.toLocaleString()}` : '—'}</td>
                          <td className="text-right">{d.run_2_value != null ? `₹${d.run_2_value.toLocaleString()}` : '—'}</td>
                          <td className="text-right">{d.value_delta != null ? `₹${d.value_delta.toLocaleString()}` : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 5: Exceptions Queue */}
      {activeTab === 'exceptions' && (
        <div className="erp-tab-content">
          <div className="erp-section-header">
            <h3>Costing Exceptions & Discrepancies Queue</h3>
            <p className="erp-subtitle">
              Action items required by Stores, Purchase, or Management before inventory can be fully valued.
            </p>
          </div>

          <div className="erp-card mb-4">
            <h4>Pending Opening Valuations ({exceptions.pending_openings.length})</h4>
            <p>Stock exists from 12-Oct-2026 opening balance but lacks approved commercial rate.</p>
            {exceptions.pending_openings.length === 0 ? (
              <p className="text-muted">No pending opening valuations.</p>
            ) : (
              <table className="erp-table">
                <thead>
                  <tr>
                    <th>Item ID</th>
                    <th>Item Code</th>
                    <th>Item Name</th>
                    <th>Opening Qty</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {exceptions.pending_openings.map((po, idx) => (
                    <tr key={idx}>
                      <td>{po.material_item_id}</td>
                      <td>{po.item_code}</td>
                      <td>{po.item_name}</td>
                      <td className="text-right">{po.opening_quantity}</td>
                      <td>{getStatusBadge(po.valuation_status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="erp-card mb-4">
            <h4>Missing GRN Receipt Rates ({exceptions.missing_rates.length})</h4>
            <p>Receipts posted to ledger without commercial rate (rate_ex_gst is None).</p>
            {exceptions.missing_rates.length === 0 ? (
              <p className="text-muted">No missing GRN receipt rates.</p>
            ) : (
              <table className="erp-table">
                <thead>
                  <tr>
                    <th>Item ID</th>
                    <th>GRN Reference</th>
                    <th>Transaction Date</th>
                    <th>Quantity</th>
                  </tr>
                </thead>
                <tbody>
                  {exceptions.missing_rates.map((mr, idx) => (
                    <tr key={idx}>
                      <td>{mr.material_item_id}</td>
                      <td>{mr.source_document_number}</td>
                      <td>{mr.transaction_date}</td>
                      <td className="text-right">{mr.quantity_delta}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
