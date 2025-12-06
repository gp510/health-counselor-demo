"""Mental wellness API routes."""
from fastapi import APIRouter, Query
from datetime import datetime, timedelta

from ..models.wellness import MentalWellnessEntry
from ..database import db_manager

router = APIRouter(prefix="/api/health", tags=["Mental Wellness"])


def _row_to_wellness(row) -> MentalWellnessEntry:
    """Convert SQLite row to MentalWellnessEntry model."""
    return MentalWellnessEntry(
        entry_id=row["entry_id"],
        date=row["date"],
        time_of_day=row["time_of_day"],
        mood_score=int(row["mood_score"]),
        energy_level=int(row["energy_level"]),
        stress_level=int(row["stress_level"]),
        anxiety_level=int(row["anxiety_level"]),
        sleep_quality_rating=int(row["sleep_quality_rating"]),
        activities=row["activities"] or "",
        social_interaction=row["social_interaction"],
        journal_entry=row["journal_entry"],
        gratitude_notes=row["gratitude_notes"],
        tags=row["tags"] or "",
    )


@router.get("/wellness", response_model=list[MentalWellnessEntry])
async def get_wellness_entries(
    days: int = Query(default=7, ge=1, le=90, description="Number of days of history"),
):
    """Get mental wellness journal entries for the specified number of days."""
    with db_manager.get_wellness_conn() as conn:
        cursor = conn.cursor()

        # Get the most recent date in the database as reference point (for demo data)
        cursor.execute("SELECT MAX(date) as max_date FROM mental_wellness")
        result = cursor.fetchone()
        max_date_str = result["max_date"] if result else None

        if max_date_str:
            max_date = datetime.strptime(max_date_str, "%Y-%m-%d").date()
            cutoff_date = max_date - timedelta(days=days - 1)
        else:
            return []

        cursor.execute(
            """
            SELECT * FROM mental_wellness
            WHERE date >= ?
            ORDER BY date DESC
            """,
            (str(cutoff_date),),
        )
        rows = cursor.fetchall()

    return [_row_to_wellness(row) for row in rows]
