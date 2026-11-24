import React, { useState } from 'react';
import { 
  ShieldCheck, 
  CheckCircle2, 
  XCircle, 
  Eye, 
  ShoppingCart, 
  Flame, 
  Package
} from 'lucide-react';
import type { UserRole } from '../types';

interface RolesResponsibilitiesViewProps {
  currentRole: UserRole;
  onSwitchRole?: (role: UserRole) => void;
}

interface RoleDefinition {
  role: UserRole;
  title: string;
  department: string;
  badgeClass: string;
  icon: React.ReactNode;
  summary: string;
  makerCheckerRole: string;
  visibleModules: string[];
  responsibilities: string[];
  restrictions: string[];
}

const ROLES_DATA: RoleDefinition[] = [
  {
    role: 'Management',
    title: 'Management / Executive Authority',
    department: 'Executive Management & Finance',
    badgeClass: 'badge-primary',
    icon: <ShieldCheck size={22} className="text-primary" />,
    summary: 'Executive sign-off authority for high-value procurements, costing calculations, stock baseline posting, and material master code activations.',
    makerCheckerRole: 'Final Checker & Financial Approver',
    visibleModules: [
      'System Dashboard',
      'Purchase Orders (PO Approvals)',
      'Goods Receipt Notes (Review)',
      'Material Issue Approvals',
      'Furnace Heat Logs & Reconciliation',
      'Costing & Valuation Engine',
      'Item Approvals (10-char code generator)',
      'Opening Baseline Balances',
      'Physical Stock Audits',
      'Live Inventory Ledger',
      'Material Master & Vendor Master',
      'System Diagnostics'
    ],
    responsibilities: [
      'Level 3 Management Approval on Purchase Orders exceeding commercial threshold.',
      'Final review and approval of proposed Material Items; assigns authoritative 10-character code ({DEPT}-{CAT}-{SEQ}).',
      'Execution and sign-off on Weighted-Average Costing engine and Heat Melting Cost per kg.',
      'Approval of Physical Inventory Audit adjustments, discrepancies, and book value write-offs.',
      'Resolution of heat reconciliation anomalies and abnormal melt loss variances (> 4.5%).',
      'Posting of verified Opening Stock Balances baseline (frozen starting valuation).'
    ],
    restrictions: [
      'Cannot create Goods Receipt Notes (GRN) directly (must be created by Stores upon physical arrival).',
      'Cannot directly enter floor furnace charge weights (must be logged by melting technicians).'
    ]
  },
  {
    role: 'Stores',
    title: 'Stores & Inventory Custody',
    department: 'General / Stores',
    badgeClass: 'badge-info',
    icon: <Package size={22} className="text-info" />,
    summary: 'Custody, inbound verification, storage, and controlled disbursement of all raw materials, scrap, ferro alloys, and plant consumables.',
    makerCheckerRole: 'Store Inward Maker / Custodian',
    visibleModules: [
      'System Dashboard',
      'Purchase Orders (Read-only lookup for gate entry)',
      'Goods Receipt Notes (GRN Creation)',
      'Material Issue Slips (Issue to Dept / Heat)',
      'Waste & Scrap Dispositions',
      'Live Inventory Ledger',
      'Physical Stock Audits (Count Recording)',
      'Material Master (Catalog lookup)',
      'Item Approvals (Requisition creation)',
      'Depts & UOMs Reference',
      'Material Aliases',
      'Excel Bulk Import',
      'System Diagnostics'
    ],
    responsibilities: [
      'Inward all deliveries from external vendors against active POs via Goods Receipt Notes (GRN).',
      'Inspect physical packaging, capture vendor invoice, delivery challan, heat/batch numbers, and manufacturer TC/MTC.',
      'Disburse materials to plant departments and furnace charges via authorized Material Issue Slips.',
      'Log shop-floor waste, slag, dross, and non-conforming scrap returns.',
      'Conduct regular physical stock audits and record actual counted floor quantities.',
      'Propose shop-floor material aliases for shorthand labels used by material handlers.'
    ],
    restrictions: [
      'Strictly prohibited from modifying purchase order unit rates or supplier prices.',
      'Cannot approve and activate new material codes in the Item Master (Management prerogative).',
      'Cannot run financial costing valuation or post baseline opening balances.',
      'Cannot create furnace heat logs or liquid heel measurements.'
    ]
  },
  {
    role: 'Purchase',
    title: 'Procurement & Supply Chain Management',
    department: 'Purchase / SCM',
    badgeClass: 'badge-warning',
    icon: <ShoppingCart size={22} className="text-warning" />,
    summary: 'Commercial negotiation, vendor relationship management, purchase order issuance, and material replenishment planning.',
    makerCheckerRole: 'Procurement Maker',
    visibleModules: [
      'System Dashboard',
      'Purchase Orders (PO Generation & Tracking)',
      'Vendor Master (Onboarding & Profiles)',
      'Material Master (Catalog for PO Line items)',
      'Item Approvals (Procurement Requisitions)',
      'Roles & Responsibilities',
      'System Diagnostics'
    ],
    responsibilities: [
      'Generate Purchase Orders (PO) for raw materials, pig iron, scrap, ferro alloys, and tooling based on plant requisitions.',
      'Maintain Vendor Master: supplier profiles, GSTIN numbers, MSME classification, and payment terms.',
      'Verify GST-excluded base unit rates against negotiated commercial contracts.',
      'Submit POs for Level 1 Department and Level 2 SCM approvals.',
      'Track vendor delivery timelines and resolve supply chain delays.'
    ],
    restrictions: [
      'Strictly barred from creating Goods Receipt Notes (cannot acknowledge physical receipt of goods they purchased).',
      'Cannot issue materials to factory departments.',
      'Cannot alter live inventory ledger balances or post inventory write-offs.',
      'Cannot access furnace melting logs or costing engines.'
    ]
  },
  {
    role: 'Foundry',
    title: 'Foundry Melting & Metallurgy',
    department: 'Induction Melting & Metallurgy',
    badgeClass: 'badge-danger',
    icon: <Flame size={22} className="text-danger" />,
    summary: 'Induction furnace melting operations, charge mix entry, liquid heel measurement, and melt recovery reconciliation.',
    makerCheckerRole: 'Furnace Charge Maker / Melter',
    visibleModules: [
      'System Dashboard',
      'Furnace Heat Log (Heat entry, heel & charges)',
      'Heat Reconciliation (Melt recovery & yield)',
      'Heat Excel Import (Batch log upload)',
      'Material Issues (View issues made to Foundry)',
      'Material Aliases (Furnace floor nicknames)',
      'Material Master (Raw materials catalog)',
      'Item Approvals (Requisition foundry materials)',
      'Roles & Responsibilities',
      'System Diagnostics'
    ],
    responsibilities: [
      'Log furnace heats: Furnace ID, sequence, heat date, tapping temperature, and tap times.',
      'Accurately record furnace charge mix: Pig iron, CRCA scrap, in-house returns, ferro alloys, inoculants.',
      'Measure opening and closing liquid heel using dip gauge methods to maintain strict mass balance.',
      'Monitor melt loss %, tapped recovery %, and good casting yield per heat.',
      'Execute 3-pass reconciliation matching furnace charges against store issue slips.',
      'Map furnace floor nicknames (e.g. "Tata Pig", "Heavy Scrap") to formal ERP item codes.'
    ],
    restrictions: [
      'Cannot create Purchase Orders or onboard vendors.',
      'Cannot generate Goods Receipt Notes (GRN).',
      'Cannot alter stock ledger balances outside furnace consumption.',
      'Cannot run financial costing calculations.'
    ]
  },
  {
    role: 'Admin',
    title: 'System Administrator & IT Governance',
    department: 'IT / Enterprise Systems',
    badgeClass: 'badge-secondary',
    icon: <ShieldCheck size={22} className="text-secondary" />,
    summary: 'Universal technical oversight, database health telemetry, user account provisioning, role enforcement, and system diagnostics.',
    makerCheckerRole: 'System Superuser & IT Administrator',
    visibleModules: [
      'Universal Access across All Operational & Master Data Modules',
      'System Health & Database Telemetry',
      'Roles & Responsibilities Governance Matrix'
    ],
    responsibilities: [
      'Maintain ERP database connections, connection pool scaling, and server availability.',
      'Monitor API response times and PostgreSQL telemetry.',
      'Oversee Role-Based Access Control (RBAC) integrity and user session authentication.',
      'Perform emergency operational data corrections and assist shop-floor users across any module.',
      'Maintain Item Nomenclature Standard v1.0 rules and system reference tables.'
    ],
    restrictions: [
      'Superuser access is audited in system logs; normal day-to-day transactions should be performed under respective departmental roles.'
    ]
  }
];

export const RolesResponsibilitiesView: React.FC<RolesResponsibilitiesViewProps> = ({ 
  currentRole,
  onSwitchRole 
}) => {
  const [selectedRole, setSelectedRole] = useState<UserRole>(currentRole);

  const activeDef = ROLES_DATA.find((r) => r.role === selectedRole) || ROLES_DATA[0];

  return (
    <div className="view-container">
      {/* View Header */}
      <div className="view-header flex-between mb-4">
        <div>
          <div className="flex-align-center gap-2 mb-1">
            <ShieldCheck size={24} className="text-primary" />
            <h2 className="m-0">Roles & Responsibilities (RBAC)</h2>
            <span className="badge badge-primary">Foundry Governance Standard</span>
          </div>
          <p className="text-muted m-0">
            Vijay Spheroidals Pvt. Ltd. (VSPL) strict separation of duties, maker-checker authorization, and role-based UI/UX visibility.
          </p>
        </div>

        {/* Current Active Role Pill */}
        <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '8px 16px', textAlign: 'right' }}>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>
            Your Verified Identity
          </div>
          <div className="flex-align-center gap-2 mt-1">
            <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#10b981' }}></span>
            <strong style={{ fontSize: '14px', color: '#0f172a' }}>{currentRole} Role</strong>
          </div>
        </div>
      </div>

      {/* Role Selection Tabs */}
      <div className="flex gap-2 mb-4" style={{ flexWrap: 'wrap', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
        {ROLES_DATA.map((r) => {
          const isSelected = selectedRole === r.role;
          const isCurrent = currentRole === r.role;
          return (
            <button
              key={r.role}
              type="button"
              className={`erp-btn ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setSelectedRole(r.role)}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', fontSize: '13px' }}
            >
              <span>{r.role}</span>
              {isCurrent && (
                <span style={{ fontSize: '10px', background: isSelected ? 'rgba(255,255,255,0.25)' : '#10b981', color: '#fff', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>
                  ACTIVE
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Detailed Role Profile Card */}
      <div className="card mb-4" style={{ background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '24px' }}>
        <div className="flex-between mb-3" style={{ flexWrap: 'wrap', gap: '12px', borderBottom: '1px solid #f1f5f9', paddingBottom: '16px' }}>
          <div className="flex-align-center gap-3">
            <div style={{ width: '48px', height: '48px', borderRadius: '10px', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {activeDef.icon}
            </div>
            <div>
              <h3 className="m-0" style={{ fontSize: '18px', fontWeight: 700, color: '#0f172a' }}>
                {activeDef.title}
              </h3>
              <div style={{ fontSize: '13px', color: '#64748b' }}>
                Department: <strong>{activeDef.department}</strong> &bull; Governance Role: <strong className="text-primary">{activeDef.makerCheckerRole}</strong>
              </div>
            </div>
          </div>

          {onSwitchRole && currentRole !== activeDef.role && (
            <button
              type="button"
              className="erp-btn btn-secondary"
              onClick={() => onSwitchRole(activeDef.role)}
              style={{ fontSize: '12px', padding: '6px 14px' }}
            >
              Switch Session to {activeDef.role}
            </button>
          )}
        </div>

        <p style={{ fontSize: '14px', color: '#334155', lineHeight: '1.6', marginBottom: '20px' }}>
          {activeDef.summary}
        </p>

        <div className="grid grid-2 gap-4">
          {/* Key Responsibilities */}
          <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
            <h4 className="flex-align-center gap-2 m-0 mb-3" style={{ fontSize: '14px', color: '#0f172a', fontWeight: 600 }}>
              <CheckCircle2 size={16} className="text-success" />
              Primary Responsibilities & Authorized Actions
            </h4>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#475569', lineHeight: '1.7' }}>
              {activeDef.responsibilities.map((resp, i) => (
                <li key={i}>{resp}</li>
              ))}
            </ul>
          </div>

          {/* Boundaries & Restrictions */}
          <div style={{ background: '#fef2f2', padding: '16px', borderRadius: '8px', border: '1px solid #fecaca' }}>
            <h4 className="flex-align-center gap-2 m-0 mb-3" style={{ fontSize: '14px', color: '#991b1b', fontWeight: 600 }}>
              <XCircle size={16} className="text-danger" />
              Separation of Duties & Prohibited Actions
            </h4>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#7f1d1d', lineHeight: '1.7' }}>
              {activeDef.restrictions.map((rest, i) => (
                <li key={i}>{rest}</li>
              ))}
            </ul>
          </div>
        </div>

        {/* Visible Modules for this Role */}
        <div className="mt-4 pt-3" style={{ borderTop: '1px solid #f1f5f9' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', color: '#64748b', marginBottom: '10px' }}>
            UI & UX Modules Exclusively Visible in Sidebar for {activeDef.role}
          </div>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            {activeDef.visibleModules.map((mod, i) => (
              <span
                key={i}
                style={{
                  fontSize: '12px',
                  background: '#f1f5f9',
                  color: '#1e293b',
                  padding: '4px 10px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  fontWeight: 500,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px'
                }}
              >
                <Eye size={12} className="text-primary" /> {mod}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Feature-by-Feature RBAC Comparison Matrix */}
      <div className="card" style={{ background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '24px' }}>
        <h3 className="m-0 mb-2" style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a' }}>
          VSPL ERP Feature Authority Matrix (5 Operational Roles)
        </h3>
        <p className="text-muted mb-3" style={{ fontSize: '13px' }}>
          Comparison of operational capabilities across the enterprise. Green indicates creation authority; Blue indicates review/approval authority.
        </p>

        <div className="table-responsive">
          <table className="erp-table">
            <thead>
              <tr>
                <th>Operational Function</th>
                <th style={{ textAlign: 'center' }}>Management</th>
                <th style={{ textAlign: 'center' }}>Stores</th>
                <th style={{ textAlign: 'center' }}>Purchase</th>
                <th style={{ textAlign: 'center' }}>Foundry</th>
                <th style={{ textAlign: 'center' }}>Admin</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Purchase Orders (PO)</strong></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-info">Level 3 Approval</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-secondary">Read Only</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-success">Create & Submit</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-primary">Superuser</span></td>
              </tr>
              <tr>
                <td><strong>Goods Receipt (GRN)</strong></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-info">Approve & Review</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-success">Create & Submit</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-primary">Superuser</span></td>
              </tr>
              <tr>
                <td><strong>Material Issue Slips</strong></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-info">Approve Special</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-success">Create & Post</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-secondary">View Issues</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-primary">Superuser</span></td>
              </tr>
              <tr>
                <td><strong>Waste & Scrap Logs</strong></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-info">Approve & Write-off</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-success">Create & Submit</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-primary">Superuser</span></td>
              </tr>
              <tr>
                <td><strong>Furnace Heat Logs & Heel</strong></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-info">Audit & Resolve</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-success">Create & Record</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-primary">Superuser</span></td>
              </tr>
              <tr>
                <td><strong>Heat Reconciliation</strong></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-info">Exception Resolve</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-success">Run 3-Pass Reconcile</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-primary">Superuser</span></td>
              </tr>
              <tr>
                <td><strong>Item Requisitions & Approvals</strong></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-primary">Approve & Code</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-secondary">Submit Request</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-secondary">Submit Request</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-secondary">Submit Request</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-primary">Superuser</span></td>
              </tr>
              <tr>
                <td><strong>Weighted-Average Costing</strong></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-success">Calculate & Sign-off</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-secondary">Read Only</span></td>
              </tr>
              <tr>
                <td><strong>Opening Stock Baseline</strong></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-success">Post & Commit</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
              </tr>
              <tr>
                <td><strong>Physical Inventory Audit</strong></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-info">Approve Variance</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-success">Record Count</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-primary">Superuser</span></td>
              </tr>
              <tr>
                <td><strong>Vendor Master Management</strong></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-secondary">Read Only</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-secondary">Read Only</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-success">Create & Maintain</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-primary">Superuser</span></td>
              </tr>
              <tr>
                <td><strong>Material Aliases (Nicknames)</strong></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-info">Approve & Deactivate</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-success">Map Alias</span></td>
                <td style={{ textAlign: 'center' }}><span className="text-muted">&mdash;</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-success">Map Alias</span></td>
                <td style={{ textAlign: 'center' }}><span className="badge badge-primary">Superuser</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
