"""Fitness API routes."""
from fastapi import APIRouter, Query
from datetime import datetime, timedelta

from ..models.fitness import FitnessRecord
from ..database import db_manager

router = APIRouter(prefix="/api/health", tags=["Fitness"])


def _row_to_fitness(row) -> FitnessRecord:
    """Convert SQLite row to FitnessRecord model."""
    workout_type = row["workout_type"]
    if workout_type in ("none", "None", ""):
        workout_type = None

    return FitnessRecord(
        record_id=row["record_id"],
        date=row["date"],
        data_source=row["data_source"],
        steps=int(row["steps"]),
        distance_km=float(row["distance_km"]),
        active_minutes=int(row["active_minutes"]),
        calories_burned=int(row["calories_burned"]),
        resting_heart_rate=int(row["resting_heart_rate"]),
        avg_heart_rate=int(row["avg_heart_rate"]),
        max_heart_rate=int(row["max_heart_rate"]),
        sleep_hours=float(row["sleep_hours"]),
        sleep_quality_score=int(row["sleep_quality_score"]),
        workout_type=workout_type,
        workout_duration_min=int(row["workout_duration_min"]),
    )


@router.get("/fitness", response_model=list[FitnessRecord])
async def get_fitness_records(
    days: int = Query(default=7, ge=1, le=90, description="Number of days of history"),
):
    """Get fitness records for the specified number of days."""
    with db_manager.get_fitness_conn() as conn:
        cursor = conn.cursor()

        # Get the most recent date in the database as reference point (for demo data)
        cursor.execute("SELECT MAX(date) as max_date FROM fitness_data")
        result = cursor.fetchone()
        max_date_str = result["max_date"] if result else None

        if max_date_str:
            max_date = datetime.strptime(max_date_str, "%Y-%m-%d").date()
            cutoff_date = max_date - timedelta(days=days - 1)
        else:
            return []

        cursor.execute(
            """
            SELECT * FROM fitness_data
            WHERE date >= ?
            ORDER BY date DESC
            """,
            (str(cutoff_date),),
        )
        rows = cursor.fetchall()

    return [_row_to_fitness(row) for row in rows]
