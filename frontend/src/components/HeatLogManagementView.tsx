import React, { useState, useEffect, useMemo } from 'react';
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
  Calendar,
  Scale,
  Trash2
} from 'lucide-react';
import type { HeatHeader, UserRole } from '../types';
import { apiFetch } from '../api/client';
import { hasPermission } from '../auth/permissions';
import { useReferenceData } from '../hooks/useReferenceData';
import { ReferenceDataNotice } from './ReferenceDataNotice';
import { 
  computeHeatKPIs, 
  computeFullHeatCalculations,
  type HeatCalculatedKPIs, 
  type FullHeatCalculationResult 
} from '../utils/heatCalculations';

interface HeatLogManagementViewProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const HeatLogManagementView: React.FC<HeatLogManagementViewProps> = ({ currentRole, currentUserId }) => {
  const canCreateHeat = hasPermission(currentRole, 'heat_log:create');
  const [heats, setHeats] = useState<HeatHeader[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [dateFilter, setDateFilter] = useState<string>('');
  const [selectedHeat, setSelectedHeat] = useState<HeatHeader | null>(null);
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [showAdvancedMetallurgy, setShowAdvancedMetallurgy] = useState<boolean>(false);
  const [showMetallurgyCols, setShowMetallurgyCols] = useState<boolean>(false);
  const [showMetallurgyDetails, setShowMetallurgyDetails] = useState<boolean>(false);
  const [showManualChargeAndParts, setShowManualChargeAndParts] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [heatCostData, setHeatCostData] = useState<any | null>(null);
  const [_loadingCostData, setLoadingCostData] = useState<boolean>(false);
  const [productionStatus, setProductionStatus] = useState<'IN_PROGRESS' | 'COMPLETED'>('IN_PROGRESS');

  // Master references
  const refs = useReferenceData(['items', 'uoms']);
  const { items, uoms } = refs;
  // Items only feed the description suggestions; UOMs are written into the heat payload.
  const uomsUnavailable = refs.loading || Boolean(refs.errors.uoms) || (uoms?.length ?? 0) === 0;
  const defaultUom = useMemo(() => uoms.find(u => u.code === 'KG') || uoms[0], [uoms]);

  // Form state
  const [heatNumber, setHeatNumber] = useState<string>('');
  const [heatDate, setHeatDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [furnaceId, setFurnaceId] = useState<string>('FURNACE-1');
  const [shift, setShift] = useState<string>('SHIFT_A');
  const [metalTappedWeight, setMetalTappedWeight] = useState<string>('');
  const [powerKwh, setPowerKwh] = useState<string>('');
  const [notes, setNotes] = useState<string>('');

  // Liquid Heel & Furnace Mass-Balance Form State
  const [openingLiquidHeelKg, setOpeningLiquidHeelKg] = useState<string>('');
  const [closingLiquidHeelKg, setClosingLiquidHeelKg] = useState<string>('');
  const [heelMeasurementMethod, setHeelMeasurementMethod] = useState<string>('DIP_ROD');
  const [isColdStart, setIsColdStart] = useState<boolean>(false);
  const [isFurnaceEmpty, setIsFurnaceEmpty] = useState<boolean>(false);
  const [openingHeelSourceHeatId, setOpeningHeelSourceHeatId] = useState<number | null>(null);
  const [openingHeelSourceHeatNumber, setOpeningHeelSourceHeatNumber] = useState<string | null>(null);
  const [proposingCarryForward, setProposingCarryForward] = useState<boolean>(false);
  const [carryForwardMessage, setCarryForwardMessage] = useState<string | null>(null);
  const [verificationComments, setVerificationComments] = useState<string>('');

  // Configurable Costing & Yield Policy Parameters
  const [showConfigPolicy, setShowConfigPolicy] = useState<boolean>(false);
  const [powerTariff, setPowerTariff] = useState<number>(8.50);
  const [consumableOverheadPerMt, setConsumableOverheadPerMt] = useState<number>(1200.00);
  const [warningMeltLossPct, setWarningMeltLossPct] = useState<number>(6.5);
  const [criticalMeltLossPct, setCriticalMeltLossPct] = useState<number>(8.0);

  // Charge lines builder
  const [chargeLines, setChargeLines] = useState<Array<{
    selected_source_key?: string;
    custom_mode?: boolean;
    original_material_description: string;
    charged_quantity: string;
    uom_id: number | '';
    remarks: string;
  }>>([
    { selected_source_key: '', custom_mode: false, original_material_description: '', charged_quantity: '', uom_id: '', remarks: '' }
  ]);

  // Stores Issue Linking State
  const [linkedIssues, setLinkedIssues] = useState<any[]>([]);
  const [loadingLinkedIssues, setLoadingLinkedIssues] = useState<boolean>(false);
  const [selectedHeatIssues, setSelectedHeatIssues] = useState<any[]>([]);
  const [loadingSelectedHeatIssues, setLoadingSelectedHeatIssues] = useState<boolean>(false);
  const [allApprovedIssues, setAllApprovedIssues] = useState<any[]>([]);

  // Load all approved stores issues so they are readily available in the charge dropdown
  useEffect(() => {
    let isMounted = true;
    apiFetch('/api/v1/issues/?status=APPROVED')
      .then(async (res) => {
        if (res.ok) {
          const data = await res.json();
          if (isMounted) {
            setAllApprovedIssues(Array.isArray(data) ? data : (data?.items || []));
          }
        }
      })
      .catch(() => {});
    return () => { isMounted = false; };
  }, []);

  // Compute available materials issued from Stores to Foundry
  const availableIssuedMaterials = useMemo(() => {
    const list: Array<{
      key: string;
      issueSlip: string;
      issueDate: string;
      itemId?: number;
      itemName: string;
      itemCode?: string;
      quantity: number;
      uomCode: string;
      uomId?: number;
      heatRef?: string;
    }> = [];

    // Prioritize issues tagged with the active heatNumber
    const trimmedHeat = heatNumber.trim().toUpperCase();
    const sorted = [...allApprovedIssues].sort((a, b) => {
      const aRef = (a.heat_reference_number || '').toUpperCase();
      const bRef = (b.heat_reference_number || '').toUpperCase();
      const aMatch = trimmedHeat && aRef.includes(trimmedHeat);
      const bMatch = trimmedHeat && bRef.includes(trimmedHeat);
      if (aMatch && !bMatch) return -1;
      if (!aMatch && bMatch) return 1;
      return 0;
    });

    sorted.forEach((issue) => {
      (issue.lines || []).forEach((line: any, lIdx: number) => {
        list.push({
          key: `issue:${issue.id || issue.issue_slip_number}:${lIdx}`,
          issueSlip: issue.issue_slip_number,
          issueDate: issue.issue_date,
          itemId: line.material_item_id,
          itemName: line.item_name || 'Raw Material',
          itemCode: line.item_code,
          quantity: Number(line.quantity) || 0,
          uomCode: line.uom_code || 'KG',
          uomId: line.uom_id,
          heatRef: issue.heat_reference_number,
        });
      });
    });
    return list;
  }, [allApprovedIssues, heatNumber]);

  const rawMaterialItems = useMemo(() => {
    return items.filter(
      it => it.category === 'Raw Material' || it.item_code?.startsWith('FDY-RM') || it.department_id === 1
    );
  }, [items]);

  const otherCatalogItems = useMemo(() => {
    return items.filter(
      it => !(it.category === 'Raw Material' || it.item_code?.startsWith('FDY-RM') || it.department_id === 1)
    );
  }, [items]);

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
        const res = await apiFetch(`/api/v1/issues/?status=APPROVED&heat_reference_number=${encodeURIComponent(norm)}`);
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
    apiFetch(`/api/v1/issues/?status=APPROVED&heat_reference_number=${encodeURIComponent(heatRef)}`)
      .then(async (res) => {
        if (res.ok) {
          const data = await res.json();
          setSelectedHeatIssues(Array.isArray(data) ? data : (data?.items || []));
        }
      })
      .catch(() => setSelectedHeatIssues([]))
      .finally(() => setLoadingSelectedHeatIssues(false));
    // Also fetch simplified raw material consumption & total batch cost
    setLoadingCostData(true);
    apiFetch(`/api/v1/heats/${selectedHeat.id}/consumption-cost`)
      .then(async (res) => {
        if (res.ok) {
          const costData = await res.json();
          setHeatCostData(costData);
        }
      })
      .catch(() => setHeatCostData(null))
      .finally(() => setLoadingCostData(false));
  }, [selectedHeat]);

  const handleCloseHeat = async (heatId: number) => {
    try {
      const res = await apiFetch(`/api/v1/heats/${heatId}/close`, { method: 'POST' });
      if (res.ok) {
        setFeedback({ type: 'success', message: 'Heat marked as CLOSED (COMPLETED).' });
        await fetchHeats();
        if (selectedHeat?.id === heatId) {
          const updated = await res.json();
          setSelectedHeat(updated);
        }
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Failed to close heat.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error closing heat.' });
    }
  };

  const handleReopenHeat = async (heatId: number) => {
    try {
      const res = await apiFetch(`/api/v1/heats/${heatId}/reopen`, { method: 'POST' });
      if (res.ok) {
        setFeedback({ type: 'success', message: 'Heat successfully reopened as ACTIVE (IN_PROGRESS).' });
        await fetchHeats();
        if (selectedHeat?.id === heatId) {
          const updated = await res.json();
          setSelectedHeat(updated);
        }
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Failed to reopen heat.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error reopening heat.' });
    }
  };

  const handleImportFromIssue = (issue: any) => {
    if (!issue.lines || issue.lines.length === 0) return;
    const defaultUom = uoms.find(u => u.code === 'KG') || uoms[0];
    const newLines = issue.lines.map((l: any, lIdx: number) => ({
      selected_source_key: `issue:${issue.id || issue.issue_slip_number}:${lIdx}`,
      custom_mode: false,
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

  const handleFetchCarryForward = async () => {
    if (!furnaceId) return;
    setProposingCarryForward(true);
    setCarryForwardMessage(null);
    try {
      const res = await apiFetch(`/api/v1/heats/propose-carry-forward?furnace_id=${encodeURIComponent(furnaceId)}`);
      if (res.ok) {
        const data = await res.json();
        setCarryForwardMessage(data.message);
        if (data.can_carry_forward) {
          if (data.is_cold_start) {
            setIsColdStart(true);
            setOpeningLiquidHeelKg('0');
            setOpeningHeelSourceHeatId(null);
            setOpeningHeelSourceHeatNumber(null);
            setHeelMeasurementMethod('COLD_START');
          } else {
            setIsColdStart(false);
            setOpeningLiquidHeelKg(String(data.proposed_opening_heel_kg || ''));
            setOpeningHeelSourceHeatId(data.source_heat_id);
            setOpeningHeelSourceHeatNumber(data.source_heat_number);
            setHeelMeasurementMethod('DIP_ROD');
          }
        }
      } else {
        const err = await res.json();
        setCarryForwardMessage(err.detail || 'Failed to propose carry-forward heel.');
      }
    } catch {
      setCarryForwardMessage('Network error fetching carry-forward data.');
    } finally {
      setProposingCarryForward(false);
    }
  };

  const handleVerifyHeel = async (decision: 'VERIFY' | 'REJECT', comments?: string) => {
    if (!selectedHeat) return;
    try {
      const res = await apiFetch(`/api/v1/heats/${selectedHeat.id}/verify-heel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, comments: comments || null }),
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedHeat(updated);
        setFeedback({ type: 'success', message: `Liquid heel measurement ${decision.toLowerCase()}ed successfully.` });
        fetchHeats();
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || `Failed to ${decision.toLowerCase()} liquid heel.` });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error submitting verification.' });
    }
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
      { selected_source_key: '', custom_mode: false, original_material_description: '', charged_quantity: '', uom_id: uoms[0]?.id || '', remarks: '' }
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

  // Helper to compute metrics for a heat using authoritative calculation service
  const computeHeatMetrics = (h: HeatHeader): HeatCalculatedKPIs => {
    return computeHeatKPIs(h, {
      powerTariff,
      consumableOverheadPerMt,
      warningMeltLossPct,
      criticalMeltLossPct,
    });
  };

  const computeFullHeatMetrics = (h: HeatHeader): FullHeatCalculationResult => {
    return computeFullHeatCalculations(h, {
      powerTariff,
      consumableOverheadPerMt,
      warningMeltLossPct,
      criticalMeltLossPct,
    });
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
      production_status: productionStatus,
      notes: notes.trim() || null,
      opening_liquid_heel_kg: openingLiquidHeelKg !== '' ? openingLiquidHeelKg : null,
      closing_liquid_heel_kg: closingLiquidHeelKg !== '' ? closingLiquidHeelKg : null,
      heel_measurement_method: heelMeasurementMethod,
      is_cold_start: isColdStart,
      is_furnace_empty: isFurnaceEmpty,
      opening_heel_source_heat_id: openingHeelSourceHeatId,
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
        setOpeningLiquidHeelKg('');
        setClosingLiquidHeelKg('');
        setHeelMeasurementMethod('DIP_ROD');
        setIsColdStart(false);
        setIsFurnaceEmpty(false);
        setOpeningHeelSourceHeatId(null);
        setOpeningHeelSourceHeatNumber(null);
        setCarryForwardMessage(null);
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
          {canCreateHeat && (
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
          <span className="filter-label">Heat Lifecycle:</span>
          {[
            { id: 'ALL', label: 'All Heats' },
            { id: 'IN_PROGRESS', label: '🟢 Active Heats' },
            { id: 'COMPLETED', label: '⚪ Closed Heats' },
          ].map((tab) => (
            <button
              key={tab.id}
              className={`filter-chip ${statusFilter === tab.id ? 'active' : ''}`}
              onClick={() => setStatusFilter(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="filter-group" style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#475569', cursor: 'pointer', background: '#f1f5f9', padding: '4px 8px', borderRadius: '4px', border: '1px solid #cbd5e1' }}>
            <input 
              type="checkbox" 
              checked={showMetallurgyCols} 
              onChange={(e) => setShowMetallurgyCols(e.target.checked)} 
            />
            <span>Show Advanced Metallurgy Columns (Tapped Weight, Melt Loss %, Yield %)</span>
          </label>
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
              <th>Melt Loss %</th>
              <th>Melting Recovery</th>
              <th>Casting Yield</th>
              <th>Est. Direct Cost</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={11} className="text-center py-4">Loading furnace heat logs...</td></tr>
            ) : heats.filter((h) => {
              if (statusFilter !== 'ALL') {
                const st = h.production_status || 'COMPLETED';
                if (statusFilter === 'IN_PROGRESS' && st !== 'IN_PROGRESS') return false;
                if (statusFilter === 'COMPLETED' && st !== 'COMPLETED') return false;
              }
              return true;
            }).length === 0 ? (
              <tr><td colSpan={11} className="text-center py-4 text-muted">No furnace heats recorded for this criteria.</td></tr>
            ) : (
              heats.filter((h) => {
                if (statusFilter !== 'ALL') {
                  const st = h.production_status || 'COMPLETED';
                  if (statusFilter === 'IN_PROGRESS' && st !== 'IN_PROGRESS') return false;
                  if (statusFilter === 'COMPLETED' && st !== 'COMPLETED') return false;
                }
                return true;
              }).map((h) => {
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
                            m.meltLossPct < 0 || m.yieldStatus === 'CRITICAL' ? 'badge-danger' :
                            m.yieldStatus === 'WARNING' ? 'badge-warning' : 'badge-success'
                          }`} style={{ fontWeight: 700 }}>
                            {m.meltLossPct < 0 ? `⚠️ ${m.meltLossPct.toFixed(2)}%` : `${m.meltLossPct.toFixed(2)}%`}
                          </span>
                          <div style={{ fontSize: '11px', color: m.meltLossKg !== null && m.meltLossKg < 0 ? '#b91c1c' : '#64748b', marginTop: '2px' }}>
                            {m.meltLossKg !== null ? (m.meltLossKg < 0 ? `Excess Tapped: ${Math.abs(m.meltLossKg).toFixed(1)} KG` : `${m.meltLossKg.toFixed(1)} KG loss`) : '—'}
                          </div>
                        </div>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td>
                      {m.meltingRecoveryPct !== null ? (
                        <div>
                          <strong style={{ color: m.meltingRecoveryPct > 100 ? '#b91c1c' : '#1e3a8a' }}>
                            {m.meltingRecoveryPct.toFixed(1)}%
                          </strong>
                          <div style={{ fontSize: '10px', color: '#64748b' }}>Liquid Recovery</div>
                        </div>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td>
                      {m.castingYieldPct !== null ? (
                        <div>
                          <strong style={{ color: m.castingYieldPct > 100 ? '#b91c1c' : '#047857' }}>
                            {m.castingYieldPct.toFixed(1)}%
                          </strong>
                          <div style={{ fontSize: '10px', color: '#64748b' }}>
                            {m.goodCastingsKg !== null ? `${m.goodCastingsKg.toLocaleString()} KG Good` : 'Good Yield'}
                          </div>
                        </div>
                      ) : (
                        <span className="text-muted" title="Requires parts produced with unit weight">Pending Weighment</span>
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
                      {h.production_status === 'IN_PROGRESS' ? (
                        <span className="badge badge-success" style={{ fontWeight: 700 }}>
                          🟢 ACTIVE
                        </span>
                      ) : (
                        <span className="badge badge-secondary" style={{ fontWeight: 600 }}>
                          ⚪ CLOSED
                        </span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <button 
                          className="erp-btn btn-sm btn-outline"
                          onClick={() => setSelectedHeat(h)}
                        >
                          <Eye size={12} className="btn-icon" /> Details
                        </button>
                        {(currentRole === 'Foundry' || currentRole === 'Management' || currentRole === 'Admin') && (
                          h.production_status === 'IN_PROGRESS' ? (
                            <button
                              className="erp-btn btn-sm btn-secondary"
                              onClick={() => handleCloseHeat(h.id)}
                              title="Mark Heat as Closed/Completed"
                            >
                              Close
                            </button>
                          ) : (
                            <button
                              className="erp-btn btn-sm btn-outline"
                              onClick={() => handleReopenHeat(h.id)}
                              title="Reopen Heat as Active"
                            >
                              Reopen
                            </button>
                          )
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

      {/* Heat Details Drawer / Modal */}
      {selectedHeat && (() => {
        const fullMetrics = computeFullHeatMetrics(selectedHeat);
        const m = fullMetrics.kpis;
        const recon = fullMetrics.reconciliation;
        const chargeLinesWithPct = fullMetrics.chargeLines;
        const partsAllocated = fullMetrics.partsAllocated;

        return (
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

                {/* Hero Card: Authoritative Raw Material Consumed & Total Batch Cost */}
                <div style={{
                  background: 'linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%)',
                  borderRadius: '10px',
                  padding: '18px 22px',
                  color: '#ffffff',
                  marginBottom: '20px',
                  boxShadow: '0 4px 12px rgba(30, 58, 138, 0.15)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
                    <div>
                      <div style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#93c5fd', fontWeight: 700 }}>
                        Authoritative Induction Furnace Batch Costing
                      </div>
                      <h4 style={{ margin: 0, fontSize: '18px', color: '#ffffff', fontWeight: 800 }}>
                        Raw Material Consumed & Total Batch Cost
                      </h4>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      {selectedHeat.production_status === 'IN_PROGRESS' ? (
                        <span className="badge badge-success" style={{ fontWeight: 700, fontSize: '12px', padding: '5px 12px' }}>
                          🟢 ACTIVE HEAT (FOUNDRY FLOOR)
                        </span>
                      ) : (
                        <span className="badge badge-secondary" style={{ fontWeight: 600, fontSize: '12px', padding: '5px 12px' }}>
                          ⚪ CLOSED HEAT (COMPLETED)
                        </span>
                      )}
                      {(currentRole === 'Foundry' || currentRole === 'Management' || currentRole === 'Admin') && (
                        selectedHeat.production_status === 'IN_PROGRESS' ? (
                          <button
                            className="erp-btn btn-sm btn-secondary"
                            onClick={() => handleCloseHeat(selectedHeat.id)}
                            style={{ background: '#ffffff', color: '#1e3a8a', fontWeight: 700 }}
                          >
                            Close Heat
                          </button>
                        ) : (
                          <button
                            className="erp-btn btn-sm btn-outline"
                            onClick={() => handleReopenHeat(selectedHeat.id)}
                            style={{ borderColor: '#ffffff', color: '#ffffff' }}
                          >
                            Reopen Heat
                          </button>
                        )
                      )}
                    </div>
                  </div>

                  {/* 4 Hero KPI Numbers */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
                    <div style={{ background: 'rgba(255, 255, 255, 0.12)', padding: '12px 14px', borderRadius: '8px' }}>
                      <div style={{ fontSize: '11px', color: '#bfdbfe' }}>Raw Material Consumed (Net)</div>
                      <div style={{ fontSize: '20px', fontWeight: 800, marginTop: '2px' }}>
                        {heatCostData ? `${Number(heatCostData.total_consumed_kg).toLocaleString()} KG` : `${m.grossCharged.toLocaleString()} KG`}
                      </div>
                      <div style={{ fontSize: '10px', color: '#93c5fd' }}>Gross issued − Returned</div>
                    </div>

                    <div style={{ background: 'rgba(255, 255, 255, 0.12)', padding: '12px 14px', borderRadius: '8px' }}>
                      <div style={{ fontSize: '11px', color: '#bfdbfe' }}>Liquid Metal Tapped</div>
                      <div style={{ fontSize: '20px', fontWeight: 800, marginTop: '2px' }}>
                        {selectedHeat.metal_tapped_weight ? `${Number(selectedHeat.metal_tapped_weight).toLocaleString()} KG` : '—'}
                      </div>
                      <div style={{ fontSize: '10px', color: '#93c5fd' }}>Furnace tapping weight</div>
                    </div>

                    <div style={{ background: 'rgba(255, 255, 255, 0.12)', padding: '12px 14px', borderRadius: '8px' }}>
                      <div style={{ fontSize: '11px', color: '#bfdbfe' }}>Melt Loss %</div>
                      <div style={{ fontSize: '20px', fontWeight: 800, marginTop: '2px', color: (heatCostData?.melt_loss_pct || m.meltLossPct || 0) > 8 ? '#fca5a5' : '#ffffff' }}>
                        {heatCostData ? `${heatCostData.melt_loss_pct}%` : (m.meltLossPct !== null ? `${m.meltLossPct.toFixed(2)}%` : '—')}
                      </div>
                      <div style={{ fontSize: '10px', color: '#93c5fd' }}>
                        {heatCostData ? `${Number(heatCostData.melt_loss_kg).toFixed(1)} KG furnace loss` : (m.meltLossKg !== null ? `${m.meltLossKg.toFixed(1)} KG` : '—')}
                      </div>
                    </div>

                    <div style={{ background: 'rgba(255, 255, 255, 0.2)', padding: '12px 14px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.3)' }}>
                      <div style={{ fontSize: '11px', color: '#fef08a', fontWeight: 700 }}>Total Heat Batch Cost</div>
                      <div style={{ fontSize: '22px', fontWeight: 900, marginTop: '2px', color: '#fef08a' }}>
                        {heatCostData ? `₹${Number(heatCostData.total_batch_cost_inr).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : `₹${Math.round(m.totalEstCost).toLocaleString('en-IN')}`}
                      </div>
                      <div style={{ fontSize: '11px', color: '#fef08a' }}>
                        <strong>{heatCostData ? `₹${Number(heatCostData.cost_per_kg_liquid_metal).toFixed(2)}` : `₹${(m.costPerKg || 0).toFixed(2)}`}</strong> / kg molten metal
                      </div>
                    </div>
                  </div>

                  {/* Materials breakdown table inside Hero Card */}
                  {heatCostData && heatCostData.materials && heatCostData.materials.length === 0 && (
                    <div style={{ marginTop: '14px', background: 'rgba(0, 0, 0, 0.25)', borderRadius: '6px', padding: '12px 16px', textAlign: 'center' }}>
                      <div style={{ color: '#fef08a', fontSize: '13px', fontWeight: 700 }}>
                        ⏳ Awaiting Stores Material Issuance
                      </div>
                      <p style={{ margin: '4px 0 0', color: '#bfdbfe', fontSize: '11px' }}>
                        This heat is registered as <strong>Active</strong>. When Stores issues raw materials against <code>{selectedHeat.normalized_heat_number || selectedHeat.heat_number}</code> in <strong>Material Issue Slips</strong>, they will automatically auto-fill and calculate here with zero double-entry.
                      </p>
                    </div>
                  )}
                  {heatCostData && heatCostData.materials && heatCostData.materials.length > 0 && (
                    <div style={{ marginTop: '16px', background: 'rgba(0, 0, 0, 0.22)', borderRadius: '6px', overflow: 'hidden' }}>
                      <div style={{ padding: '8px 12px', fontSize: '12px', fontWeight: 700, color: '#bfdbfe', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                        Materials Consumed in this Heat Batch (Net of Returns to Store)
                      </div>
                      <table style={{ width: '100%', fontSize: '12px', color: '#ffffff', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ background: 'rgba(0, 0, 0, 0.15)', color: '#93c5fd', textAlign: 'left', fontSize: '11px' }}>
                            <th style={{ padding: '6px 12px' }}>Material Item</th>
                            <th style={{ padding: '6px 12px', textAlign: 'right' }}>Gross Issued</th>
                            <th style={{ padding: '6px 12px', textAlign: 'right' }}>Returned (RTS)</th>
                            <th style={{ padding: '6px 12px', textAlign: 'right' }}>Net Consumed</th>
                            <th style={{ padding: '6px 12px', textAlign: 'right' }}>Unit Rate</th>
                            <th style={{ padding: '6px 12px', textAlign: 'right' }}>Line Total (₹)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {heatCostData.materials.map((mat: any) => (
                            <tr key={mat.item_id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                              <td style={{ padding: '6px 12px' }}>
                                <strong>{mat.item_name}</strong>
                                <span style={{ color: '#93c5fd', marginLeft: '6px', fontSize: '10px' }}>({mat.item_code})</span>
                              </td>
                              <td style={{ padding: '6px 12px', textAlign: 'right' }}>{Number(mat.gross_issued_qty).toLocaleString()} {mat.uom_code}</td>
                              <td style={{ padding: '6px 12px', textAlign: 'right', color: mat.returned_qty > 0 ? '#86efac' : '#94a3b8' }}>
                                {mat.returned_qty > 0 ? `−${Number(mat.returned_qty).toLocaleString()} ${mat.uom_code}` : '—'}
                              </td>
                              <td style={{ padding: '6px 12px', textAlign: 'right', fontWeight: 700 }}>
                                {Number(mat.net_consumed_qty).toLocaleString()} {mat.uom_code}
                              </td>
                              <td style={{ padding: '6px 12px', textAlign: 'right' }}>₹{Number(mat.unit_rate_inr).toFixed(2)}/{mat.uom_code}</td>
                              <td style={{ padding: '6px 12px', textAlign: 'right', fontWeight: 700, color: '#fef08a' }}>
                                ₹{Number(mat.line_total_cost_inr).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* Optional Metallurgy Diagnostics & Mass-Balance Controls Toggle */}
                <div style={{ marginBottom: '16px' }}>
                  <button
                    type="button"
                    onClick={() => setShowMetallurgyDetails(!showMetallurgyDetails)}
                    style={{
                      width: '100%',
                      background: '#f8fafc',
                      border: '1px solid #cbd5e1',
                      borderRadius: '6px',
                      padding: '8px 14px',
                      fontSize: '12px',
                      fontWeight: 600,
                      color: '#475569',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      cursor: 'pointer',
                    }}
                  >
                    <span>{showMetallurgyDetails ? '▾ Hide' : '▸ Show'} Advanced Metallurgy Diagnostics (Melt Loss, Recovery %, Heel Mass-Balance)</span>
                    <span style={{ fontSize: '11px', color: '#94a3b8' }}>Optional / Diagnostics</span>
                  </button>
                </div>

                {showMetallurgyDetails && (
                  <div>
                {/* Melt Yield & Costing Breakdown Panel */}
                <div style={{
                  background: '#f8fafc',
                  border: '1.5px solid #e2e8f0',
                  borderRadius: '8px',
                  padding: '14px 18px',
                  marginBottom: '18px'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <span style={{ fontSize: '13px', fontWeight: 700, color: '#1e3a8a' }}>
                      🔥 Melt Loss, Yield & Operational Metrics (Authoritative Excel Reference)
                    </span>
                    <span className={`badge ${
                      m.meltLossPct !== null && m.meltLossPct < 0 ? 'badge-danger' :
                      m.yieldStatus === 'CRITICAL' ? 'badge-danger' :
                      m.yieldStatus === 'WARNING' ? 'badge-warning' : 'badge-success'
                    }`} style={{ fontWeight: 700 }}>
                      {m.meltLossPct !== null ? `${m.meltLossPct.toFixed(2)}% Melt Loss` : 'Pending Weighment'}
                    </span>
                  </div>

                  {/* Operational Anomaly Banner */}
                  {m.anomalies.length > 0 && (
                    <div style={{
                      background: '#fef2f2',
                      border: '1px solid #f87171',
                      borderRadius: '6px',
                      padding: '10px 14px',
                      marginBottom: '14px',
                      fontSize: '12px',
                      color: '#991b1b'
                    }}>
                      <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                        <AlertTriangle size={15} /> ⚠️ Operational Validation Anomalies Detected:
                      </div>
                      <ul style={{ margin: 0, paddingLeft: '20px' }}>
                        {m.anomalies.map((anom, aIdx) => (
                          <li key={aIdx}>{anom}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* 8 Separated KPI Cards */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px', marginBottom: '12px' }}>
                    {/* 1. Total Charge */}
                    <div style={{ background: '#fff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>Total Charge</div>
                      <div style={{ fontSize: '15px', fontWeight: 700, color: '#0f172a' }}>{m.grossCharged.toLocaleString()} KG</div>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>{selectedHeat.charge_lines?.length || 0} line(s)</div>
                    </div>

                    {/* 2. Metal Tapped */}
                    <div style={{ background: '#fff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>Metal Tapped</div>
                      <div style={{ fontSize: '15px', fontWeight: 700, color: m.tapped > m.grossCharged ? '#b91c1c' : '#0f172a' }}>
                        {m.tapped > 0 ? `${m.tapped.toLocaleString()} KG` : '—'}
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>Liquid Output</div>
                    </div>

                    {/* 3. Melt Loss (kg) */}
                    <div style={{ background: '#fff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>Melt Loss (kg)</div>
                      <div style={{ fontSize: '15px', fontWeight: 700, color: m.meltLossKg !== null && m.meltLossKg < 0 ? '#b91c1c' : '#0f172a' }}>
                        {m.meltLossKg !== null ? `${m.meltLossKg.toFixed(1)} KG` : '—'}
                      </div>
                      <div style={{ fontSize: '10px', color: m.meltLossKg !== null && m.meltLossKg < 0 ? '#b91c1c' : '#64748b' }}>
                        {m.meltLossKg !== null && m.meltLossKg < 0 ? 'Negative Loss' : 'Charge − Tapped'}
                      </div>
                    </div>

                    {/* 4. Melt Loss % */}
                    <div style={{ background: '#fff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>Melt Loss %</div>
                      <div style={{ fontSize: '15px', fontWeight: 700, color: m.meltLossPct !== null && m.meltLossPct < 0 ? '#b91c1c' : '#0f172a' }}>
                        {m.meltLossPct !== null ? `${m.meltLossPct.toFixed(2)}%` : '—'}
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>Loss / Charge</div>
                    </div>

                    {/* 5. Melting Recovery % */}
                    <div style={{ background: '#eff6ff', padding: '10px', borderRadius: '6px', border: '1px solid #bfdbfe' }}>
                      <div style={{ fontSize: '11px', color: '#1e40af', fontWeight: 600 }}>Melting Recovery %</div>
                      <div style={{ fontSize: '15px', fontWeight: 800, color: m.meltingRecoveryPct !== null && m.meltingRecoveryPct > 100 ? '#b91c1c' : '#1e3a8a' }}>
                        {m.meltingRecoveryPct !== null ? `${m.meltingRecoveryPct.toFixed(2)}%` : '—'}
                      </div>
                      <div style={{ fontSize: '10px', color: '#3b82f6' }}>Tapped / Charge</div>
                    </div>

                    {/* 6. Good Castings */}
                    <div style={{ background: '#f0fdf4', padding: '10px', borderRadius: '6px', border: '1px solid #bbf7d0' }}>
                      <div style={{ fontSize: '11px', color: '#166534', fontWeight: 600 }}>Good Castings</div>
                      <div style={{ fontSize: '15px', fontWeight: 800, color: '#166534' }}>
                        {m.goodCastingsKg !== null ? `${m.goodCastingsKg.toLocaleString()} KG` : '—'}
                      </div>
                      <div style={{ fontSize: '10px', color: '#15803d' }}>
                        {m.goodCastingsKg !== null ? '∑(Good Qty × Cast Wt)' : 'No Good Weights'}
                      </div>
                    </div>

                    {/* 7. Casting Yield % */}
                    <div style={{ background: '#f0fdf4', padding: '10px', borderRadius: '6px', border: '1px solid #bbf7d0' }}>
                      <div style={{ fontSize: '11px', color: '#166534', fontWeight: 600 }}>Casting Yield %</div>
                      <div style={{ fontSize: '15px', fontWeight: 800, color: m.castingYieldPct !== null && m.castingYieldPct > 100 ? '#b91c1c' : '#166534' }}>
                        {m.castingYieldPct !== null ? `${m.castingYieldPct.toFixed(2)}%` : '—'}
                      </div>
                      <div style={{ fontSize: '10px', color: '#15803d' }}>Good Castings / Charge</div>
                    </div>

                    {/* 8. RM per Good kg */}
                    <div style={{ background: '#fffbeb', padding: '10px', borderRadius: '6px', border: '1px solid #fde68a' }}>
                      <div style={{ fontSize: '11px', color: '#92400e', fontWeight: 600 }}>RM per Good kg</div>
                      <div style={{ fontSize: '15px', fontWeight: 800, color: '#92400e' }}>
                        {m.rmPerGoodKg !== null ? `${m.rmPerGoodKg.toFixed(3)} kg/kg` : '—'}
                      </div>
                      <div style={{ fontSize: '10px', color: '#b45309' }}>Charge / Good Castings</div>
                    </div>
                  </div>

                  {/* Authoritative Costing Measures (Phase 2B-2B & Phase 2B-2C) */}
                  <div style={{ borderTop: '1px dashed #cbd5e1', paddingTop: '10px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px', marginBottom: '8px' }}>
                      <div style={{ background: '#f8fafc', padding: '8px 10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                        <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600 }}>Measure A (Charge RM / kg)</div>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: '#1e293b' }}>
                          {m.measureACostPerKg ? `₹${m.measureACostPerKg.toFixed(2)} / kg` : '—'}
                        </div>
                      </div>
                      <div style={{ background: '#f0f9ff', padding: '8px 10px', borderRadius: '6px', border: '1px solid #bae6fd' }}>
                        <div style={{ fontSize: '11px', color: '#0369a1', fontWeight: 600 }}>Measure B (Tapped Liquid / kg)</div>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: '#0369a1' }}>
                          {m.measureBCostPerKg ? `₹${m.measureBCostPerKg.toFixed(2)} / kg` : (m.costPerKg ? `₹${m.costPerKg.toFixed(2)} / kg` : '—')}
                        </div>
                      </div>
                      <div style={{ background: '#f0fdf4', padding: '8px 10px', borderRadius: '6px', border: '1.5px solid #bbf7d0' }}>
                        <div style={{ fontSize: '11px', color: '#166534', fontWeight: 700 }}>Measure C (Good Casting RM / kg)</div>
                        <div style={{ fontSize: '14px', fontWeight: 800, color: '#166534' }}>
                          {m.measureCCostPerKg ? `₹${m.measureCCostPerKg.toFixed(2)} / kg` : '—'}
                        </div>
                      </div>
                    </div>
                    <div style={{ fontSize: '10px', color: '#92400e', background: '#fffbeb', padding: '6px 10px', borderRadius: '4px', border: '1px solid #fde68a' }}>
                      ⚡ <strong>Conversion Costs Separated (FIN-DEC-05):</strong> Power & overhead excluded from raw material unit rates. Status: <strong>NOT_AVAILABLE</strong> pending physical sub-meter logs.
                    </div>
                  </div>
                </div>

                {/* Liquid Heel & Induction Furnace Mass-Balance Section */}
                <div style={{
                  background: '#f8fafc',
                  border: '1.5px solid #cbd5e1',
                  borderRadius: '8px',
                  padding: '14px 18px',
                  marginBottom: '18px'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Scale size={16} className="text-primary" />
                      <span style={{ fontSize: '13px', fontWeight: 700, color: '#1e3a8a' }}>
                        ⚖️ Liquid Heel & Mass-Balance Verification
                      </span>
                    </div>
                    <span className={`badge ${
                      selectedHeat.heel_verification_status === 'VERIFIED' ? 'badge-success' :
                      selectedHeat.heel_verification_status === 'REJECTED' ? 'badge-danger' :
                      selectedHeat.heel_verification_status === 'PENDING_VERIFICATION' ? 'badge-warning' :
                      'badge-secondary'
                    }`} style={{ fontWeight: 700, fontSize: '11px' }}>
                      {selectedHeat.heel_verification_status || 'UNRECORDED'}
                    </span>
                  </div>

                  {/* Mass-Balance 4-Cell Grid */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px', marginBottom: '12px' }}>
                    <div style={{ background: '#fff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>Opening Liquid Heel</div>
                      <div style={{ fontSize: '15px', fontWeight: 700, color: '#0f172a' }}>
                        {selectedHeat.opening_liquid_heel_kg !== null && selectedHeat.opening_liquid_heel_kg !== undefined
                          ? `${Number(selectedHeat.opening_liquid_heel_kg).toLocaleString()} KG`
                          : <span className="text-muted">Unrecorded</span>}
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>
                        {selectedHeat.is_cold_start ? 'Cold Start (0 kg)' : selectedHeat.heel_measurement_method || 'Method Pending'}
                      </div>
                    </div>

                    <div style={{ background: '#eff6ff', padding: '10px', borderRadius: '6px', border: '1px solid #bfdbfe' }}>
                      <div style={{ fontSize: '11px', color: '#1e40af', fontWeight: 600 }}>Total Avail. Liquid Metal</div>
                      <div style={{ fontSize: '15px', fontWeight: 800, color: '#1e3a8a' }}>
                        {m.totalLiquidMetalAvailableKg !== null
                          ? `${m.totalLiquidMetalAvailableKg.toLocaleString()} KG`
                          : <span className="text-muted">Pending Heel</span>}
                      </div>
                      <div style={{ fontSize: '10px', color: '#3b82f6' }}>Solid Charge + Opening Heel</div>
                    </div>

                    <div style={{ background: '#fff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>Closing Liquid Heel</div>
                      <div style={{ fontSize: '15px', fontWeight: 700, color: '#0f172a' }}>
                        {selectedHeat.closing_liquid_heel_kg !== null && selectedHeat.closing_liquid_heel_kg !== undefined
                          ? `${Number(selectedHeat.closing_liquid_heel_kg).toLocaleString()} KG`
                          : <span className="text-muted">Unrecorded</span>}
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>
                        {selectedHeat.is_furnace_empty ? 'Furnace Emptied (0 kg)' : 'Carryover to Next Heat'}
                      </div>
                    </div>

                    <div style={{ background: '#eff6ff', padding: '10px', borderRadius: '6px', border: '1px solid #bfdbfe' }}>
                      <div style={{ fontSize: '11px', color: '#1e40af', fontWeight: 600 }}>Total Metal Accounted</div>
                      <div style={{ fontSize: '15px', fontWeight: 800, color: '#1e3a8a' }}>
                        {m.totalMetalAccountedKg !== null
                          ? `${m.totalMetalAccountedKg.toLocaleString()} KG`
                          : <span className="text-muted">Pending Heel</span>}
                      </div>
                      <div style={{ fontSize: '10px', color: '#3b82f6' }}>Metal Tapped + Closing Heel</div>
                    </div>
                  </div>

                  {/* Mass-Balance Yield & Recovery Comparison */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px', borderTop: '1px dashed #cbd5e1', paddingTop: '10px', marginBottom: '12px' }}>
                    <div style={{ background: '#fff', padding: '8px 10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>True Melt Loss</div>
                      <div style={{ fontSize: '14px', fontWeight: 700, color: m.trueMeltLossKg !== null && m.trueMeltLossKg < 0 ? '#b91c1c' : '#0f172a' }}>
                        {m.trueMeltLossKg !== null ? `${m.trueMeltLossKg.toFixed(1)} KG` : '—'}
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>Avail − Accounted</div>
                    </div>

                    <div style={{ background: '#fff', padding: '8px 10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>Mass-Balance Recovery</div>
                      <div style={{ fontSize: '14px', fontWeight: 700, color: m.massBalanceRecoveryPct !== null && m.massBalanceRecoveryPct > 100 ? '#b91c1c' : '#0f172a' }}>
                        {m.massBalanceRecoveryPct !== null ? `${m.massBalanceRecoveryPct.toFixed(2)}%` : '—'}
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>Accounted / Available</div>
                    </div>

                    <div style={{ background: '#fff', padding: '8px 10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>Tapped Metal Recovery</div>
                      <div style={{ fontSize: '14px', fontWeight: 700, color: m.tappedMetalRecoveryPct !== null && m.tappedMetalRecoveryPct > 100 ? '#b91c1c' : '#0f172a' }}>
                        {m.tappedMetalRecoveryPct !== null ? `${m.tappedMetalRecoveryPct.toFixed(2)}%` : '—'}
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>Tapped / Available</div>
                    </div>

                    <div style={{ background: '#f0fdf4', padding: '8px 10px', borderRadius: '6px', border: '1px solid #bbf7d0' }}>
                      <div style={{ fontSize: '11px', color: '#166534', fontWeight: 600 }}>Casting Yield (Solid)</div>
                      <div style={{ fontSize: '14px', fontWeight: 800, color: '#166534' }}>
                        {m.castingYieldPct !== null ? `${m.castingYieldPct.toFixed(2)}%` : '—'}
                      </div>
                      <div style={{ fontSize: '10px', color: '#15803d' }}>Good Castings / Solid Charge</div>
                    </div>
                  </div>

                  {/* Audit & Maker-Checker Verification Action Bar */}
                  <div style={{ background: '#f1f5f9', padding: '10px 14px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                      <div style={{ fontSize: '11px', color: '#475569' }}>
                        Recorded by: <strong>{selectedHeat.heel_recorded_by || 'Unrecorded'}</strong>
                        {selectedHeat.heel_verified_by && (
                          <span style={{ marginLeft: '12px' }}>
                            • Verified by: <strong>{selectedHeat.heel_verified_by}</strong> ({selectedHeat.heel_verified_at ? new Date(selectedHeat.heel_verified_at).toLocaleDateString() : ''})
                          </span>
                        )}
                      </div>

                      {/* Maker-Checker Verification Controls */}
                      {canCreateHeat && selectedHeat.heel_verification_status !== 'VERIFIED' && (
                        <div>
                          {selectedHeat.heel_recorded_by === currentUserId ? (
                            <span style={{ fontSize: '11px', color: '#b91c1c', fontWeight: 600 }}>
                              ⚠️ Maker-checker restriction: You recorded this heel measurement and cannot verify it.
                            </span>
                          ) : (
                            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                              <input
                                type="text"
                                placeholder="Verification comment..."
                                value={verificationComments}
                                onChange={(e) => setVerificationComments(e.target.value)}
                                style={{ fontSize: '11px', padding: '4px 8px', width: '180px' }}
                              />
                              <button
                                className="erp-btn btn-sm btn-success"
                                onClick={() => handleVerifyHeel('VERIFY', verificationComments)}
                                style={{ fontSize: '11px', padding: '3px 10px' }}
                              >
                                ✓ Verify
                              </button>
                              <button
                                className="erp-btn btn-sm btn-danger"
                                onClick={() => handleVerifyHeel('REJECT', verificationComments)}
                                style={{ fontSize: '11px', padding: '3px 10px' }}
                              >
                                ✕ Reject
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                  </div>
                )}

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

                {/* Furnace Charge Mix Breakdown Table with % of Charge */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <h4 style={{ margin: 0 }}>Furnace Charge Mix Breakdown</h4>
                  <span style={{ fontSize: '12px', color: '#64748b' }}>
                    Total Charge: <strong>{m.grossCharged.toLocaleString()} KG</strong>
                  </span>
                </div>
                <table className="erp-table mb-4">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Material Description</th>
                      <th>Mapped Master Item</th>
                      <th>Charged Qty</th>
                      <th>% of Charge</th>
                      <th>Alias Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {chargeLinesWithPct.map((cl, cIdx) => (
                      <tr key={cl.line_number || cIdx}>
                        <td>{cl.line_number || cIdx + 1}</td>
                        <td><strong>{cl.original_material_description}</strong></td>
                        <td>{cl.material_item ? `${cl.material_item.item_code} - ${cl.material_item.name}` : <span className="text-muted">Unmapped Description</span>}</td>
                        <td><strong>{Number(cl.charged_quantity).toLocaleString()} KG</strong></td>
                        <td>
                          <span style={{ fontWeight: 600, color: '#1e3a8a' }}>
                            {cl.percentage_of_charge !== null ? `${cl.percentage_of_charge.toFixed(2)}%` : '—'}
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${cl.validation_status === 'VALID' ? 'badge-success' : 'badge-warning'}`}>
                            {cl.validation_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Secondary / Deferred Part-Level Allocations */}
                <details style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '8px',
                  padding: '14px 18px',
                  marginBottom: '18px'
                }}>
                  <summary style={{ cursor: 'pointer', fontWeight: 700, color: '#475569', fontSize: '13px' }}>
                    📦 View Castings Produced & Part-Level Distributions (Secondary / Deferred)
                  </summary>
                  <div style={{ marginTop: '14px' }}>
                    <div style={{
                      background: '#f0f9ff',
                      border: '1px solid #bae6fd',
                      borderRadius: '6px',
                      padding: '10px 14px',
                      marginBottom: '14px',
                      fontSize: '12px',
                      color: '#0369a1'
                    }}>
                      ℹ️ <strong>Shop-Floor Costing Policy:</strong> Part-level piece allocation is secondary for this phase. Active inventory valuation and cost analysis are focused strictly on <strong>Raw Material Consumed</strong> and <strong>Total Heat Batch Cost</strong>.
                    </div>

                    {/* Physical RM Allocation & Reconciliation Panel */}
                    <div style={{
                      background: '#ffffff',
                      border: '1px solid #cbd5e1',
                      borderRadius: '8px',
                      padding: '12px 16px',
                      marginBottom: '14px'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <Scale size={16} className="text-primary" />
                          <span style={{ fontSize: '13px', fontWeight: 700, color: '#1e3a8a' }}>
                            ⚖️ Physical Raw Material Allocation & Reconciliation
                          </span>
                        </div>
                        <span className={`badge ${
                          recon.reconciliation_status === 'RECONCILED' ? 'badge-success' :
                          recon.reconciliation_status === 'INCOMPLETE_ALLOCATION' ? 'badge-warning' :
                          'badge-secondary'
                        }`} style={{ fontWeight: 700, fontSize: '11px' }}>
                          {recon.reconciliation_status === 'RECONCILED' ? '✅ RECONCILED (100% Allocated)' :
                           recon.reconciliation_status === 'INCOMPLETE_ALLOCATION' ? '⚠️ INCOMPLETE ALLOCATION' :
                           recon.reconciliation_status}
                        </span>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px', marginBottom: '8px' }}>
                        <div style={{ background: '#f8fafc', padding: '8px 12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                          <div style={{ fontSize: '11px', color: '#64748b' }}>Total Heat Charge</div>
                          <div style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a' }}>
                            {recon.total_heat_charge_kg.toLocaleString()} KG
                          </div>
                        </div>
                        <div style={{ background: '#f8fafc', padding: '8px 12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                          <div style={{ fontSize: '11px', color: '#64748b' }}>Good Castings Pool</div>
                          <div style={{ fontSize: '14px', fontWeight: 700, color: '#166534' }}>
                            {recon.total_good_castings_kg !== null ? `${recon.total_good_castings_kg.toLocaleString()} KG` : '—'}
                          </div>
                        </div>
                        <div style={{ background: '#f8fafc', padding: '8px 12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                          <div style={{ fontSize: '11px', color: '#64748b' }}>Total Allocated RM</div>
                          <div style={{ fontSize: '14px', fontWeight: 700, color: '#1e40af' }}>
                            {recon.total_allocated_rm_kg.toLocaleString()} KG
                          </div>
                        </div>
                        <div style={{ background: '#f8fafc', padding: '8px 12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                          <div style={{ fontSize: '11px', color: '#64748b' }}>Allocation Variance</div>
                          <div style={{ fontSize: '14px', fontWeight: 700, color: recon.allocation_variance_kg !== 0 ? '#b91c1c' : '#166534' }}>
                            {recon.allocation_variance_kg !== 0 ? `${recon.allocation_variance_kg.toFixed(2)} KG` : '0.00 KG (Exact)'}
                          </div>
                        </div>
                      </div>

                      {recon.discrepancy_reason && (
                        <div style={{ fontSize: '12px', color: '#b91c1c', display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px' }}>
                          <AlertTriangle size={14} />
                          <span>{recon.discrepancy_reason}</span>
                        </div>
                      )}
                    </div>

                    {/* Parts & Castings Produced Table with RM Allocation */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <h4 style={{ margin: 0 }}>Parts & Castings Produced (Physical RM Distribution)</h4>
                      <span style={{ fontSize: '12px', color: '#64748b' }}>
                        RM Allocated = (Part Total Wt / Total Good Wt) × Total Charge
                      </span>
                    </div>
                    <table className="erp-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Part Description</th>
                          <th>Quantity Cast</th>
                          <th>Unit Weight (kg)</th>
                          <th>Total Weight (kg)</th>
                          <th>RM Allocated (kg)</th>
                          <th>Classification</th>
                          <th>Allocation Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {partsAllocated.length === 0 ? (
                          <tr><td colSpan={8} className="text-center text-muted">No casting parts recorded for this heat.</td></tr>
                        ) : (
                          partsAllocated.map((p, pIdx) => {
                            const isGood = p.classification === 'GOOD';
                            return (
                              <tr key={p.line_number || pIdx}>
                                <td>{p.line_number || pIdx + 1}</td>
                                <td><strong>{p.original_part_description}</strong></td>
                                <td>{Number(p.quantity_produced).toLocaleString()}</td>
                                <td>{p.unit_cast_weight !== null ? `${Number(p.unit_cast_weight).toFixed(2)} kg` : <span className="text-muted">—</span>}</td>
                                <td>{p.total_weight_kg !== null ? `${Number(p.total_weight_kg).toFixed(2)} kg` : <span className="text-muted">—</span>}</td>
                                <td>
                                  {p.rm_allocated_kg !== null ? (
                                    <strong style={{ color: '#1e3a8a' }}>{Number(p.rm_allocated_kg).toFixed(2)} kg</strong>
                                  ) : (
                                    <span className="text-muted">—</span>
                                  )}
                                </td>
                                <td>
                                  <span className={`badge ${isGood ? 'badge-success' : 'badge-secondary'}`}>
                                    {p.classification}
                                  </span>
                                </td>
                                <td>
                                  <span className={`badge ${
                                    p.allocation_status === 'ALLOCATED' ? 'badge-success' :
                                    p.allocation_status === 'PENDING_UNIT_WEIGHT' || p.allocation_status === 'MISSING_UNIT_WEIGHT' ? 'badge-warning' :
                                    p.allocation_status === 'CLASSIFICATION_EXCLUDED' ? 'badge-secondary' :
                                    'badge-danger'
                                  }`} style={{ fontSize: '10px', fontWeight: 600 }}>
                                    {p.allocation_status}
                                  </span>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </details>
              </div>
              <div className="modal-footer">
                <button className="erp-btn btn-secondary" onClick={() => setSelectedHeat(null)}>Close</button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Log New Heat Modal */}
      {showCreateModal && (
        <div className="modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="modal-card modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <Flame size={20} className="text-primary" />
                <div>
                  <h3 style={{ margin: 0 }}>Create Furnace Heat (Heat Master)</h3>
                  <p style={{ margin: '2px 0 0', fontSize: '11px', color: '#64748b' }}>
                    Register active heat campaign for Stores material issuance and batch costing.
                  </p>
                </div>
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
                    <label>Initial Heat Status *</label>
                    <select
                      value={productionStatus}
                      onChange={(e) => setProductionStatus(e.target.value as 'IN_PROGRESS' | 'COMPLETED')}
                      style={{ fontWeight: 700, borderColor: productionStatus === 'IN_PROGRESS' ? '#10b981' : '#94a3b8' }}
                    >
                      <option value="IN_PROGRESS">🟢 Active (Open for Shop Floor Issuance)</option>
                      <option value="COMPLETED">⚪ Closed (Finished Heat)</option>
                    </select>
                    <small className="text-muted">Only Active heats appear in Stores Material Issue dropdown.</small>
                  </div>
                  <div className="form-group">
                    <label>Shift</label>
                    <select value={shift} onChange={(e) => setShift(e.target.value)}>
                      <option value="SHIFT_A">Shift A (Morning)</option>
                      <option value="SHIFT_B">Shift B (Evening)</option>
                      <option value="SHIFT_C">Shift C (Night)</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Notes / Metallurgy Remarks</label>
                    <input
                      type="text"
                      placeholder="Optional remarks, charge notes, etc."
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>
                </div>

                {/* Collapsible Advanced Metallurgy Controls */}
                <div style={{ marginTop: '12px', borderTop: '1px solid #e2e8f0', paddingTop: '10px' }}>
                  <button
                    type="button"
                    onClick={() => setShowAdvancedMetallurgy(!showAdvancedMetallurgy)}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '12px',
                      fontWeight: 600,
                      color: '#475569',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '4px 0',
                    }}
                  >
                    <span>{showAdvancedMetallurgy ? '▾ Hide' : '▸ Show'} Advanced Metallurgy Controls (Tapped Weight, Power & Liquid Heel - Optional)</span>
                  </button>

                  {showAdvancedMetallurgy && (
                    <div style={{ marginTop: '10px', padding: '12px', background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '8px' }}>
                      <div className="form-grid-2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                        <div className="form-group">
                          <label>Metal Tapped Weight (kg)</label>
                          <input 
                            type="number" 
                            step="0.0001" 
                            placeholder="e.g. 5000.00 (Optional)" 
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

                {/* Liquid Heel & Furnace Mass-Balance Measurements */}
                <div style={{
                  background: '#f8fafc',
                  border: '1.5px solid #cbd5e1',
                  borderRadius: '8px',
                  padding: '12px 14px',
                  margin: '12px 0',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <span style={{ fontSize: '13px', fontWeight: 700, color: '#334155' }}>
                      ⚖️ Liquid Heel & Mass-Balance Controls
                    </span>
                    <button
                      type="button"
                      className="erp-btn btn-sm btn-outline"
                      onClick={handleFetchCarryForward}
                      disabled={proposingCarryForward}
                      style={{ fontSize: '11px', padding: '3px 8px' }}
                    >
                      {proposingCarryForward ? 'Fetching...' : '⚡ Propose from Prior Heat'}
                    </button>
                  </div>

                  {carryForwardMessage && (
                    <div style={{ fontSize: '11px', color: '#0369a1', background: '#e0f2fe', padding: '6px 10px', borderRadius: '4px', marginBottom: '10px' }}>
                      ℹ️ {carryForwardMessage}
                    </div>
                  )}

                  <div className="form-grid-3">
                    <div className="form-group">
                      <label>Opening Liquid Heel (kg)</label>
                      <input
                        type="number"
                        step="0.0001"
                        placeholder={isColdStart ? "0.0000 (Cold Start)" : "e.g. 350.00"}
                        value={isColdStart ? '0' : openingLiquidHeelKg}
                        disabled={isColdStart}
                        onChange={(e) => {
                          setOpeningLiquidHeelKg(e.target.value);
                          setOpeningHeelSourceHeatId(null);
                        }}
                      />
                      <label style={{ fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={isColdStart}
                          onChange={(e) => {
                            setIsColdStart(e.target.checked);
                            if (e.target.checked) {
                              setOpeningLiquidHeelKg('0');
                              setOpeningHeelSourceHeatId(null);
                              setHeelMeasurementMethod('COLD_START');
                            }
                          }}
                        />
                        Cold Start (Opening Heel = 0 kg)
                      </label>
                    </div>

                    <div className="form-group">
                      <label>Closing Liquid Heel (kg)</label>
                      <input
                        type="number"
                        step="0.0001"
                        placeholder={isFurnaceEmpty ? "0.0000 (Furnace Empty)" : "e.g. 400.00"}
                        value={isFurnaceEmpty ? '0' : closingLiquidHeelKg}
                        disabled={isFurnaceEmpty}
                        onChange={(e) => setClosingLiquidHeelKg(e.target.value)}
                      />
                      <label style={{ fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={isFurnaceEmpty}
                          onChange={(e) => {
                            setIsFurnaceEmpty(e.target.checked);
                            if (e.target.checked) {
                              setClosingLiquidHeelKg('0');
                              setHeelMeasurementMethod('FURNACE_EMPTIED');
                            }
                          }}
                        />
                        Furnace Emptied (Closing Heel = 0 kg)
                      </label>
                    </div>

                    <div className="form-group">
                      <label>Measurement Method</label>
                      <select
                        value={heelMeasurementMethod}
                        onChange={(e) => setHeelMeasurementMethod(e.target.value)}
                      >
                        <option value="DIP_ROD">Dip Rod Graduation</option>
                        <option value="SCALE_DIFFERENCE">Crane Scale Gross/Tare Diff</option>
                        <option value="ESTIMATED">Crucible Visual Estimate</option>
                        <option value="COLD_START">Cold Start (Verified 0 kg)</option>
                        <option value="FURNACE_EMPTIED">Furnace Emptied (Verified 0 kg)</option>
                      </select>
                      {openingHeelSourceHeatNumber && (
                        <div style={{ fontSize: '10px', color: '#047857', marginTop: '4px' }}>
                          ✓ Carried from #{openingHeelSourceHeatNumber}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
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
                  const previewKPIs = computeHeatKPIs({
                    metal_tapped_weight: metalTappedWeight,
                    opening_liquid_heel_kg: isColdStart ? '0' : openingLiquidHeelKg,
                    closing_liquid_heel_kg: isFurnaceEmpty ? '0' : closingLiquidHeelKg,
                    is_cold_start: isColdStart,
                    is_furnace_empty: isFurnaceEmpty,
                    charge_lines: chargeLines.map(c => ({ charged_quantity: c.charged_quantity })),
                    parts_produced: partsProduced.map(p => ({
                      quantity_produced: p.quantity_produced,
                      unit_cast_weight: p.unit_cast_weight,
                      classification: p.classification,
                    }))
                  }, {
                    powerTariff,
                    consumableOverheadPerMt,
                    warningMeltLossPct,
                    criticalMeltLossPct,
                  });

                  return (
                    <div style={{
                      background: previewKPIs.yieldStatus === 'CRITICAL' || (previewKPIs.meltLossPct !== null && previewKPIs.meltLossPct < 0) ? '#fef2f2' : previewKPIs.yieldStatus === 'WARNING' ? '#fffbeb' : '#f0fdf4',
                      border: `1.5px solid ${previewKPIs.yieldStatus === 'CRITICAL' || (previewKPIs.meltLossPct !== null && previewKPIs.meltLossPct < 0) ? '#fca5a5' : previewKPIs.yieldStatus === 'WARNING' ? '#fde68a' : '#bbf7d0'}`,
                      borderRadius: '8px',
                      padding: '12px 16px',
                      marginTop: '10px',
                      marginBottom: '14px'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <span style={{ fontSize: '12px', fontWeight: 700, color: '#0f172a' }}>
                          ⚡ Live Heat Yield & Operational Estimation Preview
                        </span>
                        {previewKPIs.grossCharged > 0 && previewKPIs.tapped > 0 && (
                          <span className={`badge ${
                            previewKPIs.yieldStatus === 'CRITICAL' || (previewKPIs.meltLossPct !== null && previewKPIs.meltLossPct < 0) ? 'badge-danger' :
                            previewKPIs.yieldStatus === 'WARNING' ? 'badge-warning' : 'badge-success'
                          }`} style={{ fontWeight: 700 }}>
                            {previewKPIs.meltLossPct !== null ? `${previewKPIs.meltLossPct.toFixed(2)}% Melt Loss` : ''} • {previewKPIs.meltingRecoveryPct !== null ? `${previewKPIs.meltingRecoveryPct.toFixed(1)}% Recovery` : ''}
                          </span>
                        )}
                      </div>

                      {previewKPIs.anomalies.length > 0 && (
                        <div style={{ fontSize: '11px', color: '#b91c1c', fontWeight: 600, marginBottom: '6px' }}>
                          ⚠️ {previewKPIs.anomalies.join(' | ')}
                        </div>
                      )}

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px', fontSize: '11px' }}>
                        <div>Gross Charge: <strong>{previewKPIs.grossCharged.toLocaleString()} kg</strong></div>
                        <div>Tapped Metal: <strong>{previewKPIs.tapped.toLocaleString()} kg</strong></div>
                        <div>Opening Heel: <strong>{previewKPIs.openingLiquidHeelKg !== null ? `${previewKPIs.openingLiquidHeelKg} kg` : '—'}</strong></div>
                        <div>Avail. Liquid Metal: <strong>{previewKPIs.totalLiquidMetalAvailableKg !== null ? `${previewKPIs.totalLiquidMetalAvailableKg.toLocaleString()} kg` : '—'}</strong></div>
                        <div>Closing Heel: <strong>{previewKPIs.closingLiquidHeelKg !== null ? `${previewKPIs.closingLiquidHeelKg} kg` : '—'}</strong></div>
                        <div>True Melt Loss: <strong style={{ color: previewKPIs.trueMeltLossKg !== null && previewKPIs.trueMeltLossKg < 0 ? '#b91c1c' : '#0f172a' }}>
                          {previewKPIs.trueMeltLossKg !== null ? `${previewKPIs.trueMeltLossKg.toFixed(1)} kg` : '—'}
                        </strong></div>
                        <div>Mass Balance Rec: <strong>{previewKPIs.massBalanceRecoveryPct !== null ? `${previewKPIs.massBalanceRecoveryPct.toFixed(2)}%` : '—'}</strong></div>
                        <div>Good Castings: <strong>{previewKPIs.goodCastingsKg !== null ? `${previewKPIs.goodCastingsKg.toLocaleString()} kg` : '—'}</strong></div>
                        <div>Casting Yield: <strong>{previewKPIs.castingYieldPct !== null ? `${previewKPIs.castingYieldPct.toFixed(1)}%` : '—'}</strong></div>
                        <div>Est. Net Cost: <strong style={{ color: '#065f46' }}>{previewKPIs.costPerKg && previewKPIs.costPerKg > 0 ? `₹${previewKPIs.costPerKg.toFixed(2)}/kg` : '—'}</strong></div>
                      </div>
                    </div>
                  );
                })()}

                {/* Zero Double Entry Banner */}
                <div style={{ background: '#ecfdf5', border: '1.5px solid #a7f3d0', borderRadius: '8px', padding: '14px 16px', margin: '14px 0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, color: '#065f46', fontSize: '13px' }}>
                    <span>⚡ Zero Double Entry: Materials Auto-Fill From Stores Issuance</span>
                  </div>
                  <p style={{ margin: '6px 0 0', fontSize: '11px', color: '#047857', lineHeight: 1.5 }}>
                    When this heat is registered as <strong>Active</strong>, Stores will select <strong>{heatNumber ? (heatNumber.startsWith('H-') ? heatNumber : `H-${heatNumber}`) : 'this heat'}</strong> in <em>Material Issue Slips</em> and issue raw materials directly. The Heat Log automatically auto-fills all materials consumed and calculates the total batch production value.
                  </p>
                </div>

                <div style={{ margin: '12px 0' }}>
                  <button
                    type="button"
                    onClick={() => setShowManualChargeAndParts(!showManualChargeAndParts)}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '12px',
                      fontWeight: 600,
                      color: '#475569',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '4px 0',
                    }}
                  >
                    <span>{showManualChargeAndParts ? '▾ Hide' : '▸ Show'} Manual Crucible Charges & Parts Produced (Optional / Overrides)</span>
                  </button>
                </div>

                {showManualChargeAndParts && (
                  <div>
                <div className="section-divider mt-2 mb-2">
                  <span className="section-title"><Layers size={14} className="inline-icon" /> Charge Materials (Crucible Charge)</span>
                </div>
                {chargeLines.map((c, idx) => {
                  const isCustom = c.selected_source_key === '__CUSTOM__' || c.custom_mode;
                  return (
                    <div 
                      key={idx} 
                      style={{ 
                        background: '#f8fafc', 
                        border: '1px solid #cbd5e1', 
                        borderRadius: '8px', 
                        padding: '12px 14px', 
                        marginBottom: '10px' 
                      }}
                    >
                      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 2fr) minmax(130px, 1fr) minmax(160px, 1.2fr) auto', gap: '10px', alignItems: 'flex-start' }}>
                        <div className="form-group" style={{ margin: 0 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                            <label style={{ margin: 0, fontSize: '12px', fontWeight: 600 }}>
                              Raw Material (Issued to Foundry / Catalog) *
                            </label>
                            <button
                              type="button"
                              onClick={() => {
                                setChargeLines(prev => prev.map((row, i) => i === idx ? {
                                  ...row,
                                  custom_mode: !row.custom_mode,
                                  selected_source_key: !row.custom_mode ? '__CUSTOM__' : '',
                                } : row));
                              }}
                              style={{ 
                                background: 'none', 
                                border: 'none', 
                                color: '#0284c7', 
                                fontSize: '11px', 
                                cursor: 'pointer', 
                                textDecoration: 'underline', 
                                padding: 0 
                              }}
                            >
                              {isCustom ? '← Use Dropdown List' : '✏️ Free-Text Alias'}
                            </button>
                          </div>

                          {!isCustom ? (
                            <select
                              value={c.selected_source_key || ''}
                              onChange={(e) => {
                                const val = e.target.value;
                                if (!val) {
                                  setChargeLines(prev => prev.map((row, i) => i === idx ? {
                                    ...row,
                                    selected_source_key: '',
                                    original_material_description: '',
                                  } : row));
                                  return;
                                }
                                if (val === '__CUSTOM__') {
                                  setChargeLines(prev => prev.map((row, i) => i === idx ? {
                                    ...row,
                                    selected_source_key: '__CUSTOM__',
                                    custom_mode: true,
                                  } : row));
                                  return;
                                }
                                if (val.startsWith('issue:')) {
                                  const foundIssueMat = availableIssuedMaterials.find(m => m.key === val);
                                  if (foundIssueMat) {
                                    setChargeLines(prev => prev.map((row, i) => i === idx ? {
                                      ...row,
                                      selected_source_key: val,
                                      original_material_description: foundIssueMat.itemName,
                                      charged_quantity: row.charged_quantity || String(foundIssueMat.quantity),
                                      uom_id: foundIssueMat.uomId || defaultUom?.id || '',
                                      remarks: row.remarks || `Issued via ${foundIssueMat.issueSlip}`,
                                    } : row));
                                  }
                                  return;
                                }
                                if (val.startsWith('item:')) {
                                  const itemId = Number(val.replace('item:', ''));
                                  const foundItem = items.find(it => it.id === itemId);
                                  if (foundItem) {
                                    setChargeLines(prev => prev.map((row, i) => i === idx ? {
                                      ...row,
                                      selected_source_key: val,
                                      original_material_description: foundItem.name,
                                      uom_id: foundItem.base_uom_id || defaultUom?.id || '',
                                    } : row));
                                  }
                                }
                              }}
                              required={!c.original_material_description}
                              style={{ 
                                width: '100%', 
                                padding: '6px 10px', 
                                borderRadius: '6px', 
                                border: '1.5px solid #cbd5e1', 
                                fontSize: '12px',
                                background: '#ffffff',
                                color: '#0f172a'
                              }}
                            >
                              <option value="">-- Select Material Issued to Foundry / Catalog Item --</option>
                              {availableIssuedMaterials.length > 0 && (
                                <optgroup label="📋 Issued to Foundry (Approved Stores Issue Slips)">
                                  {availableIssuedMaterials.map(m => (
                                    <option key={m.key} value={m.key}>
                                      {m.itemName} — Issued: {m.quantity.toLocaleString()} {m.uomCode} (Slip #{m.issueSlip}{m.heatRef ? ` | Ref: ${m.heatRef}` : ''})
                                    </option>
                                  ))}
                                </optgroup>
                              )}
                              <optgroup label="🏭 Foundry Raw Materials (Standard Catalog)">
                                {rawMaterialItems.map(it => (
                                  <option key={it.id} value={`item:${it.id}`}>
                                    [{it.item_code}] {it.name}
                                  </option>
                                ))}
                              </optgroup>
                              <optgroup label="📦 Other Catalog Materials & Consumables">
                                {otherCatalogItems.map(it => (
                                  <option key={it.id} value={`item:${it.id}`}>
                                    [{it.item_code}] {it.name}
                                  </option>
                                ))}
                              </optgroup>
                              <option value="__CUSTOM__">✏️ Custom / Free-text Description...</option>
                            </select>
                          ) : (
                            <input
                              type="text"
                              placeholder="e.g. Pig Iron Grade 1, Returns, Runner/Riser..."
                              value={c.original_material_description}
                              onChange={(e) => {
                                const val = e.target.value;
                                setChargeLines(prev => prev.map((row, i) => i === idx ? {
                                  ...row,
                                  original_material_description: val,
                                } : row));
                              }}
                              required
                              autoFocus
                              style={{ 
                                width: '100%', 
                                padding: '6px 10px', 
                                borderRadius: '6px', 
                                border: '1.5px solid #cbd5e1', 
                                fontSize: '12px',
                                background: '#ffffff'
                              }}
                            />
                          )}

                          {c.original_material_description && !isCustom && (
                            <div style={{ fontSize: '11px', color: '#047857', marginTop: '3px', fontWeight: 500 }}>
                              ✓ Charge: {c.original_material_description}
                            </div>
                          )}
                        </div>

                        <div className="form-group" style={{ margin: 0 }}>
                          <label style={{ margin: 0, fontSize: '12px', fontWeight: 600, marginBottom: '4px' }}>
                            Charged Quantity (kg) *
                          </label>
                          <input
                            type="number"
                            step="0.0001"
                            placeholder="Qty (kg)"
                            value={c.charged_quantity}
                            onChange={(e) => {
                              const val = e.target.value;
                              setChargeLines(prev => prev.map((row, i) => i === idx ? { ...row, charged_quantity: val } : row));
                            }}
                            required
                            style={{ 
                              width: '100%', 
                              padding: '6px 10px', 
                              borderRadius: '6px', 
                              border: '1.5px solid #cbd5e1', 
                              fontSize: '12px',
                              background: '#ffffff'
                            }}
                          />
                        </div>

                        <div className="form-group" style={{ margin: 0 }}>
                          <label style={{ margin: 0, fontSize: '12px', fontWeight: 600, marginBottom: '4px' }}>
                            Remarks
                          </label>
                          <input
                            type="text"
                            placeholder="e.g. Bucket 1, Ladle additions"
                            value={c.remarks}
                            onChange={(e) => {
                              const val = e.target.value;
                              setChargeLines(prev => prev.map((row, i) => i === idx ? { ...row, remarks: val } : row));
                            }}
                            style={{ 
                              width: '100%', 
                              padding: '6px 10px', 
                              borderRadius: '6px', 
                              border: '1.5px solid #cbd5e1', 
                              fontSize: '12px',
                              background: '#ffffff'
                            }}
                          />
                        </div>

                        <div style={{ paddingTop: '20px' }}>
                          {chargeLines.length > 1 && (
                            <button
                              type="button"
                              className="erp-btn btn-danger btn-sm"
                              onClick={() => removeChargeRow(idx)}
                              title="Remove Charge Line"
                              style={{ padding: '6px 10px' }}
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
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
                )}
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
