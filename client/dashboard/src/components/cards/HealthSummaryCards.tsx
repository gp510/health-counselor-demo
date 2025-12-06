import type { HealthSummary, Biomarker, DietEntry } from '../../types/health';
import { BiomarkerCard } from './BiomarkerCard';
import { FitnessCard } from './FitnessCard';
import { DietCard } from './DietCard';
import { MentalWellnessCard } from './MentalWellnessCard';

interface HealthSummaryCardsProps {
  summary: HealthSummary | null;
  biomarkers: Biomarker[];
  todayDiet: DietEntry[];
  loading?: boolean;
}

export function HealthSummaryCards({
  summary,
  biomarkers,
  todayDiet,
  loading,
}: HealthSummaryCardsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <BiomarkerCard biomarkers={biomarkers} loading={loading} />
      <FitnessCard
        today={summary?.fitness.today ?? null}
        weekAvgSteps={summary?.fitness.weekAvgSteps}
        weekAvgSleep={summary?.fitness.weekAvgSleep}
        loading={loading}
      />
      <DietCard
        todayMeals={todayDiet}
        weekAvgCalories={summary?.diet.weekAvgCalories}
        loading={loading}
      />
      <MentalWellnessCard
        latest={summary?.mentalWellness.latest ?? null}
        weekAvgMood={summary?.mentalWellness.weekAvgMood}
        weekAvgStress={summary?.mentalWellness.weekAvgStress}
        weekAvgEnergy={summary?.mentalWellness.weekAvgEnergy}
        loading={loading}
      />
    </div>
  );
}
