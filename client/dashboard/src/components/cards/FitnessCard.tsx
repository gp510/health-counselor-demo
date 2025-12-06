import type { FitnessRecord } from '../../types/health';
import { ProgressRing } from '../shared/ProgressRing';

interface FitnessCardProps {
  today: FitnessRecord | null;
  weekAvgSteps?: number;
  weekAvgSleep?: number;
  loading?: boolean;
}

const STEP_GOAL = 10000;
const SLEEP_GOAL = 8;

export function FitnessCard({ today, weekAvgSteps = 0, weekAvgSleep = 0, loading }: FitnessCardProps) {
  if (loading) {
    return (
      <div className="bg-bg-card rounded-xl p-5 animate-pulse">
        <div className="h-6 bg-bg-hover rounded w-24 mb-4"></div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 bg-bg-hover rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  const steps = today?.steps ?? weekAvgSteps;
  const sleep = today?.sleep_hours ?? weekAvgSleep;
  const stepProgress = Math.min((steps / STEP_GOAL) * 100, 100);
  const sleepProgress = Math.min((sleep / SLEEP_GOAL) * 100, 100);

  return (
    <div className="bg-bg-card rounded-xl p-5 border border-domain-fitness/20 hover:border-domain-fitness/40 transition-colors">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-2xl">🏃</span>
        <h3 className="text-lg font-semibold text-text-primary">Fitness</h3>
        {today && (
          <span className="ml-auto text-xs text-text-muted">Today</span>
        )}
      </div>

      {/* Main Metrics */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* Steps */}
        <div className="flex items-center gap-3">
          <ProgressRing progress={stepProgress} size={50} color="#22c55e">
            <span className="text-xs font-medium">{Math.round(stepProgress)}%</span>
          </ProgressRing>
          <div>
            <p className="text-xl font-bold text-text-primary">{steps.toLocaleString()}</p>
            <p className="text-xs text-text-muted">steps</p>
          </div>
        </div>

        {/* Sleep */}
        <div className="flex items-center gap-3">
          <ProgressRing progress={sleepProgress} size={50} color="#8b5cf6">
            <span className="text-xs font-medium">{sleep.toFixed(1)}h</span>
          </ProgressRing>
          <div>
            <p className="text-xl font-bold text-text-primary">{sleep.toFixed(1)}</p>
            <p className="text-xs text-text-muted">hrs sleep</p>
          </div>
        </div>
      </div>

      {/* Heart Rate & Activity */}
      <div className="grid grid-cols-3 gap-2 pt-3 border-t border-bg-hover">
        <div className="text-center">
          <p className="text-lg font-semibold text-text-primary">
            {today?.resting_heart_rate ?? '--'}
          </p>
          <p className="text-xs text-text-muted">Resting HR</p>
        </div>
        <div className="text-center border-x border-bg-hover">
          <p className="text-lg font-semibold text-text-primary">
            {today?.active_minutes ?? '--'}
          </p>
          <p className="text-xs text-text-muted">Active min</p>
        </div>
        <div className="text-center">
          <p className="text-lg font-semibold text-text-primary">
            {today?.calories_burned?.toLocaleString() ?? '--'}
          </p>
          <p className="text-xs text-text-muted">Calories</p>
        </div>
      </div>

      {/* Workout Info */}
      {today?.workout_type && today.workout_type !== 'none' && (
        <div className="mt-3 pt-3 border-t border-bg-hover">
          <div className="flex items-center gap-2">
            <span className="text-sm">🎯</span>
            <span className="text-sm text-text-secondary capitalize">
              {today.workout_type}
            </span>
            <span className="text-xs text-text-muted ml-auto">
              {today.workout_duration_min} min
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
