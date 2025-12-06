"""Health alerts API routes."""
from fastapi import APIRouter
from datetime import datetime, timedelta
import uuid

from ..models.alerts import HealthAlert
from ..database import db_manager

router = APIRouter(prefix="/api/health", tags=["Alerts"])


def _get_reference_date(cursor, table: str, date_column: str = "date") -> str | None:
    """Get the most recent date from a table as reference point."""
    cursor.execute(f"SELECT MAX({date_column}) as max_date FROM {table}")
    result = cursor.fetchone()
    return result["max_date"] if result else None


@router.get("/alerts", response_model=list[HealthAlert])
async def get_active_alerts():
    """
    Get active health alerts based on current data.
    Analyzes recent data to identify concerning patterns.
    """
    alerts = []

    # Check biomarker alerts
    with db_manager.get_biomarker_conn() as conn:
        cursor = conn.cursor()
        max_date_str = _get_reference_date(cursor, "biomarker_data", "test_date")

        if max_date_str:
            max_date = datetime.strptime(max_date_str, "%Y-%m-%d").date()
            week_ago = max_date - timedelta(days=7)

            cursor.execute(
                """
                SELECT * FROM biomarker_data
                WHERE status IN ('high', 'low', 'critical')
                AND test_date >= ?
                ORDER BY test_date DESC
                """,
                (str(week_ago),),
            )

            for row in cursor.fetchall():
                level = "critical" if row["status"] == "critical" else "warning"
                alerts.append(
                    HealthAlert(
                        id=f"bio-{row['test_id']}",
                        level=level,
                        title=f"Abnormal {row['biomarker_name']}",
                        message=f"{row['biomarker_name']} is {row['status']}: {row['value']} {row['unit']} (range: {row['reference_range_low']}-{row['reference_range_high']})",
                        domain="biomarkers",
                        timestamp=row["test_date"],
                        data={"test_id": row["test_id"], "value": row["value"]},
                    )
                )

    # Check fitness alerts (low sleep, elevated heart rate)
    with db_manager.get_fitness_conn() as conn:
        cursor = conn.cursor()
        max_date_str = _get_reference_date(cursor, "fitness_data")

        if max_date_str:
            max_date = datetime.strptime(max_date_str, "%Y-%m-%d").date()
            week_ago = max_date - timedelta(days=7)

            # Low sleep alert
            cursor.execute(
                """
                SELECT * FROM fitness_data
                WHERE CAST(sleep_hours AS REAL) < 6
                AND date >= ?
                ORDER BY date DESC
                LIMIT 3
                """,
                (str(week_ago),),
            )
            low_sleep_days = cursor.fetchall()

            if len(low_sleep_days) >= 3:
                alerts.append(
                    HealthAlert(
                        id=f"sleep-{uuid.uuid4().hex[:8]}",
                        level="warning",
                        title="Consistently Low Sleep",
                        message=f"You've had less than 6 hours of sleep on {len(low_sleep_days)} days this week",
                        domain="fitness",
                        timestamp=max_date_str,
                    )
                )

            # Elevated resting heart rate
            cursor.execute(
                """
                SELECT AVG(CAST(resting_heart_rate AS REAL)) as avg_hr
                FROM fitness_data
                WHERE date >= ?
                """,
                (str(week_ago),),
            )
            result = cursor.fetchone()
            avg_hr = result["avg_hr"] if result else None

            if avg_hr and avg_hr > 80:
                alerts.append(
                    HealthAlert(
                        id=f"hr-{uuid.uuid4().hex[:8]}",
                        level="info",
                        title="Elevated Resting Heart Rate",
                        message=f"Your average resting heart rate this week is {avg_hr:.0f} bpm",
                        domain="fitness",
                        timestamp=max_date_str,
                    )
                )

    # Check wellness alerts (high stress)
    with db_manager.get_wellness_conn() as conn:
        cursor = conn.cursor()
        max_date_str = _get_reference_date(cursor, "mental_wellness")

        if max_date_str:
            max_date = datetime.strptime(max_date_str, "%Y-%m-%d").date()
            week_ago = max_date - timedelta(days=7)

            cursor.execute(
                """
                SELECT AVG(CAST(stress_level AS REAL)) as avg_stress,
                       AVG(CAST(mood_score AS REAL)) as avg_mood
                FROM mental_wellness
                WHERE date >= ?
                """,
                (str(week_ago),),
            )
            wellness = cursor.fetchone()

            if wellness["avg_stress"] and wellness["avg_stress"] > 6:
                alerts.append(
                    HealthAlert(
                        id=f"stress-{uuid.uuid4().hex[:8]}",
                        level="warning",
                        title="High Stress Levels",
                        message=f"Your average stress level this week is {wellness['avg_stress']:.1f}/10",
                        domain="wellness",
                        timestamp=max_date_str,
                    )
                )

            if wellness["avg_mood"] and wellness["avg_mood"] < 5:
                alerts.append(
                    HealthAlert(
                        id=f"mood-{uuid.uuid4().hex[:8]}",
                        level="info",
                        title="Low Mood Pattern",
                        message=f"Your average mood this week is {wellness['avg_mood']:.1f}/10",
                        domain="wellness",
                        timestamp=max_date_str,
                    )
                )

    return alerts
