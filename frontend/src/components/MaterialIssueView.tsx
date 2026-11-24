import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  CheckCircle, 
  AlertTriangle, 
  X, 
  Search,
  Flame,
  RefreshCw,
  Lock
} from 'lucide-react';
import type { MaterialIssue, UserRole } from '../types';
import { apiFetch, readApiError } from '../api/client';
import { useReferenceData } from '../hooks/useReferenceData';
import { ReferenceDataNotice } from './ReferenceDataNotice';
import { hasPermission } from '../auth/permissions';

interface MaterialIssueViewProps {
  currentRole: UserRole;
  currentUserId: string;
  onNavigate?: (module: string) => void;
}

export const MaterialIssueView: React.FC<MaterialIssueViewProps> = ({ currentRole, onNavigate }) => {
  const canCreateIssue = hasPermission(currentRole, 'issue:create');
  const [actionError, setActionError] = useState<string | null>(null);
  const [issues, setIssues] = useState<MaterialIssue[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const refs = useReferenceData(['items', 'uoms', 'departments']);
  const { items, uoms, departments } = refs;
  const [showModal, setShowModal] = useState<boolean>(false);
  const [selectedIssue, setSelectedIssue] = useState<MaterialIssue | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const storesDept = departments.find(d => d.code === 'STR' || d.code === 'GNS' || d.name.toLowerCase().includes('stores'));

  // Form State
  const [issueDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [issuingDeptId, setIssuingDeptId] = useState<number | ''>('');
  const [receivingDeptId, setReceivingDeptId] = useState<number | ''>('');
  const [heatRefNo, setHeatRefNo] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [itemSearchFilter, setItemSearchFilter] = useState<string>('');
  const [lines, setLines] = useState<Array<{
    material_item_id: number | '';
    uom_id: number | '';
    quantity: string;
    remarks: string;
  }>>([
    { material_item_id: '', uom_id: '', quantity: '', remarks: '' }
  ]);
  const [formError, setFormError] = useState<string | null>(null);
  const [formWarnings, setFormWarnings] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [availableHeats, setAvailableHeats] = useState<any[]>([]);
  const [heatSearchFilter, setHeatSearchFilter] = useState<string>('');

  useEffect(() => {
    if (storesDept && !issuingDeptId) {
      setIssuingDeptId(storesDept.id);
    }
  }, [storesDept, issuingDeptId]);

  const isFoundrySelected = Boolean(
    departments.find(d => d.id === Number(receivingDeptId))?.code === 'FDY' ||
    departments.find(d => d.id === Number(receivingDeptId))?.name?.toLowerCase().includes('foundry')
  );

  const filteredItems = itemSearchFilter.trim()
    ? items.filter(it => 
        (it.name && it.name.toLowerCase().includes(itemSearchFilter.toLowerCase())) ||
        (it.item_code && it.item_code.toLowerCase().includes(itemSearchFilter.toLowerCase()))
      )
    : items;

  const filteredHeats = availableHeats.filter((h: any) => {
    if (!heatSearchFilter.trim()) return true;
    const term = heatSearchFilter.toLowerCase();
    const hNum = String(h.heat_number || '').toLowerCase();
    const fId = String(h.furnace_id || '').toLowerCase();
    const hDate = String(h.heat_date || '').toLowerCase();
    return hNum.includes(term) || fId.includes(term) || hDate.includes(term);
  });

  const fetchIssues = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/v1/issues/');
      if (res.ok) {
        const data = await res.json();
        setIssues(Array.isArray(data) ? data : (data?.items || []));
      }
    } catch (err) {
      console.error('Error fetching issue slips:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchActiveHeats = async () => {
    try {
      const res = await apiFetch('/api/v1/heats/active');
      if (res.ok) {
        const data = await res.json();
        const list = Array.isArray(data) ? data : (data?.items || []);
        // Strictly filter to active/in-progress heats
        const active = list.filter((h: any) => h.production_status === 'IN_PROGRESS' || !h.production_status || h.production_status === 'ACTIVE');
        setAvailableHeats(active);
      } else {
        // Fallback to query with status_filter
        const fallback = await apiFetch('/api/v1/heats?status_filter=IN_PROGRESS&limit=50');
        if (fallback.ok) {
          const fbData = await fallback.json();
          setAvailableHeats(Array.isArray(fbData) ? fbData : (fbData?.items || []));
        }
      }
    } catch (err) {
      console.error('Error fetching active heats:', err);
    }
  };

  useEffect(() => {
    fetchIssues();
    fetchActiveHeats();
  }, []);

  const handleAddLine = () => {
    setLines([...lines, { material_item_id: '', uom_id: '', quantity: '', remarks: '' }]);
  };

  const handleRemoveLine = (idx: number) => {
    if (lines.length > 1) {
      setLines(lines.filter((_, i) => i !== idx));
    }
  };

  const handleLineChange = (idx: number, field: string, value: any) => {
    const updated = [...lines];
    updated[idx] = { ...updated[idx], [field]: value };
    if (field === 'material_item_id' && value) {
      const selectedItem = items.find(i => i.id === Number(value));
      if (selectedItem) {
        updated[idx].uom_id = selectedItem.base_uom_id;
      }
    }
    setLines(updated);
  };

  const handleCreateIssue = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setFormWarnings([]);

    if (isFoundrySelected && !heatRefNo.trim()) {
      setFormError('Furnace Heat Reference is mandatory when issuing raw material to the Foundry. Please select or enter a heat number.');
      return;
    }

    setSubmitting(true);

    try {
      const payloadLines = lines.map((l, index) => ({
        line_number: index + 1,
        material_item_id: Number(l.material_item_id),
        uom_id: Number(l.uom_id),
        quantity: l.quantity,
        remarks: l.remarks || null,
      }));

      const payload = {
        issue_date: issueDate,
        issuing_department_id: Number(issuingDeptId),
        receiving_department_id: Number(receivingDeptId),
        heat_reference_number: heatRefNo ? heatRefNo.trim() : null,
        notes: notes || null,
        lines: payloadLines,
      };

      const res = await apiFetch(`/api/v1/issues/?direct_issue=true`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        setFormError(data.detail || 'Failed to create Issue Slip');
      } else {
        if (data.validation_warnings && data.validation_warnings.length > 0) {
          setFormWarnings(data.validation_warnings);
        }
        fetchIssues();
        setShowModal(false);
        setLines([{ material_item_id: '', uom_id: '', quantity: '', remarks: '' }]);
      }
    } catch (err: any) {
      setFormError(err.message || 'Error occurred while saving issue slip');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAction = async (issueId: number, action: 'direct-issue' | 'submit' | 'approve' | 'cancel') => {
    setActionError(null);
    try {
      const res = await apiFetch(`/api/v1/issues/${issueId}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comments: `Action ${action}` }),
      });
      if (res.ok) {
        fetchIssues();
        if (selectedIssue && selectedIssue.id === issueId) {
          const updated = await res.json();
          setSelectedIssue(updated);
        }
      } else {
        setActionError(await readApiError(res, 'Could not '+action+' the issue slip'));
      }
    } catch (err) {
      console.error(`Failed to ${action} issue slip:`, err);
      setActionError('Network error: the request could not be completed.');
    }
  };

  const filteredIssues = issues.filter(i => {
    const matchesStatus = statusFilter === 'ALL' || i.status === statusFilter;
    const matchesSearch = 
      i.issue_slip_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (i.heat_reference_number && i.heat_reference_number.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (i.receiving_department_name && i.receiving_department_name.toLowerCase().includes(searchTerm.toLowerCase()));
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="erp-view">
      {actionError && (
        <div className="erp-alert alert-danger" role="alert">
          {actionError}
        </div>
      )}
      <div className="view-header">
        <div>
          <h2>Material Issue Slips</h2>
          <p className="subtitle">
            Authorize and trace material issues across plant departments and furnace heat numbers.
          </p>
        </div>
        <div className="header-actions">
          <button className="erp-btn btn-secondary" onClick={fetchIssues}>
            <RefreshCw size={14} className="btn-icon" /> Refresh
          </button>
          {canCreateIssue ? (
            <button
              className="erp-btn btn-primary"
              onClick={() => {
                if (storesDept) setIssuingDeptId(storesDept.id);
                setShowModal(true);
              }}
            >
              <Plus size={14} className="btn-icon" /> Create Issue Slip
            </button>
          ) : (
            <div className="text-xs text-muted font-medium bg-slate-100 px-3 py-1.5 rounded flex items-center gap-1.5 border border-slate-200">
              <Lock size={12} className="text-slate-500" /> Issue creation restricted to Stores
            </div>
          )}
        </div>
      </div>

      {formWarnings.length > 0 && (
        <div className="audit-card p-3 mb-3 bg-amber-50 border-amber-200">
          <div className="flex items-center gap-2 text-amber-800 font-medium">
            <AlertTriangle size={18} /> Traceability Notice / Warnings:
          </div>
          <ul className="list-disc ml-5 mt-1 text-sm text-amber-700">
            {formWarnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      <ReferenceDataNotice refs={refs} />

      {/* Filter Toolbar */}
      <div className="filter-toolbar">
        <div className="search-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search by Slip #, Heat Ref (H-XXXX), Receiving Dept..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <span className="filter-label">Status:</span>
          {['ALL', 'DRAFT', 'SUBMITTED', 'APPROVED', 'CANCELLED'].map((st) => (
            <button
              key={st}
              className={`filter-btn ${statusFilter === st ? 'active' : ''}`}
              onClick={() => setStatusFilter(st)}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Issue Slips Table */}
      <div className="erp-table-container">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Issue Slip #</th>
              <th>Issue Date</th>
              <th>Issuing Dept</th>
              <th>Receiving Dept</th>
              <th>Furnace Heat Ref</th>
              <th>Items</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="text-center p-4">Loading issue slips...</td></tr>
            ) : filteredIssues.length === 0 ? (
              <tr><td colSpan={8} className="text-center p-4">No issue slips match current criteria.</td></tr>
            ) : (
              filteredIssues.map((issue) => (
                <tr key={issue.id} onClick={() => setSelectedIssue(issue)} className="cursor-pointer">
                  <td className="font-mono font-medium">{issue.issue_slip_number}</td>
                  <td>{issue.issue_date}</td>
                  <td>{issue.issuing_department_name}</td>
                  <td><strong>{issue.receiving_department_name}</strong></td>
                  <td>
                    {issue.heat_reference_number ? (
                      <span className="badge badge-primary flex items-center gap-1 w-fit">
                        <Flame size={12} /> {issue.heat_reference_number}
                      </span>
                    ) : '—'}
                  </td>
                  <td>{issue.lines?.length || 0} item(s)</td>
                  <td>
                    <span className={`status-pill status-${issue.status.toLowerCase()}`}>
                      {issue.status === 'APPROVED' ? '🟢 ISSUED (APPROVED)' : issue.status}
                    </span>
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-1.5">
                      {(issue.status === 'DRAFT' || issue.status === 'SUBMITTED') && canCreateIssue && (
                        <button
                          className="erp-btn btn-sm btn-primary flex items-center gap-1 font-semibold text-xs shadow-sm"
                          title="Stores direct issue directly to stock ledger"
                          onClick={() => handleAction(issue.id, 'direct-issue')}
                        >
                          <CheckCircle size={12} /> Issue Now
                        </button>
                      )}
                      {issue.status === 'APPROVED' && (
                        <span className="text-xs text-emerald-700 font-medium flex items-center gap-1">
                          <CheckCircle size={12} className="text-emerald-600" /> Issued
                        </span>
                      )}
                      {(issue.status === 'DRAFT' || issue.status === 'SUBMITTED') && canCreateIssue && (
                        <button
                          className="erp-btn btn-sm btn-danger text-xs p-1"
                          title="Cancel Slip"
                          onClick={() => handleAction(issue.id, 'cancel')}
                        >
                          <X size={12} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Detail Modal */}
      {selectedIssue && (
        <div className="modal-backdrop" onClick={() => setSelectedIssue(null)}>
          <div className="modal-content max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Issue Slip Details: {selectedIssue.issue_slip_number}</h3>
              <button className="close-btn" onClick={() => setSelectedIssue(null)}><X size={18} /></button>
            </div>
            <div className="modal-body">
              <div className="grid grid-cols-3 gap-4 mb-4 text-sm">
                <div><strong>Issue Date:</strong> {selectedIssue.issue_date}</div>
                <div><strong>Issuing Dept:</strong> {selectedIssue.issuing_department_name}</div>
                <div><strong>Receiving Dept:</strong> {selectedIssue.receiving_department_name}</div>
                <div><strong>Furnace Heat Ref:</strong> {selectedIssue.heat_reference_number || 'N/A'}</div>
                <div><strong>Status:</strong> {selectedIssue.status}</div>
                <div><strong>Created By:</strong> {selectedIssue.created_by}</div>
              </div>

              <h4 className="font-semibold mb-2">Issued Material Lines</h4>
              <table className="erp-table mb-4">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Item Code & Name</th>
                    <th>UOM</th>
                    <th>Issued Quantity</th>
                    <th>Remarks</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedIssue.lines.map((l) => (
                    <tr key={l.line_number}>
                      <td>{l.line_number}</td>
                      <td>{l.item_code} - {l.item_name}</td>
                      <td>{l.uom_code}</td>
                      <td className="font-mono font-medium">{l.quantity}</td>
                      <td>{l.remarks || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h4 className="font-semibold mb-2">Audit History</h4>
              <div className="audit-timeline">
                {selectedIssue.audit_logs?.map((log) => (
                  <div key={log.id} className="timeline-item text-xs mb-1">
                    <span className="font-semibold">{log.action}</span> by {log.actor_id} on {new Date(log.timestamp).toLocaleString()}: {log.comments}
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-footer">
              <button className="erp-btn btn-secondary" onClick={() => setSelectedIssue(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="modal-content max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleCreateIssue}>
              <div className="modal-header">
                <h3>New Material Issue Slip</h3>
                <button type="button" className="close-btn" onClick={() => setShowModal(false)}><X size={18} /></button>
              </div>
              <div className="modal-body">
                <div className="mb-3">
                  <ReferenceDataNotice refs={refs} />
                </div>
                {formError && (
                  <div className="alert-error p-3 mb-3 bg-red-50 text-red-700 text-sm rounded">
                    {formError}
                  </div>
                )}

                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div>
                    <label className="form-label">Issuing Department (Fixed)</label>
                    <div className="form-control bg-slate-100 flex items-center gap-1.5 text-slate-700 font-semibold text-xs py-2 cursor-not-allowed">
                      <Lock size={12} className="text-slate-500" />
                      {storesDept ? `${storesDept.name} (${storesDept.code})` : 'General/Stores (GNS)'}
                    </div>
                    <span className="text-xs text-muted mt-1 block">Material issue strictly originates from Stores</span>
                  </div>
                  <div>
                    <label className="form-label">Issue Timestamp</label>
                    <div className="form-control bg-slate-100 text-slate-700 font-medium text-xs py-2">
                      Auto-Captured Today ({new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })})
                    </div>
                    <span className="text-xs text-muted mt-1 block">System records current creation timestamp</span>
                  </div>
                  <div>
                    <label className="form-label required">Receiving Department *</label>
                    <select
                      className="form-control"
                      value={receivingDeptId}
                      onChange={(e) => {
                        const val = e.target.value ? Number(e.target.value) : '';
                        setReceivingDeptId(val);
                        const dept = departments.find(d => d.id === val);
                        const isFdy = dept?.code === 'FDY' || dept?.name?.toLowerCase().includes('foundry');
                        if (!isFdy) setHeatRefNo('');
                      }}
                      required
                    >
                      <option value="">{refs.placeholder('departments', '-- Select Receiving Dept --')}</option>
                      {departments.filter(d => d.id !== (storesDept?.id || 4)).map((d) => (
                        <option key={d.id} value={d.id}>{d.name} ({d.code})</option>
                      ))}
                    </select>
                    <span className="text-xs text-muted mt-1 block">Plant unit consuming the materials</span>
                  </div>
                </div>

                {/* Conditional Heat Reference Number: Only visible when Receiving Department is Foundry */}
                {isFoundrySelected ? (
                  <div className="mb-4 p-3.5 bg-amber-50/70 border border-amber-300 rounded-lg shadow-sm">
                    <div className="flex justify-between items-center mb-2 pb-1 border-b border-amber-200">
                      <div className="flex items-center gap-1.5 text-amber-950 font-bold text-xs">
                        <Flame size={14} className="text-amber-600" />
                        <span>Active Furnace Heat Allocation (Foundry Mandatory) *</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        {onNavigate && (
                          <button
                            type="button"
                            onClick={() => {
                              setShowModal(false);
                              onNavigate('heat-master');
                            }}
                            className="text-[11px] text-blue-700 hover:text-blue-900 underline font-semibold flex items-center gap-1 bg-white px-2 py-0.5 rounded border border-blue-200"
                            title="Open the Furnace Heat Master to register, open, or close heats"
                          >
                            Furnace Heat Master →
                          </button>
                        )}
                        <span className="badge badge-success text-[10px]">
                          🟢 {filteredHeats.length} Active Heat(s) Open
                        </span>
                      </div>
                    </div>

                    {availableHeats.length === 0 ? (
                      <div className="p-3 bg-amber-100/80 border border-amber-300 rounded text-xs text-amber-900">
                        <strong>⚠️ No Active Heat currently open in Foundry.</strong>
                        <p className="mt-1 text-[11px] text-amber-800">
                          Under VSPL Material Control governance, Stores cannot issue raw materials without an Active Heat open. Please request the Foundry Manager to open an Active Heat in the <strong>Furnace Heat Master</strong> module before creating this issue slip.
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <div className="grid grid-cols-12 gap-2">
                          {availableHeats.length > 5 && (
                            <div className="col-span-4">
                              <input
                                type="text"
                                className="form-control text-xs"
                                placeholder="Filter active heats..."
                                value={heatSearchFilter}
                                onChange={(e) => setHeatSearchFilter(e.target.value)}
                              />
                            </div>
                          )}
                          <div className={availableHeats.length > 5 ? "col-span-8" : "col-span-12"}>
                            <select
                              className="form-control text-xs font-mono font-medium"
                              value={heatRefNo}
                              onChange={(e) => setHeatRefNo(e.target.value)}
                              required
                            >
                              <option value="">-- Select Active Furnace Heat ({filteredHeats.length} Active Heats) --</option>
                              {filteredHeats.map((h: any) => {
                                const norm = h.normalized_heat_number || (String(h.heat_number).startsWith('H-') ? h.heat_number : `H-${h.heat_number}`);
                                return (
                                  <option key={h.id || h.heat_number} value={norm}>
                                    🟢 {norm} · {h.heat_date || 'Today'} (Furnace: {h.furnace_id || 'F1'}{h.shift ? ` · Shift ${h.shift}` : ''})
                                  </option>
                                );
                              })}
                            </select>
                          </div>
                        </div>
                        {heatRefNo ? (
                          <div className="space-y-1 mt-1">
                            <div className="text-xs text-amber-900 font-medium flex items-center justify-between bg-amber-100/70 px-2 py-1 rounded">
                              <span className="flex items-center gap-1.5">
                                <CheckCircle size={12} className="text-emerald-600" />
                                Allocated to Active Heat: <strong className="font-mono text-emerald-800">{heatRefNo}</strong>
                              </span>
                              {issues.filter(i => (i.heat_reference_number || '').trim().toLowerCase() === heatRefNo.trim().toLowerCase()).length > 0 && (
                                <span className="badge badge-info text-[10px]">
                                  {issues.filter(i => (i.heat_reference_number || '').trim().toLowerCase() === heatRefNo.trim().toLowerCase()).length} Prior Issue(s) on this Heat
                                </span>
                              )}
                            </div>
                            {issues.filter(i => (i.heat_reference_number || '').trim().toLowerCase() === heatRefNo.trim().toLowerCase()).length > 0 && (
                              <div className="text-[11px] text-blue-800 bg-blue-50/90 p-2 rounded border border-blue-200">
                                ℹ️ <strong>Multiple Issues Supported:</strong> {issues.filter(i => (i.heat_reference_number || '').trim().toLowerCase() === heatRefNo.trim().toLowerCase()).length} prior issue slip(s) already recorded for <code>{heatRefNo}</code>. Any additional materials issued now will accumulate directly into this heat's total batch consumption and value.
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="text-[11px] text-slate-700 bg-white/80 p-2 rounded border border-amber-200 mt-1">
                            <div className="font-semibold text-amber-900 mb-0.5 flex items-center justify-between">
                              <span>Master Registry: <strong>Furnace Heat Log</strong></span>
                              {onNavigate && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    setShowModal(false);
                                    onNavigate('heat-log');
                                  }}
                                  className="text-blue-600 hover:underline text-[10px]"
                                >
                                  Go to Master →
                                </button>
                              )}
                            </div>
                            Select the active furnace heat being charged. Active heats originate in the <strong>Furnace Heat Log</strong> master where the Foundry Manager opens and closes heats. Only active heats appear here so Stores cannot mistype a heat number.
                          </div>
                        )}
                      </div>
                    )}

                    <div className="mt-2.5 pt-2 border-t border-amber-200/60">
                      <label className="form-label text-xs">Notes / Issue Justification</label>
                      <input
                        type="text"
                        className="form-control text-xs"
                        placeholder="Furnace charge, alloy adjustment, etc."
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                      />
                    </div>
                  </div>
                ) : (
                  <div className="mb-4">
                    <label className="form-label">Notes / Issue Justification</label>
                    <input
                      type="text"
                      className="form-control text-xs"
                      placeholder="Work order reference, departmental requisition, or maintenance memo..."
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>
                )}

                {/* Lines with live Search Filter */}
                <div className="mb-4">
                  <div className="flex justify-between items-center mb-2">
                    <h4 className="font-semibold text-sm">Issued Items ({lines.length})</h4>
                    <div className="flex items-center gap-2">
                      <div style={{ position: 'relative', width: '220px' }}>
                        <Search size={12} style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
                        <input
                          type="text"
                          className="form-control text-xs"
                          style={{ paddingLeft: '26px', height: '28px' }}
                          placeholder={`Filter ${items.length} materials...`}
                          value={itemSearchFilter}
                          onChange={(e) => setItemSearchFilter(e.target.value)}
                        />
                      </div>
                      <button type="button" className="erp-btn btn-sm btn-secondary" onClick={handleAddLine}>
                        <Plus size={12} /> Add Item
                      </button>
                    </div>
                  </div>

                  {lines.map((l, idx) => (
                    <div key={idx} className="grid grid-cols-12 gap-2 mb-2 items-end bg-slate-50 p-2 rounded">
                      <div className="col-span-6">
                        <label className="form-label text-xs">Material Item *</label>
                        <select
                          className="form-control text-xs"
                          value={l.material_item_id}
                          onChange={(e) => handleLineChange(idx, 'material_item_id', e.target.value)}
                          required
                        >
                          <option value="">{refs.placeholder('items', '-- Select Material Item --')}</option>
                          {filteredItems.map((it) => (
                            <option key={it.id} value={it.id}>{it.item_code} - {it.name}</option>
                          ))}
                        </select>
                      </div>
                      <div className="col-span-2">
                        <label className="form-label text-xs">UOM *</label>
                        <select
                          className="form-control text-xs"
                          value={l.uom_id}
                          onChange={(e) => handleLineChange(idx, 'uom_id', e.target.value)}
                          required
                        >
                          <option value="">{refs.placeholder('uoms', '-- UOM --')}</option>
                          {uoms.map((u) => (
                            <option key={u.id} value={u.id}>{u.code}</option>
                          ))}
                        </select>
                      </div>
                      <div className="col-span-3">
                        <label className="form-label text-xs">Quantity *</label>
                        <input
                          type="number"
                          step="any"
                          className="form-control text-xs"
                          placeholder="e.g. 25.5"
                          value={l.quantity}
                          onChange={(e) => handleLineChange(idx, 'quantity', e.target.value)}
                          required
                        />
                      </div>
                      <div className="col-span-1 text-center">
                        {lines.length > 1 && (
                          <button
                            type="button"
                            className="erp-btn btn-sm btn-danger p-1"
                            onClick={() => handleRemoveLine(idx)}
                            title="Remove Line"
                          >
                            <X size={14} />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="erp-btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="erp-btn btn-primary font-semibold" disabled={submitting || refs.unavailable}>
                  {submitting ? 'Issuing Materials...' : '⚡ Issue Materials (Direct to Stock Ledger)'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
