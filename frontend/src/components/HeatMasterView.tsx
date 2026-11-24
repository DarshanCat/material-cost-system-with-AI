import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  Flame, 
  Search, 
  Plus, 
  RefreshCw, 
  CheckCircle, 
  AlertTriangle, 
  X, 
  Calendar, 
  Lock, 
  Unlock, 
  Coins, 
  ArrowRight,
  Layers,
  FileText
} from 'lucide-react';
import type { HeatHeader, UserRole, ModuleId } from '../types';
import { apiFetch } from '../api/client';
import { hasPermission } from '../auth/permissions';

interface HeatMasterViewProps {
  currentRole: UserRole;
  currentUserId: string;
  onNavigate?: (module: ModuleId) => void;
}

interface HeatConsumptionItem {
  key: string | number;
  itemId: number;
  itemCode: string;
  itemName: string;
  grossIssuedKg: number;
  returnedRtsKg: number;
  netConsumedKg: number;
  unitRate: number;
  lineItemCost: number;
}

export const HeatMasterView: React.FC<HeatMasterViewProps> = ({ currentRole, onNavigate }) => {
  const canManageHeat = hasPermission(currentRole, 'heat_log:create');

  const [heats, setHeats] = useState<HeatHeader[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusTab, setStatusTab] = useState<'ALL' | 'ACTIVE' | 'COMPLETED'>('ALL');
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Create Heat Modal State
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [heatNumber, setHeatNumber] = useState<string>('');
  const [heatDate, setHeatDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [furnaceId, setFurnaceId] = useState<string>('FURNACE-1');
  const [shift, setShift] = useState<string>('Shift A');
  const [productionStatus, setProductionStatus] = useState<'IN_PROGRESS' | 'COMPLETED'>('IN_PROGRESS');
  const [notes, setNotes] = useState<string>('');

  // Cost Drawer State
  const [selectedHeatForCost, setSelectedHeatForCost] = useState<HeatHeader | null>(null);
  const [costData, setCostData] = useState<any | null>(null);
  const [loadingCost, setLoadingCost] = useState<boolean>(false);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);

  const normalizedCost = useMemo(() => {
    if (!costData) return null;
    const raw = costData as any;
    const totalProductionCost = Number(raw.total_batch_cost_inr ?? raw.total_production_cost ?? 0);
    const totalNetConsumedKg = Number(raw.total_consumed_kg ?? raw.total_net_consumed_kg ?? 0);
    const unitCostPerKg = Number(raw.cost_per_kg_liquid_metal ?? raw.unit_cost_per_kg ?? 0);
    const rawMaterials = Array.isArray(raw.materials) ? raw.materials : (Array.isArray(raw.consumed_materials) ? raw.consumed_materials : []);
    const materials: HeatConsumptionItem[] = rawMaterials.map((m: any, idx: number) => ({
      key: m.item_id ?? idx,
      itemId: m.item_id,
      itemCode: m.item_code || '',
      itemName: m.item_name || 'Material Item',
      grossIssuedKg: Number(m.gross_issued_qty ?? m.gross_issued_kg ?? 0),
      returnedRtsKg: Number(m.returned_qty ?? m.returned_rts_kg ?? 0),
      netConsumedKg: Number(m.net_consumed_qty ?? m.net_consumed_kg ?? 0),
      unitRate: Number(m.unit_rate_inr ?? m.unit_rate ?? 0),
      lineItemCost: Number(m.line_total_cost_inr ?? m.line_item_cost ?? 0),
    }));
    const linkedSlips: string[] = Array.isArray(raw.linked_issue_slips) 
      ? raw.linked_issue_slips 
      : (Array.isArray(raw.issue_slips) ? raw.issue_slips : []);

    return {
      heatNumber: raw.heat_number,
      totalProductionCost,
      totalNetConsumedKg,
      unitCostPerKg,
      materials,
      linkedSlips,
    };
  }, [costData]);

  const fetchHeats = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/v1/heats?limit=100');
      if (res.ok) {
        const data = await res.json();
        setHeats(data);
      } else {
        setFeedback({ type: 'error', message: 'Failed to fetch furnace heats from server.' });
      }
    } catch (err) {
      console.error('Error fetching heats:', err);
      setFeedback({ type: 'error', message: 'Network error while retrieving heats.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHeats();
  }, [fetchHeats]);

  // Filtered heats
  const filteredHeats = useMemo(() => {
    return heats.filter((h) => {
      const matchesSearch = 
        h.heat_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (h.furnace_id && h.furnace_id.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (h.normalized_heat_number && h.normalized_heat_number.toLowerCase().includes(searchTerm.toLowerCase()));
      
      const isAct = h.production_status === 'IN_PROGRESS';
      const matchesTab = 
        statusTab === 'ALL' ||
        (statusTab === 'ACTIVE' && isAct) ||
        (statusTab === 'COMPLETED' && !isAct);

      return matchesSearch && matchesTab;
    });
  }, [heats, searchTerm, statusTab]);

  // Statistics
  const activeCount = useMemo(() => heats.filter(h => h.production_status === 'IN_PROGRESS').length, [heats]);
  const closedCount = useMemo(() => heats.filter(h => h.production_status === 'COMPLETED').length, [heats]);

  const handleCreateHeat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!heatNumber.trim()) {
      setFeedback({ type: 'error', message: 'Heat Number is required.' });
      return;
    }

    setSubmitting(true);
    setFeedback(null);
    try {
      const payload = {
        heat_number: heatNumber.trim(),
        heat_date: heatDate,
        furnace_id: furnaceId,
        shift: shift,
        production_status: productionStatus,
        notes: notes || 'Registered via Furnace Heat Master',
        charge_lines: [],
        parts_produced: []
      };

      const res = await apiFetch('/api/v1/heats', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const created = await res.json();
        setFeedback({ 
          type: 'success', 
          message: `Furnace Heat ${created.heat_number} successfully registered as ${productionStatus === 'IN_PROGRESS' ? 'ACTIVE' : 'CLOSED'}. ${productionStatus === 'IN_PROGRESS' ? 'Stores can now immediately select it for raw material issues.' : ''}` 
        });
        setShowCreateModal(false);
        setHeatNumber('');
        setNotes('');
        setProductionStatus('IN_PROGRESS');
        fetchHeats();
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Failed to create heat.' });
      }
    } catch (err) {
      console.error('Error creating heat:', err);
      setFeedback({ type: 'error', message: 'Network error occurred while creating heat.' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (heat: HeatHeader) => {
    const isCurrentlyActive = heat.production_status === 'IN_PROGRESS';
    const action = isCurrentlyActive ? 'close' : 'reopen';
    const endpoint = `/api/v1/heats/${heat.id}/${action}`;

    setActionLoadingId(heat.id);
    setFeedback(null);
    try {
      const res = await apiFetch(endpoint, { method: 'POST' });
      if (res.ok) {
        setFeedback({
          type: 'success',
          message: isCurrentlyActive 
            ? `Heat ${heat.heat_number} has been CLOSED. Stores can no longer issue materials to this completed batch.`
            : `Heat ${heat.heat_number} has been REOPENED as ACTIVE. Stores can now select it in Material Issues.`
        });
        fetchHeats();
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || `Failed to ${action} heat.` });
      }
    } catch (err) {
      console.error(`Error ${action}ing heat:`, err);
      setFeedback({ type: 'error', message: `Network error while updating heat status.` });
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleViewCost = async (heat: HeatHeader) => {
    setSelectedHeatForCost(heat);
    setLoadingCost(true);
    setCostData(null);
    try {
      const res = await apiFetch(`/api/v1/heats/${heat.id}/consumption-cost`);
      if (res.ok) {
        const data = await res.json();
        setCostData(data);
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Failed to load batch costing.' });
      }
    } catch (err) {
      console.error('Error fetching heat cost:', err);
      setFeedback({ type: 'error', message: 'Network error while loading batch costing.' });
    } finally {
      setLoadingCost(false);
    }
  };

  return (
    <div className="erp-view space-y-4">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-amber-500/10 text-amber-600 rounded-lg">
              <Flame size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                Furnace Heat Master
                <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-800 rounded font-semibold uppercase tracking-wider">
                  Master Registry
                </span>
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Central furnace heat registry. Register active heats for the shop floor so Stores can issue raw materials directly. System auto-calculates material consumption and total batch cost.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <button
            onClick={fetchHeats}
            disabled={loading}
            className="btn btn-secondary text-xs flex items-center gap-1.5 px-3 py-2"
            title="Refresh heat records"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>

          {canManageHeat && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="btn btn-primary text-xs flex items-center gap-1.5 px-3.5 py-2 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-lg shadow-sm"
            >
              <Plus size={15} />
              + Register New Heat
            </button>
          )}
        </div>
      </div>

      {/* Alerts */}
      {feedback && (
        <div className={`p-3.5 rounded-lg border text-xs flex items-center justify-between ${
          feedback.type === 'success' 
            ? 'bg-emerald-50 border-emerald-200 text-emerald-800' 
            : 'bg-rose-50 border-rose-200 text-rose-800'
        }`}>
          <div className="flex items-center gap-2">
            {feedback.type === 'success' ? <CheckCircle size={16} className="text-emerald-600" /> : <AlertTriangle size={16} className="text-rose-600" />}
            <span className="font-medium">{feedback.message}</span>
          </div>
          <button onClick={() => setFeedback(null)} className="text-slate-400 hover:text-slate-600">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Zero Double-Entry Workflow Banner */}
      <div className="p-3.5 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-xs">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-amber-600 text-white rounded-lg shadow-xs mt-0.5">
            <Coins size={18} />
          </div>
          <div>
            <h4 className="text-xs font-bold text-amber-950 uppercase tracking-wide">
              Zero Double-Entry Workflow: Heat Master & Stores Material Issues
            </h4>
            <p className="text-xs text-amber-900 mt-0.5 leading-relaxed">
              <strong>1. Foundry Team:</strong> Simply registers the Active Heat number here. No charge items to type.<br />
              <strong>2. Stores Team:</strong> Selects the Active Heat from the dropdown in Material Issues to issue Copper, Scrap, Pig Iron, etc.<br />
              <strong>3. Costing Engine:</strong> Auto-fills consumed materials, deducts Returns to Store (RTS), and calculates total batch cost in ₹.
            </p>
          </div>
        </div>
        {onNavigate && (
          <button
            onClick={() => onNavigate('material-issue')}
            className="text-xs font-semibold text-amber-900 hover:text-amber-950 bg-white border border-amber-300 px-3 py-1.5 rounded-lg shadow-2xs flex items-center gap-1.5 shrink-0"
          >
            Go to Stores Material Issues <ArrowRight size={13} />
          </button>
        )}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Active Heats on Floor</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold text-emerald-600">{activeCount}</span>
              <span className="text-xs text-slate-500 font-medium">available for Stores issue</span>
            </div>
          </div>
          <div className="p-2.5 bg-emerald-50 text-emerald-600 rounded-lg">
            <Unlock size={20} />
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Closed / Completed Heats</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold text-slate-700">{closedCount}</span>
              <span className="text-xs text-slate-500 font-medium">batches sealed</span>
            </div>
          </div>
          <div className="p-2.5 bg-slate-100 text-slate-600 rounded-lg">
            <Lock size={20} />
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Total Registered Heats</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold text-slate-900">{heats.length}</span>
              <span className="text-xs text-slate-500 font-medium">recorded in system</span>
            </div>
          </div>
          <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
            <Layers size={20} />
          </div>
        </div>
      </div>

      {/* Main Heat Master Table Card */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {/* Table Filter Bar */}
        <div className="p-3 border-b border-slate-200 flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-3 bg-slate-50/50">
          <div className="flex items-center gap-1 bg-slate-200/60 p-1 rounded-lg">
            <button
              onClick={() => setStatusTab('ALL')}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                statusTab === 'ALL' 
                  ? 'bg-white text-slate-800 shadow-xs' 
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              All ({heats.length})
            </button>
            <button
              onClick={() => setStatusTab('ACTIVE')}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors flex items-center gap-1.5 ${
                statusTab === 'ACTIVE' 
                  ? 'bg-emerald-600 text-white shadow-xs' 
                  : 'text-slate-600 hover:text-emerald-700'
              }`}
            >
              🟢 Active ({activeCount})
            </button>
            <button
              onClick={() => setStatusTab('COMPLETED')}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                statusTab === 'COMPLETED' 
                  ? 'bg-slate-700 text-white shadow-xs' 
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              ⚪ Closed ({closedCount})
            </button>
          </div>

          <div className="relative w-full sm:w-72">
            <Search size={14} className="absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search by Heat #, Furnace..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
            />
          </div>
        </div>

        {/* Heats Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-100 text-slate-600 font-semibold uppercase tracking-wider text-[10px] border-b border-slate-200">
                <th className="py-2.5 px-3">Heat Number</th>
                <th className="py-2.5 px-3">Heat Date</th>
                <th className="py-2.5 px-3">Furnace</th>
                <th className="py-2.5 px-3">Shift</th>
                <th className="py-2.5 px-3">Status in Stores</th>
                <th className="py-2.5 px-3">Batch Costing & Raw Materials</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-400">
                    <RefreshCw size={20} className="animate-spin mx-auto mb-2 text-slate-400" />
                    Loading Furnace Heat Master records...
                  </td>
                </tr>
              ) : filteredHeats.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-400">
                    No heats found matching the criteria. Click "+ Register New Heat" to create one.
                  </td>
                </tr>
              ) : (
                filteredHeats.map((heat) => {
                  const isActive = heat.production_status === 'IN_PROGRESS';
                  const isActionLoading = actionLoadingId === heat.id;

                  return (
                    <tr key={heat.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-2.5 px-3 font-mono font-bold text-slate-900">
                        <div className="flex items-center gap-1.5">
                          <Flame size={14} className={isActive ? 'text-amber-500' : 'text-slate-400'} />
                          <span>{heat.heat_number}</span>
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-slate-600">
                        <div className="flex items-center gap-1">
                          <Calendar size={12} className="text-slate-400" />
                          <span>{heat.heat_date}</span>
                        </div>
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-slate-700">
                        {heat.furnace_id || 'FURNACE-1'}
                      </td>
                      <td className="py-2.5 px-3 text-slate-600">
                        {heat.shift || 'Shift A'}
                      </td>
                      <td className="py-2.5 px-3">
                        {isActive ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                            🟢 ACTIVE (Open in Stores)
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-700 border border-slate-300">
                            ⚪ CLOSED (Batch Complete)
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        <button
                          onClick={() => handleViewCost(heat)}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-700 hover:text-blue-900 bg-blue-50 hover:bg-blue-100 px-2.5 py-1 rounded-md border border-blue-200 transition-colors"
                          title="View auto-filled material issues, returns, and calculated batch value (₹)"
                        >
                          <Coins size={13} className="text-blue-600" />
                          View Material Consumption & Value (₹) →
                        </button>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        {canManageHeat && (
                          <button
                            onClick={() => handleToggleStatus(heat)}
                            disabled={isActionLoading}
                            className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-colors ${
                              isActive 
                                ? 'bg-amber-100 text-amber-900 hover:bg-amber-200 border border-amber-300' 
                                : 'bg-emerald-100 text-emerald-900 hover:bg-emerald-200 border border-emerald-300'
                            }`}
                          >
                            {isActionLoading ? (
                              <RefreshCw size={11} className="animate-spin inline mr-1" />
                            ) : isActive ? (
                              'Close Heat'
                            ) : (
                              'Reopen to Active'
                            )}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal: Register New Heat */}
      {showCreateModal && (
        <div className="modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content max-w-lg" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleCreateHeat}>
              <div className="modal-header">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 bg-amber-500/10 text-amber-600 rounded-lg">
                    <Flame size={18} />
                  </div>
                  <h3 className="text-base font-bold text-slate-800">Register Furnace Heat in Master</h3>
                </div>
                <button 
                  type="button" 
                  className="close-btn" 
                  onClick={() => setShowCreateModal(false)}
                >
                  <X size={18} />
                </button>
              </div>

              <div className="modal-body space-y-3.5">
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900">
                  <strong>💡 Zero Double-Entry:</strong> You only need to register the Heat Number and furnace. Charge raw materials are entered once by Stores during issue, and will automatically calculate for this heat.
                </div>

                <div>
                  <label className="form-label required">Heat Number *</label>
                  <input
                    type="text"
                    className="form-control font-mono font-bold"
                    placeholder="e.g. H-20261119-0001 or 102603-3721"
                    value={heatNumber}
                    onChange={(e) => setHeatNumber(e.target.value)}
                    required
                  />
                  <span className="text-[11px] text-slate-500 mt-1 block">
                    Must be unique. This heat number will reflect in the Stores Issue dropdown.
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="form-label required">Heat Date *</label>
                    <input
                      type="date"
                      className="form-control"
                      value={heatDate}
                      onChange={(e) => setHeatDate(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <label className="form-label required">Furnace ID *</label>
                    <select
                      className="form-control"
                      value={furnaceId}
                      onChange={(e) => setFurnaceId(e.target.value)}
                      required
                    >
                      <option value="FURNACE-1">FURNACE-1 (Main Induction)</option>
                      <option value="FURNACE-2">FURNACE-2 (Induction #2)</option>
                      <option value="FURNACE-3">FURNACE-3 (Backup)</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="form-label required">Shift *</label>
                    <select
                      className="form-control"
                      value={shift}
                      onChange={(e) => setShift(e.target.value)}
                      required
                    >
                      <option value="Shift A">Shift A (Morning 06:00 - 14:00)</option>
                      <option value="Shift B">Shift B (Evening 14:00 - 22:00)</option>
                      <option value="Shift C">Shift C (Night 22:00 - 06:00)</option>
                    </select>
                  </div>
                  <div>
                    <label className="form-label required">Initial Status *</label>
                    <select
                      className="form-control font-semibold"
                      value={productionStatus}
                      onChange={(e) => setProductionStatus(e.target.value as any)}
                      required
                    >
                      <option value="IN_PROGRESS">🟢 Active (Open on Shop Floor)</option>
                      <option value="COMPLETED">⚪ Closed (Completed)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="form-label">Notes / Metallurgy Specifications (Optional)</label>
                  <textarea
                    className="form-control text-xs"
                    rows={2}
                    placeholder="e.g. Target SG Iron grade 400/18, high purity charge..."
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </div>
              </div>

              <div className="modal-footer flex justify-end gap-2 p-3 bg-slate-50 border-t border-slate-200">
                <button
                  type="button"
                  className="btn btn-secondary text-xs px-3 py-1.5"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn btn-primary text-xs px-4 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-lg shadow-sm"
                >
                  {submitting ? 'Registering...' : 'Register Heat'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal / Drawer: Batch Costing & Material Consumption Breakdown */}
      {selectedHeatForCost && (
        <div className="modal-backdrop" onClick={() => setSelectedHeatForCost(null)}>
          <div className="modal-content max-w-3xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-blue-500/10 text-blue-600 rounded-lg">
                  <Coins size={20} />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-800">
                    Raw Material Consumption & Batch Costing: {selectedHeatForCost.heat_number}
                  </h3>
                  <span className="text-xs text-slate-500">
                    Auto-calculated from Stores Material Issue Slips and Returns to Store (RTS)
                  </span>
                </div>
              </div>
              <button 
                type="button" 
                className="close-btn" 
                onClick={() => setSelectedHeatForCost(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body space-y-4">
              {loadingCost ? (
                <div className="py-12 text-center text-slate-500">
                  <RefreshCw size={24} className="animate-spin mx-auto mb-2 text-blue-500" />
                  <p className="text-xs">Calculating batch material consumption & live weighted-average valuation...</p>
                </div>
              ) : normalizedCost ? (
                <>
                  {/* Summary Metric Banners */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl">
                      <span className="text-[10px] uppercase font-bold text-amber-800 tracking-wider">Total Batch Value (₹)</span>
                      <div className="text-xl font-bold text-amber-950 mt-1 font-mono">
                        ₹ {normalizedCost.totalProductionCost.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                      <span className="text-[11px] text-amber-700 block mt-0.5">Sum of raw materials consumed</span>
                    </div>

                    <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl">
                      <span className="text-[10px] uppercase font-bold text-blue-800 tracking-wider">Net Material Consumed</span>
                      <div className="text-xl font-bold text-blue-950 mt-1 font-mono">
                        {normalizedCost.totalNetConsumedKg.toLocaleString('en-IN', { minimumFractionDigits: 2 })} <span className="text-xs font-normal">kg</span>
                      </div>
                      <span className="text-[11px] text-blue-700 block mt-0.5">Gross issued minus RTS returns</span>
                    </div>

                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                      <span className="text-[10px] uppercase font-bold text-slate-700 tracking-wider">Average Batch Cost</span>
                      <div className="text-xl font-bold text-slate-900 mt-1 font-mono">
                        ₹ {normalizedCost.unitCostPerKg.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} <span className="text-xs font-normal">/ kg</span>
                      </div>
                      <span className="text-[11px] text-slate-500 block mt-0.5">Weighted avg raw material cost</span>
                    </div>
                  </div>

                  {/* Consumed Materials Table */}
                  <div>
                    <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wide mb-2 flex items-center justify-between">
                      <span>Materials Consumed in this Heat ({normalizedCost.materials.length} Items)</span>
                      <span className="text-[11px] font-normal text-slate-500">Auto-filled from Stores Issue Slips</span>
                    </h4>

                    {normalizedCost.materials.length === 0 ? (
                      <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg text-center text-xs text-slate-500">
                        No material issue slips have been approved against Heat <strong>{normalizedCost.heatNumber || selectedHeatForCost.heat_number}</strong> yet.
                        {onNavigate && (
                          <div className="mt-2">
                            <button
                              onClick={() => {
                                setSelectedHeatForCost(null);
                                onNavigate('material-issue');
                              }}
                              className="btn btn-primary text-xs px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white font-semibold"
                            >
                              Issue Materials from Stores Now →
                            </button>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="border border-slate-200 rounded-lg overflow-hidden">
                        <table className="w-full text-left text-xs border-collapse">
                          <thead>
                            <tr className="bg-slate-100 text-slate-600 uppercase text-[10px] font-semibold border-b border-slate-200">
                              <th className="py-2 px-3">Item Name & Code</th>
                              <th className="py-2 px-3 text-right">Gross Issued (kg)</th>
                              <th className="py-2 px-3 text-right">Returned (RTS)</th>
                              <th className="py-2 px-3 text-right">Net Consumed</th>
                              <th className="py-2 px-3 text-right">Rate (₹/kg)</th>
                              <th className="py-2 px-3 text-right">Total Cost (₹)</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {normalizedCost.materials.map((item) => (
                              <tr key={item.key} className="hover:bg-slate-50">
                                <td className="py-2 px-3 font-medium text-slate-800">
                                  {item.itemName}
                                  <span className="text-[10px] text-slate-400 block font-mono">{item.itemCode}</span>
                                </td>
                                <td className="py-2 px-3 text-right font-mono text-slate-700">
                                  {item.grossIssuedKg.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                </td>
                                <td className="py-2 px-3 text-right font-mono text-emerald-700">
                                  {item.returnedRtsKg > 0 ? `-${item.returnedRtsKg.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—'}
                                </td>
                                <td className="py-2 px-3 text-right font-mono font-bold text-slate-900">
                                  {item.netConsumedKg.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                </td>
                                <td className="py-2 px-3 text-right font-mono text-slate-600">
                                  ₹ {item.unitRate.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </td>
                                <td className="py-2 px-3 text-right font-mono font-bold text-amber-900">
                                  ₹ {item.lineItemCost.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </td>
                              </tr>
                            ))}
                            <tr className="bg-slate-50 font-bold border-t-2 border-slate-200">
                              <td className="py-2 px-3 text-slate-800">Total Production Cost:</td>
                              <td className="py-2 px-3 text-right font-mono" colSpan={3}>
                                {normalizedCost.totalNetConsumedKg.toLocaleString('en-IN', { minimumFractionDigits: 2 })} kg
                              </td>
                              <td className="py-2 px-3 text-right text-slate-500">—</td>
                              <td className="py-2 px-3 text-right font-mono text-amber-900 text-sm">
                                ₹ {normalizedCost.totalProductionCost.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  {/* Linked Stores Issue Slips */}
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                    <h5 className="text-[11px] font-bold text-slate-700 uppercase tracking-wide mb-1 flex items-center gap-1.5">
                      <FileText size={13} className="text-slate-500" />
                      Linked Stores Material Issue Slips ({normalizedCost.linkedSlips.length})
                    </h5>
                    {normalizedCost.linkedSlips.length === 0 ? (
                      <span className="text-xs text-slate-500">None linked yet.</span>
                    ) : (
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {normalizedCost.linkedSlips.map((slip, i) => (
                          <span key={i} className="px-2 py-0.5 bg-white border border-slate-300 rounded text-xs font-mono font-semibold text-slate-800">
                            {slip}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="p-4 text-center text-xs text-slate-500">
                  Unable to load cost data for this heat.
                </div>
              )}
            </div>

            <div className="modal-footer flex justify-between items-center p-3 bg-slate-50 border-t border-slate-200">
              {onNavigate && (
                <button
                  type="button"
                  className="btn btn-secondary text-xs flex items-center gap-1"
                  onClick={() => {
                    setSelectedHeatForCost(null);
                    onNavigate('material-issue');
                  }}
                >
                  <Plus size={13} />
                  Issue More Materials to this Heat
                </button>
              )}
              <button
                type="button"
                className="btn btn-secondary text-xs px-4 py-1.5 ml-auto"
                onClick={() => setSelectedHeatForCost(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
