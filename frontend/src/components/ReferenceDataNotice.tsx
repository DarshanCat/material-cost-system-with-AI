import React from 'react';
import { AlertTriangle, Info, RefreshCw } from 'lucide-react';
import { REFERENCE_LABELS, type ReferenceData, type ReferenceKind } from '../hooks/useReferenceData';

interface ReferenceDataNoticeProps {
  refs: ReferenceData;
}

/**
 * Shows the state of a view's reference lists: loading, failed (with a retry), or loaded but empty.
 * Renders nothing once every list has loaded with records.
 */
export const ReferenceDataNotice: React.FC<ReferenceDataNoticeProps> = ({ refs }) => {
  if (refs.loading) {
    return (
      <div className="reference-notice reference-notice-loading" role="status">
        <RefreshCw size={16} className="spin flex-shrink-0" />
        <div className="reference-notice-body">
          Loading reference data: {refs.kinds.map((kind) => REFERENCE_LABELS[kind].toLowerCase()).join(', ')}…
        </div>
      </div>
    );
  }

  const failed = Object.entries(refs.errors) as Array<[ReferenceKind, string]>;
  if (failed.length > 0) {
    return (
      <div className="reference-notice reference-notice-error" role="alert">
        <AlertTriangle size={16} className="flex-shrink-0" />
        <div className="reference-notice-body">
          <strong>Reference data could not be loaded.</strong> Selections that depend on it are unavailable until
          it loads.
          <ul className="reference-notice-list">
            {failed.map(([kind, message]) => (
              <li key={kind}>
                {REFERENCE_LABELS[kind]}: {message}
              </li>
            ))}
          </ul>
        </div>
        <button type="button" className="erp-btn btn-sm btn-secondary" onClick={refs.reload}>
          <RefreshCw size={12} className="btn-icon" /> Retry
        </button>
      </div>
    );
  }

  if (refs.empty.length > 0) {
    return (
      <div className="reference-notice reference-notice-empty" role="status">
        <Info size={16} className="flex-shrink-0" />
        <div className="reference-notice-body">
          No active records found for: {refs.empty.map((kind) => REFERENCE_LABELS[kind]).join(', ')}. Ask an
          administrator to add them in the master data screens.
        </div>
      </div>
    );
  }

  return null;
};
