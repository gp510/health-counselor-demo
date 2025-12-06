import type { MentalWellnessEntry } from '../../types/health';

interface MentalWellnessCardProps {
  latest: MentalWellnessEntry | null;
  weekAvgMood?: number;
  weekAvgStress?: number;
  weekAvgEnergy?: number;
  loading?: boolean;
}

interface ScoreGaugeProps {
  label: string;
  value: number;
  icon: string;
  colorScale: 'positive' | 'negative';
}

function ScoreGauge({ label, value, icon, colorScale }: ScoreGaugeProps) {
  // For positive scale: higher is better (green)
  // For negative scale: lower is better (green)
  const getColor = (val: number, scale: 'positive' | 'negative') => {
    if (scale === 'positive') {
      if (val >= 7) return '#22c55e'; // Green
      if (val >= 5) return '#eab308'; // Yellow
      return '#ef4444'; // Red
    } else {
      if (val <= 3) return '#22c55e'; // Green
      if (val <= 5) return '#eab308'; // Yellow
      return '#ef4444'; // Red
    }
  };

  const color = getColor(value, colorScale);
  const width = (value / 10) * 100;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1 text-sm text-text-secondary">
          <span>{icon}</span> {label}
        </span>
        <span className="text-sm font-semibold text-text-primary">{value}/10</span>
      </div>
      <div className="h-2 bg-bg-hover rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${width}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

export function MentalWellnessCard({
  latest,
  weekAvgMood = 0,
  weekAvgStress = 0,
  weekAvgEnergy = 0,
  loading,
}: MentalWellnessCardProps) {
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

  const mood = latest?.mood_score ?? weekAvgMood;
  const stress = latest?.stress_level ?? weekAvgStress;
  const energy = latest?.energy_level ?? weekAvgEnergy;
  const anxiety = latest?.anxiety_level ?? 0;

  // Get mood emoji based on score
  const getMoodEmoji = (score: number) => {
    if (score >= 8) return '😄';
    if (score >= 6) return '🙂';
    if (score >= 4) return '😐';
    if (score >= 2) return '😔';
    return '😢';
  };

  // Parse activities
  const activities = latest?.activities?.split(';').filter(Boolean) ?? [];

  return (
    <div className="bg-bg-card rounded-xl p-5 border border-domain-mental/20 hover:border-domain-mental/40 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🧠</span>
          <h3 className="text-lg font-semibold text-text-primary">Mental Wellness</h3>
        </div>
        {latest && (
          <span className="text-xs text-text-muted capitalize">{latest.time_of_day}</span>
        )}
      </div>

      {/* Mood Display */}
      <div className="flex items-center gap-4 mb-4 p-3 bg-bg-secondary rounded-lg">
        <span className="text-4xl">{getMoodEmoji(mood)}</span>
        <div>
          <p className="text-sm text-text-secondary">Current Mood</p>
          <p className="text-2xl font-bold text-text-primary">{mood}/10</p>
        </div>
      </div>

      {/* Score Gauges */}
      <div className="space-y-3">
        <ScoreGauge label="Energy" value={energy} icon="⚡" colorScale="positive" />
        <ScoreGauge label="Stress" value={stress} icon="😓" colorScale="negative" />
        <ScoreGauge label="Anxiety" value={anxiety} icon="😰" colorScale="negative" />
      </div>

      {/* Recent Activities */}
      {activities.length > 0 && (
        <div className="mt-4 pt-3 border-t border-bg-hover">
          <p className="text-xs text-text-muted mb-2">Recent Activities</p>
          <div className="flex flex-wrap gap-1">
            {activities.slice(0, 4).map((activity, i) => (
              <span
                key={i}
                className="px-2 py-0.5 bg-domain-mental/20 text-domain-mental rounded-full text-xs capitalize"
              >
                {activity.trim()}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
