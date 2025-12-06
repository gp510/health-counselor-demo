import type { DietEntry } from '../../types/health';

interface DietCardProps {
  todayMeals: DietEntry[];
  weekAvgCalories?: number;
  loading?: boolean;
}

const CALORIE_GOAL = 2000;
const PROTEIN_GOAL = 50;
const CARBS_GOAL = 250;
const FAT_GOAL = 65;

interface MacroBarProps {
  label: string;
  value: number;
  goal: number;
  color: string;
  unit?: string;
}

function MacroBar({ label, value, goal, color, unit = 'g' }: MacroBarProps) {
  const progress = Math.min((value / goal) * 100, 100);

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-text-secondary">{label}</span>
        <span className="text-text-primary font-medium">
          {Math.round(value)}{unit} / {goal}{unit}
        </span>
      </div>
      <div className="h-2 bg-bg-hover rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${progress}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

export function DietCard({ todayMeals, weekAvgCalories = 0, loading }: DietCardProps) {
  if (loading) {
    return (
      <div className="bg-bg-card rounded-xl p-5 animate-pulse">
        <div className="h-6 bg-bg-hover rounded w-20 mb-4"></div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 bg-bg-hover rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  // Calculate today's totals
  const totals = todayMeals.reduce(
    (acc, meal) => ({
      calories: acc.calories + meal.calories,
      protein: acc.protein + meal.protein_g,
      carbs: acc.carbs + meal.carbs_g,
      fat: acc.fat + meal.fat_g,
      water: acc.water + meal.water_ml,
    }),
    { calories: 0, protein: 0, carbs: 0, fat: 0, water: 0 }
  );

  const calorieProgress = Math.min((totals.calories / CALORIE_GOAL) * 100, 100);
  const mealsLogged = todayMeals.length;

  return (
    <div className="bg-bg-card rounded-xl p-5 border border-domain-diet/20 hover:border-domain-diet/40 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🍽️</span>
          <h3 className="text-lg font-semibold text-text-primary">Diet</h3>
        </div>
        <span className="text-xs text-text-muted">{mealsLogged} meals today</span>
      </div>

      {/* Calorie Circle */}
      <div className="flex items-center gap-4 mb-4">
        <div className="relative w-20 h-20">
          <svg className="w-20 h-20 transform -rotate-90">
            <circle
              cx="40"
              cy="40"
              r="35"
              fill="none"
              stroke="#334155"
              strokeWidth="8"
            />
            <circle
              cx="40"
              cy="40"
              r="35"
              fill="none"
              stroke="#f97316"
              strokeWidth="8"
              strokeDasharray={`${calorieProgress * 2.2} 220`}
              strokeLinecap="round"
              className="transition-all duration-500"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-lg font-bold text-text-primary">{totals.calories}</span>
            <span className="text-xs text-text-muted">kcal</span>
          </div>
        </div>
        <div className="flex-1">
          <p className="text-sm text-text-secondary mb-1">Daily Goal</p>
          <p className="text-2xl font-bold text-text-primary">{CALORIE_GOAL}</p>
          <p className="text-xs text-text-muted">
            {CALORIE_GOAL - totals.calories > 0
              ? `${CALORIE_GOAL - totals.calories} remaining`
              : 'Goal reached!'
            }
          </p>
          {weekAvgCalories > 0 && (
            <p className="text-xs text-text-muted mt-1">
              Week avg: {Math.round(weekAvgCalories)} kcal
            </p>
          )}
        </div>
      </div>

      {/* Macro Bars */}
      <div className="space-y-3">
        <MacroBar label="Protein" value={totals.protein} goal={PROTEIN_GOAL} color="#22c55e" />
        <MacroBar label="Carbs" value={totals.carbs} goal={CARBS_GOAL} color="#3b82f6" />
        <MacroBar label="Fat" value={totals.fat} goal={FAT_GOAL} color="#eab308" />
      </div>

      {/* Water */}
      <div className="mt-3 pt-3 border-t border-bg-hover flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span>💧</span>
          <span className="text-sm text-text-secondary">Hydration</span>
        </div>
        <span className="text-sm font-medium text-text-primary">
          {(totals.water / 1000).toFixed(1)}L
        </span>
      </div>
    </div>
  );
}
