/**
 * Client-Side Mock Handler for Standalone / Vercel Cloud Deployments.
 * 
 * Provides instantaneous, realistic API responses using the pre-seeded VSPL demo data
 * whenever a backend server is not reachable (e.g. hosted on Vercel without a local Python proxy).
 */

import demoData from './demoData.json' with { type: 'json' };

const CATEGORIES = [
  { code: 'RM', name: 'Raw Material', category: 'Raw Material', department_code: 'FDY', cost_head: 'Material Cost', description: 'Foundry · Material Cost' },
  { code: 'LN', name: 'Lining Material', category: 'Lining Material', department_code: 'FDY', cost_head: 'Lining Cost', description: 'Foundry · Lining Cost' },
  { code: 'MD', name: 'Moulding Material', category: 'Moulding Material', department_code: 'FDY', cost_head: 'Moulding Cost', description: 'Foundry · Moulding Cost' },
  { code: 'CN', name: 'Consumables', category: 'Consumables', department_code: 'FDY', cost_head: 'Foundry Consumables', description: 'Foundry · Foundry Consumables' },
  { code: 'PT', name: 'Paints & Coatings', category: 'Paints & Coatings', department_code: 'FDY', cost_head: 'Foundry Consumables', description: 'Foundry · Foundry Consumables' },
  { code: 'CB', name: 'Cutting Blades', category: 'Cutting Blades', department_code: 'MCS', cost_head: 'Machining Consumables', description: 'Machine Shop · Machining Consumables' },
  { code: 'IT', name: 'Inserts & Tools', category: 'Inserts & Tools', department_code: 'MCS', cost_head: 'Machining Consumables', description: 'Machine Shop · Machining Consumables' },
  { code: 'OL', name: 'Oils & Lubricants', category: 'Oils & Lubricants', department_code: 'MNT', cost_head: 'Maintenance Cost', description: 'Maintenance · Maintenance Cost' },
  { code: 'BR', name: 'Bearings', category: 'Bearings', department_code: 'MNT', cost_head: 'Maintenance Cost', description: 'Maintenance · Maintenance Cost' },
  { code: 'BL', name: 'Belts', category: 'Belts', department_code: 'MNT', cost_head: 'Maintenance Cost', description: 'Maintenance · Maintenance Cost' },
  { code: 'BN', name: 'Bolts & Nuts', category: 'Bolts & Nuts', department_code: 'MNT', cost_head: 'Maintenance Cost', description: 'Maintenance · Maintenance Cost' },
  { code: 'QC', name: 'Quality Material', category: 'Quality Material', department_code: 'QLY', cost_head: 'Quality Consumables', description: 'Quality · Quality Consumables' },
  { code: 'PK', name: 'Packing Material', category: 'Packing Material', department_code: 'PKD', cost_head: 'Packing Cost', description: 'Packing · Packing Cost' },
  { code: 'FU', name: 'Fuel', category: 'Fuel', department_code: 'UTL', cost_head: 'Energy / Fuel', description: 'Utilities · Energy / Fuel' },
  { code: 'SF', name: 'Safety Material', category: 'Safety Material', department_code: 'GEN', cost_head: 'Safety Cost', description: 'General/Stores · Safety Cost' },
];

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

// In-memory clones to allow interactive mutations during a live demo session
const liveItems = [...demoData.items];
const liveVendors = [...demoData.vendors];
const liveGrns = [...demoData.grns];
const liveIssues = [...demoData.issues];

// Ensure an approved Stores Issue exists linked to demo heat H-102603-3801 for instant floor verification
if (!liveIssues.some(i => i.heat_reference_number === 'H-102603-3801')) {
  liveIssues.unshift({
    id: 101,
    issue_slip_number: 'ISS-20261022-0042',
    issue_date: '2026-10-22',
    issuing_department_id: 4,
    issuing_department_name: 'General/Stores',
    receiving_department_id: 1,
    receiving_department_name: 'Foundry',
    heat_reference_number: 'H-102603-3801',
    notes: 'Furnace Charge Allocation for Heat 102603-3801 (SG Iron 500/7)',
    status: 'APPROVED',
    created_by: 'usr_stores_01',
    created_at: '2026-10-22T06:30:00Z',
    lines: [
      {
        id: 1,
        issue_id: 101,
        line_number: 1,
        material_item_id: 1,
        item_code: 'FDY-RM-001',
        item_name: 'Pig Iron (Foundry Grade 1)',
        uom_id: 1,
        uom_code: 'KG',
        quantity: '4000.0000',
        remarks: 'Base charge Pig Iron',
      },
      {
        id: 2,
        issue_id: 101,
        line_number: 2,
        material_item_id: 2,
        item_code: 'FDY-RM-002',
        item_name: 'CRCA Steel Scrap (Low Manganese)',
        uom_id: 1,
        uom_code: 'KG',
        quantity: '5500.0000',
        remarks: 'Low Mn scrap charge',
      },
      {
        id: 3,
        issue_id: 101,
        line_number: 3,
        material_item_id: 4,
        item_code: 'FDY-RM-004',
        item_name: 'Ferro Silicon 75% (FeSi)',
        uom_id: 1,
        uom_code: 'KG',
        quantity: '85.0000',
        remarks: 'Inoculation base alloy',
      },
    ],
  } as any);
}
const liveHeats = [...demoData.heats];
const liveWaste = [...demoData.waste];
const liveAudits = [...demoData.audits];
const liveRequests = [...demoData.requests];
const liveAliases = [...demoData.aliases];

const livePOs: any[] = [
  {
    id: 1,
    po_number: 'PO-202610-0001',
    po_date: '2026-10-15',
    expected_delivery_date: '2026-10-25',
    vendor_id: 1,
    vendor_name: 'Mahaveer Steel Traders',
    vendor_gstin: '29AABCM1234F1Z5',
    department_id: 1,
    department_name: 'Foundry',
    payment_terms: 'Net 30 Days',
    delivery_terms: 'Door Delivery to VSPL Works, Shimoga',
    notes: 'Urgent requirement for Grade S-4 Pig Iron for high-tensile casting batch',
    total_amount_ex_gst: '135000.00',
    total_gst_amount: '24300.00',
    grand_total: '159300.00',
    status: 'APPROVED',
    current_approval_level: 'COMPLETED',
    dept_approved_by: 'usr_foundry_hod',
    dept_approved_at: '2026-10-15T10:30:00Z',
    scm_approved_by: 'usr_purchase_head',
    scm_approved_at: '2026-10-15T14:15:00Z',
    mgmt_approved_by: 'usr_managing_director',
    mgmt_approved_at: '2026-10-16T09:00:00Z',
    rejection_reason: null,
    grn_count: 1,
    fulfilled_percentage: 100,
    created_by: 'usr_stores_01',
    created_at: '2026-10-15T09:00:00Z',
    updated_at: '2026-10-16T09:00:00Z',
    lines: [
      {
        id: 1,
        line_number: 1,
        material_item_id: 1,
        item_code: 'FDY-RM-001',
        item_name: 'Pig Iron (Foundry Grade S-4)',
        uom_id: 1,
        uom_code: 'KG',
        quantity: 3000,
        unit_rate_ex_gst: 45.0,
        gst_percent: 18,
        line_total: '159300.00',
        remarks: 'Test certificate required with each heat lot',
      },
    ],
    audit_logs: [
      { id: 1, action: 'CREATED', from_status: 'DRAFT', to_status: 'DRAFT', actor_id: 'usr_stores_01', timestamp: '2026-10-15T09:00:00Z' },
      { id: 2, action: 'DEPT_APPROVED', from_status: 'SUBMITTED', to_status: 'DEPT_APPROVED', actor_id: 'usr_foundry_hod', timestamp: '2026-10-15T10:30:00Z' },
      { id: 3, action: 'SCM_APPROVED', from_status: 'DEPT_APPROVED', to_status: 'SCM_APPROVED', actor_id: 'usr_purchase_head', timestamp: '2026-10-15T14:15:00Z' },
      { id: 4, action: 'APPROVED', from_status: 'SCM_APPROVED', to_status: 'APPROVED', actor_id: 'usr_managing_director', timestamp: '2026-10-16T09:00:00Z' },
    ],
  },
  {
    id: 2,
    po_number: 'PO-202610-0002',
    po_date: '2026-10-22',
    expected_delivery_date: '2026-10-30',
    vendor_id: 2,
    vendor_name: 'Apex Refractories & Minerals',
    vendor_gstin: '29AADCA5678B1Z2',
    department_id: 1,
    department_name: 'Foundry',
    payment_terms: '100% Against PI / Advance',
    delivery_terms: 'FOR Destination',
    notes: 'Furnace lining refractory patching compound',
    total_amount_ex_gst: '80000.00',
    total_gst_amount: '14400.00',
    grand_total: '94400.00',
    status: 'SCM_APPROVED',
    current_approval_level: 'MANAGEMENT',
    dept_approved_by: 'usr_foundry_hod',
    dept_approved_at: '2026-10-22T11:00:00Z',
    scm_approved_by: 'usr_purchase_head',
    scm_approved_at: '2026-10-22T16:00:00Z',
    mgmt_approved_by: null,
    mgmt_approved_at: null,
    rejection_reason: null,
    grn_count: 0,
    fulfilled_percentage: 0,
    created_by: 'usr_purchase_01',
    created_at: '2026-10-22T10:00:00Z',
    updated_at: '2026-10-22T16:00:00Z',
    lines: [
      {
        id: 2,
        line_number: 1,
        material_item_id: 2,
        item_code: 'FDY-LN-001',
        item_name: 'Silica Ramming Mass (Premium)',
        uom_id: 1,
        uom_code: 'KG',
        quantity: 2000,
        unit_rate_ex_gst: 40.0,
        gst_percent: 18,
        line_total: '94400.00',
        remarks: 'Moisture proof 50kg bags',
      },
    ],
    audit_logs: [
      { id: 1, action: 'CREATED', from_status: 'DRAFT', to_status: 'SUBMITTED', actor_id: 'usr_purchase_01', timestamp: '2026-10-22T10:00:00Z' },
      { id: 2, action: 'DEPT_APPROVED', from_status: 'SUBMITTED', to_status: 'DEPT_APPROVED', actor_id: 'usr_foundry_hod', timestamp: '2026-10-22T11:00:00Z' },
      { id: 3, action: 'SCM_APPROVED', from_status: 'DEPT_APPROVED', to_status: 'SCM_APPROVED', actor_id: 'usr_purchase_head', timestamp: '2026-10-22T16:00:00Z' },
    ],
  },
  {
    id: 3,
    po_number: 'PO-202610-0003',
    po_date: '2026-10-25',
    expected_delivery_date: '2026-11-05',
    vendor_id: 3,
    vendor_name: 'Pioneer Industrial Tools',
    vendor_gstin: '29AAACP9988C1Z8',
    department_id: 2,
    department_name: 'Machine Shop',
    payment_terms: 'Net 45 Days',
    delivery_terms: 'Door Delivery to VSPL Works',
    notes: 'Carbide inserts for CNC milling machines',
    total_amount_ex_gst: '40000.00',
    total_gst_amount: '7200.00',
    grand_total: '47200.00',
    status: 'SUBMITTED',
    current_approval_level: 'DEPARTMENT',
    dept_approved_by: null,
    dept_approved_at: null,
    scm_approved_by: null,
    scm_approved_at: null,
    mgmt_approved_by: null,
    mgmt_approved_at: null,
    rejection_reason: null,
    grn_count: 0,
    fulfilled_percentage: 0,
    created_by: 'usr_machining_01',
    created_at: '2026-10-25T14:00:00Z',
    updated_at: '2026-10-25T14:00:00Z',
    lines: [
      {
        id: 3,
        line_number: 1,
        material_item_id: 3,
        item_code: 'MCS-IT-001',
        item_name: 'CNMG 120408 Carbide Insert',
        uom_id: 4,
        uom_code: 'NOS',
        quantity: 100,
        unit_rate_ex_gst: 400.0,
        gst_percent: 18,
        line_total: '47200.00',
        remarks: 'Batch ISO certified',
      },
    ],
    audit_logs: [
      { id: 1, action: 'CREATED', from_status: 'DRAFT', to_status: 'SUBMITTED', actor_id: 'usr_machining_01', timestamp: '2026-10-25T14:00:00Z' },
    ],
  },
];

const liveReconciliationRuns: any[] = [
  {
    id: 1,
    run_number: 'RUN-20261026-001',
    algorithm_version: 'v1.0.0-dual-track',
    date_from: '2026-10-25',
    date_to: '2026-10-26',
    status: 'COMPLETED',
    total_evaluated_count: 8,
    exact_matches_count: 5,
    batch_matches_count: 1,
    fuzzy_candidates_count: 1,
    discrepancies_count: 1,
    notes: 'Daily furnace charge audit across Shift A and Shift B',
    created_by: 'usr_management_01',
    created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
    results: [
      {
        id: 1,
        run_id: 1,
        material_item_id: 1,
        heat_id: 1,
        match_method: 'EXACT_HEAT_TAG',
        issued_quantity: '1200.00',
        charged_quantity: '1200.00',
        variance_quantity: '0.00',
        variance_percentage: '0.00',
        applied_tolerance: '1.50',
        status: 'MATCHED',
        material_item: { id: 1, item_code: 'FDY-RM-001', name: 'Pig Iron (Foundry Grade S-4)', base_uom_id: 1 },
        heat: { id: 1, heat_number: 'HT-20261026-01', heat_date: '2026-10-26' },
      },
      {
        id: 2,
        run_id: 1,
        material_item_id: 2,
        heat_id: 1,
        match_method: 'EXACT_HEAT_TAG',
        issued_quantity: '450.00',
        charged_quantity: '445.00',
        variance_quantity: '-5.00',
        variance_percentage: '-1.11',
        applied_tolerance: '2.00',
        status: 'MATCHED_WITHIN_TOLERANCE',
        material_item: { id: 2, item_code: 'FDY-RM-002', name: 'Mild Steel Melting Scrap', base_uom_id: 1 },
        heat: { id: 1, heat_number: 'HT-20261026-01', heat_date: '2026-10-26' },
      },
      {
        id: 3,
        run_id: 1,
        material_item_id: 3,
        heat_id: 2,
        match_method: 'TIME_WINDOW_BATCH',
        issued_quantity: '300.00',
        charged_quantity: '276.00',
        variance_quantity: '-24.00',
        variance_percentage: '-8.00',
        applied_tolerance: '2.00',
        status: 'DISCREPANCY',
        notes: 'Excess burn loss or unrecorded furnace runner top-up',
        material_item: { id: 3, item_code: 'FDY-RM-003', name: 'Cast Iron Scrap (Grade A)', base_uom_id: 1 },
        heat: { id: 2, heat_number: 'HT-20261026-02', heat_date: '2026-10-26' },
      },
    ],
    candidate_matches: [
      {
        id: 1,
        run_id: 1,
        issue_line_id: 101,
        heat_charge_line_id: 201,
        confidence_score: '0.88',
        suggestion_reason: 'Matching Pig Iron grade issued 1.5 hours prior to Heat HT-20261026-02 charge start',
        status: 'PENDING_REVIEW',
        issue_line: { id: 101, item_code: 'FDY-RM-001', quantity: '250.00', uom_code: 'KG' },
        charge_line: { id: 201, item_code: 'FDY-RM-001', charged_quantity: '250.00', heat_number: 'HT-20261026-02' },
      },
    ],
    exceptions: [
      {
        id: 1,
        run_id: 1,
        exception_type: 'UNRECORDED_HEAT_CHARGE',
        source_reference: 'ISS-20261026-0003',
        description: 'Material issued to Foundry floor but no corresponding charge logged in Heat Log HT-20261026-02',
        assigned_role: 'Foundry',
        priority: 'HIGH',
        status: 'OPEN',
        created_at: new Date(Date.now() - 3600000 * 3).toISOString(),
        updated_at: new Date(Date.now() - 3600000 * 3).toISOString(),
      },
    ],
  },
];

export function handleMockRequest(urlStr: string, init?: RequestInit): Response | null {
  const method = (init?.method || 'GET').toUpperCase();
  const url = new URL(urlStr, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
  const rawPath = url.pathname;
  const path = rawPath.endsWith('/') && rawPath.length > 1 ? rawPath.slice(0, -1) : rawPath;
  const matchPath = (target: string) => rawPath.replace(/\/?$/, '/') === (target.endsWith('/') ? target : target + '/');

  // 1. Health checks
  if (path === '/api/v1/health') {
    return jsonResponse({
      status: 'healthy',
      app_name: 'VSPL Material Management & Costing System',
      environment: 'production',
      version: '0.2.0',
      costing_start_date: '2026-10-12',
      database: {
        connected: true,
        status: 'connected',
        message: 'Database operational (Supabase PostgreSQL · Demo Mode Active)',
      },
      timestamp: new Date().toISOString(),
    });
  }

  if (path === '/api/v1/health/db-check') {
    return jsonResponse({
      status: 'healthy',
      connected: true,
      pool_size: 10,
      database: 'Supabase PostgreSQL (AWS ap-southeast-2)',
      tables_count: 38,
      timestamp: new Date().toISOString(),
    });
  }

  // 2. Auth routes
  if (path === '/api/v1/auth/status') {
    return jsonResponse({ provider: 'dev', login_available: true });
  }

  if (path === '/api/v1/auth/me') {
    return jsonResponse({ user_id: 'usr_admin_01', role: 'Admin', department: 'Admin' });
  }

  if (path === '/api/v1/auth/dev-login') {
    let role = 'Admin';
    try {
      if (init?.body) {
        const parsed = JSON.parse(String(init.body));
        role = parsed.role || 'Admin';
      }
    } catch {}
    return jsonResponse({
      access_token: 'mock_demo_token_' + Date.now(),
      token_type: 'bearer',
      user: { user_id: `usr_${role.toLowerCase()}_01`, role, department: role },
    });
  }

  // 3. Departments & UOMs
  if (path === '/api/v1/departments') {
    return jsonResponse(demoData.departments);
  }

  if (path === '/api/v1/uoms') {
    return jsonResponse(demoData.uoms);
  }

  // 4. Item categories & Nomenclature rules
  if (path === '/api/v1/items/categories') {
    return jsonResponse(CATEGORIES);
  }

  if (path === '/api/v1/item-codes/rules') {
    return jsonResponse((demoData as any).rules || {
      standard: 'VSPL Item Nomenclature Standard',
      version: '1.0',
      code_format: 'DEPT-CAT-###',
      code_pattern: '^([A-Z]{3})-([A-Z]{2})-([0-9]{3})$',
      serial_min: 1,
      serial_max: 999,
      naming_formula: 'Primary Noun → Type / Grade → Size / Specification → Material / Variant',
      departments: demoData.departments.map(d => ({ code: d.code, name: d.name, department_id: d.id, provisioned: true })),
      categories: CATEGORIES.map(c => ({
        code: c.code,
        name: c.name,
        department_code: c.department_code,
        cost_head: c.cost_head,
        pattern: '{Primary Noun} {Grade} {Size}',
        example: `${c.name} Spec-1`,
        verbatim_description: false,
      })),
      uoms: demoData.uoms.map(u => ({ code: u.code, label: u.name, meaning: u.name, uom_id: u.id, provisioned: true })),
      uom_aliases: [],
      abbreviations: [],
      registry_installed: true,
      unprovisioned_departments: [],
      unprovisioned_uoms: [],
    });
  }

  if (path === '/api/v1/item-codes/preview') {
    let deptCode = 'FDY';
    let catCode = 'RM';
    try {
      const b = JSON.parse(String(init?.body || '{}'));
      if (b.department_id) {
        const d = demoData.departments.find(x => x.id === b.department_id);
        if (d) deptCode = d.code;
      }
      if (b.category) catCode = b.category;
    } catch {}
    return jsonResponse({
      valid: true,
      provisional: true,
      proposed_code: `${deptCode}-${catCode}-015`,
      next_serial: 15,
      serials_remaining: 984,
      department_code: deptCode,
      category_code: catCode,
      category_name: 'Standard Category',
      canonical_description: 'PREVIEW ITEM',
      cost_head: 'Material Cost',
      errors: [],
      warnings: [],
      issues: [],
      duplicates: [],
      registry_installed: true,
      standard_version: '1.0',
      note: 'Provisional next code',
    });
  }

  // 5. Items
  if (path === '/api/v1/items') {
    const q = (url.searchParams.get('q') || '').toLowerCase();
    const deptId = url.searchParams.get('department_id');
    const cat = (url.searchParams.get('category') || '').toLowerCase();
    const page = parseInt(url.searchParams.get('page') || '1', 10);
    const size = parseInt(url.searchParams.get('size') || url.searchParams.get('limit') || '50', 10);

    let filtered = liveItems;
    if (q) {
      filtered = filtered.filter(i => i.item_code.toLowerCase().includes(q) || i.name.toLowerCase().includes(q));
    }
    if (deptId) {
      filtered = filtered.filter(i => String(i.department_id) === deptId);
    }
    if (cat) {
      filtered = filtered.filter(i => (i.category || '').toLowerCase() === cat);
    }

    const start = (page - 1) * size;
    const paginated = filtered.slice(start, start + size);
    return jsonResponse({
      items: paginated,
      total: filtered.length,
      page,
      size,
    });
  }

  if (path.startsWith('/api/v1/items/') && path.endsWith('/history')) {
    const id = parseInt(path.split('/')[4], 10);
    const item = liveItems.find(i => i.id === id);
    return jsonResponse({
      item_id: id,
      item_code: item?.item_code || '',
      registry_installed: true,
      registry: {
        item_code: item?.item_code || '',
        department_code: item?.item_code?.split('-')[0] || 'FDY',
        category_code: item?.item_code?.split('-')[1] || 'RM',
        serial: 1,
        standard_version: '1.0',
        issued_by: 'usr_admin_01',
        issued_at: new Date().toISOString(),
      },
      events: [
        {
          id: 1,
          action: 'REGISTERED',
          field_name: null,
          old_value: null,
          new_value: item?.name || null,
          reason: 'Initial master item registration in VSPL catalog.',
          actor_id: 'usr_admin_01',
          actor_role: 'Admin',
          timestamp: new Date().toISOString(),
        }
      ],
    });
  }

  if (path.startsWith('/api/v1/items/')) {
    const id = parseInt(path.split('/')[4], 10);
    const it = liveItems.find(i => i.id === id);
    return it ? jsonResponse(it) : jsonResponse({ detail: 'Item not found' }, 404);
  }

  // 6. Vendors
  if (path === '/api/v1/vendors') {
    const q = (url.searchParams.get('q') || '').toLowerCase();
    const page = parseInt(url.searchParams.get('page') || '1', 10);
    const size = parseInt(url.searchParams.get('size') || url.searchParams.get('limit') || '50', 10);

    let filtered = liveVendors;
    if (q) {
      filtered = filtered.filter(v => v.name.toLowerCase().includes(q) || (v.gstin || '').toLowerCase().includes(q));
    }
    const start = (page - 1) * size;
    return jsonResponse({
      items: filtered.slice(start, start + size),
      total: filtered.length,
      page,
      size,
    });
  }

  if (path.startsWith('/api/v1/vendors/')) {
    const id = parseInt(path.split('/')[4], 10);
    const vIndex = liveVendors.findIndex(x => x.id === id);
    if (vIndex < 0) return jsonResponse({ detail: 'Vendor not found' }, 404);
    if (method === 'PUT') {
      try {
        const body = JSON.parse(String(init?.body || '{}'));
        liveVendors[vIndex] = {
          ...liveVendors[vIndex],
          name: body.name !== undefined ? body.name : liveVendors[vIndex].name,
          gstin: body.gstin !== undefined ? body.gstin : liveVendors[vIndex].gstin,
          contact_person: body.contact_person !== undefined ? body.contact_person : liveVendors[vIndex].contact_person,
          phone: body.phone !== undefined ? body.phone : liveVendors[vIndex].phone,
          email: body.email !== undefined ? body.email : liveVendors[vIndex].email,
          address: body.address !== undefined ? body.address : liveVendors[vIndex].address,
          is_active: body.is_active !== undefined ? body.is_active : liveVendors[vIndex].is_active,
          updated_at: new Date().toISOString(),
        };
        return jsonResponse(liveVendors[vIndex]);
      } catch {
        return jsonResponse({ detail: 'Invalid vendor payload' }, 400);
      }
    }
    return jsonResponse(liveVendors[vIndex]);
  }

  // 7. Stock Balances & Ledger
  if (path === '/api/v1/ledger/balances') {
    const q = (url.searchParams.get('q') || '').toLowerCase();
    let res = demoData.balances;
    if (q) {
      res = res.filter(b => b.item_code.toLowerCase().includes(q) || b.item_name.toLowerCase().includes(q));
    }
    return jsonResponse(res);
  }

  if (path === '/api/v1/ledger/entries') {
    return jsonResponse({
      items: demoData.balances.map((b, idx) => ({
        id: idx + 1,
        entry_date: '2026-10-12',
        transaction_type: 'OPENING_BALANCE',
        document_number: 'OB-20261012',
        material_item_id: b.material_item_id,
        quantity: b.current_balance,
        unit_rate: (b as any).unit_rate || '120.00',
        total_value: (b as any).total_value || '12000.00',
        notes: 'Baseline opening balance',
      })),
      total: demoData.balances.length,
      page: 1,
      size: 50,
    });
  }

  // 8. Goods Receipt Notes (GRN)
  if (matchPath('/api/v1/grn/')) {
    if (method === 'POST') {
      try {
        const body = JSON.parse(String(init?.body || '{}'));
        const newId = liveGrns.length + 1;
        const newGrn = {
          id: newId,
          grn_number: `GRN-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${String(newId).padStart(4, '0')}`,
          receipt_date: body.receipt_date || new Date().toISOString().slice(0, 10),
          source_type: body.source_type || 'EXTERNAL_VENDOR',
          vendor_id: body.vendor_id,
          vendor_name: liveVendors.find(v => v.id === body.vendor_id)?.name || 'External Vendor',
          vendor_invoice_no: body.vendor_invoice_no,
          invoice_date: body.invoice_date,
          reference_document: body.reference_document,
          notes: body.notes,
          status: 'DRAFT',
          created_by: 'usr_stores_01',
          created_at: new Date().toISOString(),
          lines: (body.lines || []).map((l: any, idx: number) => ({
            id: idx + 1,
            grn_id: newId,
            line_number: idx + 1,
            material_item_id: l.material_item_id,
            item_code: liveItems.find(i => i.id === l.material_item_id)?.item_code || '',
            item_name: liveItems.find(i => i.id === l.material_item_id)?.name || '',
            uom_id: l.uom_id || 1,
            uom_code: 'KG',
            quantity: String(l.quantity),
            rate_ex_gst: String(l.rate_ex_gst || 0),
            gst_percent: String(l.gst_percent || 18),
            remarks: l.remarks,
          })),
        };
        liveGrns.unshift(newGrn as any);
        return jsonResponse(newGrn, 201);
      } catch (e) {
        return jsonResponse({ detail: 'Failed to create GRN' }, 400);
      }
    }
    return jsonResponse(liveGrns);
  }

  if (path.startsWith('/api/v1/grn/')) {
    const parts = path.split('/');
    const grnId = parseInt(parts[4], 10);
    const action = parts[5];
    const grn = liveGrns.find(g => g.id === grnId);
    let body: any = {};
    try { body = JSON.parse(String(init?.body || '{}')); } catch {}

    if (action === 'submit' && grn) {
      grn.status = 'SUBMITTED';
      return jsonResponse(grn);
    }
    if (action === 'approve' && grn) {
      grn.status = 'APPROVED';
      (grn as any).quality_document_number = body.quality_document_number || (grn as any).quality_document_number || `TC-${new Date().getFullYear()}-${String(grnId).padStart(4, '0')}`;
      (grn as any).quality_inspection_status = body.quality_inspection_status || 'PASSED';
      (grn as any).quality_inspection_notes = body.quality_inspection_notes || body.comments || 'Mill Test Certificate and chemical specifications verified.';
      (grn as any).quality_inspected_by = 'usr_quality_01';
      (grn as any).quality_inspected_at = new Date().toISOString();
      if (!(grn as any).payment_status) {
        (grn as any).payment_status = 'PENDING';
      }
      return jsonResponse(grn);
    }
    if (action === 'reject' && grn) {
      grn.status = 'REJECTED';
      (grn as any).quality_document_number = body.quality_document_number || null;
      (grn as any).quality_inspection_status = 'REJECTED';
      (grn as any).quality_inspection_notes = body.quality_inspection_notes || body.comments || 'Quality criteria failed: visual defects or chemical composition non-conformance.';
      (grn as any).quality_inspected_by = 'usr_quality_01';
      (grn as any).quality_inspected_at = new Date().toISOString();
      return jsonResponse(grn);
    }
    if (action === 'cancel' && grn) {
      grn.status = 'CANCELLED';
      return jsonResponse(grn);
    }
    if (action === 'payment' && grn) {
      (grn as any).payment_status = body.payment_status || 'PAID';
      (grn as any).amount_paid = body.amount_paid || '54000.00';
      (grn as any).payment_reference = body.payment_reference || `UTR-HDFC-${Date.now().toString().slice(-8)}`;
      (grn as any).payment_date = body.payment_date || new Date().toISOString().slice(0, 10);
      (grn as any).payment_mode = body.payment_mode || 'NEFT_RTGS';
      (grn as any).payment_notes = body.payment_notes || 'Cleared via Corporate NetBanking';
      return jsonResponse(grn);
    }
    return grn ? jsonResponse(grn) : jsonResponse({ detail: 'GRN not found' }, 404);
  }

  // 9. Material Issues
  if (matchPath('/api/v1/issues/')) {
    if (method === 'POST') {
      try {
        const body = JSON.parse(String(init?.body || '{}'));
        const newId = liveIssues.length + 1;
        const newIssue = {
          id: newId,
          issue_slip_number: `ISS-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${String(newId).padStart(4, '0')}`,
          issue_date: body.issue_date || new Date().toISOString().slice(0, 10),
          issuing_department_id: body.issuing_department_id,
          issuing_department_name: demoData.departments.find(d => d.id === body.issuing_department_id)?.name || '',
          receiving_department_id: body.receiving_department_id,
          receiving_department_name: demoData.departments.find(d => d.id === body.receiving_department_id)?.name || '',
          heat_reference_number: body.heat_reference_number,
          notes: body.notes,
          status: 'DRAFT',
          created_by: 'usr_stores_01',
          created_at: new Date().toISOString(),
          lines: (body.lines || []).map((l: any, idx: number) => ({
            id: idx + 1,
            issue_id: newId,
            line_number: idx + 1,
            material_item_id: l.material_item_id,
            item_code: liveItems.find(i => i.id === l.material_item_id)?.item_code || '',
            item_name: liveItems.find(i => i.id === l.material_item_id)?.name || '',
            uom_id: l.uom_id || 1,
            uom_code: 'KG',
            quantity: String(l.quantity),
            remarks: l.remarks,
          })),
        };
        liveIssues.unshift(newIssue as any);
        return jsonResponse(newIssue, 201);
      } catch (e) {
        return jsonResponse({ detail: 'Failed to create Material Issue' }, 400);
      }
    }
    const statusParam = url.searchParams.get('status');
    const heatRefParam = url.searchParams.get('heat_reference_number');
    let filtered = [...liveIssues];
    if (statusParam) {
      filtered = filtered.filter(i => (i.status || '').toUpperCase() === statusParam.toUpperCase());
    }
    if (heatRefParam) {
      const q = heatRefParam.toLowerCase().replace(/[^a-z0-9]/g, '');
      filtered = filtered.filter(i => {
        if (!i.heat_reference_number) return false;
        const h = i.heat_reference_number.toLowerCase().replace(/[^a-z0-9]/g, '');
        return h.includes(q) || q.includes(h);
      });
    }
    return jsonResponse(filtered);
  }

  if (path.startsWith('/api/v1/issues/')) {
    const parts = path.split('/');
    const issueId = parseInt(parts[4], 10);
    const action = parts[5];
    const issue = liveIssues.find(i => i.id === issueId);
    if (action === 'submit' && issue) {
      issue.status = 'SUBMITTED';
      return jsonResponse(issue);
    }
    if (action === 'approve' && issue) {
      issue.status = 'APPROVED';
      return jsonResponse(issue);
    }
    return issue ? jsonResponse(issue) : jsonResponse({ detail: 'Material issue not found' }, 404);
  }

  // 10. Heats
  if (path === '/api/v1/heats') {
    if (method === 'POST') {
      try {
        const body = JSON.parse(String(init?.body || '{}'));
        const newId = liveHeats.length + 1;
        const newHeat = {
          id: newId,
          heat_number: body.heat_number,
          original_heat_number: body.heat_number,
          normalized_heat_number: body.heat_number.startsWith('H-') ? body.heat_number : `H-${body.heat_number}`,
          heat_date: body.heat_date || new Date().toISOString().slice(0, 10),
          furnace_id: body.furnace_id || 'FURNACE-1',
          shift: body.shift || 'SHIFT_A',
          metal_tapped_weight: body.metal_tapped_weight,
          metal_tapped_uom_id: body.metal_tapped_uom_id || 1,
          production_status: body.production_status || 'COMPLETED',
          notes: body.notes,
          charge_lines: (body.charge_lines || []).map((c: any, idx: number) => ({
            id: idx + 1,
            heat_id: newId,
            line_number: idx + 1,
            original_material_description: c.original_material_description,
            charged_quantity: String(c.charged_quantity),
            uom_id: c.uom_id || 1,
            remarks: c.remarks,
          })),
          parts_produced: (body.parts_produced || []).map((p: any, idx: number) => ({
            id: idx + 1,
            heat_id: newId,
            line_number: idx + 1,
            original_part_description: p.original_part_description,
            quantity_produced: String(p.quantity_produced),
            unit_cast_weight: p.unit_cast_weight,
            classification: p.classification || 'GOOD',
          })),
        };
        liveHeats.unshift(newHeat as any);
        return jsonResponse(newHeat, 201);
      } catch (e) {
        return jsonResponse({ detail: 'Failed to record heat' }, 400);
      }
    }
    const search = url.searchParams.get('search');
    let results = [...liveHeats];
    if (search) {
      const q = search.toLowerCase();
      results = results.filter(h => (h.heat_number || '').toLowerCase().includes(q) || (h.normalized_heat_number || '').toLowerCase().includes(q));
    }
    return jsonResponse(results);
  }

  // 11. Waste Dispositions
  if (matchPath('/api/v1/waste/')) {
    if (method === 'POST') {
      try {
        const body = JSON.parse(String(init?.body || '{}'));
        const newId = liveWaste.length + 1;
        const newWaste = {
          id: newId,
          waste_number: `WST-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${String(newId).padStart(4, '0')}`,
          disposition_date: body.disposition_date || new Date().toISOString().slice(0, 10),
          waste_type: body.waste_type || 'BORINGS',
          disposition_type: body.disposition_type || 'INTERNAL_RECOVERY',
          disposition_stream: body.disposition_stream || 'RE_INWARD_TO_RM',
          source_department_id: body.source_department_id || 1,
          source_department_name: demoData.departments.find(d => d.id === body.source_department_id)?.name || 'Foundry',
          destination_notes: body.destination_notes,
          notes: body.notes,
          status: 'DRAFT',
          target_item_id: body.target_item_id || null,
          target_item_code: body.target_item_code || (body.target_item_id ? liveItems.find(i => i.id === body.target_item_id)?.item_code : 'FDY-RM-004'),
          valuation_rate: body.valuation_rate || '32.00',
          disposal_cost: body.disposal_cost || '0.00',
          disposal_contractor: body.disposal_contractor || null,
          gate_pass_number: body.gate_pass_number || null,
          photo_url: body.photo_url || null,
          created_by: 'usr_foundry_01',
          created_at: new Date().toISOString(),
          lines: (body.lines || []).map((l: any, idx: number) => ({
            id: idx + 1,
            line_number: idx + 1,
            material_item_id: l.material_item_id,
            item_code: liveItems.find(i => i.id === l.material_item_id)?.item_code || '',
            item_name: liveItems.find(i => i.id === l.material_item_id)?.name || '',
            uom_id: l.uom_id || 1,
            uom_code: 'KG',
            quantity: String(l.quantity),
            reason: l.reason,
          })),
          audit_logs: [
            {
              id: 1,
              action: 'CREATED',
              to_status: 'DRAFT',
              actor_id: 'usr_foundry_01',
              actor_role: 'Foundry',
              comments: 'Draft scrap disposition logged',
              timestamp: new Date().toISOString(),
            }
          ],
        };
        liveWaste.unshift(newWaste as any);
        return jsonResponse(newWaste, 201);
      } catch (e) {
        return jsonResponse({ detail: 'Failed to create waste disposition' }, 400);
      }
    }
    return jsonResponse(liveWaste);
  }

  if (path.startsWith('/api/v1/waste/')) {
    const parts = path.split('/');
    const wasteId = parseInt(parts[4], 10);
    const action = parts[5];
    const w = liveWaste.find(x => x.id === wasteId);
    if (!w) return jsonResponse({ detail: 'Waste record not found' }, 404);

    if (action === 'submit') {
      w.status = 'SUBMITTED';
      return jsonResponse(w);
    }
    if (action === 'approve') {
      w.status = 'APPROVED';
      if ((w as any).disposition_stream === 'RE_INWARD_TO_RM') {
        (w as any).ledger_posted = true;
        // Credit to target RM stock balance
        const targetCode = (w as any).target_item_code || 'FDY-RM-004';
        const bal = demoData.balances.find(b => b.item_code === targetCode);
        if (bal) {
          const qty = (w.lines || []).reduce((acc: number, l: any) => acc + Number(l.quantity || 0), 0);
          bal.current_balance = (Number(bal.current_balance) + qty).toFixed(2);
        }
      }
      return jsonResponse(w);
    }
    if (action === 'reject') {
      w.status = 'REJECTED';
      return jsonResponse(w);
    }
    return jsonResponse(w);
  }

  // 12. Physical Audits
  if (matchPath('/api/v1/physical-audits/')) {
    return jsonResponse(liveAudits);
  }

  // 13. Item Requests
  if (path === '/api/v1/item-requests/pending') {
    const pending = liveRequests.filter(r => r.status === 'SUBMITTED');
    return jsonResponse({ items: pending, total: pending.length, page: 1, size: 50 });
  }

  if (path === '/api/v1/item-requests') {
    if (method === 'POST') {
      try {
        const body = JSON.parse(String(init?.body || '{}'));
        const newId = liveRequests.length + 1;
        const newReq = {
          id: newId,
          request_number: `REQ-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${String(newId).padStart(4, '0')}`,
          department_id: body.department_id || 1,
          department_code: demoData.departments.find(d => d.id === body.department_id)?.code || 'FDY',
          department_name: demoData.departments.find(d => d.id === body.department_id)?.name || 'Foundry',
          category: body.category || 'RM',
          requested_item_name: body.proposed_name || 'New Item',
          description: body.description || '',
          base_uom_id: body.base_uom_id || 1,
          uom_code: demoData.uoms.find(u => u.id === body.base_uom_id)?.code || 'KG',
          status: 'DRAFT',
          proposed_item_code: body.proposed_item_code || 'FDY-RM-015',
          justification: body.justification || '',
          created_by: 'usr_admin_01',
          created_at: new Date().toISOString(),
        };
        liveRequests.unshift(newReq as any);
        return jsonResponse(newReq, 201);
      } catch (e) {
        return jsonResponse({ detail: 'Failed to create request' }, 400);
      }
    }
    return jsonResponse({ items: liveRequests, total: liveRequests.length, page: 1, size: 50 });
  }

  if (path === '/api/v1/item-requests/pending') {
    const pending = liveRequests.filter(r => r.status === 'SUBMITTED');
    return jsonResponse({ items: pending, total: pending.length, page: 1, size: 50 });
  }

  if (path.startsWith('/api/v1/item-requests/')) {
    const parts = path.split('/');
    const reqId = parseInt(parts[4], 10);
    const action = parts[5];
    const req = liveRequests.find(r => r.id === reqId || (r as any).request_number === parts[4]);
    if (action === 'submit' && req) {
      req.status = 'SUBMITTED';
      (req as any).submitted_at = new Date().toISOString();
      return jsonResponse(req);
    }
    if (action === 'approve' && req) {
      req.status = 'APPROVED';
      (req as any).decision_at = new Date().toISOString();
      (req as any).reviewer_id = 'usr_mgmt_01';
      return jsonResponse(req);
    }
    if (action === 'reject' && req) {
      req.status = 'REJECTED';
      (req as any).decision_at = new Date().toISOString();
      (req as any).reviewer_id = 'usr_mgmt_01';
      return jsonResponse(req);
    }
    if (action === 'cancel' && req) {
      req.status = 'CANCELLED';
      return jsonResponse(req);
    }
    return req ? jsonResponse(req) : jsonResponse({ detail: 'Item request not found' }, 404);
  }

  // 14. Material Aliases
  if (path === '/api/v1/material-aliases') {
    return jsonResponse(liveAliases);
  }

  // 15. Costing & Valuation (Phase 6)
  if (rawPath.startsWith('/api/v1/costing/valuation/current') || rawPath.startsWith('/api/v1/costing/valuation/historical') || rawPath.startsWith('/api/v1/costing/valuation/items/')) {
    return jsonResponse((demoData as any).valuation);
  }

  if (path === '/api/v1/costing/heats') {
    return jsonResponse((demoData as any).heat_costs || []);
  }

  if (path.startsWith('/api/v1/costing/rates/history/')) {
    const id = parseInt(path.split('/')[5], 10);
    const stored = (demoData as any).rate_journals?.[String(id)];
    if (stored) return jsonResponse(stored);

    const it = liveItems.find(i => i.id === id);
    const valItem = ((demoData as any).valuation?.items || []).find((x: any) => x.material_item_id === id);
    return jsonResponse({
      material_item_id: id,
      item_code: it?.item_code || 'FDY-RM-001',
      item_name: it?.name || 'Material Item',
      uom_code: it?.uom_code || 'KG',
      current_quantity: valItem?.quantity || '1000.0000',
      weighted_average_rate: valItem?.weighted_average_rate || '45.5000',
      valuation_status: valItem?.valuation_status || 'VALUED',
      rate_source: valItem?.rate_source || 'WEIGHTED_AVERAGE',
      steps: [
        {
          stock_ledger_entry_id: 1,
          entry_number: 'OB-20261012-001',
          transaction_date: '2026-10-12',
          movement_type: 'OPENING_BALANCE',
          quantity_delta: valItem?.quantity || '1000.0000',
          running_quantity: valItem?.quantity || '1000.0000',
          receipt_rate: valItem?.weighted_average_rate || '45.5000',
          applied_rate: valItem?.weighted_average_rate || '45.5000',
          resulting_average_rate: valItem?.weighted_average_rate || '45.5000',
          movement_extended_value: valItem?.extended_value || '45500.00',
          cumulative_value: valItem?.extended_value || '45500.00',
          status: 'OPENING_VALUED',
          notes: 'Baseline opening balance valuation',
        }
      ],
    });
  }

  if (path === '/api/v1/costing/runs') {
    if (method === 'POST') {
      const existing = ((demoData as any).costing_runs || [])[0];
      return jsonResponse(existing || {
        id: 1,
        run_number: `CRUN-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-0001`,
        calculation_version: '1.0.0',
        period_start: '2026-10-12',
        period_end: new Date().toISOString().slice(0, 10),
        as_of_date: new Date().toISOString().slice(0, 10),
        denominator_policy: 'METAL_TAPPED',
        cost_scope: 'MATERIAL_ONLY',
        status: 'COMPLETED',
        total_items_evaluated: 24,
        valued_items_count: 24,
        unvalued_items_count: 0,
        total_inventory_valuation: '4652929.18',
        total_heats_evaluated: 5,
        executed_by: 'usr_admin_01',
        executed_at: new Date().toISOString(),
      }, 201);
    }
    return jsonResponse((demoData as any).costing_runs || []);
  }

  if (path.startsWith('/api/v1/costing/runs/compare')) {
    return jsonResponse({
      run1: ((demoData as any).costing_runs || [])[0],
      run2: ((demoData as any).costing_runs || [])[0],
      item_differences: [],
      valuation_variance: '0.00',
    });
  }

  if (path === '/api/v1/costing/exceptions') {
    return jsonResponse((demoData as any).exceptions || {
      as_of_date: '2026-10-26',
      total_exceptions: 0,
      missing_opening_valuation: [],
      unvalued_stock: [],
      negative_stock: [],
    });
  }

  // 16. Purchase Orders (P2P Procurement)
  if (matchPath('/api/v1/purchase-orders/')) {
    if (method === 'POST') {
      try {
        const body = JSON.parse(String(init?.body || '{}'));
        const newId = livePOs.length + 1;
        const now = new Date();
        const vendor = liveVendors.find(v => v.id === body.vendor_id);
        const dept = demoData.departments.find(d => d.id === body.department_id);

        let subtotal = 0;
        let gstTotal = 0;
        const poLines = (body.lines || []).map((l: any, idx: number) => {
          const item = liveItems.find(i => i.id === l.material_item_id);
          const q = Number(l.quantity) || 0;
          const r = Number(l.unit_rate_ex_gst) || 0;
          const g = Number(l.gst_percent) || 0;
          const lineTot = q * r * (1 + g / 100);
          subtotal += q * r;
          gstTotal += (q * r * g) / 100;
          return {
            id: idx + 1,
            line_number: idx + 1,
            material_item_id: l.material_item_id,
            item_code: item?.item_code || '',
            item_name: item?.name || '',
            uom_id: l.uom_id || item?.base_uom_id || 1,
            uom_code: item?.uom_code || 'KG',
            quantity: q,
            unit_rate_ex_gst: r,
            gst_percent: g,
            line_total: lineTot.toFixed(2),
            remarks: l.remarks,
          };
        });

        const newPO = {
          id: newId,
          po_number: `PO-${now.toISOString().slice(0, 7).replace('-', '')}-${String(newId).padStart(4, '0')}`,
          po_date: body.po_date || now.toISOString().slice(0, 10),
          expected_delivery_date: body.expected_delivery_date || now.toISOString().slice(0, 10),
          vendor_id: body.vendor_id,
          vendor_name: vendor?.name || 'Approved Supplier',
          vendor_gstin: vendor?.gstin || null,
          department_id: body.department_id || 1,
          department_name: dept?.name || 'Foundry',
          payment_terms: body.payment_terms || 'Net 30 Days',
          delivery_terms: body.delivery_terms || 'Door Delivery to VSPL Works',
          notes: body.notes,
          total_amount_ex_gst: subtotal.toFixed(2),
          total_gst_amount: gstTotal.toFixed(2),
          grand_total: (subtotal + gstTotal).toFixed(2),
          status: 'DRAFT',
          current_approval_level: 'DEPARTMENT',
          created_by: 'usr_purchase_01',
          created_at: now.toISOString(),
          updated_at: now.toISOString(),
          lines: poLines,
          audit_logs: [
            { id: 1, action: 'CREATED', from_status: 'DRAFT', to_status: 'DRAFT', actor_id: 'usr_purchase_01', timestamp: now.toISOString() },
          ],
        };
        livePOs.unshift(newPO);
        return jsonResponse(newPO, 201);
      } catch {
        return jsonResponse({ detail: 'Failed to create PO' }, 400);
      }
    }
    return jsonResponse(livePOs);
  }

  if (path.startsWith('/api/v1/purchase-orders/')) {
    const parts = path.split('/');
    const poId = parseInt(parts[4], 10);
    const action = parts[5];
    const po = livePOs.find(p => p.id === poId);
    if (!po) return jsonResponse({ detail: 'Purchase order not found' }, 404);

    if (action === 'submit') {
      po.status = 'SUBMITTED';
      po.current_approval_level = 'DEPARTMENT';
      po.audit_logs.push({ id: po.audit_logs.length + 1, action: 'SUBMITTED', from_status: 'DRAFT', to_status: 'SUBMITTED', actor_id: 'usr_purchase_01', timestamp: new Date().toISOString() });
      return jsonResponse(po);
    }
    if (action === 'approve-dept') {
      po.status = 'DEPT_APPROVED';
      po.current_approval_level = 'SUPPLY_CHAIN';
      po.dept_approved_by = 'usr_foundry_hod';
      po.dept_approved_at = new Date().toISOString();
      po.audit_logs.push({ id: po.audit_logs.length + 1, action: 'DEPT_APPROVED', from_status: 'SUBMITTED', to_status: 'DEPT_APPROVED', actor_id: 'usr_foundry_hod', timestamp: new Date().toISOString() });
      return jsonResponse(po);
    }
    if (action === 'approve-scm') {
      po.status = 'SCM_APPROVED';
      po.current_approval_level = 'MANAGEMENT';
      po.scm_approved_by = 'usr_purchase_head';
      po.scm_approved_at = new Date().toISOString();
      po.audit_logs.push({ id: po.audit_logs.length + 1, action: 'SCM_APPROVED', from_status: 'DEPT_APPROVED', to_status: 'SCM_APPROVED', actor_id: 'usr_purchase_head', timestamp: new Date().toISOString() });
      return jsonResponse(po);
    }
    if (action === 'approve-mgmt') {
      po.status = 'APPROVED';
      po.current_approval_level = 'COMPLETED';
      po.mgmt_approved_by = 'usr_managing_director';
      po.mgmt_approved_at = new Date().toISOString();
      po.audit_logs.push({ id: po.audit_logs.length + 1, action: 'APPROVED', from_status: 'SCM_APPROVED', to_status: 'APPROVED', actor_id: 'usr_managing_director', timestamp: new Date().toISOString() });
      return jsonResponse(po);
    }
    if (action === 'reject') {
      let body: any = {};
      try { body = JSON.parse(String(init?.body || '{}')); } catch {}
      po.status = 'REJECTED';
      po.rejection_reason = body.comments || 'Rejected by approver';
      po.audit_logs.push({ id: po.audit_logs.length + 1, action: 'REJECTED', comments: po.rejection_reason, actor_id: 'usr_reviewer', timestamp: new Date().toISOString() });
      return jsonResponse(po);
    }
    if (action === 'cancel') {
      po.status = 'CANCELLED';
      return jsonResponse(po);
    }
    return jsonResponse(po);
  }

  // 17. Reconciliation
  if (path === '/api/v1/reconciliation/runs') {
    return jsonResponse(liveReconciliationRuns);
  }

  if (path.startsWith('/api/v1/reconciliation/runs/')) {
    const runId = parseInt(path.split('/')[5], 10);
    const run = liveReconciliationRuns.find(r => r.id === runId) || liveReconciliationRuns[0];
    return run ? jsonResponse(run) : jsonResponse({ detail: 'Run not found' }, 404);
  }

  if (path === '/api/v1/reconciliation/run') {
    let body: any = {};
    try { body = JSON.parse(String(init?.body || '{}')); } catch {}
    const newId = liveReconciliationRuns.length + 1;
    const now = new Date();
    const newRun = {
      id: newId,
      run_number: `RUN-${now.toISOString().slice(0, 10).replace(/-/g, '')}-${String(newId).padStart(3, '0')}`,
      algorithm_version: 'v1.0.0-dual-track',
      date_from: body.date_from || null,
      date_to: body.date_to || null,
      status: 'COMPLETED',
      total_evaluated_count: 6,
      exact_matches_count: 5,
      batch_matches_count: 1,
      fuzzy_candidates_count: 0,
      discrepancies_count: 0,
      notes: body.notes || 'Automated reconciliation run',
      created_by: 'usr_stores_01',
      created_at: now.toISOString(),
      results: [
        {
          id: 10,
          run_id: newId,
          material_item_id: 1,
          heat_id: 1,
          match_method: 'EXACT_HEAT_TAG',
          issued_quantity: '1000.00',
          charged_quantity: '1000.00',
          variance_quantity: '0.00',
          variance_percentage: '0.00',
          applied_tolerance: '1.50',
          status: 'MATCHED',
          material_item: liveItems[0],
          heat: { id: 1, heat_number: 'HT-20261026-01', heat_date: '2026-10-26' },
        },
      ],
      candidate_matches: [],
      exceptions: [],
    };
    liveReconciliationRuns.unshift(newRun);
    return jsonResponse(newRun, 201);
  }

  if (path.includes('/reconciliation/candidates/')) {
    const parts = path.split('/');
    const candidateId = parseInt(parts[5], 10);
    const action = parts[6];
    for (const r of liveReconciliationRuns) {
      const c = (r.candidate_matches || []).find((x: any) => x.id === candidateId);
      if (c) {
        c.status = action === 'confirm' ? 'CONFIRMED' : 'REJECTED';
        c.reviewed_by = 'usr_supervisor';
        c.reviewed_at = new Date().toISOString();
        return jsonResponse(c);
      }
    }
    return jsonResponse({ id: candidateId, status: action === 'confirm' ? 'CONFIRMED' : 'REJECTED' });
  }

  if (path.includes('/reconciliation/exceptions/')) {
    const parts = path.split('/');
    const excId = parseInt(parts[5], 10);
    for (const r of liveReconciliationRuns) {
      const exc = (r.exceptions || []).find((x: any) => x.id === excId);
      if (exc) {
        exc.status = 'RESOLVED';
        exc.resolved_by = 'usr_supervisor';
        exc.resolved_at = new Date().toISOString();
        return jsonResponse(exc);
      }
    }
    return jsonResponse({ id: excId, status: 'RESOLVED' });
  }

  return null;
}
