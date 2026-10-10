import React from 'react';
import { AlertCircle, Clock, ShieldAlert, CheckCircle2 } from 'lucide-react';

interface ModulePlaceholderProps {
  title: string;
  moduleId: string;
  phase: string;
  description: string;
  plannedFeatures: string[];
  businessRules: string[];
}

export const ModulePlaceholder: React.FC<ModulePlaceholderProps> = ({
  title,
  phase,
  description,
  plannedFeatures,
  businessRules,
}) => {
  return (
    <div className="module-placeholder-container">
      <div className="placeholder-header-card">
        <div className="placeholder-title-row">
          <div>
            <span className="phase-pill">{phase}</span>
            <h2 className="placeholder-title">{title}</h2>
          </div>
          <div className="status-indicator-tag">
            <Clock size={16} className="inline-icon" />
            <span>Implementation Pending</span>
          </div>
        </div>
        <p className="placeholder-desc">{description}</p>
      </div>

      <div className="notice-banner">
        <AlertCircle size={20} className="notice-icon text-amber" />
        <div>
          <div className="notice-title">Zero Data Fabrication Policy Active</div>
          <p className="notice-body">
            Per strict VSPL corporate guidelines, no synthetic mock inventory quantities, fictitious rates,
            or invented transactions are displayed. Real data operations will be connected in {phase}.
          </p>
        </div>
      </div>

      <div className="placeholder-grid">
        <div className="card feature-card">
          <h3 className="card-title">
            <CheckCircle2 size={18} className="inline-icon text-primary" />
            Planned Architectural Scope
          </h3>
          <ul className="spec-list">
            {plannedFeatures.map((feat, idx) => (
              <li key={idx} className="spec-item">
                <span className="spec-bullet">&bull;</span>
                <span>{feat}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="card rule-card">
          <h3 className="card-title">
            <ShieldAlert size={18} className="inline-icon text-accent" />
            Enforced Business Rules
          </h3>
          <ul className="spec-list">
            {businessRules.map((rule, idx) => (
              <li key={idx} className="spec-item">
                <span className="rule-bullet">&bull;</span>
                <span>{rule}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};
