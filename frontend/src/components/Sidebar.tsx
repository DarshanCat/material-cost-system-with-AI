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
  ShoppingCart
} from 'lucide-react';
import type { ModuleId } from '../types';

interface SidebarProps {
  activeModule: ModuleId;
  onSelectModule: (module: ModuleId) => void;
}

interface NavItem {
  id: ModuleId;
  label: string;
  icon: React.ReactNode;
  badge?: string;
  phase?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeModule, onSelectModule }) => {
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
      badge: 'Phase 2',
    },
    {
      id: 'vendor-master',
      label: 'Vendor Master',
      icon: <Building size={18} />,
      badge: 'Phase 2',
    },
    {
      id: 'item-requests',
      label: 'Item Approvals',
      icon: <ClipboardList size={18} />,
      badge: 'Phase 2',
    },
    {
      id: 'references',
      label: 'Depts & UOMs',
      icon: <Ruler size={18} />,
      badge: 'Phase 2',
    },
    {
      id: 'material-aliases',
      label: 'Material Aliases',
      icon: <Layers size={18} />,
      badge: 'Active',
    },
  ];

  const operationalNavItems: NavItem[] = [
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

  return (
    <aside className="erp-sidebar">
      <div className="sidebar-section-title">MASTER DATA & APPROVALS</div>
      <nav className="sidebar-nav">
        {masterNavItems.map((item) => {
          const isActive = activeModule === item.id;
          return (
            <button
              key={item.id}
              className={`nav-button ${isActive ? 'nav-active' : ''}`}
              onClick={() => onSelectModule(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
              {item.badge && <span className="nav-badge active-badge">{item.badge}</span>}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-section-title mt-2">OPERATIONAL MODULES</div>
      <nav className="sidebar-nav">
        {operationalNavItems.map((item) => {
          const isActive = activeModule === item.id;
          return (
            <button
              key={item.id}
              className={`nav-button ${isActive ? 'nav-active' : ''}`}
              onClick={() => onSelectModule(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
              {item.badge && <span className="nav-badge active-badge">{item.badge}</span>}
              {item.phase && <span className="nav-badge pending-badge">{item.phase}</span>}
            </button>
          );
        })}
      </nav>

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
