/**
 * Pure helpers for the Item Code Generator (Item Nomenclature Standard v1.0).
 * No network or DOM access here, so the helpers run under `npm test` (Node type stripping).
 */
import type {
  ItemCodeDuplicate,
  ItemCodeIssue,
  ItemCodePreview,
  ItemCodeRuleCategory,
  ItemCodeRules,
} from '../types';

/** Categories owned by a department (Section 4: each category belongs to exactly one department). */
export function categoriesForDepartment(rules: ItemCodeRules | null, departmentCode: string | undefined): ItemCodeRuleCategory[] {
  if (!rules || !departmentCode) return [];
  return rules.categories.filter((c) => c.department_code === departmentCode);
}

/** Display label for a stored request category: v1.0 code -> "BN · Bolts & Nuts"; legacy values shown as-is. */
export function categoryLabel(rules: ItemCodeRules | null, value: string): string {
  const match = rules?.categories.find((c) => c.code === value.toUpperCase() || c.name.toLowerCase() === value.toLowerCase());
  return match ? `${match.code} · ${match.name}` : `${value} (not in v1.0)`;
}

export interface ItemCodeApiError {
  message: string;
  errors: ItemCodeIssue[];
  duplicates: ItemCodeDuplicate[];
}

/**
 * Normalises an error body from the item request / item code endpoints. `detail` may be a string, a FastAPI
 * validation list, or the structured `{ message, errors?, duplicates? }` object used for nomenclature errors.
 */
export function parseItemCodeError(body: unknown, fallback: string): ItemCodeApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string' && detail) return { message: detail, errors: [], duplicates: [] };
  if (Array.isArray(detail)) {
    const errors: ItemCodeIssue[] = detail.map((e: any) => ({
      field: Array.isArray(e?.loc) ? String(e.loc[e.loc.length - 1]) : 'request',
      code: String(e?.type ?? 'invalid'),
      message: String(e?.msg ?? e),
    }));
    return { message: fallback, errors, duplicates: [] };
  }
  if (detail && typeof detail === 'object') {
    const d = detail as { message?: unknown; errors?: unknown; duplicates?: unknown };
    return {
      message: typeof d.message === 'string' && d.message ? d.message : fallback,
      errors: Array.isArray(d.errors) ? (d.errors as ItemCodeIssue[]) : [],
      duplicates: Array.isArray(d.duplicates) ? (d.duplicates as ItemCodeDuplicate[]) : [],
    };
  }
  return { message: fallback, errors: [], duplicates: [] };
}

/** Errors for one form field, so they can be shown next to the input. */
export function issuesForField(issues: ItemCodeIssue[], field: string): ItemCodeIssue[] {
  return issues.filter((i) => i.field === field);
}

/** A request may be saved/submitted only when the preview is valid (no errors, no blocking duplicates). */
export function canSubmitPreview(preview: ItemCodePreview | null): boolean {
  return !!preview && preview.valid && !(preview.duplicates || []).some((d) => d.blocking);
}

/** One-line description of a duplicate match. */
export function describeDuplicate(d: ItemCodeDuplicate): string {
  if (d.source === 'REQUEST') return `Request ${d.request_number ?? ''} (${d.request_status ?? 'open'}): ${d.name}`;
  const state = d.is_active === false ? 'retired' : 'active';
  const via = d.source === 'ALIAS' ? ' via alternate name' : '';
  return `${d.item_code ?? ''} (${state}${via}): ${d.name}`;
}
