import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getMatchMethodLabel,
  getVarianceClassLabel,
  getMatchMethodBadgeClass,
  getVarianceBadgeClass,
  calculateSegregatedConsumablesSummary,
  filterReconciliationResults,
  parseIssueSlipNumber,
  parseIssueId,
} from './reconciliation.ts';
import type { ReconciliationResult } from '../types.ts';

test('Reconciliation status labels return correct human-friendly names while preserving enums', () => {
  // CONSUMABLE_SEGREGATED
  assert.equal(
    getMatchMethodLabel('CONSUMABLE_SEGREGATED'),
    'Consumable — excluded from heat matching'
  );
  assert.equal(
    getVarianceClassLabel('CONSUMABLE_SEGREGATED'),
    'Consumable — excluded from heat matching'
  );

  // PENDING_REVIEW
  assert.equal(
    getVarianceClassLabel('PENDING_REVIEW'),
    'Pending material classification review'
  );

  // Other standard enums
  assert.equal(getMatchMethodLabel('EXACT_HEAT_SLIP'), 'Exact Heat-Slip Match');
  assert.equal(getMatchMethodLabel('SAME_DAY_BATCH'), 'Same-Day Batch Aggregation');
  assert.equal(getMatchMethodLabel('MANUAL_CONFIRMED'), 'Manual Confirmed');
  assert.equal(getMatchMethodLabel('UNMATCHED_SLIP'), 'Unmatched Issue Slip');
  assert.equal(getMatchMethodLabel('UNMATCHED_HEAT'), 'Unmatched Heat Charge');

  // Unknown fallback returns original enum string
  assert.equal(getMatchMethodLabel('CUSTOM_UNKNOWN'), 'CUSTOM_UNKNOWN');
  assert.equal(getVarianceClassLabel('CUSTOM_UNKNOWN'), 'CUSTOM_UNKNOWN');
});

test('Reconciliation badge styling maps correctly', () => {
  assert.equal(getMatchMethodBadgeClass('CONSUMABLE_SEGREGATED'), 'badge-info');
  assert.equal(getMatchMethodBadgeClass('EXACT_HEAT_SLIP'), 'badge-success');
  assert.equal(getMatchMethodBadgeClass('SAME_DAY_BATCH'), 'badge-secondary');
  assert.equal(getMatchMethodBadgeClass('UNMATCHED_SLIP'), 'badge-warning');

  assert.equal(getVarianceBadgeClass('PENDING_REVIEW'), 'badge-warning');
  assert.equal(getVarianceBadgeClass('CONSUMABLE_SEGREGATED'), 'badge-info');
  assert.equal(getVarianceBadgeClass('OK'), 'badge-success');
  assert.equal(getVarianceBadgeClass('SHORT_ISSUE'), 'badge-danger');
  assert.equal(getVarianceBadgeClass('EXCESS_ISSUE'), 'badge-warning');
});

test('calculateSegregatedConsumablesSummary calculates line count and quantity without double counting', () => {
  const sampleResults: ReconciliationResult[] = [
    {
      id: 1,
      run_id: 10,
      material_item_id: 101,
      match_method: 'CONSUMABLE_SEGREGATED',
      issued_quantity: '25.0000',
      charged_quantity: '0.0000',
      variance_quantity: '25.0000',
      applied_tolerance: '0.0000',
      tolerance_basis: 'Segregated floor/moulding consumable (excluded from furnace bath charge matching)',
      variance_class: 'OK',
      status: 'SEGREGATED',
    },
    {
      id: 2,
      run_id: 10,
      material_item_id: 102,
      match_method: 'CONSUMABLE_SEGREGATED',
      issued_quantity: '1000.0000',
      charged_quantity: '0.0000',
      variance_quantity: '1000.0000',
      applied_tolerance: '0.0000',
      tolerance_basis: 'Segregated floor/moulding consumable (excluded from furnace bath charge matching)',
      variance_class: 'OK',
      status: 'SEGREGATED',
    },
    {
      id: 3,
      run_id: 10,
      material_item_id: 103,
      heat_id: 5,
      match_method: 'EXACT_HEAT_SLIP',
      issued_quantity: '500.0000',
      charged_quantity: '500.0000',
      variance_quantity: '0.0000',
      applied_tolerance: '10.0000',
      tolerance_basis: 'Standard tolerance',
      variance_class: 'OK',
      status: 'RESOLVED',
    },
    {
      id: 4,
      run_id: 10,
      material_item_id: 104,
      heat_id: 6,
      match_method: 'SAME_DAY_BATCH',
      issued_quantity: '200.0000',
      charged_quantity: '195.0000',
      variance_quantity: '5.0000',
      applied_tolerance: '4.0000',
      tolerance_basis: 'Standard tolerance',
      variance_class: 'EXCESS_ISSUE',
      status: 'FLAGGED',
    },
  ];

  const summary = calculateSegregatedConsumablesSummary(sampleResults);
  assert.equal(summary.count, 2, 'Must count exactly 2 segregated lines');
  assert.equal(summary.totalQuantity, 1025.0, 'Must sum 25.0 + 1000.0 = 1025.0');
  assert.equal(summary.formattedSummary, '1,025.00 KG');
  assert.equal(summary.byUom['KG'], 1025.0);
});

test('calculateSegregatedConsumablesSummary correctly segregates mixed UOMs and never combines to kg', () => {
  const mixedResults: ReconciliationResult[] = [
    {
      id: 1,
      run_id: 10,
      material_item_id: 101,
      match_method: 'CONSUMABLE_SEGREGATED',
      issued_quantity: '50.0000',
      charged_quantity: '0.0000',
      variance_quantity: '50.0000',
      applied_tolerance: '0.0000',
      tolerance_basis: 'Floor consumable',
      variance_class: 'OK',
      status: 'SEGREGATED',
      uom_code: 'KG',
    },
    {
      id: 2,
      run_id: 10,
      material_item_id: 102,
      match_method: 'CONSUMABLE_SEGREGATED',
      issued_quantity: '10.0000',
      charged_quantity: '0.0000',
      variance_quantity: '10.0000',
      applied_tolerance: '0.0000',
      tolerance_basis: 'Safety gloves',
      variance_class: 'OK',
      status: 'SEGREGATED',
      uom_code: 'SET',
    },
  ];

  const summary = calculateSegregatedConsumablesSummary(mixedResults);
  assert.equal(summary.count, 2);
  assert.equal(summary.byUom['KG'], 50.0);
  assert.equal(summary.byUom['SET'], 10.0);
  // Must NOT collapse 50 KG and 10 SET into "60 kg"
  assert.equal(summary.formattedSummary, '50.00 KG • 10.00 SET');
});

test('calculateSegregatedConsumablesSummary handles empty or null gracefully', () => {
  assert.deepEqual(calculateSegregatedConsumablesSummary(null), { count: 0, totalQuantity: 0, byUom: {}, formattedSummary: '0 lines' });
  assert.deepEqual(calculateSegregatedConsumablesSummary(undefined), { count: 0, totalQuantity: 0, byUom: {}, formattedSummary: '0 lines' });
  assert.deepEqual(calculateSegregatedConsumablesSummary([]), { count: 0, totalQuantity: 0, byUom: {}, formattedSummary: '0 lines' });

  const onlyCharges: ReconciliationResult[] = [
    {
      id: 1,
      run_id: 10,
      match_method: 'EXACT_HEAT_SLIP',
      issued_quantity: 50,
      charged_quantity: 50,
      variance_quantity: 0,
      applied_tolerance: 1,
      tolerance_basis: 'Standard',
      variance_class: 'OK',
      status: 'RESOLVED',
    },
  ];
  assert.deepEqual(calculateSegregatedConsumablesSummary(onlyCharges), { count: 0, totalQuantity: 0, byUom: {}, formattedSummary: '0 lines' });
});

test('filterReconciliationResults partitions furnace charges and segregated consumables correctly', () => {
  const mixedResults: ReconciliationResult[] = [
    {
      id: 1,
      run_id: 1,
      match_method: 'CONSUMABLE_SEGREGATED',
      issued_quantity: 25,
      charged_quantity: 0,
      variance_quantity: 25,
      applied_tolerance: 0,
      tolerance_basis: 'Segregated',
      variance_class: 'OK',
      status: 'SEGREGATED',
    },
    {
      id: 2,
      run_id: 1,
      match_method: 'EXACT_HEAT_SLIP',
      issued_quantity: 500,
      charged_quantity: 500,
      variance_quantity: 0,
      applied_tolerance: 10,
      tolerance_basis: 'Standard',
      variance_class: 'OK',
      status: 'RESOLVED',
    },
  ];

  const all = filterReconciliationResults(mixedResults, 'all');
  assert.equal(all.length, 2);

  const charges = filterReconciliationResults(mixedResults, 'charges');
  assert.equal(charges.length, 1);
  assert.equal(charges[0].match_method, 'EXACT_HEAT_SLIP');

  const consumables = filterReconciliationResults(mixedResults, 'consumables');
  assert.equal(consumables.length, 1);
  assert.equal(consumables[0].match_method, 'CONSUMABLE_SEGREGATED');
});

test('parseIssueSlipNumber and parseIssueId extract transaction references for traceability', () => {
  const resWithSlipInNotes: ReconciliationResult = {
    id: 1,
    run_id: 1,
    match_method: 'CONSUMABLE_SEGREGATED',
    issued_quantity: 50,
    charged_quantity: 0,
    variance_quantity: 50,
    applied_tolerance: 0,
    tolerance_basis: 'Segregated',
    variance_class: 'OK',
    status: 'SEGREGATED',
    contributing_issue_ids: '[42]',
    notes: "Floor consumable 'Slax' (FDY-RM-021) issued on slip ISS-20261016-0005 without heat attribution.",
  };

  assert.equal(parseIssueSlipNumber(resWithSlipInNotes), 'ISS-20261016-0005');
  assert.equal(parseIssueId(resWithSlipInNotes), 42);

  const resWithOnlyIds: ReconciliationResult = {
    id: 2,
    run_id: 1,
    match_method: 'CONSUMABLE_SEGREGATED',
    issued_quantity: 25,
    charged_quantity: 0,
    variance_quantity: 25,
    applied_tolerance: 0,
    tolerance_basis: 'Segregated',
    variance_class: 'OK',
    status: 'SEGREGATED',
    contributing_issue_ids: '[108]',
    notes: "Floor consumable 'Pre-Coated Sand' without heat attribution.",
  };

  assert.equal(parseIssueSlipNumber(resWithOnlyIds), 'Issue Slip #108');
  assert.equal(parseIssueId(resWithOnlyIds), 108);

  const resEmpty: ReconciliationResult = {
    id: 3,
    run_id: 1,
    match_method: 'CONSUMABLE_SEGREGATED',
    issued_quantity: 10,
    charged_quantity: 0,
    variance_quantity: 10,
    applied_tolerance: 0,
    tolerance_basis: 'Segregated',
    variance_class: 'OK',
    status: 'SEGREGATED',
  };

  assert.equal(parseIssueSlipNumber(resEmpty), 'Unassigned Slip');
  assert.equal(parseIssueId(resEmpty), null);
});
