import type { Biomarker } from '../../types/health';
import { StatusBadge } from '../shared/StatusBadge';

interface BiomarkerCardProps {
  biomarkers: Biomarker[];
  loading?: boolean;
}

// Key biomarkers to display
const keyBiomarkers = [
  { name: 'Blood Pressure (Systolic)', icon: '🩺', shortName: 'BP Sys' },
  { name: 'Blood Pressure (Diastolic)', icon: '🩺', shortName: 'BP Dia' },
  { name: 'Glucose (Fasting)', icon: '🩸', shortName: 'Glucose' },
  { name: 'LDL Cholesterol', icon: '💊', shortName: 'LDL' },
  { name: 'HDL Cholesterol', icon: '💚', shortName: 'HDL' },
  { name: 'HbA1c', icon: '📊', shortName: 'HbA1c' },
];

export function BiomarkerCard({ biomarkers, loading }: BiomarkerCardProps) {
  if (loading) {
    return (
      <div className="bg-bg-card rounded-xl p-5 animate-pulse">
        <div className="h-6 bg-bg-hover rounded w-32 mb-4"></div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 bg-bg-hover rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  const abnormalCount = biomarkers.filter((b) => b.status !== 'normal').length;
  const lastTestDate = biomarkers[0]?.test_date;

  // Get latest value for each key biomarker
  const displayBiomarkers = keyBiomarkers
    .map((key) => {
      const match = biomarkers.find((b) =>
        b.biomarker_name.toLowerCase().includes(key.name.toLowerCase()) ||
        key.name.toLowerCase().includes(b.biomarker_name.toLowerCase())
      );
      return match ? { ...match, icon: key.icon, shortName: key.shortName } : null;
    })
    .filter(Boolean)
    .slice(0, 4);

  return (
    <div className="bg-bg-card rounded-xl p-5 border border-domain-biomarkers/20 hover:border-domain-biomarkers/40 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🧬</span>
          <h3 className="text-lg font-semibold text-text-primary">Biomarkers</h3>
        </div>
        {abnormalCount > 0 && (
          <span className="px-2 py-1 bg-health-warning/20 text-health-warning rounded-full text-xs font-medium">
            {abnormalCount} flagged
          </span>
        )}
      </div>

      {/* Metrics Grid */}
      <div className="space-y-3">
        {displayBiomarkers.length > 0 ? (
          displayBiomarkers.map((biomarker) => (
            <div
              key={biomarker!.test_id}
              className="flex items-center justify-between py-2 border-b border-bg-hover last:border-0"
            >
              <div className="flex items-center gap-2">
                <span className="text-lg">{biomarker!.icon}</span>
                <span className="text-sm text-text-secondary">{biomarker!.shortName}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-semibold text-text-primary">
                  {biomarker!.value}
                </span>
                <span className="text-xs text-text-muted">{biomarker!.unit}</span>
                <StatusBadge status={biomarker!.status} />
              </div>
            </div>
          ))
        ) : (
          <p className="text-sm text-text-muted text-center py-4">No biomarker data</p>
        )}
      </div>

      {/* Footer */}
      {lastTestDate && (
        <div className="mt-4 pt-3 border-t border-bg-hover">
          <p className="text-xs text-text-muted">
            Last test: {new Date(lastTestDate).toLocaleDateString()}
          </p>
        </div>
      )}
    </div>
  );
}
