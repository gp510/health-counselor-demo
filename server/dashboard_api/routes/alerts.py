"""Health alerts API routes.

Includes both database-driven alerts and real-time automation alerts via SSE.
"""
import json
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from datetime import datetime, timedelta
import uuid

from ..models.alerts import HealthAlert
from ..database import db_manager
from ..services.alert_queue import alert_queue, AutomationAlert, AlertType

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


# ============================================================================
# Real-Time Automation Alerts (SSE)
# ============================================================================


@router.get("/alerts/stream")
async def stream_automation_alerts(
    include_history: bool = Query(True, description="Include recent alerts on connect"),
    history_count: int = Query(10, ge=0, le=50, description="Number of historical alerts")
):
    """
    Stream real-time automation alerts via Server-Sent Events (SSE).

    This endpoint streams alerts generated by the automation system including:
    - Anomaly detection alerts (unusual patterns in health data)
    - Goal achievement notifications
    - Goal reminders/nudges
    - Critical health alerts
    - Report ready notifications
    - Investigation completion summaries

    The stream never closes - clients should handle reconnection.

    Usage with curl:
        curl -N http://localhost:8082/api/health/alerts/stream

    Usage with JavaScript:
        const eventSource = new EventSource('/api/health/alerts/stream');
        eventSource.onmessage = (event) => {
            const alert = JSON.parse(event.data);
            console.log('New alert:', alert);
        };
    """
    async def event_generator():
        async for alert in alert_queue.subscribe(
            include_history=include_history,
            history_count=history_count
        ):
            # Format as SSE event
            data = json.dumps(alert.to_dict())
            yield f"event: alert\ndata: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/alerts/automation/history")
async def get_automation_alert_history(
    count: int = Query(50, ge=1, le=100, description="Number of alerts to return")
):
    """
    Get recent automation alerts from history.

    Returns alerts that were generated by the automation system,
    ordered from newest to oldest.
    """
    alerts = alert_queue.get_history(count)
    return [alert.to_dict() for alert in alerts]


@router.get("/alerts/automation/stats")
async def get_automation_stats():
    """
    Get statistics about the automation alert system.

    Returns counts of alerts by type, current subscribers,
    and other operational metrics.
    """
    return alert_queue.get_stats()


@router.post("/alerts/automation/test")
async def send_test_alert(
    alert_type: AlertType = Query(AlertType.ANOMALY_DETECTED, description="Type of test alert"),
    message: str = Query("This is a test alert", description="Alert message")
):
    """
    Send a test automation alert (for development/testing).

    Publishes a test alert to all connected SSE subscribers.
    """
    alert = AutomationAlert(
        alert_type=alert_type,
        title=f"Test Alert: {alert_type.value.replace('_', ' ').title()}",
        message=message,
        severity="info",
        data_type="test",
        value=42.0,
    )
    alert_queue.publish(alert)
    return {"status": "published", "alert_id": alert.id}
