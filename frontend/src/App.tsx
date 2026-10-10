import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import type { ModuleId, UserRole, SystemHealthData } from './types';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { DashboardView } from './components/DashboardView';
import { MaterialMasterView } from './components/MaterialMasterView';
import { VendorMasterView } from './components/VendorMasterView';
import { ItemRequestsView } from './components/ItemRequestsView';
import { ReferenceDataView } from './components/ReferenceDataView';
import { DiagnosticsView } from './components/DiagnosticsView';
import { GRNManagementView } from './components/GRNManagementView';
import { MaterialIssueView } from './components/MaterialIssueView';
import { WasteDispositionView } from './components/WasteDispositionView';
import { ExcelImportView } from './components/ExcelImportView';
import { LiveInventoryDashboard } from './components/LiveInventoryDashboard';
import { OpeningBalanceView } from './components/OpeningBalanceView';
import { PhysicalAuditView } from './components/PhysicalAuditView';
import { HeatLogManagementView } from './components/HeatLogManagementView';
import { MaterialAliasView } from './components/MaterialAliasView';
import { ReconciliationDashboard } from './components/ReconciliationDashboard';
import { HeatExcelImportView } from './components/HeatExcelImportView';
import { CostingDashboard } from './components/CostingDashboard';

export const App: React.FC = () => {
  const [activeModule, setActiveModule] = useState<ModuleId>('dashboard');
  const [currentRole, setCurrentRole] = useState<UserRole>('Stores');
  const [health, setHealth] = useState<SystemHealthData | null>(null);
  const [loadingHealth, setLoadingHealth] = useState<boolean>(false);

  const getUserIdForRole = (role: UserRole): string => {
    switch (role) {
      case 'Stores':
        return 'usr_stores_01';
      case 'Foundry':
        return 'usr_foundry_01';
      case 'Purchase':
        return 'usr_purchase_01';
      case 'Management':
        return 'usr_mgmt_01';
      case 'Admin':
        return 'usr_admin_01';
      default:
        return 'usr_dev_01';
    }
  };

  const currentUserId = getUserIdForRole(currentRole);

  const fetchHealth = useCallback(async () => {
    setLoadingHealth(true);
    try {
      const response = await fetch('/api/v1/health');
      if (response.ok) {
        const data: SystemHealthData = await response.json();
        setHealth(data);
      } else {
        setHealth({
          status: 'degraded',
          app_name: 'VSPL Material Management & Costing System',
          environment: 'development',
          version: '0.2.0',
          costing_start_date: '2026-10-12',
          database: {
            connected: false,
            status: 'disconnected',
            message: `API responded with HTTP status ${response.status}`,
          },
          timestamp: new Date().toISOString(),
        });
      }
    } catch (err: any) {
      setHealth({
        status: 'degraded',
        app_name: 'VSPL Material Management & Costing System',
        environment: 'development',
        version: '0.2.0',
        costing_start_date: '2026-10-12',
        database: {
          connected: false,
          status: 'unreachable',
          message: 'Backend server is not reachable on port 8000',
        },
        timestamp: new Date().toISOString(),
      });
    } finally {
      setLoadingHealth(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  const renderContent = () => {
    switch (activeModule) {
      case 'dashboard':
        return (
          <DashboardView
            health={health}
            loadingHealth={loadingHealth}
            onRefreshHealth={fetchHealth}
            onNavigate={(mod) => setActiveModule(mod)}
          />
        );

      case 'material-master':
        return (
          <MaterialMasterView
            currentRole={currentRole}
            onRequestNewItem={() => setActiveModule('item-requests')}
          />
        );

      case 'vendor-master':
        return (
          <VendorMasterView
            currentRole={currentRole}
          />
        );

      case 'item-requests':
        return (
          <ItemRequestsView
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'references':
        return <ReferenceDataView />;

      case 'grn-management':
        return (
          <GRNManagementView
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'material-issue':
        return (
          <MaterialIssueView
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'waste-disposition':
        return (
          <WasteDispositionView
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'excel-import':
        return (
          <ExcelImportView
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'inventory-ledger':
        return (
          <LiveInventoryDashboard
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'opening-balances':
        return (
          <OpeningBalanceView
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'physical-audits':
        return (
          <PhysicalAuditView
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'heat-log':
        return (
          <HeatLogManagementView
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'material-aliases':
        return (
          <MaterialAliasView
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'heat-reconciliation':
        return (
          <ReconciliationDashboard
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'heat-import':
        return (
          <HeatExcelImportView
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'costing':
        return (
          <CostingDashboard
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'system-health':
        return (
          <DiagnosticsView
            health={health}
            loadingHealth={loadingHealth}
            onRefreshHealth={fetchHealth}
          />
        );

      default:
        return null;
    }
  };

  return (
    <div className="app-container">
      <Header
        currentRole={currentRole}
        onRoleChange={setCurrentRole}
        health={health}
        loadingHealth={loadingHealth}
        onRefreshHealth={fetchHealth}
      />
      <div className="erp-body">
        <Sidebar
          activeModule={activeModule}
          onSelectModule={setActiveModule}
        />
        <main className="erp-content">
          {renderContent()}
        </main>
      </div>
    </div>
  );
};

export default App;
