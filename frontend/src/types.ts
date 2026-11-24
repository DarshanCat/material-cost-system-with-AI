export type ModuleId = 
  | 'dashboard'
  | 'heat-master'
  | 'material-master'
  | 'vendor-master'
  | 'p2p-cycle'
  | 'purchase-requests'
  | 'purchase-orders'
  | 'item-requests'
  | 'references'
  | 'grn-management'
  | 'material-issue'
  | 'return-to-store'
  | 'waste-disposition'
  | 'inventory-ledger'
  | 'opening-balances'
  | 'physical-audits'
  | 'heat-log'
  | 'material-aliases'
  | 'heat-reconciliation'
  | 'heat-import'
  | 'excel-import'
  | 'costing'
  | 'system-health'
  | 'roles-responsibilities'
  | 'users';

export type UserRole = 
  | 'Stores'
  | 'Foundry'
  | 'Purchase'
  | 'Management'
  | 'Admin'
  | 'Quality'
  | 'Accounts';

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

/* ---- Item Code Generator (Item Nomenclature Standard v1.0) ---- */

export interface ItemCodeIssue {
  field: string;
  code: string;
  message: string;
}

export interface ItemCodeDuplicate {
  source: 'ITEM' | 'ALIAS' | 'REQUEST';
  match_type: 'EXACT' | 'COMPACT';
  name: string;
  item_id?: number | null;
  item_code?: string | null;
  is_active?: boolean | null;
  department_code?: string | null;
  request_id?: number | null;
  request_number?: string | null;
  request_status?: string | null;
  blocking: boolean;
}

export interface ItemCodeRuleDepartment {
  code: string;
  name: string;
  department_id: number | null;
  provisioned: boolean;
}

export interface ItemCodeRuleCategory {
  code: string;
  name: string;
  department_code: string;
  cost_head: string;
  pattern: string;
  example: string;
  verbatim_description: boolean;
}

export interface ItemCodeRuleUom {
  code: string;
  label: string;
  meaning: string;
  uom_id: number | null;
  provisioned: boolean;
}

export interface ItemCodeRules {
  standard: string;
  version: string;
  code_format: string;
  serial_min: number;
  serial_max: number;
  naming_formula: string;
  departments: ItemCodeRuleDepartment[];
  categories: ItemCodeRuleCategory[];
  uoms: ItemCodeRuleUom[];
  uom_aliases: { alias: string; maps_to: string }[];
  abbreviations: { abbreviation: string; meaning: string }[];
  registry_installed: boolean;
  unprovisioned_departments: string[];
  unprovisioned_uoms: string[];
}

export interface ItemCodePreview {
  valid: boolean;
  provisional: boolean;
  proposed_code: string | null;
  next_serial: number | null;
  serials_remaining: number | null;
  department_code: string | null;
  category_code: string | null;
  category_name: string | null;
  cost_head: string | null;
  uom_code: string | null;
  errors: ItemCodeIssue[];
  warnings: ItemCodeIssue[];
  duplicates: ItemCodeDuplicate[];
  registry_installed: boolean;
  standard_version: string;
  note: string;
}

export interface ItemHistoryEvent {
  id: number;
  action: string;
  field_name?: string | null;
  old_value?: string | null;
  new_value?: string | null;
  reason?: string | null;
  item_request_id?: number | null;
  actor_id: string;
  actor_role: string;
  timestamp: string;
}

export interface ItemHistory {
  item_id: number;
  item_code: string;
  registry_installed: boolean;
  registry: {
    item_code: string;
    department_code: string;
    category_code: string;
    serial: number;
    item_request_id?: number | null;
    standard_version: string;
    issued_by: string;
    issued_at: string;
  } | null;
  events: ItemHistoryEvent[];
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
  status: 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED' | 'CANCELLED';
  created_by: string;
  created_at: string;
  updated_at: string;
  lines: GRNLineItem[];
  audit_logs: AuditLog[];
  validation_warnings?: string[];
  // Quality Inspection & Certification
  quality_document_number?: string | null;
  quality_inspection_status?: 'PENDING' | 'PASSED' | 'REJECTED' | 'CONDITIONALLY_ACCEPTED' | null;
  quality_inspection_notes?: string | null;
  quality_inspected_by?: string | null;
  quality_inspected_at?: string | null;
  // P2P Purchase Order & Payment Settlement Tracking
  po_id?: number | null;
  po_number?: string | null;
  payment_status?: 'UNPAID' | 'PENDING' | 'PARTIALLY_PAID' | 'PAID' | null;
  payable_total?: string | number | null;
  amount_paid?: string | number | null;
  payment_reference?: string | null;
  payment_date?: string | null;
  payment_mode?: 'NEFT_RTGS' | 'CHEQUE' | 'BANK_TRANSFER' | 'UPI' | 'CASH' | null;
  payment_notes?: string | null;
}

export interface POLineItem {
  id?: number;
  line_number: number;
  material_item_id: number;
  item_code?: string;
  item_name?: string;
  uom_id: number;
  uom_code?: string;
  quantity: string | number;
  unit_rate_ex_gst: string | number;
  gst_percent: string | number;
  line_total: string | number;
  remarks?: string;
}

export interface PRLineItem {
  id?: number;
  line_number: number;
  material_item_id: number;
  item_code?: string;
  item_name?: string;
  uom_id: number;
  uom_code?: string;
  quantity: string | number;
  estimated_rate?: string | number | null;
  remarks?: string;
}

export interface PurchaseRequest {
  id: number;
  pr_number: string;
  department_id: number;
  department_name: string;
  requisitioner_id: string;
  requisitioner_role: string;
  request_date: string;
  target_date: string;
  justification: string;
  status: 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED' | 'CONVERTED_TO_PO' | 'CANCELLED';
  plant_head_approved_by?: string | null;
  plant_head_approved_at?: string | null;
  rejection_reason?: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  lines: PRLineItem[];
  audit_logs: AuditLog[];
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  pr_id?: number | null;
  pr_number?: string | null;
  po_date: string;
  expected_delivery_date: string;
  vendor_id: number;
  vendor_name: string;
  vendor_gstin?: string;
  department_id: number;
  department_name: string;
  payment_terms: string;
  delivery_terms?: string;
  notes?: string;
  total_amount_ex_gst: string | number;
  total_gst_amount: string | number;
  grand_total: string | number;
  status: 'DRAFT' | 'SUBMITTED' | 'DEPT_APPROVED' | 'SCM_APPROVED' | 'APPROVED' | 'ORDER_PLACED' | 'CLOSED' | 'REJECTED' | 'CANCELLED';
  current_approval_level: 'DEPARTMENT' | 'SUPPLY_CHAIN' | 'MANAGEMENT' | 'COMPLETED';
  dept_approved_by?: string | null;
  dept_approved_at?: string | null;
  scm_approved_by?: string | null;
  scm_approved_at?: string | null;
  mgmt_approved_by?: string | null;
  mgmt_approved_at?: string | null;
  order_placed_by?: string | null;
  order_placed_at?: string | null;
  vendor_order_ref?: string | null;
  rejection_reason?: string | null;
  grn_count?: number;
  fulfilled_percentage?: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  lines: POLineItem[];
  audit_logs: AuditLog[];
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

export type ReturnCondition =
  | 'UNUSED_GOOD'
  | 'MACHINE_SHOP_BORINGS'
  | 'FOUNDRY_RETURNS'
  | 'REJECTED_CASTINGS'
  | 'DAMAGED_CONTAMINATED';

export type ReturnStatus = 'DRAFT' | 'SUBMITTED' | 'ACCEPTED' | 'REJECTED';

export interface MaterialReturnLineItem {
  id?: number;
  return_id?: number;
  line_number: number;
  material_item_id: number;
  uom_id: number;
  quantity: string | number;
  condition: ReturnCondition;
  remarks?: string;
  item_code?: string;
  item_name?: string;
  uom_code?: string;
}

export interface MaterialReturn {
  id: number;
  return_number: string;
  return_date: string;
  returning_department_id: number;
  returning_department_name?: string;
  receiving_department_id: number;
  receiving_department_name?: string;
  reference_issue_id?: number | null;
  heat_reference_number?: string | null;
  condition: ReturnCondition;
  status: ReturnStatus;
  notes?: string | null;
  rejection_reason?: string | null;
  created_by: string;
  accepted_by?: string | null;
  accepted_at?: string | null;
  created_at: string;
  updated_at: string;
  lines: MaterialReturnLineItem[];
  audit_logs: AuditLog[];
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
  // Foundry Return vs External Disposal Stream
  disposition_stream?: 'RE_INWARD_TO_RM' | 'EXTERNAL_DISPOSAL';
  target_item_id?: number | null;
  target_item_code?: string | null;
  valuation_rate?: string | number | null;
  disposal_cost?: string | number | null;
}

export interface WasteDisposition {
  id: number;
  waste_number: string;
  disposition_date: string;
  waste_type: string;
  disposition_type: string;
  disposition_stream: 'RE_INWARD_TO_RM' | 'EXTERNAL_DISPOSAL';
  source_department_id: number;
  source_department_name?: string;
  destination_notes?: string | null;
  notes?: string | null;
  status: 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED' | 'CANCELLED';
  // Re-inward to RM fields
  target_item_id?: number | null;
  target_item_code?: string | null;
  valuation_rate?: string | number | null;
  ledger_posted?: boolean;
  // External Disposal fields
  disposal_cost?: string | number | null;
  disposal_contractor?: string | null;
  gate_pass_number?: string | null;
  photo_url?: string | null;
  photo_note?: string | null;
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

export interface UOMStockSummary {
  uom_id: number;
  uom_code: string;
  uom_name: string;
  decimal_precision: number;
  total_quantity: string | number;
  item_count: number;
  in_stock_items_count: number;
  zero_stock_items_count: number;
  negative_stock_items_count: number;
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

export interface HeatChargeLine {
  id?: number;
  heat_id?: number;
  line_number: number;
  material_item_id?: number | null;
  original_material_description: string;
  charged_quantity: string | number;
  uom_id: number;
  validation_status: string;
  source_row_reference?: string | null;
  remarks?: string | null;
  material_item?: MaterialItem;
  uom?: UOM;
}

export interface HeatPartsProduced {
  id?: number;
  heat_id?: number;
  line_number: number;
  part_item_id?: number | null;
  original_part_description: string;
  quantity_produced: string | number;
  unit_cast_weight?: string | number | null;
  weight_uom_id?: number | null;
  classification: string;
  source_row_reference?: string | null;
  remarks?: string | null;
}

export interface HeatHeader {
  id: number;
  heat_number: string;
  original_heat_number: string;
  normalized_heat_number: string;
  heat_date: string;
  furnace_id?: string | null;
  shift?: string | null;
  metal_tapped_weight?: string | number | null;
  metal_tapped_uom_id?: number | null;
  production_status: string;
  source_document_reference?: string | null;
  notes?: string | null;
  opening_liquid_heel_kg?: string | number | null;
  closing_liquid_heel_kg?: string | number | null;
  heel_measurement_method?: string | null;
  heel_recorded_by?: string | null;
  heel_verified_by?: string | null;
  heel_verified_at?: string | null;
  heel_verification_status?: string | null;
  is_cold_start?: boolean;
  is_furnace_empty?: boolean;
  opening_heel_source_heat_id?: number | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  charge_lines: HeatChargeLine[];
  parts_produced: HeatPartsProduced[];
}

export interface MaterialAlias {
  id: number;
  alias_text: string;
  normalized_alias_key: string;
  material_item_id: number;
  is_active: boolean;
  status: string;
  reviewer_id?: string | null;
  reviewed_at?: string | null;
  decision_notes?: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  material_item?: MaterialItem;
}

export interface ReconciliationResult {
  id: number;
  run_id: number;
  material_item_id?: number | null;
  heat_id?: number | null;
  match_method: string;
  issued_quantity: string | number;
  charged_quantity: string | number;
  variance_quantity: string | number;
  variance_percentage?: string | number | null;
  applied_tolerance: string | number;
  tolerance_basis: string;
  variance_class: string;
  contributing_issue_ids?: string | null;
  contributing_issue_line_ids?: string | null;
  contributing_heat_ids?: string | null;
  contributing_charge_line_ids?: string | null;
  notes?: string | null;
  status: string;
  uom_code?: string | null;
  material_item?: MaterialItem;
  heat?: HeatHeader;
}

export interface ReconciliationCandidateMatch {
  id: number;
  run_id: number;
  issue_line_id: number;
  heat_charge_line_id: number;
  confidence_score: string | number;
  suggestion_reason: string;
  status: string;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  review_comments?: string | null;
  issue_line?: any;
  charge_line?: any;
}

export interface ReconciliationException {
  id: number;
  run_id: number;
  exception_type: string;
  source_reference: string;
  description: string;
  assigned_role: string;
  priority: string;
  status: string;
  resolution_comments?: string | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReconciliationRun {
  id: number;
  run_number: string;
  algorithm_version: string;
  date_from?: string | null;
  date_to?: string | null;
  status: string;
  total_evaluated_count: number;
  exact_matches_count: number;
  batch_matches_count: number;
  fuzzy_candidates_count: number;
  discrepancies_count: number;
  segregated_consumables_count?: number;
  segregated_consumables_quantity?: string | number;
  notes?: string | null;
  created_by: string;
  created_at: string;
  results?: ReconciliationResult[];
  candidate_matches?: ReconciliationCandidateMatch[];
  exceptions?: ReconciliationException[];
}

// ---- Costing & valuation contract --------------------------------------------------------------
// Mirrors backend/app/schemas/costing.py (the authority). backend/tests/test_costing_contract.py fails
// if a field declared here does not exist in the corresponding backend response schema.
// Decimal values arrive as JSON strings; only the exceptions endpoint returns plain numbers.

export interface ItemValuationSummary {
  material_item_id: number;
  item_code: string;
  item_name: string;
  department_name?: string | null;
  category: string;
  inventory_quantity: string;
  uom_code: string;
  weighted_average_rate?: string | null;
  extended_value?: string | null;
  as_of_date: string;
  valuation_status: string;
  rate_source?: string | null;
  anomaly_notes?: string | null;
}

export interface InventoryValuationReport {
  as_of_date: string;
  total_items: number;
  valued_items_count: number;
  unvalued_items_count: number;
  zero_stock_items_count: number;
  negative_stock_items_count: number;
  total_inventory_valuation: string;
  items: ItemValuationSummary[];
}

export interface ItemRateJournalEntry {
  stock_ledger_entry_id?: number | null;
  entry_number?: string | null;
  transaction_date: string;
  movement_type: string;
  quantity_delta: string;
  running_quantity: string;
  receipt_rate?: string | null;
  applied_rate?: string | null;
  resulting_average_rate?: string | null;
  movement_extended_value?: string | null;
  cumulative_value?: string | null;
  status: string;
  notes?: string | null;
}

export interface ItemRateJournal {
  material_item_id: number;
  item_code: string;
  item_name: string;
  uom_code: string;
  current_quantity: string;
  weighted_average_rate?: string | null;
  valuation_status: string;
  rate_source?: string | null;
  steps: ItemRateJournalEntry[];
}

export interface HeatCostLineSummary {
  heat_charge_line_id: number;
  line_number: number;
  material_item_id?: number | null;
  canonical_item_code?: string | null;
  canonical_item_name?: string | null;
  raw_material_description: string;
  charged_quantity: string;
  applicable_rate?: string | null;
  line_cost?: string | null;
  rate_source?: string | null;
  is_included: boolean;
  status: string;
  remarks?: string | null;
}

export interface HeatCostSummary {
  heat_id: number;
  heat_number: string;
  heat_date: string;
  furnace_id?: string | null;
  total_charged_quantity: string;
  total_material_cost: string;
  metal_tapped_weight?: string | null;
  cost_denominator_value?: string | null;
  denominator_type: string;
  cost_per_kg?: string | null;
  cost_scope: string;
  status: string;
  total_lines: number;
  valued_lines: number;
  unvalued_lines: number;
  lines: HeatCostLineSummary[];

  // Three Authoritative Costing Measures (Phase 2B-2B & Phase 2B-2C)
  measure_a_cost_per_kg?: string | null;
  measure_a_status?: string | null;
  measure_b_cost_per_kg?: string | null;
  measure_b_status?: string | null;
  measure_c_cost_per_kg?: string | null;
  measure_c_status?: string | null;

  // Liquid Heel & Continuity
  opening_liquid_heel_kg?: string | null;
  opening_liquid_heel_value?: string | null;
  closing_liquid_heel_kg?: string | null;
  closing_liquid_heel_value?: string | null;

  // Scrap Credit (FIN-DEC-03)
  approved_scrap_credit?: string | null;

  // Mass Balance & Melting Loss (FIN-DEC-04)
  true_melt_loss_kg?: string | null;
  true_melt_loss_pct?: string | null;
  melting_recovery_pct?: string | null;
  casting_yield_pct?: string | null;

  // Governance & Status (FIN-DEC-05 & FIN-DEC-06)
  conversion_cost_status?: string;
  is_historical_exception?: boolean;
  anomalies?: string[];
}

export interface PartCostSummary {
  heat_parts_produced_id: number;
  part_number: string;
  part_name: string;
  part_item_id?: number | null;
  quantity_produced: string;
  unit_cast_weight?: string | null;
  cost_per_kg?: string | null;
  part_material_cost_per_unit?: string | null;
  total_part_material_cost?: string | null;
  cost_scope: string;
  status: string;
  notes?: string | null;
}

export interface CostingRunSummary {
  id: number;
  run_number: string;
  calculation_version: string;
  period_start: string;
  period_end: string;
  as_of_date: string;
  denominator_policy: string;
  cost_scope: string;
  status: string;
  total_items_evaluated: number;
  valued_items_count: number;
  unvalued_items_count: number;
  total_inventory_valuation: string;
  total_heats_evaluated: number;
  completed_heats_count: number;
  partial_heats_count: number;
  total_heat_material_cost: string;
  summary_notes?: string | null;
  created_by: string;
  created_at: string;
}

export interface CostingExceptionRow {
  material_item_id: number;
  item_code: string;
  item_name: string;
  quantity: number;
  uom: string;
  issue: string;
}

/** GET /costing/exceptions (untyped dict on the backend; shape pinned by test_costing_contract.py). */
export interface CostingExceptionsReport {
  as_of_date: string;
  total_exceptions: number;
  missing_opening_valuation: CostingExceptionRow[];
  unvalued_stock: CostingExceptionRow[];
  negative_stock: CostingExceptionRow[];
}

export interface CostingComparisonSummary {
  summary: {
    run_1_number: string;
    run_2_number: string;
    run_1_as_of: string;
    run_2_as_of: string;
    valuation_run_1: number;
    valuation_run_2: number;
    valuation_delta: number;
    heat_cost_run_1: number;
    heat_cost_run_2: number;
    heat_cost_delta: number;
  };
  item_differences: Array<{
    material_item_id: number;
    item_code: string;
    item_name: string;
    run_1_rate?: number | null;
    run_2_rate?: number | null;
    rate_delta?: number | null;
    run_1_value?: number | null;
    run_2_value?: number | null;
    value_delta?: number | null;
    run_1_status?: string | null;
    run_2_status?: string | null;
  }>;
}

