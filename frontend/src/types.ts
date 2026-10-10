export type ModuleId = 
  | 'dashboard'
  | 'material-master'
  | 'vendor-master'
  | 'item-requests'
  | 'references'
  | 'grn-management'
  | 'material-issue'
  | 'waste-disposition'
  | 'excel-import'
  | 'inventory-ledger'
  | 'stock-history'
  | 'opening-balances'
  | 'physical-audits'
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

export interface GRNLineItem {
  id?: number;
  line_number: number;
  material_item_id: number;
  uom_id: number;
  quantity: string | number;
  rate_ex_gst?: string | number | null;
  gst_percent?: string | number | null;
  remarks?: string;
  item_code?: string;
  item_name?: string;
  uom_code?: string;
}

export interface GRN {
  id: number;
  grn_number: string;
  receipt_date: string;
  source_type: 'EXTERNAL_VENDOR' | 'INTERNAL_VSPL' | 'SEGREGATION_YARD';
  vendor_id?: number | null;
  vendor_name?: string | null;
  vendor_invoice_no?: string | null;
  invoice_date?: string | null;
  reference_document?: string | null;
  notes?: string | null;
  status: 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'CANCELLED';
  created_by: string;
  created_at: string;
  updated_at: string;
  lines: GRNLineItem[];
  audit_logs: AuditLog[];
  validation_warnings?: string[];
}

export interface MaterialIssueLineItem {
  id?: number;
  line_number: number;
  material_item_id: number;
  uom_id: number;
  quantity: string | number;
  remarks?: string;
  item_code?: string;
  item_name?: string;
  uom_code?: string;
}

export interface MaterialIssue {
  id: number;
  issue_slip_number: string;
  issue_date: string;
  issuing_department_id: number;
  issuing_department_name?: string;
  receiving_department_id: number;
  receiving_department_name?: string;
  heat_reference_number?: string | null;
  notes?: string | null;
  status: 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'CANCELLED';
  created_by: string;
  created_at: string;
  updated_at: string;
  lines: MaterialIssueLineItem[];
  audit_logs: AuditLog[];
  validation_warnings?: string[];
}

export interface WasteDispositionLineItem {
  id?: number;
  line_number: number;
  material_item_id: number;
  uom_id: number;
  quantity: string | number;
  reason?: string;
  remarks?: string;
  item_code?: string;
  item_name?: string;
  uom_code?: string;
}

export interface WasteDisposition {
  id: number;
  waste_number: string;
  disposition_date: string;
  waste_type: string;
  disposition_type: string;
  source_department_id: number;
  source_department_name?: string;
  destination_notes?: string | null;
  notes?: string | null;
  status: 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'CANCELLED';
  created_by: string;
  created_at: string;
  updated_at: string;
  lines: WasteDispositionLineItem[];
  audit_logs: AuditLog[];
  validation_warnings?: string[];
}

export interface StockLedgerEntry {
  id: number;
  entry_number: string;
  posting_group_id: string;
  material_item_id: number;
  item_code?: string;
  item_name?: string;
  uom_id: number;
  uom_code?: string;
  transaction_date: string;
  posted_at: string;
  movement_type: string;
  quantity_delta: string | number;
  source_document_type: string;
  source_document_id: number;
  source_line_id: number;
  source_document_number: string;
  reference_number?: string | null;
  reason?: string | null;
  posted_by: string;
  reversal_of_entry_id?: number | null;
  created_at: string;
}

export interface StockBalance {
  material_item_id: number;
  item_code: string;
  item_name: string;
  category: string;
  department_name?: string | null;
  base_uom_id: number;
  uom_code: string;
  current_balance: string | number;
  is_initialized: boolean;
  status: 'UNINITIALIZED' | 'OUT_OF_STOCK' | 'IN_STOCK' | 'NEGATIVE_STOCK';
  last_movement_date?: string | null;
  movement_count: number;
}

export interface PhysicalAuditLine {
  id?: number;
  audit_id?: number;
  line_number: number;
  material_item_id: number;
  uom_id: number;
  system_quantity: string | number;
  physical_quantity: string | number;
  variance: string | number;
  reason?: string | null;
  remarks?: string | null;
  item_code?: string;
  item_name?: string;
  uom_code?: string;
}

export interface PhysicalAudit {
  id: number;
  audit_number: string;
  audit_date: string;
  department_id?: number | null;
  department_name?: string | null;
  status: 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'CANCELLED';
  notes?: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  lines: PhysicalAuditLine[];
  audit_logs: AuditLog[];
}
