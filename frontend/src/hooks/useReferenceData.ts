import { useCallback, useEffect, useState } from 'react';
import type { Department, MaterialItem, UOM, Vendor } from '../types';
import {
  fetchReferenceDepartments,
  fetchReferenceItems,
  fetchReferenceUoms,
  fetchReferenceVendors,
} from '../api/client';

export type ReferenceKind = 'items' | 'uoms' | 'departments' | 'vendors';

const LOADERS = {
  items: fetchReferenceItems,
  uoms: fetchReferenceUoms,
  departments: fetchReferenceDepartments,
  vendors: fetchReferenceVendors,
} satisfies Record<ReferenceKind, () => Promise<unknown[]>>;

export const REFERENCE_LABELS: Record<ReferenceKind, string> = {
  items: 'Material items',
  uoms: 'Units of measure',
  departments: 'Departments',
  vendors: 'Vendors',
};

type ReferenceLists = Pick<ReferenceData, 'items' | 'uoms' | 'departments' | 'vendors'>;

export interface ReferenceData {
  items: MaterialItem[];
  uoms: UOM[];
  departments: Department[];
  vendors: Vendor[];
  /** The reference lists this view requested. */
  kinds: ReferenceKind[];
  loading: boolean;
  /** One message per reference list that failed to load. */
  errors: Partial<Record<ReferenceKind, string>>;
  /** Requested lists that loaded successfully but contain no records. */
  empty: ReferenceKind[];
  /** True while loading or when any requested list failed; transaction forms should not submit. */
  unavailable: boolean;
  reload: () => void;
  /** Placeholder text for a <select>, reflecting loading / failed / empty state. */
  placeholder: (kind: ReferenceKind, ready: string) => string;
}

/**
 * Loads the reference lists a transaction form needs. Each list loads independently, so one failing
 * endpoint is reported by name without hiding the others; nothing is swallowed into an empty list.
 */
export function useReferenceData(kinds: readonly ReferenceKind[]): ReferenceData {
  const kindsKey = kinds.join(',');
  const [attempt, setAttempt] = useState(0);
  // Loading is derived: the latest settled result belongs to an earlier request until this one lands.
  const requestKey = `${kindsKey}#${attempt}`;
  const [result, setResult] = useState<{ key: string; lists: ReferenceLists; errors: ReferenceData['errors'] }>({
    key: '',
    lists: { items: [], uoms: [], departments: [], vendors: [] },
    errors: {},
  });

  useEffect(() => {
    let cancelled = false;
    const requested = kindsKey.split(',') as ReferenceKind[];

    Promise.allSettled(requested.map((kind) => LOADERS[kind]())).then((results) => {
      if (cancelled) return;
      const errors: ReferenceData['errors'] = {};
      const lists: ReferenceLists = { items: [], uoms: [], departments: [], vendors: [] };
      results.forEach((settled, i) => {
        const kind = requested[i];
        if (settled.status === 'fulfilled') {
          lists[kind] = settled.value as never;
        } else {
          const reason = settled.reason;
          errors[kind] = reason instanceof Error ? reason.message : String(reason);
        }
      });
      setResult({ key: requestKey, lists, errors });
    });

    return () => {
      cancelled = true;
    };
  }, [kindsKey, requestKey]);

  const loading = result.key !== requestKey;
  const { lists } = result;
  const errors: ReferenceData['errors'] = loading ? {} : result.errors;

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  const requested = kindsKey.split(',') as ReferenceKind[];
  const empty = loading ? [] : requested.filter((kind) => !errors[kind] && lists[kind].length === 0);

  const placeholder = (kind: ReferenceKind, ready: string) => {
    if (loading) return `Loading ${REFERENCE_LABELS[kind].toLowerCase()}…`;
    if (errors[kind]) return `${REFERENCE_LABELS[kind]} unavailable`;
    if (lists[kind].length === 0) return `No active ${REFERENCE_LABELS[kind].toLowerCase()} found`;
    return ready;
  };

  return {
    ...lists,
    kinds: requested,
    loading,
    errors,
    empty,
    unavailable: loading || Object.keys(errors).length > 0,
    reload,
    placeholder,
  };
}
