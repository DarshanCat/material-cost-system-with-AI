import test from 'node:test';
import assert from 'node:assert/strict';
import {
  computeHeatKPIs,
  calculateChargeLinePercentages,
  calculatePartsAllocation,
  computeFullHeatCalculations,
} from './heatCalculations.ts';

test('H-2004 scenario: preserves negative melt loss and computes recovery %', () => {
  const heat = {
    heat_number: 'H-2004',
    metal_tapped_weight: '450.0',
    charge_lines: [
      { charged_quantity: '50.0' },
      { charged_quantity: '100.0' },
      { charged_quantity: '150.0' },
      { charged_quantity: '30.0' },
      { charged_quantity: '35.0' },
      { charged_quantity: '45.0' },
      { charged_quantity: '20.0' },
    ],
    parts_produced: [
      {
        quantity_produced: '10.0',
        unit_cast_weight: '150.0',
        classification: 'GOOD',
      },
    ],
  };

  const kpis = computeHeatKPIs(heat);

  // 1. Total Charge = 430 kg
  assert.equal(kpis.grossCharged, 430);
  assert.equal(kpis.tapped, 450);

  // 2. Melt Loss = -20 kg (NEVER clamped to 0)
  assert.equal(kpis.meltLossKg, -20);

  // 3. Melt Loss % = -4.65116279...%
  assert.ok(kpis.meltLossPct !== null);
  assert.ok(Math.abs(kpis.meltLossPct - (-4.65116279)) < 0.001);

  // 4. Melting Recovery % = 104.65116279...%
  assert.ok(kpis.meltingRecoveryPct !== null);
  assert.ok(Math.abs(kpis.meltingRecoveryPct - 104.65116279) < 0.001);

  // 5. Good Castings = 10 * 150 = 1500 kg
  assert.equal(kpis.goodCastingsKg, 1500);

  // 6. Casting Yield % = (1500 / 430) * 100 = 348.837%
  assert.ok(kpis.castingYieldPct !== null);
  assert.ok(Math.abs(kpis.castingYieldPct - 348.8372) < 0.001);

  // 7. RM per Good kg = 430 / 1500 = 0.28666...
  assert.ok(kpis.rmPerGoodKg !== null);
  assert.ok(Math.abs(kpis.rmPerGoodKg - (430 / 1500)) < 0.001);

  // 8. Anomalies flagged
  assert.ok(kpis.anomalies.some((a) => a.includes('Metal tapped')));
  assert.ok(kpis.anomalies.some((a) => a.includes('Negative melt loss')));
  assert.ok(kpis.anomalies.some((a) => a.includes('Good castings')));
  assert.equal(kpis.yieldStatus, 'CRITICAL');
});

test('Normal production heat: positive melt loss, recovery, yield, and RM per good kg', () => {
  const heat = {
    heat_number: 'H-3001',
    metal_tapped_weight: '950.0',
    charge_lines: [
      { charged_quantity: '700.0' },
      { charged_quantity: '200.0' },
      { charged_quantity: '100.0' },
    ],
    parts_produced: [
      {
        quantity_produced: '50.0',
        unit_cast_weight: '10.0',
        classification: 'GOOD',
      },
      {
        quantity_produced: '20.0',
        unit_cast_weight: '10.0',
        classification: 'GOOD',
      },
      {
        quantity_produced: '5.0',
        unit_cast_weight: '10.0',
        classification: 'REJECTED',
      },
    ],
  };

  const kpis = computeHeatKPIs(heat);

  assert.equal(kpis.grossCharged, 1000);
  assert.equal(kpis.tapped, 950);
  assert.equal(kpis.meltLossKg, 50);
  assert.equal(kpis.meltLossPct, 5.0);
  assert.equal(kpis.meltingRecoveryPct, 95.0);

  // Good castings: 50*10 + 20*10 = 700 kg (REJECTED excluded)
  assert.equal(kpis.goodCastingsKg, 700);

  // Casting Yield %: 700 / 1000 * 100 = 70.0%
  assert.equal(kpis.castingYieldPct, 70.0);

  // RM per Good kg: 1000 / 700 = 1.42857...
  assert.ok(kpis.rmPerGoodKg !== null);
  assert.ok(Math.abs(kpis.rmPerGoodKg - (1000 / 700)) < 0.0001);

  assert.equal(kpis.anomalies.length, 0);
  // Per FIN-DEC-04, normal threshold is 3.5%; 5.0% loss triggers WARNING
  assert.equal(kpis.yieldStatus, 'WARNING');
});

test('Zero or missing charge handling', () => {
  const heat = {
    heat_number: 'H-EMPTY',
    metal_tapped_weight: null,
    charge_lines: [],
    parts_produced: [],
  };

  const kpis = computeHeatKPIs(heat);
  assert.equal(kpis.grossCharged, 0);
  assert.equal(kpis.meltLossKg, null);
  assert.equal(kpis.meltLossPct, null);
  assert.equal(kpis.meltingRecoveryPct, null);
  assert.equal(kpis.goodCastingsKg, null);
  assert.equal(kpis.castingYieldPct, null);
  assert.equal(kpis.rmPerGoodKg, null);
  assert.ok(kpis.anomalies.some((a) => a.includes('Missing or zero charge')));
});

test('Zero good castings handling prevents divide-by-zero', () => {
  const heat = {
    heat_number: 'H-NOGOOD',
    metal_tapped_weight: '500.0',
    charge_lines: [{ charged_quantity: '520.0' }],
    parts_produced: [
      {
        quantity_produced: '10.0',
        unit_cast_weight: '0',
        classification: 'GOOD',
      },
      {
        quantity_produced: '5.0',
        unit_cast_weight: '20.0',
        classification: 'REJECTED',
      },
    ],
  };

  const kpis = computeHeatKPIs(heat);
  assert.equal(kpis.grossCharged, 520);
  assert.equal(kpis.goodCastingsKg, null);
  assert.equal(kpis.castingYieldPct, null);
  assert.equal(kpis.rmPerGoodKg, null);
  assert.equal(kpis.meltLossKg, 20);
});

// ==============================================================================
// Stage 2 Tests: Material % of Charge
// ==============================================================================

test('calculateChargeLinePercentages: computes percentage and preserves 100% sum', () => {
  const lines = [
    { line_number: 1, original_material_description: 'Pig Iron', charged_quantity: 400 },
    { line_number: 2, original_material_description: 'Scrap', charged_quantity: 300 },
    { line_number: 3, original_material_description: 'Returns', charged_quantity: 200 },
    { line_number: 4, original_material_description: 'Alloys', charged_quantity: 100 },
  ];

  const result = calculateChargeLinePercentages(lines, 1000);
  assert.equal(result.length, 4);
  assert.equal(result[0].percentage_of_charge, 40.0);
  assert.equal(result[1].percentage_of_charge, 30.0);
  assert.equal(result[2].percentage_of_charge, 20.0);
  assert.equal(result[3].percentage_of_charge, 10.0);

  const sumPct = result.reduce((s, r) => s + (r.percentage_of_charge || 0), 0);
  assert.equal(sumPct, 100.0);
});

test('calculateChargeLinePercentages: handles zero charge safely', () => {
  const lines = [{ charged_quantity: 0 }];
  const result = calculateChargeLinePercentages(lines, 0);
  assert.equal(result[0].percentage_of_charge, null);
});

// ==============================================================================
// Stage 2 Tests: Physical RM Allocation & Reconciliation
// ==============================================================================

test('calculatePartsAllocation: multiple parts with unequal weights reconciles to total charge', () => {
  const parts = [
    { line_number: 1, original_part_description: 'Part A', quantity_produced: 50, unit_cast_weight: 10, classification: 'GOOD' },
    { line_number: 2, original_part_description: 'Part B', quantity_produced: 20, unit_cast_weight: 10, classification: 'GOOD' },
  ];
  const totalCharge = 1000;

  const { partsAllocated, reconciliation } = calculatePartsAllocation(parts, totalCharge);

  assert.equal(partsAllocated.length, 2);
  assert.equal(partsAllocated[0].total_weight_kg, 500);
  assert.equal(partsAllocated[0].rm_allocated_kg, 714.2857);
  assert.equal(partsAllocated[0].allocation_status, 'ALLOCATED');

  assert.equal(partsAllocated[1].total_weight_kg, 200);
  assert.equal(partsAllocated[1].rm_allocated_kg, 285.7143);
  assert.equal(partsAllocated[1].allocation_status, 'ALLOCATED');

  assert.equal(reconciliation.total_heat_charge_kg, 1000);
  assert.equal(reconciliation.total_good_castings_kg, 700);
  assert.equal(reconciliation.total_allocated_rm_kg, 1000);
  assert.equal(reconciliation.allocation_variance_kg, 0);
  assert.equal(reconciliation.reconciliation_status, 'RECONCILED');
  assert.equal(reconciliation.is_reconciled, true);
});

test('calculatePartsAllocation: excludes REJECT, RUNNERS, and GATING from good allocation', () => {
  const parts = [
    { line_number: 1, original_part_description: 'Good Housing', quantity_produced: 50, unit_cast_weight: 10, classification: 'GOOD' },
    { line_number: 2, original_part_description: 'Defective Housing', quantity_produced: 5, unit_cast_weight: 10, classification: 'REJECTED' },
    { line_number: 3, original_part_description: 'Furnace Runners', quantity_produced: 10, unit_cast_weight: 5, classification: 'RUNNERS' },
    { line_number: 4, original_part_description: 'Gating', quantity_produced: 20, unit_cast_weight: 2, classification: 'GATING' },
  ];
  const totalCharge = 1000;

  const { partsAllocated, reconciliation } = calculatePartsAllocation(parts, totalCharge);

  assert.equal(partsAllocated[0].allocation_status, 'ALLOCATED');
  assert.equal(partsAllocated[0].rm_allocated_kg, 1000);

  assert.equal(partsAllocated[1].allocation_status, 'CLASSIFICATION_EXCLUDED');
  assert.equal(partsAllocated[1].rm_allocated_kg, null);

  assert.equal(partsAllocated[2].allocation_status, 'CLASSIFICATION_EXCLUDED');
  assert.equal(partsAllocated[2].rm_allocated_kg, null);

  assert.equal(partsAllocated[3].allocation_status, 'CLASSIFICATION_EXCLUDED');
  assert.equal(partsAllocated[3].rm_allocated_kg, null);

  assert.equal(reconciliation.total_good_castings_kg, 500);
  assert.equal(reconciliation.total_allocated_rm_kg, 1000);
  assert.equal(reconciliation.reconciliation_status, 'RECONCILED');
  assert.equal(reconciliation.is_reconciled, true);
});

test('calculatePartsAllocation: missing unit weight marks PENDING_UNIT_WEIGHT and INCOMPLETE_ALLOCATION', () => {
  const parts = [
    { line_number: 1, original_part_description: 'Known Weight Part', quantity_produced: 50, unit_cast_weight: 10, classification: 'GOOD' },
    { line_number: 2, original_part_description: 'Unweighed Part', quantity_produced: 20, unit_cast_weight: null, classification: 'GOOD' },
  ];
  const totalCharge = 1000;

  const { partsAllocated, reconciliation } = calculatePartsAllocation(parts, totalCharge);

  assert.equal(partsAllocated[0].allocation_status, 'INCOMPLETE_ALLOCATION');
  assert.equal(partsAllocated[0].rm_allocated_kg, null);

  assert.equal(partsAllocated[1].allocation_status, 'PENDING_UNIT_WEIGHT');
  assert.equal(partsAllocated[1].rm_allocated_kg, null);

  assert.equal(reconciliation.reconciliation_status, 'INCOMPLETE_ALLOCATION');
  assert.equal(reconciliation.is_reconciled, false);
  assert.equal(reconciliation.allocation_variance_kg, 1000);
});

test('computeFullHeatCalculations: integrates KPIs, charge % and part allocations', () => {
  const heat = {
    heat_number: 'H-FULL',
    metal_tapped_weight: '950',
    charge_lines: [
      { charged_quantity: 600 },
      { charged_quantity: 400 },
    ],
    parts_produced: [
      { quantity_produced: 50, unit_cast_weight: 10, classification: 'GOOD' },
      { quantity_produced: 20, unit_cast_weight: 10, classification: 'GOOD' },
    ],
  };

  const result = computeFullHeatCalculations(heat);
  assert.equal(result.kpis.grossCharged, 1000);
  assert.equal(result.chargeLines[0].percentage_of_charge, 60.0);
  assert.equal(result.chargeLines[1].percentage_of_charge, 40.0);
  assert.equal(result.partsAllocated[0].rm_allocated_kg, 714.2857);
  assert.equal(result.partsAllocated[1].rm_allocated_kg, 285.7143);
  assert.equal(result.reconciliation.reconciliation_status, 'RECONCILED');
  assert.equal(result.reconciliation.is_reconciled, true);
});

test('Liquid heel mass-balance: computes true melt loss, mass balance recovery and tapped recovery', () => {
  const heat = {
    heat_number: 'H-HEEL-01',
    metal_tapped_weight: '950.0',
    opening_liquid_heel_kg: '400.0',
    closing_liquid_heel_kg: '420.0',
    charge_lines: [
      { charged_quantity: '600.0' },
      { charged_quantity: '400.0' },
    ],
    parts_produced: [
      { quantity_produced: '50.0', unit_cast_weight: '12.0', classification: 'GOOD' },
    ],
  };

  const kpis = computeHeatKPIs(heat);
  assert.equal(kpis.grossCharged, 1000.0);
  assert.equal(kpis.openingLiquidHeelKg, 400.0);
  assert.equal(kpis.totalLiquidMetalAvailableKg, 1400.0);
  assert.equal(kpis.closingLiquidHeelKg, 420.0);
  assert.equal(kpis.totalMetalAccountedKg, 1370.0);
  assert.equal(kpis.trueMeltLossKg, 30.0);
  assert.equal(kpis.heelStatus, 'COMPLETE');
  assert.ok(kpis.massBalanceRecoveryPct !== null);
  assert.ok(Math.abs(kpis.massBalanceRecoveryPct - 97.8571) < 0.01);
  assert.ok(kpis.tappedMetalRecoveryPct !== null);
  assert.ok(Math.abs(kpis.tappedMetalRecoveryPct - 67.8571) < 0.01);
  // Casting yield remains independent: (600 / 1000) * 100 = 60%
  assert.equal(kpis.castingYieldPct, 60.0);
});

test('Liquid heel mass-balance: incomplete heel data sets INCOMPLETE_HEEL_DATA and flags anomaly', () => {
  const heat = {
    heat_number: 'H-HEEL-INCOMPLETE',
    metal_tapped_weight: '950.0',
    opening_liquid_heel_kg: '400.0',
    closing_liquid_heel_kg: null,
    charge_lines: [{ charged_quantity: '1000.0' }],
  };

  const kpis = computeHeatKPIs(heat);
  assert.equal(kpis.heelStatus, 'INCOMPLETE_HEEL_DATA');
  assert.equal(kpis.trueMeltLossKg, null);
  assert.equal(kpis.massBalanceRecoveryPct, null);
  assert.ok(kpis.anomalies.some((a) => a.includes('Both opening and closing liquid heels are required')));
});

test('Liquid heel mass-balance: verified cold start sets opening heel 0 and computes mass balance', () => {
  const heat = {
    heat_number: 'H-COLD-START',
    metal_tapped_weight: '970.0',
    opening_liquid_heel_kg: '0',
    closing_liquid_heel_kg: '300.0',
    is_cold_start: true,
    charge_lines: [{ charged_quantity: '1300.0' }],
  };

  const kpis = computeHeatKPIs(heat);
  assert.equal(kpis.openingLiquidHeelKg, 0);
  assert.equal(kpis.totalLiquidMetalAvailableKg, 1300.0);
  assert.equal(kpis.totalMetalAccountedKg, 1270.0);
  assert.equal(kpis.trueMeltLossKg, 30.0);
  assert.equal(kpis.heelStatus, 'COMPLETE');
  assert.ok(kpis.massBalanceRecoveryPct !== null);
  assert.ok(Math.abs(kpis.massBalanceRecoveryPct - 97.6923) < 0.01);
});

test('Liquid heel mass-balance: flags negative true melt loss and recovery > 100% anomalies', () => {
  const heat = {
    heat_number: 'H-ANOMALY-HEEL',
    metal_tapped_weight: '1200.0',
    opening_liquid_heel_kg: '100.0',
    closing_liquid_heel_kg: '200.0',
    charge_lines: [{ charged_quantity: '1000.0' }],
  };

  const kpis = computeHeatKPIs(heat);
  // Available: 1000 + 100 = 1100 kg
  // Accounted: 1200 + 200 = 1400 kg
  // True melt loss: 1100 - 1400 = -300 kg
  // Mass balance recovery: 1400 / 1100 = 127.27%
  assert.equal(kpis.totalLiquidMetalAvailableKg, 1100.0);
  assert.equal(kpis.totalMetalAccountedKg, 1400.0);
  assert.equal(kpis.trueMeltLossKg, -300.0);
  assert.ok(kpis.massBalanceRecoveryPct !== null && kpis.massBalanceRecoveryPct > 100);
  assert.ok(kpis.anomalies.some((a) => a.includes('True melt loss is negative')));
  assert.ok(kpis.anomalies.some((a) => a.includes('exceeding physical 100% threshold')));
});
