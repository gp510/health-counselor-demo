// Health status types
export type HealthStatus = 'normal' | 'low' | 'high' | 'critical';
export type AlertLevel = 'info' | 'warning' | 'critical';

// Biomarker data
export interface Biomarker {
  test_id: string;
  test_date: string;
  test_type: string;
  biomarker_name: string;
  value: number;
  unit: string;
  reference_range_low: number;
  reference_range_high: number;
  status: HealthStatus;
  lab_source: string;
  notes: string | null;
}

// Fitness data
export interface FitnessRecord {
  record_id: string;
  date: string;
  data_source: string;
  steps: number;
  distance_km: number;
  active_minutes: number;
  calories_burned: number;
  resting_heart_rate: number;
  avg_heart_rate: number;
  max_heart_rate: number;
  sleep_hours: number;
  sleep_quality_score: number;
  workout_type: string | null;
  workout_duration_min: number;
}

// Diet data
export interface DietEntry {
  meal_id: string;
  date: string;
  meal_type: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  food_items: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  sodium_mg: number;
  sugar_g: number;
  water_ml: number;
  notes: string | null;
}

// Mental wellness data
export interface MentalWellnessEntry {
  entry_id: string;
  date: string;
  time_of_day: 'morning' | 'afternoon' | 'evening';
  mood_score: number;
  energy_level: number;
  stress_level: number;
  anxiety_level: number;
  sleep_quality_rating: number;
  activities: string;
  social_interaction: 'low' | 'medium' | 'high';
  journal_entry: string | null;
  gratitude_notes: string | null;
  tags: string;
}

// Aggregated health summary
export interface HealthSummary {
  biomarkers: {
    latest: Biomarker[];
    abnormalCount: number;
    lastTestDate: string | null;
  };
  fitness: {
    today: FitnessRecord | null;
    weekAvgSteps: number;
    weekAvgSleep: number;
    weekAvgHR: number;
  };
  diet: {
    todayCalories: number;
    todayProtein: number;
    todayCarbs: number;
    todayFat: number;
    todayWater: number;
    weekAvgCalories: number;
  };
  mentalWellness: {
    latest: MentalWellnessEntry | null;
    weekAvgMood: number;
    weekAvgStress: number;
    weekAvgEnergy: number;
  };
}

// Health event from agents
export interface HealthEvent {
  id: string;
  type: string;
  domain: 'biomarkers' | 'fitness' | 'diet' | 'wellness' | 'weather' | 'system';
  timestamp: string;
  level: AlertLevel;
  message: string;
  source: string;
}

// Health alert
export interface HealthAlert {
  id: string;
  level: AlertLevel;
  title: string;
  message: string;
  domain: string;
  timestamp: string;
  dismissed: boolean;
}

// Trend data point
export interface TrendDataPoint {
  date: string;
  value: number;
  label?: string;
}

// Multi-series trend data
export interface TrendSeries {
  name: string;
  color: string;
  data: TrendDataPoint[];
}

// Chat message
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

// System status
export interface SystemStatus {
  brokerConnected: boolean;
  agentsOnline: number;
  lastSyncTime: string | null;
}

// AI-generated health insight
export interface HealthInsight {
  content: string;
  generated_at: string;
}

// Domain types for insights
export type InsightDomain = 'biomarker' | 'fitness' | 'diet' | 'wellness';
