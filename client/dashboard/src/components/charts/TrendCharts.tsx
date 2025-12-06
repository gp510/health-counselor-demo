import { useState, useMemo } from 'react';
import type { FitnessRecord, MentalWellnessEntry, DietEntry } from '../../types/health';
import { TrendChart } from './TrendChart';

interface TrendChartsProps {
  fitness: FitnessRecord[];
  wellness: MentalWellnessEntry[];
  diet: DietEntry[];
  loading?: boolean;
}

type TabId = 'heart-rate' | 'sleep' | 'mood' | 'macros';

interface Tab {
  id: TabId;
  label: string;
  icon: string;
}

const tabs: Tab[] = [
  { id: 'heart-rate', label: 'Heart Rate', icon: '💓' },
  { id: 'sleep', label: 'Sleep', icon: '😴' },
  { id: 'mood', label: 'Mood', icon: '🧠' },
  { id: 'macros', label: 'Nutrition', icon: '🍽️' },
];

export function TrendCharts({ fitness, wellness, diet, loading }: TrendChartsProps) {
  const [activeTab, setActiveTab] = useState<TabId>('heart-rate');

  // Prepare heart rate data
  const heartRateData = useMemo(
    () =>
      fitness
        .slice()
        .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
        .map((f) => ({
          date: f.date,
          resting: f.resting_heart_rate,
          average: f.avg_heart_rate,
          max: f.max_heart_rate,
        })),
    [fitness]
  );

  // Prepare sleep data
  const sleepData = useMemo(
    () =>
      fitness
        .slice()
        .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
        .map((f) => ({
          date: f.date,
          hours: f.sleep_hours,
          quality: f.sleep_quality_score,
        })),
    [fitness]
  );

  // Prepare mood data
  const moodData = useMemo(
    () =>
      wellness
        .slice()
        .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
        .map((w) => ({
          date: w.date,
          mood: w.mood_score,
          energy: w.energy_level,
          stress: w.stress_level,
        })),
    [wellness]
  );

  // Prepare nutrition data (aggregate by date)
  const macrosData = useMemo(() => {
    const byDate = new Map<string, { protein: number; carbs: number; fat: number }>();

    diet.forEach((d) => {
      const existing = byDate.get(d.date) || { protein: 0, carbs: 0, fat: 0 };
      byDate.set(d.date, {
        protein: existing.protein + d.protein_g,
        carbs: existing.carbs + d.carbs_g,
        fat: existing.fat + d.fat_g,
      });
    });

    return Array.from(byDate.entries())
      .map(([date, values]) => ({ date, ...values }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  }, [diet]);

  if (loading) {
    return (
      <div className="bg-bg-card rounded-xl p-5 animate-pulse">
        <div className="h-6 bg-bg-hover rounded w-40 mb-4"></div>
        <div className="h-48 bg-bg-hover rounded"></div>
      </div>
    );
  }

  const renderChart = () => {
    switch (activeTab) {
      case 'heart-rate':
        return (
          <TrendChart
            data={heartRateData}
            series={[
              { key: 'resting', name: 'Resting', color: '#22c55e' },
              { key: 'average', name: 'Average', color: '#3b82f6' },
              { key: 'max', name: 'Max', color: '#ef4444' },
            ]}
            type="line"
            height={220}
            showLegend
            yAxisDomain={[40, 'auto']}
          />
        );
      case 'sleep':
        return (
          <TrendChart
            data={sleepData}
            series={[
              { key: 'hours', name: 'Sleep Hours', color: '#8b5cf6' },
              { key: 'quality', name: 'Quality Score', color: '#06b6d4' },
            ]}
            type="area"
            height={220}
            showLegend
          />
        );
      case 'mood':
        return (
          <TrendChart
            data={moodData}
            series={[
              { key: 'mood', name: 'Mood', color: '#22c55e' },
              { key: 'energy', name: 'Energy', color: '#f97316' },
              { key: 'stress', name: 'Stress', color: '#ef4444' },
            ]}
            type="line"
            height={220}
            showLegend
            yAxisDomain={[0, 10]}
          />
        );
      case 'macros':
        return (
          <TrendChart
            data={macrosData}
            series={[
              { key: 'protein', name: 'Protein (g)', color: '#22c55e' },
              { key: 'carbs', name: 'Carbs (g)', color: '#3b82f6' },
              { key: 'fat', name: 'Fat (g)', color: '#eab308' },
            ]}
            type="bar"
            height={220}
            showLegend
          />
        );
    }
  };

  return (
    <div className="bg-bg-card rounded-xl p-5">
      {/* Tab Header */}
      <div className="flex items-center gap-1 mb-4 border-b border-bg-hover pb-3">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'bg-bg-hover text-text-primary'
                : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover/50'
            }`}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Chart Area */}
      <div className="min-h-[220px]">
        {(activeTab === 'heart-rate' || activeTab === 'sleep') && fitness.length === 0 ? (
          <div className="flex items-center justify-center h-[220px] text-text-muted">
            No fitness data available
          </div>
        ) : activeTab === 'mood' && wellness.length === 0 ? (
          <div className="flex items-center justify-center h-[220px] text-text-muted">
            No wellness data available
          </div>
        ) : activeTab === 'macros' && diet.length === 0 ? (
          <div className="flex items-center justify-center h-[220px] text-text-muted">
            No nutrition data available
          </div>
        ) : (
          renderChart()
        )}
      </div>
    </div>
  );
}
