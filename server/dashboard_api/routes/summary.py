"""Health summary API routes."""
from fastapi import APIRouter
from datetime import datetime, timedelta

from ..models.summary import HealthSummary
from ..models.biomarker import BiomarkerSummary, Biomarker
from ..models.fitness import FitnessSummary, FitnessRecord
from ..models.diet import DietSummary
from ..models.wellness import WellnessSummary, MentalWellnessEntry
from ..database import db_manager

router = APIRouter(prefix="/api/health", tags=["Health Summary"])


def _row_to_biomarker(row) -> Biomarker:
    """Convert SQLite row to Biomarker model."""
    return Biomarker(
        test_id=row["test_id"],
        test_date=row["test_date"],
        test_type=row["test_type"],
        biomarker_name=row["biomarker_name"],
        value=float(row["value"]),
        unit=row["unit"],
        reference_range_low=float(row["reference_range_low"]),
        reference_range_high=float(row["reference_range_high"]),
        status=row["status"],
        lab_source=row["lab_source"],
        notes=row["notes"],
    )


def _row_to_fitness(row) -> FitnessRecord:
    """Convert SQLite row to FitnessRecord model."""
    workout_type = row["workout_type"]
    if workout_type in ("none", "None", ""):
        workout_type = None

    # Helper to safely convert to int (handles float strings like '111.0' and None)
    def to_int(val):
        return int(float(val)) if val else 0

    return FitnessRecord(
        record_id=row["record_id"],
        date=row["date"],
        data_source=row["data_source"],
        steps=to_int(row["steps"]),
        distance_km=float(row["distance_km"] or 0),
        active_minutes=to_int(row["active_minutes"]),
        calories_burned=to_int(row["calories_burned"]),
        resting_heart_rate=to_int(row["resting_heart_rate"]),
        avg_heart_rate=to_int(row["avg_heart_rate"]),
        max_heart_rate=to_int(row["max_heart_rate"]),
        sleep_hours=float(row["sleep_hours"] or 0),
        sleep_quality_score=to_int(row["sleep_quality_score"]),
        workout_type=workout_type,
        workout_duration_min=to_int(row["workout_duration_min"]),
    )


def _row_to_wellness(row) -> MentalWellnessEntry:
    """Convert SQLite row to MentalWellnessEntry model."""
    # Helper to safely convert to int (handles float strings like '7.0' and None)
    def to_int(val):
        return int(float(val)) if val else 0

    return MentalWellnessEntry(
        entry_id=row["entry_id"],
        date=row["date"],
        time_of_day=row["time_of_day"],
        mood_score=to_int(row["mood_score"]),
        energy_level=to_int(row["energy_level"]),
        stress_level=to_int(row["stress_level"]),
        anxiety_level=to_int(row["anxiety_level"]),
        sleep_quality_rating=to_int(row["sleep_quality_rating"]),
        activities=row["activities"] or "",
        social_interaction=row["social_interaction"],
        journal_entry=row["journal_entry"],
        gratitude_notes=row["gratitude_notes"],
        tags=row["tags"] or "",
    )


@router.get("/summary", response_model=HealthSummary, response_model_by_alias=True)
async def get_health_summary():
    """
    Get aggregated health summary across all domains.
    Combines latest biomarkers, fitness stats, diet totals, and wellness metrics.
    """
    # Note: We use max dates from each database as reference points for demo data

    # Biomarkers summary
    with db_manager.get_biomarker_conn() as conn:
        cursor = conn.cursor()

        # Get latest biomarkers
        cursor.execute(
            """
            SELECT * FROM biomarker_data
            ORDER BY test_date DESC
            LIMIT 10
            """
        )
        latest_biomarkers = [_row_to_biomarker(row) for row in cursor.fetchall()]

        # Count abnormal biomarkers
        cursor.execute(
            """
            SELECT COUNT(*) as cnt FROM biomarker_data
            WHERE status IN ('low', 'high', 'critical')
            """
        )
        abnormal_count = cursor.fetchone()["cnt"]

        # Get last test date
        cursor.execute("SELECT MAX(test_date) as max_date FROM biomarker_data")
        last_test_date = cursor.fetchone()["max_date"]

    biomarker_summary = BiomarkerSummary(
        latest=latest_biomarkers,
        abnormal_count=abnormal_count,
        last_test_date=last_test_date,
    )

    # Fitness summary
    with db_manager.get_fitness_conn() as conn:
        cursor = conn.cursor()

        # Get the most recent date as reference point
        cursor.execute("SELECT MAX(date) as max_date FROM fitness_data")
        result = cursor.fetchone()
        fitness_max_date_str = result["max_date"] if result else None

        # Get today's fitness (or latest valid record)
        # Filter out incomplete records where all key metrics are zero
        # (e.g., records created by wearable listener with only heart rate data)
        cursor.execute(
            """
            SELECT * FROM fitness_data
            WHERE NOT (
                CAST(steps AS INTEGER) = 0
                AND CAST(active_minutes AS INTEGER) = 0
                AND CAST(calories_burned AS INTEGER) = 0
                AND CAST(sleep_hours AS REAL) = 0
            )
            ORDER BY date DESC
            LIMIT 1
            """
        )
        today_row = cursor.fetchone()
        today_fitness = _row_to_fitness(today_row) if today_row else None

        # Get week averages using max date as reference
        if fitness_max_date_str:
            fitness_max_date = datetime.strptime(fitness_max_date_str, "%Y-%m-%d").date()
            fitness_week_ago = fitness_max_date - timedelta(days=7)
            cursor.execute(
                """
                SELECT
                    AVG(CAST(steps AS REAL)) as avg_steps,
                    AVG(CAST(sleep_hours AS REAL)) as avg_sleep,
                    AVG(CAST(resting_heart_rate AS REAL)) as avg_hr
                FROM fitness_data
                WHERE date >= ?
                """,
                (str(fitness_week_ago),),
            )
            avgs = cursor.fetchone()
        else:
            avgs = {"avg_steps": 0, "avg_sleep": 0, "avg_hr": 0}

    fitness_summary = FitnessSummary(
        today=today_fitness,
        week_avg_steps=avgs["avg_steps"] or 0,
        week_avg_sleep=avgs["avg_sleep"] or 0,
        week_avg_hr=avgs["avg_hr"] or 0,
    )

    # Diet summary
    with db_manager.get_diet_conn() as conn:
        cursor = conn.cursor()

        # Get the most recent date as reference point
        cursor.execute("SELECT MAX(date) as max_date FROM diet_logs")
        result = cursor.fetchone()
        diet_max_date_str = result["max_date"] if result else None

        if diet_max_date_str:
            cursor.execute(
                """
                SELECT
                    SUM(CAST(calories AS INTEGER)) as calories,
                    SUM(CAST(protein_g AS REAL)) as protein,
                    SUM(CAST(carbs_g AS REAL)) as carbs,
                    SUM(CAST(fat_g AS REAL)) as fat,
                    SUM(CAST(water_ml AS INTEGER)) as water
                FROM diet_logs
                WHERE date = ?
                """,
                (diet_max_date_str,),
            )
            today_diet = cursor.fetchone()

            # Get week average calories using max date as reference
            diet_max_date = datetime.strptime(diet_max_date_str, "%Y-%m-%d").date()
            diet_week_ago = diet_max_date - timedelta(days=7)
            cursor.execute(
                """
                SELECT AVG(daily_cal) as avg_cal FROM (
                    SELECT date, SUM(CAST(calories AS INTEGER)) as daily_cal
                    FROM diet_logs
                    WHERE date >= ?
                    GROUP BY date
                )
                """,
                (str(diet_week_ago),),
            )
            week_avg = cursor.fetchone()
        else:
            today_diet = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0, "water": 0}
            week_avg = {"avg_cal": 0}

    diet_summary = DietSummary(
        today_calories=today_diet["calories"] or 0,
        today_protein=today_diet["protein"] or 0,
        today_carbs=today_diet["carbs"] or 0,
        today_fat=today_diet["fat"] or 0,
        today_water=today_diet["water"] or 0,
        week_avg_calories=week_avg["avg_cal"] or 0,
    )

    # Mental wellness summary
    with db_manager.get_wellness_conn() as conn:
        cursor = conn.cursor()

        # Get the most recent date as reference point
        cursor.execute("SELECT MAX(date) as max_date FROM mental_wellness")
        result = cursor.fetchone()
        wellness_max_date_str = result["max_date"] if result else None

        # Get latest entry
        cursor.execute(
            """
            SELECT * FROM mental_wellness
            ORDER BY date DESC, time_of_day DESC
            LIMIT 1
            """
        )
        latest_row = cursor.fetchone()
        latest_wellness = _row_to_wellness(latest_row) if latest_row else None

        # Get week averages using max date as reference
        if wellness_max_date_str:
            wellness_max_date = datetime.strptime(wellness_max_date_str, "%Y-%m-%d").date()
            wellness_week_ago = wellness_max_date - timedelta(days=7)
            cursor.execute(
                """
                SELECT
                    AVG(CAST(mood_score AS REAL)) as avg_mood,
                    AVG(CAST(stress_level AS REAL)) as avg_stress,
                    AVG(CAST(energy_level AS REAL)) as avg_energy
                FROM mental_wellness
                WHERE date >= ?
                """,
                (str(wellness_week_ago),),
            )
            wellness_avgs = cursor.fetchone()
        else:
            wellness_avgs = {"avg_mood": 0, "avg_stress": 0, "avg_energy": 0}

    wellness_summary = WellnessSummary(
        latest=latest_wellness,
        week_avg_mood=wellness_avgs["avg_mood"] or 0,
        week_avg_stress=wellness_avgs["avg_stress"] or 0,
        week_avg_energy=wellness_avgs["avg_energy"] or 0,
    )

    return HealthSummary(
        biomarkers=biomarker_summary,
        fitness=fitness_summary,
        diet=diet_summary,
        mental_wellness=wellness_summary,
    )
