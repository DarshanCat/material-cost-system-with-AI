import React, { useState, useEffect, useMemo } from 'react';
import {
  CheckCircle2,
  Clock,
  FileText,
  ShoppingCart,
  Truck,
  FileCheck,
  CreditCard,
  AlertCircle,
  Search,
  RefreshCw,
  ShieldCheck,
  XCircle,
  Eye,
  X,
  Send,
  Building2,
  Calendar
} from 'lucide-react';
import type { ModuleId, UserRole } from '../types';
import { apiFetch } from '../api/client';

export interface P2PCycleViewProps {
  currentRole: UserRole;
  currentUserId: string;
  onNavigate?: (module: ModuleId, context?: any) => void;
}

export type P2PStage = 
  | 'PR_PENDING_PLANT_HEAD'
  | 'PR_APPROVED_NEEDS_PO'
  | 'PO_PENDING_CEO'
  | 'PO_APPROVED_NEEDS_PLACEMENT'
  | 'ORDER_PLACED_AWAITING_GRN'
  | 'GRN_PENDING_QA'
  | 'QA_ACCEPTED_PENDING_PAYMENT'
  | 'PAYMENT_SETTLED_CLOSED'
  | 'REJECTED';

export interface P2PEntry {
  key: string;
  pr?: any;
  po?: any;
  grn?: any;
  currentStage: P2PStage;
  stageName: string;
  stageStep: number;
  badgeClass: string;
  vendorName: string;
  totalAmount: number;
  itemSummary: string;
  actionRequired: string;
  nextActorRole: string;
}

export const P2PCycleView: React.FC<P2PCycleViewProps> = ({
  currentRole: _currentRole,
  currentUserId: _currentUserId,
  onNavigate,
}) => {
  const [prs, setPrs] = useState<any[]>([]);
  const [pos, setPos] = useState<any[]>([]);
  const [grns, setGrns] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [stageFilter, setStageFilter] = useState<string>('ALL');
  const [selectedEntry, setSelectedEntry] = useState<P2PEntry | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchP2PData = async () => {
    setLoading(true);
    setActionError(null);
    try {
      const [prRes, poRes, grnRes] = await Promise.all([
        apiFetch('/api/v1/purchase-requests/').catch(() => null),
        apiFetch('/api/v1/purchase-orders/').catch(() => null),
        apiFetch('/api/v1/grn/').catch(() => null),
      ]);

      if (prRes && prRes.ok) {
        const prData = await prRes.json();
        setPrs(Array.isArray(prData) ? prData : (prData.items || []));
      }
      if (poRes && poRes.ok) {
        const poData = await poRes.json();
        setPos(Array.isArray(poData) ? poData : (poData.items || []));
      }
      if (grnRes && grnRes.ok) {
        const grnData = await grnRes.json();
        setGrns(Array.isArray(grnData) ? grnData : (grnData.items || []));
      }
    } catch (err: any) {
      console.error('Error fetching P2P lifecycle data:', err);
      setActionError('Could not refresh full P2P lifecycle state.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchP2PData();
  }, []);

  // Correlate PR -> PO -> Placement -> GRN -> QA -> Payment
  const p2pEntries: P2PEntry[] = useMemo(() => {
    const list: P2PEntry[] = [];
    const matchedPoIds = new Set<number>();
    const matchedPrIds = new Set<number>();

    // 1. Process from PRs first
    prs.forEach((pr) => {
      matchedPrIds.add(pr.id);
      // Find matching PO(s)
      const linkedPos = pos.filter((p) => p.pr_id === pr.id || p.pr_number === pr.pr_number);

      if (linkedPos.length === 0) {
        // PR with no PO yet
        let currentStage: P2PStage = 'PR_PENDING_PLANT_HEAD';
        let stageName = 'PR: Pending Plant Head';
        let stageStep = 1;
        let badgeClass = 'badge-warning';
        let actionRequired = 'Plant Head review & 1st Layer authorization';
        let nextActorRole = 'Plant Head (Management)';

        if (pr.status === 'APPROVED') {
          currentStage = 'PR_APPROVED_NEEDS_PO';
          stageName = 'PR Approved: Awaiting PO';
          stageStep = 2;
          badgeClass = 'badge-primary';
          actionRequired = 'SCM / Purchase to draft Purchase Order';
          nextActorRole = 'SCM / Purchase';
        } else if (pr.status === 'REJECTED') {
          currentStage = 'REJECTED';
          stageName = 'PR Rejected';
          stageStep = 1;
          badgeClass = 'badge-danger';
          actionRequired = 'Review rejection remarks from Plant Head';
          nextActorRole = 'SCM Planning';
        }

        const itemSummary = pr.lines?.map((l: any) => `${l.material_item_name || l.item_name || 'Item'} (${l.quantity} ${l.uom_code || ''})`).join(', ') || 'General Requisition';

        list.push({
          key: `pr-${pr.id}`,
          pr,
          po: null,
          grn: null,
          currentStage,
          stageName,
          stageStep,
          badgeClass,
          vendorName: 'Awaiting PO Allocation',
          totalAmount: 0,
          itemSummary,
          actionRequired,
          nextActorRole,
        });
      } else {
        // Each linked PO creates a tracked pipeline
        linkedPos.forEach((po) => {
          matchedPoIds.add(po.id);
          const linkedGrns = grns.filter((g) => g.purchase_order_id === po.id || g.purchase_order_number === po.po_number);
          const primaryGrn = linkedGrns[0] || null;

          let currentStage: P2PStage = 'PO_PENDING_CEO';
          let stageName = 'PO: Pending CEO / MD';
          let stageStep = 3;
          let badgeClass = 'badge-warning';
          let actionRequired = 'CEO / MD Final Purchase Authorization';
          let nextActorRole = 'CEO / MD (Management)';

          if (po.status === 'APPROVED') {
            currentStage = 'PO_APPROVED_NEEDS_PLACEMENT';
            stageName = 'PO Approved: Needs Vendor Placement';
            stageStep = 4;
            badgeClass = 'badge-info';
            actionRequired = 'Place Order with Vendor & Record Date/Ref';
            nextActorRole = 'SCM / Purchase';
          } else if (po.status === 'ORDER_PLACED') {
            if (!primaryGrn) {
              currentStage = 'ORDER_PLACED_AWAITING_GRN';
              stageName = 'Order Placed: Awaiting Stores Delivery';
              stageStep = 5;
              badgeClass = 'badge-info';
              actionRequired = 'Stores to inward goods against PO on arrival';
              nextActorRole = 'Stores Department';
            } else if (primaryGrn.status === 'DRAFT' || primaryGrn.status === 'SUBMITTED') {
              currentStage = 'GRN_PENDING_QA';
              stageName = 'GRN Inwarded: Awaiting QA Acceptance';
              stageStep = 6;
              badgeClass = 'badge-primary';
              actionRequired = 'Quality Head / QA inspection signoff';
              nextActorRole = 'Quality Assurance';
            } else if (primaryGrn.status === 'APPROVED') {
              if (primaryGrn.payment_status === 'PAID') {
                currentStage = 'PAYMENT_SETTLED_CLOSED';
                stageName = 'Fully Settled & Closed';
                stageStep = 8;
                badgeClass = 'badge-success';
                actionRequired = 'Complete: 100% P2P Cycle Satisfied';
                nextActorRole = 'Completed';
              } else {
                currentStage = 'QA_ACCEPTED_PENDING_PAYMENT';
                stageName = 'QA Passed: Awaiting Payment Settlement';
                stageStep = 7;
                badgeClass = 'badge-success';
                actionRequired = 'Accounts to process vendor invoice & voucher';
                nextActorRole = 'Accounts Department';
              }
            } else if (primaryGrn.status === 'REJECTED') {
              currentStage = 'REJECTED';
              stageName = 'GRN Rejected by QA';
              stageStep = 6;
              badgeClass = 'badge-danger';
              actionRequired = 'Resolve material rejection with supplier';
              nextActorRole = 'SCM / Vendor';
            }
          }

          const itemSummary = po.lines?.map((l: any) => `${l.material_item_name || l.item_name || 'Item'} (${l.quantity} ${l.uom_code || ''})`).join(', ') || pr.justification;

          list.push({
            key: `pr-${pr.id}-po-${po.id}`,
            pr,
            po,
            grn: primaryGrn,
            currentStage,
            stageName,
            stageStep,
            badgeClass,
            vendorName: po.vendor_name || 'Vendor',
            totalAmount: Number(po.total_amount || 0),
            itemSummary,
            actionRequired,
            nextActorRole,
          });
        });
      }
    });

    // 2. Add POs without PR (legacy / direct purchase records)
    pos.forEach((po) => {
      if (!matchedPoIds.has(po.id)) {
        const linkedGrns = grns.filter((g) => g.purchase_order_id === po.id || g.purchase_order_number === po.po_number);
        const primaryGrn = linkedGrns[0] || null;

        let currentStage: P2PStage = 'PO_PENDING_CEO';
        let stageName = 'PO: Pending CEO / MD';
        let stageStep = 3;
        let badgeClass = 'badge-warning';
        let actionRequired = 'CEO / MD Final Authorization';
        let nextActorRole = 'CEO / MD';

        if (po.status === 'APPROVED') {
          currentStage = 'PO_APPROVED_NEEDS_PLACEMENT';
          stageName = 'PO Approved: Needs Placement';
          stageStep = 4;
          badgeClass = 'badge-info';
          actionRequired = 'Dispatch order to vendor';
          nextActorRole = 'SCM / Purchase';
        } else if (po.status === 'ORDER_PLACED') {
          if (!primaryGrn) {
            currentStage = 'ORDER_PLACED_AWAITING_GRN';
            stageName = 'Order Placed: Awaiting Stores Delivery';
            stageStep = 5;
            badgeClass = 'badge-info';
            actionRequired = 'Stores to inward goods against PO on arrival';
            nextActorRole = 'Stores';
          } else if (primaryGrn.status === 'APPROVED') {
            if (primaryGrn.payment_status === 'PAID') {
              currentStage = 'PAYMENT_SETTLED_CLOSED';
              stageName = 'Settled & Closed';
              stageStep = 8;
              badgeClass = 'badge-success';
              actionRequired = 'Fully Cleared';
              nextActorRole = 'Completed';
            } else {
              currentStage = 'QA_ACCEPTED_PENDING_PAYMENT';
              stageName = 'QA Passed: Awaiting Payment';
              stageStep = 7;
              badgeClass = 'badge-success';
              actionRequired = 'Accounts payment voucher';
              nextActorRole = 'Accounts';
            }
          } else {
            currentStage = 'GRN_PENDING_QA';
            stageName = 'GRN Inwarded: Awaiting QA';
            stageStep = 6;
            badgeClass = 'badge-primary';
            actionRequired = 'QA inspection signoff';
            nextActorRole = 'Quality Assurance';
          }
        }

        const itemSummary = po.lines?.map((l: any) => `${l.material_item_name || l.item_name || 'Item'} (${l.quantity} ${l.uom_code || ''})`).join(', ') || 'Direct Purchase Order';

        list.push({
          key: `po-${po.id}`,
          pr: null,
          po,
          grn: primaryGrn,
          currentStage,
          stageName,
          stageStep,
          badgeClass,
          vendorName: po.vendor_name || 'Vendor',
          totalAmount: Number(po.total_amount || 0),
          itemSummary,
          actionRequired,
          nextActorRole,
        });
      }
    });

    return list;
  }, [prs, pos, grns]);

  // Stage Metrics Counts
  const counts = useMemo(() => {
    return {
      total: p2pEntries.length,
      prPending: p2pEntries.filter(e => e.currentStage === 'PR_PENDING_PLANT_HEAD').length,
      prApproved: p2pEntries.filter(e => e.currentStage === 'PR_APPROVED_NEEDS_PO').length,
      poPending: p2pEntries.filter(e => e.currentStage === 'PO_PENDING_CEO').length,
      poApproved: p2pEntries.filter(e => e.currentStage === 'PO_APPROVED_NEEDS_PLACEMENT').length,
      orderPlaced: p2pEntries.filter(e => e.currentStage === 'ORDER_PLACED_AWAITING_GRN').length,
      grnPendingQA: p2pEntries.filter(e => e.currentStage === 'GRN_PENDING_QA').length,
      qaPassed: p2pEntries.filter(e => e.currentStage === 'QA_ACCEPTED_PENDING_PAYMENT').length,
      closed: p2pEntries.filter(e => e.currentStage === 'PAYMENT_SETTLED_CLOSED').length,
    };
  }, [p2pEntries]);

  // Filtered entries
  const filteredEntries = useMemo(() => {
    return p2pEntries.filter((entry) => {
      const matchesStage = 
        stageFilter === 'ALL' ||
        (stageFilter === 'PR_STAGE' && (entry.currentStage === 'PR_PENDING_PLANT_HEAD' || entry.currentStage === 'PR_APPROVED_NEEDS_PO')) ||
        (stageFilter === 'PO_STAGE' && (entry.currentStage === 'PO_PENDING_CEO' || entry.currentStage === 'PO_APPROVED_NEEDS_PLACEMENT')) ||
        (stageFilter === 'ORDER_PLACED' && entry.currentStage === 'ORDER_PLACED_AWAITING_GRN') ||
        (stageFilter === 'GRN_QA' && (entry.currentStage === 'GRN_PENDING_QA' || entry.currentStage === 'QA_ACCEPTED_PENDING_PAYMENT')) ||
        (stageFilter === 'CLOSED' && entry.currentStage === 'PAYMENT_SETTLED_CLOSED') ||
        entry.currentStage === stageFilter;

      const q = searchTerm.toLowerCase().trim();
      const matchesSearch = !q ||
        (entry.pr?.pr_number && entry.pr.pr_number.toLowerCase().includes(q)) ||
        (entry.po?.po_number && entry.po.po_number.toLowerCase().includes(q)) ||
        (entry.grn?.grn_number && entry.grn.grn_number.toLowerCase().includes(q)) ||
        (entry.vendorName && entry.vendorName.toLowerCase().includes(q)) ||
        (entry.itemSummary && entry.itemSummary.toLowerCase().includes(q)) ||
        (entry.stageName && entry.stageName.toLowerCase().includes(q));

      return matchesStage && matchesSearch;
    });
  }, [p2pEntries, stageFilter, searchTerm]);

  return (
    <div className="erp-view">
      {actionError && (
        <div className="erp-alert alert-danger mb-3" role="alert">
          {actionError}
        </div>
      )}

      {/* Header */}
      <div className="view-header">
        <div>
          <div className="flex items-center gap-2">
            <h2>Procure-to-Pay (P2P) Lifecycle Control</h2>
            <span className="badge badge-success text-xs font-semibold px-2 py-0.5">End-to-End Governance</span>
          </div>
          <p className="subtitle">
            Enterprise procurement audit pipeline: <strong>PR (SCM Planning)</strong> &rarr; <strong>Plant Head Approval</strong> &rarr; <strong>PO (Purchase)</strong> &rarr; <strong>CEO / MD Approval</strong> &rarr; <strong>Order Placed</strong> &rarr; <strong>GRN (Stores)</strong> &rarr; <strong>QA Acceptance</strong> &rarr; <strong>Payment & Closure</strong>.
          </p>
        </div>
        <div className="header-actions">
          <button className="erp-btn btn-secondary" onClick={fetchP2PData} disabled={loading}>
            <RefreshCw size={14} className={`btn-icon ${loading ? 'animate-spin' : ''}`} /> Refresh Pipeline
          </button>
          {onNavigate && (
            <>
              <button 
                className="erp-btn btn-secondary"
                onClick={() => onNavigate('purchase-requests')}
              >
                <FileText size={14} className="btn-icon" /> Open PRs
              </button>
              <button 
                className="erp-btn btn-primary"
                onClick={() => onNavigate('purchase-orders')}
              >
                <ShoppingCart size={14} className="btn-icon" /> Open POs
              </button>
            </>
          )}
        </div>
      </div>

      {/* Visual Pipeline Funnel Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-5">
        {/* Step 1: PR Layer */}
        <div 
          className={`p-3 rounded-lg border cursor-pointer transition-all ${stageFilter === 'PR_STAGE' ? 'bg-amber-100/70 border-amber-500 shadow-md ring-2 ring-amber-400' : 'bg-white border-slate-200 hover:border-amber-400'}`}
          onClick={() => setStageFilter(stageFilter === 'PR_STAGE' ? 'ALL' : 'PR_STAGE')}
        >
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span className="font-bold uppercase tracking-wider text-amber-700">Stage 1: PR Planning</span>
            <FileText size={14} className="text-amber-600" />
          </div>
          <div className="text-2xl font-black text-slate-800">{counts.prPending + counts.prApproved}</div>
          <div className="text-[11px] text-slate-600 mt-1 flex justify-between">
            <span className="text-amber-700 font-semibold">{counts.prPending} Awaiting Plant Head</span>
            <span className="text-slate-400">{counts.prApproved} Approved</span>
          </div>
        </div>

        {/* Step 2: PO Layer */}
        <div 
          className={`p-3 rounded-lg border cursor-pointer transition-all ${stageFilter === 'PO_STAGE' ? 'bg-blue-100/70 border-blue-500 shadow-md ring-2 ring-blue-400' : 'bg-white border-slate-200 hover:border-blue-400'}`}
          onClick={() => setStageFilter(stageFilter === 'PO_STAGE' ? 'ALL' : 'PO_STAGE')}
        >
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span className="font-bold uppercase tracking-wider text-blue-700">Stage 2: PO Approval</span>
            <ShoppingCart size={14} className="text-blue-600" />
          </div>
          <div className="text-2xl font-black text-slate-800">{counts.poPending + counts.poApproved}</div>
          <div className="text-[11px] text-slate-600 mt-1 flex justify-between">
            <span className="text-amber-700 font-semibold">{counts.poPending} Awaiting CEO</span>
            <span className="text-blue-600 font-semibold">{counts.poApproved} To Place</span>
          </div>
        </div>

        {/* Step 3: Order Placed */}
        <div 
          className={`p-3 rounded-lg border cursor-pointer transition-all ${stageFilter === 'ORDER_PLACED' ? 'bg-cyan-100/70 border-cyan-500 shadow-md ring-2 ring-cyan-400' : 'bg-white border-slate-200 hover:border-cyan-400'}`}
          onClick={() => setStageFilter(stageFilter === 'ORDER_PLACED' ? 'ALL' : 'ORDER_PLACED')}
        >
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span className="font-bold uppercase tracking-wider text-cyan-700">Stage 3: Placed Orders</span>
            <Truck size={14} className="text-cyan-600" />
          </div>
          <div className="text-2xl font-black text-slate-800">{counts.orderPlaced}</div>
          <div className="text-[11px] text-slate-600 mt-1">
            <span className="text-cyan-700 font-medium">Vendor Ack &bull; In-Transit</span>
          </div>
        </div>

        {/* Step 4: GRN Inward */}
        <div 
          className={`p-3 rounded-lg border cursor-pointer transition-all ${stageFilter === 'GRN_PENDING_QA' ? 'bg-indigo-100/70 border-indigo-500 shadow-md ring-2 ring-indigo-400' : 'bg-white border-slate-200 hover:border-indigo-400'}`}
          onClick={() => setStageFilter(stageFilter === 'GRN_PENDING_QA' ? 'ALL' : 'GRN_PENDING_QA')}
        >
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span className="font-bold uppercase tracking-wider text-indigo-700">Stage 4: GRN Inward</span>
            <Building2 size={14} className="text-indigo-600" />
          </div>
          <div className="text-2xl font-black text-slate-800">{counts.grnPendingQA}</div>
          <div className="text-[11px] text-slate-600 mt-1">
            <span className="text-indigo-700 font-medium">Stores Inward &bull; Pending QA</span>
          </div>
        </div>

        {/* Step 5: QA Accepted */}
        <div 
          className={`p-3 rounded-lg border cursor-pointer transition-all ${stageFilter === 'QA_ACCEPTED_PENDING_PAYMENT' ? 'bg-teal-100/70 border-teal-500 shadow-md ring-2 ring-teal-400' : 'bg-white border-slate-200 hover:border-teal-400'}`}
          onClick={() => setStageFilter(stageFilter === 'QA_ACCEPTED_PENDING_PAYMENT' ? 'ALL' : 'QA_ACCEPTED_PENDING_PAYMENT')}
        >
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span className="font-bold uppercase tracking-wider text-teal-700">Stage 5: QA Accepted</span>
            <FileCheck size={14} className="text-teal-600" />
          </div>
          <div className="text-2xl font-black text-slate-800">{counts.qaPassed}</div>
          <div className="text-[11px] text-slate-600 mt-1">
            <span className="text-teal-700 font-medium">Quality Certified &bull; In Accounts</span>
          </div>
        </div>

        {/* Step 6: Payment & Closure */}
        <div 
          className={`p-3 rounded-lg border cursor-pointer transition-all ${stageFilter === 'CLOSED' ? 'bg-emerald-100/70 border-emerald-500 shadow-md ring-2 ring-emerald-400' : 'bg-white border-slate-200 hover:border-emerald-400'}`}
          onClick={() => setStageFilter(stageFilter === 'CLOSED' ? 'ALL' : 'CLOSED')}
        >
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span className="font-bold uppercase tracking-wider text-emerald-700">Stage 6: Settled</span>
            <CreditCard size={14} className="text-emerald-600" />
          </div>
          <div className="text-2xl font-black text-slate-800">{counts.closed}</div>
          <div className="text-[11px] text-slate-600 mt-1">
            <span className="text-emerald-700 font-medium">Paid &bull; Closed P2P Cycle</span>
          </div>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="erp-card mb-4 p-3 bg-slate-50 border border-slate-200">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-1 max-w-md">
            <div style={{ position: 'relative', width: '100%' }}>
              <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
              <input
                type="text"
                className="form-control text-xs"
                style={{ paddingLeft: '32px' }}
                placeholder="Search PR #, PO #, Vendor, GRN #, or materials..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            {searchTerm && (
              <button 
                className="erp-btn btn-xs btn-secondary" 
                onClick={() => setSearchTerm('')}
              >
                Clear
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-600">Filter Stage:</span>
            <select
              className="form-control text-xs"
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
            >
              <option value="ALL">All P2P Stages ({p2pEntries.length})</option>
              <option value="PR_STAGE">Stage 1: PR Layer ({counts.prPending + counts.prApproved})</option>
              <option value="PR_PENDING_PLANT_HEAD">&bull; PR Awaiting Plant Head ({counts.prPending})</option>
              <option value="PR_APPROVED_NEEDS_PO">&bull; PR Approved (Needs PO) ({counts.prApproved})</option>
              <option value="PO_STAGE">Stage 2: PO Layer ({counts.poPending + counts.poApproved})</option>
              <option value="PO_PENDING_CEO">&bull; PO Awaiting CEO / MD ({counts.poPending})</option>
              <option value="PO_APPROVED_NEEDS_PLACEMENT">&bull; PO Approved (Needs Vendor Order) ({counts.poApproved})</option>
              <option value="ORDER_PLACED">Stage 3: Placed with Vendor ({counts.orderPlaced})</option>
              <option value="GRN_QA">Stage 4-5: Inward & QA ({counts.grnPendingQA + counts.qaPassed})</option>
              <option value="GRN_PENDING_QA">&bull; GRN Inwarded (Pending QA) ({counts.grnPendingQA})</option>
              <option value="QA_ACCEPTED_PENDING_PAYMENT">&bull; QA Accepted (Pending Payment) ({counts.qaPassed})</option>
              <option value="CLOSED">Stage 6: Fully Paid & Closed ({counts.closed})</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Traceability Table */}
      <div className="erp-card overflow-hidden">
        <div className="p-3 border-b border-slate-200 bg-white flex justify-between items-center">
          <div className="font-bold text-sm text-slate-800 flex items-center gap-2">
            <ShieldCheck size={16} className="text-emerald-600" />
            <span>Master P2P Traceability Ledger ({filteredEntries.length} Records)</span>
          </div>
          <span className="text-xs text-slate-500">
            Showing complete lifecycle from Planning Requisition through Bank Settlement
          </span>
        </div>

        {loading ? (
          <div className="p-8 text-center text-slate-500">
            <RefreshCw size={24} className="animate-spin mx-auto mb-2 text-primary" />
            <p>Loading enterprise P2P lifecycle matrix...</p>
          </div>
        ) : filteredEntries.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            <AlertCircle size={28} className="mx-auto mb-2 text-slate-400" />
            <p className="font-medium">No procurement records found matching the filter.</p>
            <p className="text-xs text-slate-400 mt-1">Try resetting the stage filter or creating a new Purchase Request (PR).</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="erp-table">
              <thead>
                <tr>
                  <th style={{ width: '130px' }}>1. PR Reference</th>
                  <th style={{ width: '130px' }}>2. Plant Head (L1)</th>
                  <th style={{ width: '140px' }}>3. Purchase Order</th>
                  <th style={{ width: '130px' }}>4. CEO / MD</th>
                  <th style={{ width: '140px' }}>5. Order Placed</th>
                  <th style={{ width: '130px' }}>6. Stores GRN</th>
                  <th style={{ width: '120px' }}>7. QA Acceptance</th>
                  <th style={{ width: '120px' }}>8. Accounts Payment</th>
                  <th style={{ width: '110px' }} className="text-center">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredEntries.map((entry) => {
                  const pr = entry.pr;
                  const po = entry.po;
                  const grn = entry.grn;

                  return (
                    <tr key={entry.key} className="hover:bg-slate-50/70">
                      {/* 1. PR Info */}
                      <td>
                        {pr ? (
                          <div>
                            <div className="font-mono font-bold text-xs text-slate-900">{pr.pr_number}</div>
                            <div className="text-[11px] text-slate-500 flex items-center gap-1">
                              <Calendar size={10} /> {pr.request_date || pr.created_at?.slice(0, 10)}
                            </div>
                            <div className="text-[11px] text-slate-600 truncate max-w-[120px]" title={pr.justification}>
                              {pr.department_name || 'SCM Planning'}
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400 italic">Direct PO (No PR)</span>
                        )}
                      </td>

                      {/* 2. Plant Head Approval */}
                      <td>
                        {pr ? (
                          pr.status === 'APPROVED' ? (
                            <div>
                              <span className="badge badge-success text-[10px] font-semibold flex items-center gap-1 w-fit">
                                <CheckCircle2 size={10} /> Approved
                              </span>
                              <div className="text-[10px] text-slate-500 mt-0.5">
                                by {pr.plant_head_approved_by || 'Plant Head'}
                              </div>
                            </div>
                          ) : pr.status === 'REJECTED' ? (
                            <span className="badge badge-danger text-[10px] font-semibold flex items-center gap-1 w-fit">
                              <XCircle size={10} /> Rejected
                            </span>
                          ) : (
                            <div>
                              <span className="badge badge-warning text-[10px] font-semibold flex items-center gap-1 w-fit">
                                <Clock size={10} /> Pending L1
                              </span>
                              <div className="text-[10px] text-amber-700 font-medium mt-0.5">
                                Awaiting Plant Head
                              </div>
                            </div>
                          )
                        ) : (
                          <span className="text-slate-400 text-xs">—</span>
                        )}
                      </td>

                      {/* 3. PO Reference */}
                      <td>
                        {po ? (
                          <div>
                            <div className="font-mono font-bold text-xs text-blue-900">{po.po_number}</div>
                            <div className="text-[11px] text-slate-700 font-medium truncate max-w-[130px]" title={entry.vendorName}>
                              {entry.vendorName}
                            </div>
                            {entry.totalAmount > 0 && (
                              <div className="text-[11px] font-mono text-emerald-700 font-bold flex items-center gap-0.5">
                                ₹{entry.totalAmount.toLocaleString('en-IN')}
                              </div>
                            )}
                          </div>
                        ) : (
                          <div>
                            <span className="badge badge-secondary text-[10px] font-normal">Awaiting PO</span>
                            <div className="text-[10px] text-slate-400 mt-0.5">PR Approved</div>
                          </div>
                        )}
                      </td>

                      {/* 4. CEO / MD Approval */}
                      <td>
                        {po ? (
                          po.status === 'APPROVED' || po.status === 'ORDER_PLACED' ? (
                            <div>
                              <span className="badge badge-success text-[10px] font-semibold flex items-center gap-1 w-fit">
                                <CheckCircle2 size={10} /> Approved
                              </span>
                              <div className="text-[10px] text-slate-500 mt-0.5">CEO / MD Authorized</div>
                            </div>
                          ) : po.status === 'REJECTED' ? (
                            <span className="badge badge-danger text-[10px] font-semibold">Rejected</span>
                          ) : (
                            <div>
                              <span className="badge badge-warning text-[10px] font-semibold flex items-center gap-1 w-fit">
                                <Clock size={10} /> Pending CEO
                              </span>
                              <div className="text-[10px] text-amber-700 font-medium mt-0.5">Management Signoff</div>
                            </div>
                          )
                        ) : (
                          <span className="text-slate-400 text-xs">—</span>
                        )}
                      </td>

                      {/* 5. Order Placed with Vendor */}
                      <td>
                        {po ? (
                          po.status === 'ORDER_PLACED' ? (
                            <div>
                              <span className="badge badge-info text-[10px] font-semibold flex items-center gap-1 w-fit">
                                <Truck size={10} /> Placed
                              </span>
                              <div className="text-[10px] text-slate-600 mt-0.5 font-mono">
                                {po.order_placed_at ? po.order_placed_at.slice(0, 10) : 'Active Order'}
                              </div>
                              {po.vendor_order_ref && (
                                <div className="text-[10px] text-slate-500 truncate max-w-[130px]">
                                  Ref: {po.vendor_order_ref}
                                </div>
                              )}
                            </div>
                          ) : po.status === 'APPROVED' ? (
                            <div>
                              <span className="badge badge-primary text-[10px] font-semibold flex items-center gap-1 w-fit">
                                <Send size={10} /> Ready to Place
                              </span>
                              <div className="text-[10px] text-blue-700 mt-0.5">SCM Placement Pending</div>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400">Needs PO Approval</span>
                          )
                        ) : (
                          <span className="text-slate-400 text-xs">—</span>
                        )}
                      </td>

                      {/* 6. Stores GRN */}
                      <td>
                        {grn ? (
                          <div>
                            <div className="font-mono font-bold text-xs text-indigo-900">{grn.grn_number}</div>
                            <div className="text-[10px] text-slate-500">
                              Recv: {grn.receipt_date}
                            </div>
                          </div>
                        ) : po?.status === 'ORDER_PLACED' ? (
                          <div>
                            <span className="badge badge-warning text-[10px] font-semibold flex items-center gap-1 w-fit">
                              <Clock size={10} /> Awaiting Stores
                            </span>
                            <div className="text-[10px] text-slate-500 mt-0.5">Pending Delivery</div>
                          </div>
                        ) : (
                          <span className="text-slate-400 text-xs">—</span>
                        )}
                      </td>

                      {/* 7. QA Acceptance */}
                      <td>
                        {grn ? (
                          grn.status === 'APPROVED' ? (
                            <div>
                              <span className="badge badge-success text-[10px] font-semibold flex items-center gap-1 w-fit">
                                <CheckCircle2 size={10} /> Accepted
                              </span>
                              <div className="text-[10px] text-emerald-700 mt-0.5">QA Certified</div>
                            </div>
                          ) : grn.status === 'REJECTED' ? (
                            <span className="badge badge-danger text-[10px] font-semibold">QA Rejected</span>
                          ) : (
                            <div>
                              <span className="badge badge-warning text-[10px] font-semibold flex items-center gap-1 w-fit">
                                <Clock size={10} /> Pending QA
                              </span>
                              <div className="text-[10px] text-amber-700 font-medium mt-0.5">Inspection Required</div>
                            </div>
                          )
                        ) : (
                          <span className="text-slate-400 text-xs">—</span>
                        )}
                      </td>

                      {/* 8. Accounts Payment */}
                      <td>
                        {grn ? (
                          grn.payment_status === 'PAID' ? (
                            <div>
                              <span className="badge badge-success text-[10px] font-semibold flex items-center gap-1 w-fit">
                                <CheckCircle2 size={10} /> Settled
                              </span>
                              <div className="text-[10px] text-slate-500 mt-0.5">Voucher Cleared</div>
                            </div>
                          ) : grn.status === 'APPROVED' ? (
                            <div>
                              <span className="badge badge-warning text-[10px] font-semibold flex items-center gap-1 w-fit">
                                <CreditCard size={10} /> Ready for Pay
                              </span>
                              <div className="text-[10px] text-amber-800 font-medium mt-0.5">Accounts Action</div>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400">Needs QA Signoff</span>
                          )
                        ) : (
                          <span className="text-slate-400 text-xs">—</span>
                        )}
                      </td>

                      {/* Action / Detail Trigger */}
                      <td className="text-center">
                        <button
                          className="erp-btn btn-xs btn-secondary flex items-center gap-1 mx-auto text-[11px]"
                          onClick={() => setSelectedEntry(entry)}
                          title="Inspect P2P Audit Trail"
                        >
                          <Eye size={12} /> View Trail
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail Modal for Full Traceability Audit Trail */}
      {selectedEntry && (
        <div className="modal-backdrop" onClick={() => setSelectedEntry(null)}>
          <div className="modal-content max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="flex items-center gap-2">
                <ShieldCheck size={20} className="text-emerald-600" />
                <h3 className="text-base font-bold text-slate-900">
                  Procure-to-Pay (P2P) Complete Audit Trail
                </h3>
              </div>
              <button className="close-btn" onClick={() => setSelectedEntry(null)}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body space-y-4">
              {/* Status Header Box */}
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between">
                <div>
                  <div className="text-xs text-slate-500 uppercase font-semibold">Active Pipeline Stage</div>
                  <div className="text-sm font-bold text-slate-800 flex items-center gap-2 mt-0.5">
                    <span className={`badge ${selectedEntry.badgeClass}`}>{selectedEntry.stageName}</span>
                    <span>&bull; Step {selectedEntry.stageStep} of 6</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-slate-500 uppercase font-semibold">Responsible Function</div>
                  <div className="text-xs font-bold text-slate-800 mt-0.5">{selectedEntry.nextActorRole}</div>
                  <div className="text-[11px] text-amber-800 mt-0.5">{selectedEntry.actionRequired}</div>
                </div>
              </div>

              {/* 6-Step Visual Timeline */}
              <div className="border border-slate-200 rounded-lg p-4 bg-white">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-4">
                  End-to-End Governance Timeline
                </h4>

                <div className="space-y-4">
                  {/* Step 1: PR Creation */}
                  <div className="flex gap-3 items-start">
                    <div className="mt-0.5">
                      {selectedEntry.pr ? (
                        <CheckCircle2 size={18} className="text-emerald-600" />
                      ) : (
                        <Clock size={18} className="text-slate-300" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <div className="font-bold text-xs text-slate-800">
                          Step 1: Purchase Request (SCM / Planning Requisition)
                        </div>
                        {selectedEntry.pr && (
                          <span className="font-mono text-xs font-semibold text-slate-600">
                            {selectedEntry.pr.pr_number} &bull; {selectedEntry.pr.request_date}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-600 mt-1">
                        {selectedEntry.pr ? (
                          <>
                            Raised by <strong>{selectedEntry.pr.created_by || selectedEntry.pr.requisitioner_id}</strong> for <strong>{selectedEntry.pr.department_name}</strong>.
                            <br />
                            <span className="italic text-slate-500">Justification: "{selectedEntry.pr.justification}"</span>
                          </>
                        ) : (
                          'Legacy purchase order created directly prior to formal PR mandate.'
                        )}
                      </p>
                    </div>
                  </div>

                  {/* Step 2: Plant Head Approval */}
                  <div className="flex gap-3 items-start border-t border-slate-100 pt-3">
                    <div className="mt-0.5">
                      {selectedEntry.pr?.status === 'APPROVED' ? (
                        <CheckCircle2 size={18} className="text-emerald-600" />
                      ) : selectedEntry.pr?.status === 'REJECTED' ? (
                        <XCircle size={18} className="text-red-600" />
                      ) : (
                        <Clock size={18} className="text-amber-500" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <div className="font-bold text-xs text-slate-800">
                          Step 2: Layer 1 Authorization (Plant Head Signoff)
                        </div>
                        {selectedEntry.pr?.plant_head_approved_at && (
                          <span className="text-xs text-slate-500">
                            {selectedEntry.pr.plant_head_approved_at.slice(0, 19).replace('T', ' ')}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-600 mt-1">
                        {selectedEntry.pr?.status === 'APPROVED' ? (
                          <>Approved by <strong>{selectedEntry.pr.plant_head_approved_by || 'Plant Head'}</strong>. Requisition authorized for PO drafting.</>
                        ) : selectedEntry.pr?.status === 'REJECTED' ? (
                          <span className="text-red-700">Requisition rejected by Plant Head. Remarks: {selectedEntry.pr.rejection_reason || 'N/A'}</span>
                        ) : (
                          <span className="text-amber-700 font-medium">Pending 1st Layer authorization by Plant Head.</span>
                        )}
                      </p>
                    </div>
                  </div>

                  {/* Step 3: PO Creation & CEO Approval */}
                  <div className="flex gap-3 items-start border-t border-slate-100 pt-3">
                    <div className="mt-0.5">
                      {selectedEntry.po?.status === 'APPROVED' || selectedEntry.po?.status === 'ORDER_PLACED' ? (
                        <CheckCircle2 size={18} className="text-emerald-600" />
                      ) : selectedEntry.po ? (
                        <Clock size={18} className="text-amber-500" />
                      ) : (
                        <Clock size={18} className="text-slate-300" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <div className="font-bold text-xs text-slate-800">
                          Step 3: Purchase Order & Management (CEO / MD) Signoff
                        </div>
                        {selectedEntry.po && (
                          <span className="font-mono text-xs font-semibold text-blue-900">
                            {selectedEntry.po.po_number}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-600 mt-1">
                        {selectedEntry.po ? (
                          <>
                            Vendor: <strong>{selectedEntry.vendorName}</strong> &bull; Total Value: <strong>₹{selectedEntry.totalAmount.toLocaleString('en-IN')}</strong>.
                            <br />
                            Status: <strong>{selectedEntry.po.status}</strong> &bull; Authorized by CEO / MD for supplier dispatch.
                          </>
                        ) : (
                          'Awaiting SCM / Purchase creation of official Purchase Order.'
                        )}
                      </p>
                    </div>
                  </div>

                  {/* Step 4: Order Placed */}
                  <div className="flex gap-3 items-start border-t border-slate-100 pt-3">
                    <div className="mt-0.5">
                      {selectedEntry.po?.status === 'ORDER_PLACED' ? (
                        <CheckCircle2 size={18} className="text-emerald-600" />
                      ) : (
                        <Clock size={18} className="text-slate-300" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <div className="font-bold text-xs text-slate-800">
                          Step 4: Order Placed with Vendor (Timestamp & Ack)
                        </div>
                        {selectedEntry.po?.order_placed_at && (
                          <span className="text-xs text-slate-500 font-mono">
                            {selectedEntry.po.order_placed_at.slice(0, 19).replace('T', ' ')}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-600 mt-1">
                        {selectedEntry.po?.status === 'ORDER_PLACED' ? (
                          <>
                            Placed by <strong>{selectedEntry.po.order_placed_by || 'Purchase Officer'}</strong>.
                            {selectedEntry.po.vendor_order_ref && (
                              <span> Vendor Ref: <strong>{selectedEntry.po.vendor_order_ref}</strong>.</span>
                            )}
                          </>
                        ) : (
                          'Purchase Order awaiting vendor dispatch confirmation.'
                        )}
                      </p>
                    </div>
                  </div>

                  {/* Step 5: GRN Inward & QA Inspection */}
                  <div className="flex gap-3 items-start border-t border-slate-100 pt-3">
                    <div className="mt-0.5">
                      {selectedEntry.grn?.status === 'APPROVED' ? (
                        <CheckCircle2 size={18} className="text-emerald-600" />
                      ) : selectedEntry.grn ? (
                        <Clock size={18} className="text-amber-500" />
                      ) : (
                        <Clock size={18} className="text-slate-300" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <div className="font-bold text-xs text-slate-800">
                          Step 5: Physical Stores Inward (GRN) & QA Acceptance
                        </div>
                        {selectedEntry.grn && (
                          <span className="font-mono text-xs font-semibold text-indigo-900">
                            {selectedEntry.grn.grn_number}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-600 mt-1">
                        {selectedEntry.grn ? (
                          <>
                            Inwarded by Stores on <strong>{selectedEntry.grn.receipt_date}</strong>.
                            <br />
                            QA Status: <strong>{selectedEntry.grn.status === 'APPROVED' ? 'Passed Quality Inspection' : selectedEntry.grn.status}</strong>.
                          </>
                        ) : (
                          'Materials in-transit or pending physical gate inwarding by Stores.'
                        )}
                      </p>
                    </div>
                  </div>

                  {/* Step 6: Payment & Settlement */}
                  <div className="flex gap-3 items-start border-t border-slate-100 pt-3">
                    <div className="mt-0.5">
                      {selectedEntry.grn?.payment_status === 'PAID' ? (
                        <CheckCircle2 size={18} className="text-emerald-600" />
                      ) : (
                        <Clock size={18} className="text-slate-300" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <div className="font-bold text-xs text-slate-800">
                          Step 6: Accounts Invoice Settlement & Closure
                        </div>
                        {selectedEntry.grn?.payment_status === 'PAID' && (
                          <span className="badge badge-success text-[10px]">Settled</span>
                        )}
                      </div>
                      <p className="text-xs text-slate-600 mt-1">
                        {selectedEntry.grn?.payment_status === 'PAID' ? (
                          'Vendor payment recorded, invoice cleared, and PO cycle completely closed.'
                        ) : selectedEntry.grn?.status === 'APPROVED' ? (
                          <span className="text-amber-700 font-medium">Approved GRN pending invoice voucher payment by Accounts.</span>
                        ) : (
                          'Awaiting QA approval before invoice settlement can be processed.'
                        )}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="modal-footer flex justify-between items-center">
              <div className="text-xs text-slate-500">
                VSPL SOX / Internal Control Framework &bull; Strict Role Separation Enforced
              </div>
              <div className="flex gap-2">
                {onNavigate && selectedEntry.pr && (
                  <button
                    className="erp-btn btn-secondary text-xs"
                    onClick={() => {
                      setSelectedEntry(null);
                      onNavigate('purchase-requests');
                    }}
                  >
                    Go to PR
                  </button>
                )}
                {onNavigate && selectedEntry.po && (
                  <button
                    className="erp-btn btn-secondary text-xs"
                    onClick={() => {
                      setSelectedEntry(null);
                      onNavigate('purchase-orders');
                    }}
                  >
                    Go to PO
                  </button>
                )}
                {onNavigate && selectedEntry.grn && (
                  <button
                    className="erp-btn btn-secondary text-xs"
                    onClick={() => {
                      setSelectedEntry(null);
                      onNavigate('grn-management');
                    }}
                  >
                    Go to GRN
                  </button>
                )}
                <button
                  className="erp-btn btn-primary text-xs"
                  onClick={() => setSelectedEntry(null)}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
