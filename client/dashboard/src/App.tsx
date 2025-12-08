import { useState, useMemo } from 'react';
import type { HealthSummary, HealthAlert, DietEntry } from './types/health';
import { useHealthData } from './hooks/useHealthData';
import { useAlertStream } from './hooks/useAlertStream';

// Layout components
import { Header } from './components/layout/Header';
import { AlertBanner } from './components/layout/AlertBanner';
import { StatusFooter } from './components/layout/StatusFooter';

// Card components
import { HealthSummaryCards } from './components/cards/HealthSummaryCards';
import { ExecutiveSummaryCard } from './components/cards/ExecutiveSummaryCard';

// Chart components
import { TrendCharts } from './components/charts/TrendCharts';

// Chat components
import { ChatPanel } from './components/chat/ChatPanel';

function App() {
  const {
    summary,
    fitness,
    biomarkers,
    diet,
    wellness,
    alerts: fetchedAlerts,
    systemStatus,
    loading,
    error,
    refresh,
  } = useHealthData(30000); // Refresh every 30 seconds

  // Connect to SSE stream for real-time automation alerts
  const { sseAlerts, clearAlert: clearSSEAlert } = useAlertStream();

  const [dismissedAlerts, setDismissedAlerts] = useState<Set<string>>(new Set());
  const [refreshing, setRefreshing] = useState(false);

  // Merge SSE alerts with polled alerts, filter out dismissed
  const alerts: HealthAlert[] = useMemo(() => {
    // SSE alerts come first (real-time), then polled alerts
    const allAlerts = [
      ...sseAlerts,
      ...fetchedAlerts.map(a => ({ ...a, dismissed: false })),
    ];

    // Filter out dismissed and deduplicate by ID
    const seen = new Set<string>();
    return allAlerts.filter(a => {
      if (dismissedAlerts.has(a.id) || seen.has(a.id)) return false;
      seen.add(a.id);
      return true;
    });
  }, [sseAlerts, fetchedAlerts, dismissedAlerts]);

  // Get today's diet entries (most recent date in the data)
  const todayDiet: DietEntry[] = useMemo(() => {
    if (diet.length === 0) return [];
    const latestDate = diet[0]?.date;
    return diet.filter(d => d.date === latestDate);
  }, [diet]);

  // Build summary with fallback for loading state
  const healthSummary: HealthSummary = useMemo(() => {
    if (summary) return summary;

    // Return empty summary during loading
    return {
      biomarkers: {
        latest: [],
        abnormalCount: 0,
        lastTestDate: null,
      },
      fitness: {
        today: null,
        weekAvgSteps: 0,
        weekAvgSleep: 0,
        weekAvgHR: 0,
      },
      diet: {
        todayCalories: 0,
        todayProtein: 0,
        todayCarbs: 0,
        todayFat: 0,
        todayWater: 0,
        weekAvgCalories: 0,
      },
      mentalWellness: {
        latest: null,
        weekAvgMood: 0,
        weekAvgStress: 0,
        weekAvgEnergy: 0,
      },
    };
  }, [summary]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await refresh();
    setRefreshing(false);
  };

  const handleDismissAlert = (alertId: string) => {
    setDismissedAlerts(prev => new Set([...prev, alertId]));
    // Also clear from SSE alerts
    clearSSEAlert(alertId);
  };

  return (
    <div className="h-screen flex flex-col bg-bg-primary overflow-hidden">
      {/* Alert Banner */}
      <AlertBanner alerts={alerts} onDismiss={handleDismissAlert} />

      {/* Header */}
      <Header onRefresh={handleRefresh} refreshing={refreshing} />

      {/* Main Content */}
      <main className="flex-1 flex min-h-0 overflow-hidden">
        {/* Dashboard Area */}
        <div className="flex-1 p-6 overflow-y-auto">
          {error && (
            <div className="max-w-6xl mx-auto mb-4 p-4 bg-health-critical/10 border border-health-critical/30 rounded-lg">
              <p className="text-health-critical font-medium">Error loading data</p>
              <p className="text-sm text-text-secondary mt-1">{error}</p>
              <button
                onClick={handleRefresh}
                className="mt-2 px-3 py-1 text-sm bg-health-critical/20 hover:bg-health-critical/30 rounded transition-colors"
              >
                Retry
              </button>
            </div>
          )}

          <div className="max-w-6xl mx-auto space-y-6">
            {/* Executive Summary */}
            <ExecutiveSummaryCard />

            {/* Summary Cards */}
            <HealthSummaryCards
              summary={healthSummary}
              biomarkers={biomarkers}
              todayDiet={todayDiet}
              loading={loading}
            />

            {/* Trend Charts */}
            <TrendCharts
              fitness={fitness}
              wellness={wellness}
              diet={diet}
              loading={loading}
            />
          </div>
        </div>

        {/* Chat Panel */}
        <ChatPanel className="w-96 border-l border-bg-hover flex-shrink-0" />
      </main>

      {/* Status Footer */}
      <StatusFooter status={systemStatus} loading={loading} />
    </div>
  );
}

export default App;
