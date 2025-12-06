/**
 * Health Dashboard API client for fetching health data from the backend.
 */
import type {
  Biomarker,
  FitnessRecord,
  DietEntry,
  MentalWellnessEntry,
  HealthSummary,
  HealthAlert,
  HealthInsight,
  InsightDomain,
} from '../types/health';

const API_BASE = '/api/health';

class HealthAPI {
  private async fetch<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`);
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Fetch aggregated health summary across all domains.
   */
  async getHealthSummary(): Promise<HealthSummary> {
    return this.fetch<HealthSummary>('/summary');
  }

  /**
   * Fetch recent biomarker/lab results.
   */
  async getBiomarkers(days: number = 30): Promise<Biomarker[]> {
    return this.fetch<Biomarker[]>(`/biomarkers?days=${days}`);
  }

  /**
   * Fetch fitness records for the specified number of days.
   */
  async getFitnessRecords(days: number = 7): Promise<FitnessRecord[]> {
    return this.fetch<FitnessRecord[]>(`/fitness?days=${days}`);
  }

  /**
   * Fetch diet/meal log entries for the specified number of days.
   */
  async getDietEntries(days: number = 7): Promise<DietEntry[]> {
    return this.fetch<DietEntry[]>(`/diet?days=${days}`);
  }

  /**
   * Fetch mental wellness entries for the specified number of days.
   */
  async getMentalWellness(days: number = 7): Promise<MentalWellnessEntry[]> {
    return this.fetch<MentalWellnessEntry[]>(`/wellness?days=${days}`);
  }

  /**
   * Fetch active health alerts.
   */
  async getActiveAlerts(): Promise<HealthAlert[]> {
    return this.fetch<HealthAlert[]>('/alerts');
  }

  /**
   * Fetch all health data in parallel.
   */
  async fetchAllHealthData(days: number = 7) {
    const [summary, biomarkers, fitness, diet, wellness, alerts] = await Promise.all([
      this.getHealthSummary(),
      this.getBiomarkers(days),
      this.getFitnessRecords(days),
      this.getDietEntries(days),
      this.getMentalWellness(days),
      this.getActiveAlerts(),
    ]);

    return { summary, biomarkers, fitness, diet, wellness, alerts };
  }

  /**
   * Generate an AI-powered executive health summary.
   * This triggers the orchestrator to query all agents and synthesize insights.
   */
  async getExecutiveSummary(): Promise<HealthInsight> {
    return this.fetch<HealthInsight>('/insights/executive-summary');
  }

  /**
   * Generate AI-powered insights for a specific health domain.
   */
  async getDomainInsights(domain: InsightDomain): Promise<HealthInsight> {
    return this.fetch<HealthInsight>(`/insights/${domain}`);
  }
}

export const healthApi = new HealthAPI();
export default healthApi;
