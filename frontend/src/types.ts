export type ModuleId = 
  | 'dashboard'
  | 'material-master'
  | 'vendor-master'
  | 'item-requests'
  | 'references'
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

export interface Department {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UOM {
  id: number;
  code: string;
  name: string;
  decimal_precision: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface MaterialItem {
  id: number;
  item_code: string;
  name: string;
  department_id: number;
  department_name?: string;
  category: string;
  subcategory?: string;
  base_uom_id: number;
  uom_code?: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Vendor {
  id: number;
  name: string;
  normalized_name: string;
  gstin?: string;
  address?: string;
  contact_person?: string;
  phone?: string;
  email?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuditLog {
  id: number;
  action: string;
  from_status?: string;
  to_status: string;
  actor_id: string;
  actor_role: string;
  comments?: string;
  timestamp: string;
}

export interface ItemRequest {
  id: number;
  request_number: string;
  requested_name: string;
  proposed_department_id: number;
  department_name?: string;
  proposed_category: string;
  proposed_subcategory?: string;
  proposed_uom_id: number;
  uom_code?: string;
  justification: string;
  requester_id: string;
  requester_role: string;
  requester_department: string;
  status: 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED' | 'CANCELLED';
  submitted_at?: string;
  reviewer_id?: string;
  decision_at?: string;
  decision_comments?: string;
  linked_item_id?: number;
  linked_item_code?: string;
  created_at: string;
  updated_at: string;
  audit_logs: AuditLog[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}
