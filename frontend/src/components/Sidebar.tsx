import React from 'react';
import { 
  LayoutDashboard, 
  Package,
  Building,
  ClipboardList,
  Ruler,
  FileInput, 
  BookOpen, 
  Flame, 
  Calculator, 
  Server,
  Scale,
  Layers,
  FileSpreadsheet,
  Lock,
  ShoppingCart,
  ShieldCheck,
  Workflow,
  RotateCcw,
  Users
} from 'lucide-react';
import type { ModuleId, UserRole } from '../types';
import { canAccessModule } from '../auth/permissions';

interface SidebarProps {
  activeModule: ModuleId;
  onSelectModule: (module: ModuleId) => void;
  currentRole?: UserRole | null;
}

interface NavItem {
  id: ModuleId;
  label: string;
  icon: React.ReactNode;
  badge?: string;
  phase?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeModule, onSelectModule, currentRole }) => {
  const masterNavItems: NavItem[] = [
    {
      id: 'dashboard',
      label: 'System Dashboard',
      icon: <LayoutDashboard size={18} />,
      badge: 'Active',
    },
    {
      id: 'material-master',
      label: 'Material Master',
      icon: <Package size={18} />,
      badge: 'Active',
    },
    {
      id: 'heat-master',
      label: 'Furnace Heat Master',
      icon: <Flame size={18} />,
      badge: 'Active',
    },
    {
      id: 'vendor-master',
      label: 'Vendor Master',
      icon: <Building size={18} />,
      badge: 'Active',
    },
    {
      id: 'item-requests',
      label: 'Item Approvals',
      icon: <ClipboardList size={18} />,
      badge: 'Active',
    },
    {
      id: 'references',
      label: 'Depts & UOMs',
      icon: <Ruler size={18} />,
      badge: 'Active',
    },
    {
      id: 'material-aliases',
      label: 'Material Aliases',
      icon: <Layers size={18} />,
      badge: 'Active',
    },
    {
      id: 'roles-responsibilities',
      label: 'Roles & Responsibilities',
      icon: <ShieldCheck size={18} />,
      badge: 'RBAC',
    },
    {
      id: 'users',
      label: 'User Management',
      icon: <Users size={18} />,
      badge: 'Admin',
    },
  ];

  const operationalNavItems: NavItem[] = [
    {
      id: 'p2p-cycle',
      label: 'Procure-to-Pay (P2P)',
      icon: <Workflow size={18} />,
      badge: 'E2E Flow',
    },
    {
      id: 'purchase-requests',
      label: 'Purchase Requests (PR)',
      icon: <ClipboardList size={18} />,
      badge: 'Plant Head',
    },
    {
      id: 'purchase-orders',
      label: 'Purchase Orders (PO)',
      icon: <ShoppingCart size={18} />,
      badge: 'Active',
    },
    {
      id: 'grn-management',
      label: 'Goods Receipt (GRN)',
      icon: <FileInput size={18} />,
      badge: 'Active',
    },
    {
      id: 'material-issue',
      label: 'Material Issues',
      icon: <Flame size={18} />,
      badge: 'Active',
    },
    {
      id: 'return-to-store',
      label: 'Return to Store (RTS)',
      icon: <RotateCcw size={18} />,
      badge: 'Active',
    },
    {
      id: 'waste-disposition',
      label: 'Waste & Scrap',
      icon: <Package size={18} />,
      badge: 'Active',
    },
    {
      id: 'inventory-ledger',
      label: 'Live Inventory Ledger',
      icon: <BookOpen size={18} />,
      badge: 'Active',
    },
    {
      id: 'opening-balances',
      label: 'Opening Balances',
      icon: <Layers size={18} />,
      badge: 'Active',
    },
    {
      id: 'physical-audits',
      label: 'Physical Stock Audits',
      icon: <Scale size={18} />,
      badge: 'Active',
    },
    {
      id: 'heat-log',
      label: 'Furnace Heat Log',
      icon: <Flame size={18} />,
      badge: 'Active',
    },
    {
      id: 'heat-reconciliation',
      label: 'Heat Reconciliation',
      icon: <Scale size={18} />,
      badge: 'Active',
    },
    {
      id: 'heat-import',
      label: 'Heat Excel Import',
      icon: <FileSpreadsheet size={18} />,
      badge: 'Active',
    },
    {
      id: 'excel-import',
      label: 'Excel Bulk Import',
      icon: <FileSpreadsheet size={18} />,
      badge: 'Active',
    },
    {
      id: 'costing',
      label: 'Costing & Valuation',
      icon: <Calculator size={18} />,
      phase: 'Phase 6',
    },
    {
      id: 'system-health',
      label: 'System Diagnostics',
      icon: <Server size={18} />,
      badge: 'Active',
    },
  ];

  const isGuest = !currentRole;
  const visibleMasterNavItems = isGuest
    ? masterNavItems.filter((item) => item.id !== 'users')
    : masterNavItems.filter((item) => canAccessModule(currentRole, item.id));
  const visibleOperationalNavItems = isGuest
    ? operationalNavItems
    : operationalNavItems.filter((item) => canAccessModule(currentRole, item.id));

  return (
    <aside className="erp-sidebar">
      {currentRole && (
        <div style={{ padding: '8px 12px', margin: '8px 8px 12px', background: 'rgba(56, 189, 248, 0.08)', borderRadius: '6px', border: '1px solid rgba(56, 189, 248, 0.2)' }}>
          <div style={{ fontSize: '10px', textTransform: 'uppercase', color: '#94a3b8', letterSpacing: '0.5px', fontWeight: 600 }}>
            Active Workspace
          </div>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#38bdf8' }}>
            {currentRole} Role Portal
          </div>
        </div>
      )}

      {visibleOperationalNavItems.length > 0 && (
        <>
          <div className="sidebar-section-title">OPERATIONAL MODULES</div>
          <nav className="sidebar-nav">
            {visibleOperationalNavItems.map((item) => {
              const isActive = activeModule === item.id;
              const isLocked = isGuest && item.id !== 'dashboard' && item.id !== 'system-health';
              return (
                <button
                  key={item.id}
                  className={`nav-button ${isActive ? 'nav-active' : ''}`}
                  onClick={() => onSelectModule(item.id)}
                  title={isLocked ? `Sign in to access ${item.label}` : undefined}
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                  {item.badge && <span className="nav-badge active-badge">{item.badge}</span>}
                  {item.phase && <span className="nav-badge pending-badge">{item.phase}</span>}
                  {isLocked && <Lock size={12} className="text-slate-500 ml-auto shrink-0" />}
                </button>
              );
            })}
          </nav>
        </>
      )}

      {visibleMasterNavItems.length > 0 && (
        <>
          <div className="sidebar-section-title mt-2">MASTER DATA & APPROVALS</div>
          <nav className="sidebar-nav">
            {visibleMasterNavItems.map((item) => {
              const isActive = activeModule === item.id;
              const isLocked = isGuest && item.id !== 'dashboard' && item.id !== 'system-health';
              return (
                <button
                  key={item.id}
                  className={`nav-button ${isActive ? 'nav-active' : ''}`}
                  onClick={() => onSelectModule(item.id)}
                  title={isLocked ? `Sign in to access ${item.label}` : undefined}
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                  {item.badge && <span className="nav-badge active-badge">{item.badge}</span>}
                  {item.phase && <span className="nav-badge pending-badge">{item.phase}</span>}
                  {isLocked && <Lock size={12} className="text-slate-500 ml-auto shrink-0" />}
                </button>
              );
            })}
          </nav>
        </>
      )}

      <div className="sidebar-footer">
        <div className="sidebar-footer-card">
          <div className="footer-title">
            <Lock size={12} className="inline-icon" /> Plant LAN Deployment
          </div>
          <p className="footer-desc">
            Restricted to factory network. Audit logging enabled.
          </p>
          <div className="system-version">v0.5.0 (Phase 5 Active)</div>
        </div>
      </div>
    </aside>
  );
};
