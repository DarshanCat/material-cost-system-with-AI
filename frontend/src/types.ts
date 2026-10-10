export type ModuleId = 
  | 'dashboard'
  | 'material-entry'
  | 'inventory-ledger'
  | 'heat-reconciliation'
  | 'costing'
  | 'system-health';

export type UserRole = 
  | 'Stores'
  | 'Foundry'
  | 'Purchase'
  | 'Management'
  | 'Admin';

export interface DatabaseHealth {
  connected: boolean;
  status: string;
  message: string;
}

export interface SystemHealthData {
  status: 'healthy' | 'degraded' | 'error';
  app_name: string;
  environment: string;
  version: string;
  costing_start_date: string;
  database: DatabaseHealth;
  timestamp: string;
}
