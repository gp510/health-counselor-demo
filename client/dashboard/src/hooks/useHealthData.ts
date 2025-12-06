import { useState, useEffect, useCallback } from 'react';
import healthApi from '../services/healthApi';
import type {
  HealthSummary,
  FitnessRecord,
  Biomarker,
  DietEntry,
  MentalWellnessEntry,
  HealthAlert,
  SystemStatus,
} from '../types/health';

interface UseHealthDataReturn {
  summary: HealthSummary | null;
  fitness: FitnessRecord[];
  biomarkers: Biomarker[];
  diet: DietEntry[];
  wellness: MentalWellnessEntry[];
  alerts: HealthAlert[];
  systemStatus: SystemStatus;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const defaultSystemStatus: SystemStatus = {
  brokerConnected: false,
  agentsOnline: 0,
  lastSyncTime: new Date().toISOString(),
};

export function useHealthData(refreshInterval: number = 30000): UseHealthDataReturn {
  const [summary, setSummary] = useState<HealthSummary | null>(null);
  const [fitness, setFitness] = useState<FitnessRecord[]>([]);
  const [biomarkers, setBiomarkers] = useState<Biomarker[]>([]);
  const [diet, setDiet] = useState<DietEntry[]>([]);
  const [wellness, setWellness] = useState<MentalWellnessEntry[]>([]);
  const [alerts, setAlerts] = useState<HealthAlert[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>(defaultSystemStatus);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setError(null);

      const [
        summaryData,
        fitnessData,
        biomarkersData,
        dietData,
        wellnessData,
        alertsData,
      ] = await Promise.all([
        healthApi.getHealthSummary(),
        healthApi.getFitnessRecords(7),
        healthApi.getBiomarkers(30),
        healthApi.getDietEntries(7),
        healthApi.getMentalWellness(7),
        healthApi.getActiveAlerts(),
      ]);

      setSummary(summaryData);
      setFitness(fitnessData);
      setBiomarkers(biomarkersData);
      setDiet(dietData);
      setWellness(wellnessData);
      setAlerts(alertsData);
      setSystemStatus({
        brokerConnected: true,
        agentsOnline: 5,
        lastSyncTime: new Date().toISOString(),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch health data');
      setSystemStatus({
        brokerConnected: false,
        agentsOnline: 0,
        lastSyncTime: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();

    if (refreshInterval > 0) {
      const intervalId = setInterval(fetchData, refreshInterval);
      return () => clearInterval(intervalId);
    }
  }, [fetchData, refreshInterval]);

  return {
    summary,
    fitness,
    biomarkers,
    diet,
    wellness,
    alerts,
    systemStatus,
    loading,
    error,
    refresh: fetchData,
  };
}

// Individual data hooks for more granular control
export function useFitnessData(days: number = 7) {
  const [data, setData] = useState<FitnessRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    healthApi.getFitnessRecords(days)
      .then(setData)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [days]);

  return { data, loading, error };
}

export function useBiomarkerData(days: number = 30) {
  const [data, setData] = useState<Biomarker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    healthApi.getBiomarkers(days)
      .then(setData)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [days]);

  return { data, loading, error };
}

export function useDietData(days: number = 7) {
  const [data, setData] = useState<DietEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    healthApi.getDietEntries(days)
      .then(setData)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [days]);

  return { data, loading, error };
}

export function useWellnessData(days: number = 7) {
  const [data, setData] = useState<MentalWellnessEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    healthApi.getMentalWellness(days)
      .then(setData)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [days]);

  return { data, loading, error };
}
