/**
 * VSPL Material Management System — Architectural Implementation & Verification Roadmap
 *
 * Defines the authoritative status for each architectural phase, distinguishing between
 * implementation state (code, models, services, tests) and operational approval state
 * (physical certification, migrations, management sign-off).
 */

export type ImplementationStatus = 'COMPLETED' | 'IMPLEMENTED' | 'IN_PROGRESS' | 'QUEUED';
export type ApprovalStatus = 'OPERATIONAL' | 'PENDING_APPROVAL' | 'PENDING_UAT' | 'PENDING_MIGRATION' | 'QUEUED_FOR_DATA';

export interface RoadmapPhase {
  id: number;
  number: string;
  title: string;
  description: string;
  moduleId?: string;
  implementationStatus: ImplementationStatus;
  implementationLabel: string;
  implementationBadgeClass: 'active' | 'blue' | 'pending' | 'queued';
  approvalStatus: ApprovalStatus;
  approvalLabel: string;
  approvalBadgeClass: 'active' | 'blue' | 'pending' | 'queued';
  cardClass: 'completed' | 'active-gate' | 'queued';
  icon: 'check' | 'clock';
}

export const IMPLEMENTATION_ROADMAP: RoadmapPhase[] = [
  {
    id: 1,
    number: 'Phase 1',
    title: 'Foundation & Shell',
    description: 'FastAPI, PostgreSQL schema base, React ERP shell, Alembic migrations, test suites.',
    implementationStatus: 'COMPLETED',
    implementationLabel: 'COMPLETED',
    implementationBadgeClass: 'active',
    approvalStatus: 'OPERATIONAL',
    approvalLabel: 'OPERATIONAL',
    approvalBadgeClass: 'active',
    cardClass: 'completed',
    icon: 'check',
  },
  {
    id: 2,
    number: 'Phase 2',
    title: 'Master Data & Approvals',
    description: '741 Items master, categories, vendors, UOMs, item approval workflow, Item Code Generator v1.0.',
    moduleId: 'material-master',
    implementationStatus: 'COMPLETED',
    implementationLabel: 'COMPLETED',
    implementationBadgeClass: 'active',
    approvalStatus: 'OPERATIONAL',
    approvalLabel: 'OPERATIONAL',
    approvalBadgeClass: 'active',
    cardClass: 'completed',
    icon: 'check',
  },
  {
    id: 3,
    number: 'Phase 3',
    title: 'Material Entry',
    description: 'GRNs, store receipts with GST-excluded rates, issues, waste logs, maker-checker duplicate check.',
    moduleId: 'grn-management',
    implementationStatus: 'COMPLETED',
    implementationLabel: 'COMPLETED',
    implementationBadgeClass: 'active',
    approvalStatus: 'OPERATIONAL',
    approvalLabel: 'OPERATIONAL',
    approvalBadgeClass: 'active',
    cardClass: 'completed',
    icon: 'check',
  },
  {
    id: 4,
    number: 'Phase 4',
    title: 'Live Inventory Ledger',
    description: 'Append-only movements, opening stock, physical audit adjustments, concurrency-tested ledger.',
    moduleId: 'inventory-ledger',
    implementationStatus: 'IMPLEMENTED',
    implementationLabel: 'IMPLEMENTED & TESTED',
    implementationBadgeClass: 'active',
    approvalStatus: 'PENDING_APPROVAL',
    approvalLabel: 'PENDING OPENING STOCK SIGN-OFF',
    approvalBadgeClass: 'pending',
    cardClass: 'active-gate',
    icon: 'clock',
  },
  {
    id: 5,
    number: 'Phase 5',
    title: 'Heat Log & Reconciliation',
    description: 'Heat records, charge details, native Excel import, 3-pass reconciliation. Operational gate requires UAT clearance (P5-05 to P5-09), migration review, and sign-offs.',
    moduleId: 'heat-reconciliation',
    implementationStatus: 'IMPLEMENTED',
    implementationLabel: 'IMPLEMENTED & TESTED',
    implementationBadgeClass: 'active',
    approvalStatus: 'PENDING_UAT',
    approvalLabel: 'PENDING UAT & SIGN-OFF',
    approvalBadgeClass: 'blue',
    cardClass: 'active-gate',
    icon: 'clock',
  },
  {
    id: 6,
    number: 'Phase 6',
    title: 'Costing Engine',
    description: 'Weighted-average rate journal, heat melting cost, cost per kg, part costing, baseline date 12-Oct-2026.',
    moduleId: 'costing',
    implementationStatus: 'IMPLEMENTED',
    implementationLabel: 'IMPLEMENTED & TESTED',
    implementationBadgeClass: 'active',
    approvalStatus: 'QUEUED_FOR_DATA',
    approvalLabel: 'AWAITING LIVE LEDGER DATA',
    approvalBadgeClass: 'queued',
    cardClass: 'active-gate',
    icon: 'clock',
  },
];
