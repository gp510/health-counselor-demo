"""Diet API routes."""
from fastapi import APIRouter, Query
from datetime import datetime, timedelta

from ..models.diet import DietEntry
from ..database import db_manager

router = APIRouter(prefix="/api/health", tags=["Diet"])


def _row_to_diet(row) -> DietEntry:
    """Convert SQLite row to DietEntry model."""
    return DietEntry(
        meal_id=row["meal_id"],
        date=row["date"],
        meal_type=row["meal_type"],
        food_items=row["food_items"],
        calories=int(row["calories"]),
        protein_g=float(row["protein_g"]),
        carbs_g=float(row["carbs_g"]),
        fat_g=float(row["fat_g"]),
        fiber_g=float(row["fiber_g"]),
        sodium_mg=int(row["sodium_mg"]),
        sugar_g=float(row["sugar_g"]),
        water_ml=int(row["water_ml"]),
        notes=row["notes"],
    )


@router.get("/diet", response_model=list[DietEntry])
async def get_diet_entries(
    days: int = Query(default=7, ge=1, le=90, description="Number of days of history"),
):
    """Get diet/meal log entries for the specified number of days."""
    with db_manager.get_diet_conn() as conn:
        cursor = conn.cursor()

        # Get the most recent date in the database as reference point (for demo data)
        cursor.execute("SELECT MAX(date) as max_date FROM diet_logs")
        result = cursor.fetchone()
        max_date_str = result["max_date"] if result else None

        if max_date_str:
            max_date = datetime.strptime(max_date_str, "%Y-%m-%d").date()
            cutoff_date = max_date - timedelta(days=days - 1)
        else:
            return []

        cursor.execute(
            """
            SELECT * FROM diet_logs
            WHERE date >= ?
            ORDER BY date DESC,
                CASE meal_type
                    WHEN 'breakfast' THEN 1
                    WHEN 'snack' THEN 2
                    WHEN 'lunch' THEN 3
                    WHEN 'dinner' THEN 4
                END
            """,
            (str(cutoff_date),),
        )
        rows = cursor.fetchall()

    return [_row_to_diet(row) for row in rows]
