# Data Model Reference

This document describes the data schemas used by the Health Counselor health agents.

## Overview

Each health domain agent maintains its own SQLite database, populated from CSV source files in `CSV_Data/`. The databases are initialized when agents start and are queried via natural language using the `execute_sql_query` tool.

## Biomarker Data

**Source:** `CSV_Data/biomarker_data.csv`
**Database:** `biomarker.db`
**Table:** `biomarker_data`

| Column | Type | Description | Example Values |
|--------|------|-------------|----------------|
| `test_id` | TEXT | Unique identifier | BIO-001, BIO-002 |
| `test_date` | DATE | Date of test | 2024-10-15 |
| `test_type` | TEXT | Category of test | blood_panel, metabolic, vitamin |
| `biomarker_name` | TEXT | Name of biomarker | Glucose, LDL Cholesterol |
| `value` | REAL | Measured value | 95, 120 |
| `unit` | TEXT | Unit of measurement | mg/dL, ng/mL |
| `reference_range_low` | REAL | Normal range minimum | 70, 0 |
| `reference_range_high` | REAL | Normal range maximum | 100, 100 |
| `status` | TEXT | Result status | normal, low, high, critical |
| `lab_source` | TEXT | Testing facility | LabCorp, Quest |
| `notes` | TEXT | Additional notes | Fasting sample |

## Fitness Data

**Source:** `CSV_Data/fitness_data.csv`
**Database:** `fitness.db`
**Table:** `fitness_data`

| Column | Type | Description | Example Values |
|--------|------|-------------|----------------|
| `record_id` | TEXT | Unique identifier | FIT-001, FIT-002 |
| `date` | DATE | Record date | 2024-12-01 |
| `data_source` | TEXT | Device source | Apple Watch, Fitbit, Garmin |
| `steps` | INTEGER | Daily step count | 8500 |
| `distance_km` | REAL | Distance traveled | 6.2 |
| `active_minutes` | INTEGER | Active exercise minutes | 45 |
| `calories_burned` | INTEGER | Total calories | 2200 |
| `resting_heart_rate` | INTEGER | Resting HR (bpm) | 62 |
| `avg_heart_rate` | INTEGER | Average HR (bpm) | 75 |
| `sleep_hours` | REAL | Sleep duration | 7.5 |
| `sleep_quality_score` | INTEGER | Sleep quality (1-100) | 85 |
| `workout_type` | TEXT | Exercise type | running, cycling, strength |
| `workout_duration_min` | INTEGER | Workout length | 45 |

## Diet Logs

**Source:** `CSV_Data/diet_logs.csv`
**Database:** `diet.db`
**Table:** `diet_logs`

| Column | Type | Description | Example Values |
|--------|------|-------------|----------------|
| `meal_id` | TEXT | Unique identifier | MEAL-001, MEAL-002 |
| `date` | DATE | Meal date | 2024-12-01 |
| `meal_type` | TEXT | Type of meal | breakfast, lunch, dinner, snack |
| `food_items` | TEXT | Foods consumed | Oatmeal with berries |
| `calories` | INTEGER | Total calories | 350 |
| `protein_g` | REAL | Protein grams | 12 |
| `carbs_g` | REAL | Carbohydrate grams | 55 |
| `fat_g` | REAL | Fat grams | 8 |
| `fiber_g` | REAL | Fiber grams | 6 |
| `sodium_mg` | INTEGER | Sodium milligrams | 150 |
| `sugar_g` | REAL | Sugar grams | 12 |
| `water_ml` | INTEGER | Water intake | 500 |
| `notes` | TEXT | Additional notes | Pre-workout meal |

## Mental Wellness

**Source:** `CSV_Data/mental_wellness.csv`
**Database:** `mental_wellness.db`
**Table:** `mental_wellness`

| Column | Type | Description | Example Values |
|--------|------|-------------|----------------|
| `entry_id` | TEXT | Unique identifier | MW-001, MW-002 |
| `date` | DATE | Entry date | 2024-12-01 |
| `time_of_day` | TEXT | Time period | morning, afternoon, evening |
| `mood_score` | INTEGER | Mood rating (1-10) | 7 |
| `energy_level` | INTEGER | Energy rating (1-10) | 6 |
| `stress_level` | INTEGER | Stress rating (1-10) | 4 |
| `anxiety_level` | INTEGER | Anxiety rating (1-10) | 3 |
| `sleep_quality_rating` | INTEGER | Sleep quality (1-10) | 8 |
| `activities` | TEXT | Day's activities | work, exercise, socializing |
| `social_interaction` | TEXT | Social contact level | high, medium, low, none |
| `journal_entry` | TEXT | Free-form notes | Felt productive today |
| `gratitude_notes` | TEXT | Gratitude journaling | Grateful for good weather |
| `tags` | TEXT | Categorization tags | productive, relaxed, anxious |

## Wearable Events

Real-time wearable data is published to Solace topics and processed by the WearableListenerAgent. See [Wearable Simulation](simulation-demo.md) for event format details.

**Topic Pattern:** `health/events/wearable/{data_type}/update`

**Event Payload:**
```json
{
  "event_id": "WRB-A1B2C3D4",
  "event_type": "wearable_data",
  "data_type": "heart_rate",
  "timestamp": "2024-12-03T15:30:00Z",
  "value": 72,
  "unit": "bpm",
  "source_device": "smartwatch",
  "alert_level": "normal",
  "message": "Heart rate reading: 72 bpm"
}
```
