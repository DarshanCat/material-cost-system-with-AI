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
import { ModulePlaceholder } from './components/ModulePlaceholder';
import { DiagnosticsView } from './components/DiagnosticsView';
import { GRNManagementView } from './components/GRNManagementView';
import { MaterialIssueView } from './components/MaterialIssueView';
import { WasteDispositionView } from './components/WasteDispositionView';
import { ExcelImportView } from './components/ExcelImportView';

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

      case 'material-entry':
        return (
          <GRNManagementView
            currentRole={currentRole}
            currentUserId={currentUserId}
          />
        );

      case 'inventory-ledger':
        return (
          <ModulePlaceholder
            title="Module 2: Live Inventory Ledger"
            moduleId="inventory-ledger"
            phase="Phase 4 (Scheduled)"
            description="Immutable, append-only transaction ledger maintaining real-time stock balances, valuation, and physical stock count audit adjustments."
            plannedFeatures={[
              'Strict append-only stock movement tracking across 741 material items.',
              'Zero destructive ledger operations (DELETE/UPDATE prohibition on financial entries).',
              'Physical stock count reconciliation and audit adjustment journal entries.',
              'Multi-department stock separation (Stores, Foundry floor, Machine shop buffer).',
              'Traceable audit trail recording transaction author, department, timestamp, and source document.',
            ]}
            businessRules={[
              'Never clear or overwrite transaction history to correct stock balances.',
              'Physical stock discrepancies must be represented by distinct adjustment entries.',
              'Heat Log charge records do NOT independently move inventory.',
              'Stock movements require immutable transaction IDs with cryptographic audit logs.',
            ]}
          />
        );

      case 'heat-reconciliation':
        return (
          <ModulePlaceholder
            title="Module 3: Heat Log & Issue Reconciliation"
            moduleId="heat-reconciliation"
            phase="Phase 5 (Scheduled)"
            description="Logs induction furnace heat records, charge detail mixes (pig iron, scrap, ferro alloys, inoculants), parts cast, and reconciles issues to actual charge consumption."
            plannedFeatures={[
              'Furnace heat log capture (Heat Number, Date, Shift, Furnace ID, Metallurgist).',
              'Charge mix detail logging (Pig Iron, Return Borings, Steel Scrap, FeSi, FeMn, Mg treatment).',
              'Casting and parts produced tracking linked to specific heat chemistry.',
              'Issue-Slip-to-Heat-Log reconciliation variance reporting.',
              'Foundry yield and melting loss calculation.',
            ]}
            businessRules={[
              'Heat Log charge records do NOT independently deplete inventory (ledger movement occurs via authorized issue slip).',
              'Heat-to-issue reconciliation identifies floor consumption variances without fabricating ledger balance adjustments.',
              'Reconciliation discrepancies must be flagged for metallurgical supervisor review.',
            ]}
          />
        );

      case 'costing':
        return (
          <ModulePlaceholder
            title="Module 4: Weighted-Average Costing & Valuation"
            moduleId="costing"
            phase="Phase 6 (Scheduled)"
            description="Calculates true material and production costs per heat, cost per kg of liquid metal, and finished part costs starting from 12 October 2026."
            plannedFeatures={[
              'Weighted-average costing engine utilizing Decimal/Numeric precision.',
              'Heat metal cost computation based on reconciled charge materials and rates.',
              'Cost per kg of good casting produced factoring in melting loss and runner/riser returns.',
              'Part-level unit costing for SG iron automotive and engineering castings.',
              'Variance reporting between standard batch cost and actual heat batch cost.',
            ]}
            businessRules={[
              'The costing baseline start date is strictly 12 October 2026.',
              'Weighted-average costing must be verified against separate automated test suites.',
              'Unresolved costing decisions (internal rates, scrap valuation) remain documented as pending.',
              'No floating-point arithmetic permitted in monetary or inventory valuations.',
            ]}
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
