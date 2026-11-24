import type { ReconciliationResult } from '../types';

/**
 * Returns a human-friendly label for a reconciliation match method.
 * Preserves the original enum values in API requests and stored data.
 */
export function getMatchMethodLabel(method: string): string {
  switch (method) {
    case 'CONSUMABLE_SEGREGATED':
      return 'Consumable — excluded from heat matching';
    case 'EXACT_HEAT_SLIP':
      return 'Exact Heat-Slip Match';
    case 'SAME_DAY_BATCH':
      return 'Same-Day Batch Aggregation';
    case 'MANUAL_CONFIRMED':
      return 'Manual Confirmed';
    case 'UNMATCHED_SLIP':
      return 'Unmatched Issue Slip';
    case 'UNMATCHED_HEAT':
      return 'Unmatched Heat Charge';
    case 'AMBIGUOUS_MATCH':
      return 'Ambiguous Match';
    default:
      return method;
  }
}

/**
 * Returns a human-friendly label for a variance class or exception type.
 * Preserves the original enum values in API requests and stored data.
 */
export function getVarianceClassLabel(vClass: string): string {
  switch (vClass) {
    case 'PENDING_REVIEW':
      return 'Pending material classification review';
    case 'CONSUMABLE_SEGREGATED':
      return 'Consumable — excluded from heat matching';
    case 'OK':
      return 'OK';
    case 'SHORT_ISSUE':
      return 'Short Issue';
    case 'EXCESS_ISSUE':
      return 'Excess Issue';
    case 'DECIMAL_SUSPECT':
      return 'Decimal Suspect';
    case 'UNMATCHED_SLIP':
      return 'Unmatched Slip';
    case 'UNMATCHED_HEAT':
      return 'Unmatched Heat';
    case 'AMBIGUOUS_MATCH':
      return 'Ambiguous Match';
    case 'UNMAPPED_MATERIAL':
      return 'Unmapped Material';
    default:
      return vClass;
  }
}

/**
 * Badge style class for match method.
 */
export function getMatchMethodBadgeClass(method: string): string {
  switch (method) {
    case 'EXACT_HEAT_SLIP':
      return 'badge-success';
    case 'CONSUMABLE_SEGREGATED':
      return 'badge-info';
    case 'MANUAL_CONFIRMED':
      return 'badge-primary';
    case 'SAME_DAY_BATCH':
      return 'badge-secondary';
    case 'UNMATCHED_SLIP':
    case 'UNMATCHED_HEAT':
    case 'AMBIGUOUS_MATCH':
      return 'badge-warning';
    default:
      return 'badge-secondary';
  }
}

/**
 * Badge style class for variance class and exception types.
 */
export function getVarianceBadgeClass(vClass: string): string {
  switch (vClass) {
    case 'OK':
      return 'badge-success';
    case 'PENDING_REVIEW':
    case 'EXCESS_ISSUE':
      return 'badge-warning';
    case 'CONSUMABLE_SEGREGATED':
      return 'badge-info';
    case 'SHORT_ISSUE':
    case 'DECIMAL_SUSPECT':
    case 'UNMATCHED_SLIP':
    case 'UNMATCHED_HEAT':
    case 'UNMAPPED_MATERIAL':
      return 'badge-danger';
    default:
      return 'badge-secondary';
  }
}

export interface SegregatedConsumablesSummary {
  count: number;
  totalQuantity: number;
  byUom: Record<string, number>;
  formattedSummary: string;
}

/**
 * Calculates authoritative Segregated Consumables summary metrics from persisted reconciliation results.
 * Groups quantities strictly by UOM so heterogeneous units are never conflated into a single mass.
 */
export function calculateSegregatedConsumablesSummary(
  results?: ReconciliationResult[] | null
): SegregatedConsumablesSummary {
  if (!results || !Array.isArray(results) || results.length === 0) {
    return { count: 0, totalQuantity: 0, byUom: {}, formattedSummary: '0 lines' };
  }

  const segregated = results.filter((r) => r.match_method === 'CONSUMABLE_SEGREGATED');
  const count = segregated.length;
  const byUom: Record<string, number> = {};
  let totalQuantity = 0;

  for (const r of segregated) {
    const qty = Number(r.issued_quantity || 0);
    const validQty = Number.isFinite(qty) ? qty : 0;
    totalQuantity += validQty;

    const uom = (r.material_item as any)?.base_uom?.code || (r as any).uom_code || 'KG';
    byUom[uom] = (byUom[uom] || 0) + validQty;
  }

  const uomKeys = Object.keys(byUom).sort();
  let formattedSummary = '';
  if (uomKeys.length === 0) {
    formattedSummary = '0 lines';
  } else if (uomKeys.length === 1) {
    const u = uomKeys[0];
    formattedSummary = `${byUom[u].toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })} ${u}`;
  } else {
    formattedSummary = uomKeys
      .map((u) => `${byUom[u].toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })} ${u}`)
      .join(' • ');
  }

  return { count, totalQuantity, byUom, formattedSummary };
}

/**
 * Filters reconciliation results by scope.
 */
export function filterReconciliationResults(
  results: ReconciliationResult[] | undefined | null,
  filter: 'all' | 'charges' | 'consumables'
): ReconciliationResult[] {
  if (!results || !Array.isArray(results)) {
    return [];
  }

  switch (filter) {
    case 'charges':
      return results.filter((r) => r.match_method !== 'CONSUMABLE_SEGREGATED');
    case 'consumables':
      return results.filter((r) => r.match_method === 'CONSUMABLE_SEGREGATED');
    case 'all':
    default:
      return results;
  }
}

/**
 * Extracts human-readable issue slip reference number from notes or contributing issue IDs.
 */
export function parseIssueSlipNumber(res: ReconciliationResult): string {
  if (res.notes) {
    const slipMatch = res.notes.match(/issued on slip\s+([A-Za-z0-9-]+)/i);
    if (slipMatch && slipMatch[1]) {
      return slipMatch[1];
    }
  }

  if (res.contributing_issue_ids) {
    try {
      const ids = JSON.parse(res.contributing_issue_ids);
      if (Array.isArray(ids) && ids.length > 0) {
        return `Issue Slip #${ids[0]}`;
      }
    } catch {
      // ignore JSON parse error
    }
  }

  return 'Unassigned Slip';
}

/**
 * Extracts the primary issue header ID to link to the original issue transaction.
 */
export function parseIssueId(res: ReconciliationResult): number | null {
  if (res.contributing_issue_ids) {
    try {
      const ids = JSON.parse(res.contributing_issue_ids);
      if (Array.isArray(ids) && ids.length > 0 && typeof ids[0] === 'number') {
        return ids[0];
      }
    } catch {
      // ignore
    }
  }
  return null;
}
