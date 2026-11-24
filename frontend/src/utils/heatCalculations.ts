export interface HeatCalculatedKPIs {
  grossCharged: number;
  tapped: number;
  meltLossKg: number | null;
  meltLossPct: number | null;
  meltingRecoveryPct: number | null;
  goodCastingsKg: number | null;
  castingYieldPct: number | null;
  rmPerGoodKg: number | null;
  totalPartsCount: number;
  anomalies: string[];
  yieldStatus: 'NORMAL' | 'WARNING' | 'CRITICAL';
  powerCost: number;
  overheadCost: number;
  totalEstCost: number;
  costPerKg: number | null;

  // Mass-Balance & Liquid Heel KPIs
  openingLiquidHeelKg: number | null;
  closingLiquidHeelKg: number | null;
  totalLiquidMetalAvailableKg: number | null;
  totalMetalAccountedKg: number | null;
  trueMeltLossKg: number | null;
  massBalanceRecoveryPct: number | null;
  tappedMetalRecoveryPct: number | null;
  heelStatus: 'COMPLETE' | 'INCOMPLETE_HEEL_DATA' | 'UNRECORDED';

  // Authoritative Costing Measures (Phase 2B-2B & Phase 2B-2C)
  measureACostPerKg: number | null;
  measureBCostPerKg: number | null;
  measureCCostPerKg: number | null;
  conversionCostStatus: 'NOT_AVAILABLE' | 'PENDING_DATA';
  approvedScrapCredit: number | null;
}

export interface HeatKPIPolicyOptions {
  powerTariff?: number; // ₹/KWH (informative only)
  consumableOverheadPerMt?: number; // ₹/MT (informative only)
  warningMeltLossPct?: number; // default 3.5% (FIN-DEC-04)
  criticalMeltLossPct?: number; // default 5.0%
}

export interface HeatInputForKPI {
  metal_tapped_weight?: string | number | null;
  opening_liquid_heel_kg?: string | number | null;
  closing_liquid_heel_kg?: string | number | null;
  is_cold_start?: boolean;
  is_furnace_empty?: boolean;
  total_material_cost?: string | number | null;
  opening_liquid_heel_value?: string | number | null;
  approved_scrap_credit?: string | number | null;
  charge_lines?: Array<{
    line_number?: number;
    original_material_description?: string;
    charged_quantity: string | number;
    validation_status?: string;
    material_item?: any;
  }>;
  parts_produced?: Array<{
    line_number?: number;
    original_part_description?: string;
    quantity_produced: string | number;
    unit_cast_weight?: string | number | null;
    classification?: string;
    part_item?: any;
  }>;
}

export interface ChargeLineWithPct {
  line_number?: number;
  original_material_description?: string;
  charged_quantity: number;
  percentage_of_charge: number | null;
  validation_status?: string;
  material_item?: any;
}

export interface PartAllocationResult {
  line_number?: number;
  original_part_description?: string;
  quantity_produced: number;
  unit_cast_weight: number | null;
  total_weight_kg: number | null;
  rm_allocated_kg: number | null;
  classification: string;
  allocation_status:
    | 'ALLOCATED'
    | 'PENDING_UNIT_WEIGHT'
    | 'MISSING_UNIT_WEIGHT'
    | 'CLASSIFICATION_EXCLUDED'
    | 'ZERO_GOOD_CASTING_WEIGHT'
    | 'INCOMPLETE_ALLOCATION'
    | 'MISSING_OR_ZERO_CHARGE';
  part_item?: any;
}

export interface HeatReconciliationResult {
  total_heat_charge_kg: number;
  total_good_castings_kg: number | null;
  total_allocated_rm_kg: number;
  allocation_variance_kg: number;
  reconciliation_status:
    | 'RECONCILED'
    | 'INCOMPLETE_ALLOCATION'
    | 'UNALLOCATED'
    | 'ZERO_GOOD_CASTING_WEIGHT'
    | 'MISSING_OR_ZERO_CHARGE';
  is_reconciled: boolean;
  discrepancy_reason: string | null;
}

export interface FullHeatCalculationResult {
  kpis: HeatCalculatedKPIs;
  chargeLines: ChargeLineWithPct[];
  partsAllocated: PartAllocationResult[];
  reconciliation: HeatReconciliationResult;
}

const RECONCILIATION_TOLERANCE = 0.05; // 50 grams tolerance for rounding

/**
 * Calculates material-wise percentage of charge for each charge line:
 * Material % = (Charged Quantity / Total Heat Charge) * 100.
 */
export function calculateChargeLinePercentages(
  chargeLines: Array<{
    line_number?: number;
    original_material_description?: string;
    charged_quantity: string | number;
    validation_status?: string;
    material_item?: any;
  }> = [],
  totalCharge?: number
): ChargeLineWithPct[] {
  const sumCharge =
    totalCharge !== undefined
      ? totalCharge
      : chargeLines.reduce((acc, l) => acc + (Number(l.charged_quantity) || 0), 0);

  return chargeLines.map((l) => {
    const qty = Number(l.charged_quantity) || 0;
    const pct = sumCharge > 0 ? (qty / sumCharge) * 100 : null;

    return {
      line_number: l.line_number,
      original_material_description: l.original_material_description,
      charged_quantity: qty,
      percentage_of_charge: pct !== null ? Number(pct.toFixed(4)) : null,
      validation_status: l.validation_status,
      material_item: l.material_item,
    };
  });
}

/**
 * Calculates physical raw material allocated (kg) per produced part:
 * Part Total Weight = Quantity Cast * Unit Cast Weight.
 * RM Allocated = (Part Total Weight / Total Good Casting Weight) * Total Heat Charge.
 *
 * Rules:
 * - Denominator is strictly weight in kg, not part count.
 * - Excludes REJECT, RUNNERS, GATING from raw material allocation.
 * - Missing unit weight yields PENDING_UNIT_WEIGHT / MISSING_UNIT_WEIGHT.
 * - Zero good casting weight yields safe non-calculable result.
 * - Verifies complete reconciliation vs Total Charge.
 */
export function calculatePartsAllocation(
  partsProduced: Array<{
    line_number?: number;
    original_part_description?: string;
    quantity_produced: string | number;
    unit_cast_weight?: string | number | null;
    classification?: string;
    part_item?: any;
  }> = [],
  totalChargeKg: number = 0,
  heatGoodCastingsWeight?: number | null
): {
  partsAllocated: PartAllocationResult[];
  reconciliation: HeatReconciliationResult;
} {
  if (!partsProduced || partsProduced.length === 0) {
    return {
      partsAllocated: [],
      reconciliation: {
        total_heat_charge_kg: totalChargeKg,
        total_good_castings_kg: null,
        total_allocated_rm_kg: 0,
        allocation_variance_kg: totalChargeKg,
        reconciliation_status: 'UNALLOCATED',
        is_reconciled: false,
        discrepancy_reason: 'No parts recorded for heat.',
      },
    };
  }

  let hasMissingGoodWeight = false;
  let goodWeightSum = 0;

  const parsed = partsProduced.map((p) => {
    const qty = Number(p.quantity_produced) || 0;
    const classification = (p.classification || 'GOOD').trim().toUpperCase();
    const hasUnitWt =
      p.unit_cast_weight !== undefined &&
      p.unit_cast_weight !== null &&
      p.unit_cast_weight !== '' &&
      Number(p.unit_cast_weight) > 0;
    const unitWt = hasUnitWt ? Number(p.unit_cast_weight) : null;
    const totalWt = unitWt !== null ? qty * unitWt : null;
    const isGood = classification === 'GOOD';

    if (isGood) {
      if (totalWt !== null) {
        goodWeightSum += totalWt;
      } else {
        hasMissingGoodWeight = true;
      }
    }

    return {
      line_number: p.line_number,
      original_part_description: p.original_part_description,
      part_item: p.part_item,
      quantity_produced: qty,
      unit_cast_weight: unitWt,
      total_weight_kg: totalWt !== null ? Number(totalWt.toFixed(4)) : null,
      classification,
      isGood,
    };
  });

  const effectiveGoodCastingsKg =
    heatGoodCastingsWeight !== undefined && heatGoodCastingsWeight !== null
      ? heatGoodCastingsWeight
      : goodWeightSum > 0
      ? goodWeightSum
      : null;

  let totalAllocatedRm = 0;
  const partsAllocated: PartAllocationResult[] = [];

  for (const item of parsed) {
    let rmAllocated: number | null = null;
    let status: PartAllocationResult['allocation_status'];

    if (!item.isGood) {
      status = 'CLASSIFICATION_EXCLUDED';
      rmAllocated = null;
    } else if (item.unit_cast_weight === null || item.unit_cast_weight <= 0) {
      status = 'PENDING_UNIT_WEIGHT';
      rmAllocated = null;
    } else if (totalChargeKg <= 0) {
      status = 'MISSING_OR_ZERO_CHARGE';
      rmAllocated = null;
    } else if (effectiveGoodCastingsKg === null || effectiveGoodCastingsKg <= 0) {
      status = 'ZERO_GOOD_CASTING_WEIGHT';
      rmAllocated = null;
    } else if (hasMissingGoodWeight && (heatGoodCastingsWeight === undefined || heatGoodCastingsWeight === null)) {
      status = 'INCOMPLETE_ALLOCATION';
      rmAllocated = null;
    } else {
      rmAllocated = Number(
        (((item.total_weight_kg || 0) / effectiveGoodCastingsKg) * totalChargeKg).toFixed(4)
      );
      totalAllocatedRm += rmAllocated;
      status = 'ALLOCATED';
    }

    partsAllocated.push({
      line_number: item.line_number,
      original_part_description: item.original_part_description,
      part_item: item.part_item,
      quantity_produced: item.quantity_produced,
      unit_cast_weight: item.unit_cast_weight,
      total_weight_kg: item.total_weight_kg,
      rm_allocated_kg: rmAllocated,
      classification: item.classification,
      allocation_status: status,
    });
  }

  totalAllocatedRm = Number(totalAllocatedRm.toFixed(4));
  const variance = Number((totalChargeKg - totalAllocatedRm).toFixed(4));

  let reconciliation_status: HeatReconciliationResult['reconciliation_status'];
  let is_reconciled = false;
  let discrepancy_reason: string | null = null;

  if (totalChargeKg <= 0) {
    reconciliation_status = 'MISSING_OR_ZERO_CHARGE';
    discrepancy_reason = 'Total heat charge is missing or zero.';
  } else if (effectiveGoodCastingsKg === null || effectiveGoodCastingsKg <= 0) {
    reconciliation_status = 'ZERO_GOOD_CASTING_WEIGHT';
    discrepancy_reason = 'Total good casting weight is zero.';
  } else if (hasMissingGoodWeight) {
    reconciliation_status = 'INCOMPLETE_ALLOCATION';
    discrepancy_reason = 'One or more GOOD parts has missing unit cast weight.';
  } else if (Math.abs(variance) <= RECONCILIATION_TOLERANCE) {
    reconciliation_status = 'RECONCILED';
    is_reconciled = true;
    discrepancy_reason = null;
  } else {
    reconciliation_status = 'INCOMPLETE_ALLOCATION';
    discrepancy_reason = `Allocated RM (${totalAllocatedRm} kg) does not reconcile to Total Charge (${totalChargeKg} kg). Variance: ${variance} kg.`;
  }

  const reconciliation: HeatReconciliationResult = {
    total_heat_charge_kg: totalChargeKg,
    total_good_castings_kg: effectiveGoodCastingsKg !== null ? Number(effectiveGoodCastingsKg.toFixed(4)) : null,
    total_allocated_rm_kg: totalAllocatedRm,
    allocation_variance_kg: variance,
    reconciliation_status,
    is_reconciled,
    discrepancy_reason,
  };

  return { partsAllocated, reconciliation };
}

/**
 * Computes authoritative Heat Log KPIs following canonical Excel reference formulas
 * (VSPL_Foundry_Heat_Log_TEMPLATE.xlsx).
 */
export function computeHeatKPIs(
  heat: HeatInputForKPI,
  options: HeatKPIPolicyOptions = {}
): HeatCalculatedKPIs {
  const powerTariff = options.powerTariff ?? 8.5;
  const consumableOverheadPerMt = options.consumableOverheadPerMt ?? 1200.0;
  const warningMeltLossPct = options.warningMeltLossPct ?? 3.5; // FIN-DEC-04 standard normal threshold
  const criticalMeltLossPct = options.criticalMeltLossPct ?? 5.0;

  const anomalies: string[] = [];

  // 1. Total Charge
  const grossCharged =
    heat.charge_lines?.reduce(
      (sum, cl) => sum + (Number(cl.charged_quantity) || 0),
      0
    ) || 0;

  if (grossCharged <= 0) {
    anomalies.push('Missing or zero charge quantity.');
  }

  // 2. Metal Tapped
  const tapped =
    heat.metal_tapped_weight !== undefined &&
    heat.metal_tapped_weight !== null &&
    heat.metal_tapped_weight !== ''
      ? Number(heat.metal_tapped_weight)
      : 0;

  const hasTapped =
    heat.metal_tapped_weight !== undefined &&
    heat.metal_tapped_weight !== null &&
    heat.metal_tapped_weight !== '';

  // 3. Melt Loss & Melting Recovery
  let meltLossKg: number | null = null;
  let meltLossPct: number | null = null;
  let meltingRecoveryPct: number | null = null;

  if (hasTapped) {
    meltLossKg = grossCharged - tapped;

    if (grossCharged > 0) {
      meltLossPct = (meltLossKg / grossCharged) * 100;
      meltingRecoveryPct = (tapped / grossCharged) * 100;
    }

    if (tapped > grossCharged) {
      anomalies.push(
        `Metal tapped (${tapped.toLocaleString()} kg) exceeds total charge (${grossCharged.toLocaleString()} kg). Possible scale error or unlogged furnace addition.`
      );
    }
    if (meltLossKg < 0) {
      anomalies.push(`Negative melt loss (${meltLossKg.toFixed(2)} kg).`);
    }
  }

  // 4. Good Castings & Parts
  let totalPartsCount = 0;
  let goodCastingsKg: number | null = null;
  let hasGoodCastings = false;
  let goodWeightSum = 0;

  if (heat.parts_produced && heat.parts_produced.length > 0) {
    for (const p of heat.parts_produced) {
      const qty = Number(p.quantity_produced) || 0;
      totalPartsCount += qty;
      const isGood = (p.classification || 'GOOD').toUpperCase() === 'GOOD';
      const unitWt =
        p.unit_cast_weight !== undefined &&
        p.unit_cast_weight !== null &&
        p.unit_cast_weight !== ''
          ? Number(p.unit_cast_weight)
          : null;

      if (isGood && unitWt !== null && unitWt > 0) {
        goodWeightSum += qty * unitWt;
        hasGoodCastings = true;
      }
    }
    if (hasGoodCastings) {
      goodCastingsKg = goodWeightSum;
    }
  }

  // 5. Casting Yield % & RM per Good kg
  let castingYieldPct: number | null = null;
  let rmPerGoodKg: number | null = null;

  if (goodCastingsKg !== null && grossCharged > 0) {
    castingYieldPct = (goodCastingsKg / grossCharged) * 100;
  }

  if (goodCastingsKg !== null && goodCastingsKg > 0) {
    rmPerGoodKg = grossCharged / goodCastingsKg;
  }

  // Anomaly check: Good castings > Tapped
  if (goodCastingsKg !== null && hasTapped && goodCastingsKg > tapped) {
    anomalies.push(
      `Good castings (${goodCastingsKg.toLocaleString()} kg) exceeds metal tapped (${tapped.toLocaleString()} kg). Physical yield impossibility.`
    );
  }

  // Status classification
  let yieldStatus: 'NORMAL' | 'WARNING' | 'CRITICAL' = 'NORMAL';
  if (meltLossPct !== null) {
    if (meltLossPct > criticalMeltLossPct || meltLossPct < 0) {
      yieldStatus = 'CRITICAL';
    } else if (meltLossPct > warningMeltLossPct) {
      yieldStatus = 'WARNING';
    }
  }

  // Power & Overhead estimates
  const estKwh = (tapped / 1000) * 550;
  const powerCost = estKwh * powerTariff;
  const overheadCost = (tapped / 1000) * consumableOverheadPerMt;
  const estMaterialCost = grossCharged * 42.0;
  const totalEstCost = estMaterialCost + powerCost + overheadCost;
  const costPerKg = tapped > 0 ? totalEstCost / tapped : null;

  // 6. Liquid Heel & Mass-Balance Calculations
  const openingLiquidHeelKg =
    heat.opening_liquid_heel_kg !== undefined &&
    heat.opening_liquid_heel_kg !== null &&
    heat.opening_liquid_heel_kg !== ''
      ? Number(heat.opening_liquid_heel_kg)
      : null;

  const closingLiquidHeelKg =
    heat.closing_liquid_heel_kg !== undefined &&
    heat.closing_liquid_heel_kg !== null &&
    heat.closing_liquid_heel_kg !== ''
      ? Number(heat.closing_liquid_heel_kg)
      : null;

  if (openingLiquidHeelKg !== null && openingLiquidHeelKg < 0) {
    anomalies.push(`Opening liquid heel (${openingLiquidHeelKg} kg) cannot be negative.`);
  }
  if (closingLiquidHeelKg !== null && closingLiquidHeelKg < 0) {
    anomalies.push(`Closing liquid heel (${closingLiquidHeelKg} kg) cannot be negative.`);
  }

  let heelStatus: 'COMPLETE' | 'INCOMPLETE_HEEL_DATA' | 'UNRECORDED' = 'UNRECORDED';
  if (openingLiquidHeelKg !== null && closingLiquidHeelKg !== null) {
    heelStatus = 'COMPLETE';
  } else if (openingLiquidHeelKg !== null || closingLiquidHeelKg !== null) {
    heelStatus = 'INCOMPLETE_HEEL_DATA';
    anomalies.push('Both opening and closing liquid heels are required for full mass-balance verification.');
  }

  let totalLiquidMetalAvailableKg: number | null = null;
  let totalMetalAccountedKg: number | null = null;
  let trueMeltLossKg: number | null = null;
  let massBalanceRecoveryPct: number | null = null;
  let tappedMetalRecoveryPct: number | null = null;

  // Total Liquid Metal Available = total solid charge + opening heel
  if (openingLiquidHeelKg !== null) {
    totalLiquidMetalAvailableKg = grossCharged + openingLiquidHeelKg;
    if (totalLiquidMetalAvailableKg <= 0) {
      anomalies.push('Total available liquid metal is zero or negative.');
    }
  }

  // Total Metal Accounted = metal tapped + closing heel
  if (hasTapped && closingLiquidHeelKg !== null) {
    totalMetalAccountedKg = tapped + closingLiquidHeelKg;
  }

  // True Melt Loss = Total Liquid Metal Available - Total Metal Accounted
  if (totalLiquidMetalAvailableKg !== null && totalMetalAccountedKg !== null) {
    trueMeltLossKg = totalLiquidMetalAvailableKg - totalMetalAccountedKg;
    if (trueMeltLossKg < 0) {
      anomalies.push(
        `True melt loss is negative (${trueMeltLossKg.toLocaleString()} kg). Accounted metal exceeds available liquid metal.`
      );
    }
    if (totalLiquidMetalAvailableKg > 0) {
      massBalanceRecoveryPct = (totalMetalAccountedKg / totalLiquidMetalAvailableKg) * 100;
      if (massBalanceRecoveryPct > 100) {
        anomalies.push(
          `Mass balance recovery is ${massBalanceRecoveryPct.toFixed(2)}%, exceeding physical 100% threshold.`
        );
      }
    }
  }

  // Tapped Metal Recovery % = (Metal Tapped / Total Liquid Metal Available) * 100
  if (hasTapped && totalLiquidMetalAvailableKg !== null && totalLiquidMetalAvailableKg > 0) {
    tappedMetalRecoveryPct = (tapped / totalLiquidMetalAvailableKg) * 100;
    if (tappedMetalRecoveryPct > 100) {
      anomalies.push(
        `Tapped metal recovery is ${tappedMetalRecoveryPct.toFixed(2)}%, exceeding physical 100% threshold.`
      );
    }
  }

  // 7. Authoritative Costing Measures (Phase 2B-2B & Phase 2B-2C)
  const totalMatCost = heat.total_material_cost !== undefined && heat.total_material_cost !== null
    ? Number(heat.total_material_cost)
    : null;
  const opHeelVal = heat.opening_liquid_heel_value !== undefined && heat.opening_liquid_heel_value !== null
    ? Number(heat.opening_liquid_heel_value)
    : 0;
  const approvedScrapCredit = heat.approved_scrap_credit !== undefined && heat.approved_scrap_credit !== null
    ? Number(heat.approved_scrap_credit)
    : null;

  // Measure A: Solid Material Charge Cost per kg
  const measureACostPerKg = (grossCharged > 0 && totalMatCost !== null)
    ? Number((totalMatCost / grossCharged).toFixed(4))
    : null;

  // Measure B: Molten Metal Tapped Cost per kg (accounting for liquid heel)
  const clHeelKgNum = closingLiquidHeelKg || 0;
  const liquidAccountedKg = tapped + clHeelKgNum;
  let measureBCostPerKg: number | null = null;
  if (liquidAccountedKg > 0 && totalMatCost !== null) {
    const totalInputVal = opHeelVal + totalMatCost;
    measureBCostPerKg = Number((totalInputVal / liquidAccountedKg).toFixed(4));
  }

  // Measure C: Good Casting Raw Material Cost per kg (accounting for scrap credit)
  let measureCCostPerKg: number | null = null;
  if (goodCastingsKg !== null && goodCastingsKg > 0) {
    const scrapVal = approvedScrapCredit || 0;
    if (measureBCostPerKg !== null && tapped > 0) {
      const tappedVal = tapped * measureBCostPerKg;
      measureCCostPerKg = Number((Math.max(0, tappedVal - scrapVal) / goodCastingsKg).toFixed(4));
    } else if (totalMatCost !== null) {
      measureCCostPerKg = Number((Math.max(0, totalMatCost - scrapVal) / goodCastingsKg).toFixed(4));
    }
  }

  return {
    grossCharged,
    tapped,
    meltLossKg,
    meltLossPct,
    meltingRecoveryPct,
    goodCastingsKg,
    castingYieldPct,
    rmPerGoodKg,
    totalPartsCount,
    anomalies,
    yieldStatus,
    powerCost,
    overheadCost,
    totalEstCost,
    costPerKg: measureBCostPerKg ?? costPerKg,
    openingLiquidHeelKg,
    closingLiquidHeelKg,
    totalLiquidMetalAvailableKg,
    totalMetalAccountedKg,
    trueMeltLossKg,
    massBalanceRecoveryPct,
    tappedMetalRecoveryPct,
    heelStatus,
    measureACostPerKg,
    measureBCostPerKg,
    measureCCostPerKg,
    conversionCostStatus: 'NOT_AVAILABLE',
    approvedScrapCredit,
  };
}

/**
 * Computes full Heat Log calculations combining KPIs, line charge percentages,
 * physical RM allocation across parts, and heat-level allocation reconciliation.
 */
export function computeFullHeatCalculations(
  heat: HeatInputForKPI,
  options: HeatKPIPolicyOptions = {}
): FullHeatCalculationResult {
  const kpis = computeHeatKPIs(heat, options);
  const chargeLines = calculateChargeLinePercentages(
    heat.charge_lines || [],
    kpis.grossCharged
  );
  const { partsAllocated, reconciliation } = calculatePartsAllocation(
    heat.parts_produced || [],
    kpis.grossCharged,
    kpis.goodCastingsKg
  );

  return {
    kpis,
    chargeLines,
    partsAllocated,
    reconciliation,
  };
}
