"""
Wearable Listener Tools.

Provides tools for the WearableListenerAgent to check and process
real-time health data from wearable devices.
"""

from typing import Any, Dict
from .lifecycle import (
    get_pending_events,
    get_wearable_listener_status,
    get_automation_status as _get_automation_status,
)


def check_pending_events(agent_context=None) -> Dict[str, Any]:
    """
    Check for pending wearable health data events.

    Returns a list of events that need to be processed.
    Each event should be handled by requesting the appropriate agent
    (e.g., FitnessAgent) to update the database or send notifications.

    Returns:
        Dict containing:
        - events: List of pending event objects
        - count: Number of pending events
        - status: Current listener status
        - events_by_type: Breakdown of events by data type
    """
    events = get_pending_events()
    status = get_wearable_listener_status()

    # Categorize pending events by type
    events_summary = {}
    for event in events:
        data_type = event.get("data_type", "unknown")
        if data_type not in events_summary:
            events_summary[data_type] = []
        events_summary[data_type].append(event)

    return {
        "events": events,
        "count": len(events),
        "events_by_type": {k: len(v) for k, v in events_summary.items()},
        "events_detail": events_summary,
        "listener_status": status,
        "message": (
            f"Found {len(events)} pending health events to process"
            if events
            else "No pending health events"
        ),
    }


def format_alert_for_notification(
    data_type: str,
    value: float,
    unit: str,
    alert_level: str,
    message: str = "",
    source_device: str = "wearable",
    timestamp: str = "",
) -> str:
    """
    Format a health alert event for user notification.

    Args:
        data_type: Type of health data (heart_rate, steps, sleep, etc.)
        value: The measured value
        unit: Unit of measurement (bpm, steps, hours, etc.)
        alert_level: Alert level (normal, elevated, critical)
        message: Optional additional message
        source_device: Device that captured the data
        timestamp: Time of the reading

    Returns:
        Formatted notification message suitable for display to user
    """
    # Map data types to user-friendly names
    type_names = {
        "heart_rate": "Heart Rate",
        "steps": "Step Count",
        "sleep": "Sleep Duration",
        "workout": "Workout",
        "stress": "Stress Level",
    }

    friendly_type = type_names.get(data_type, data_type.replace("_", " ").title())

    # Format based on alert level
    if alert_level == "critical":
        emoji = "🚨"
        prefix = "CRITICAL HEALTH ALERT"
        urgency = "Immediate attention recommended"
    elif alert_level == "elevated":
        emoji = "⚠️"
        prefix = "Elevated Reading"
        urgency = "Worth monitoring"
    else:
        emoji = "✅"
        prefix = "Health Update"
        urgency = "Normal range"

    # Build the notification
    notification = f"""
{emoji} **{prefix}: {friendly_type}**

**Value:** {value} {unit}
**Status:** {urgency}
**Source:** {source_device}
"""

    if message:
        notification += f"\n**Details:** {message}"

    if timestamp:
        notification += f"\n\n_Recorded: {timestamp}_"

    return notification.strip()


def get_listener_health(agent_context=None) -> Dict[str, Any]:
    """
    Get the health status of the wearable data listener.

    Returns information about the listener's connection status,
    events processed, and any issues detected.

    Returns:
        Dict with health status information including:
        - healthy: Whether the listener is running properly
        - events_processed: Total events processed since startup
        - events_by_type: Breakdown of events by data type
        - last_event: Timestamp of last received event
        - pending_count: Number of events waiting to be processed
    """
    status = get_wearable_listener_status()

    # Determine health status
    healthy = status.get("running", False)
    events_processed = status.get("event_count", 0)
    events_by_type = status.get("events_by_type", {})
    pending = status.get("pending_events", 0)

    # Build health message
    if not healthy:
        health_message = "Wearable listener is not running - no real-time data available"
    elif pending > 10:
        health_message = f"Wearable listener is running but has {pending} unprocessed events"
    else:
        health_message = "Wearable listener is healthy and receiving data"

    return {
        "healthy": healthy,
        "events_processed": events_processed,
        "events_by_type": events_by_type,
        "last_event": status.get("last_event_time"),
        "pending_count": pending,
        "message": health_message,
    }


def format_fitness_update_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a wearable event as a fitness database update request.

    This creates the data needed to update the fitness database
    via the FitnessAgent.

    Args:
        event: The wearable health data event

    Returns:
        Dict with update parameters for FitnessAgent
    """
    data_type = event.get("data_type", "unknown")
    value = event.get("value")
    timestamp = event.get("timestamp")
    source = event.get("source_device", "wearable")

    # Map wearable events to fitness database columns
    column_mapping = {
        "heart_rate": "avg_heart_rate",
        "steps": "steps",
        "sleep": "sleep_hours",
        "workout": "workout_type",
        "stress": None,  # Not directly mapped to fitness table
    }

    target_column = column_mapping.get(data_type)

    return {
        "data_type": data_type,
        "value": value,
        "target_column": target_column,
        "timestamp": timestamp,
        "source_device": source,
        "event_id": event.get("event_id"),
        "can_update_fitness_db": target_column is not None,
        "message": (
            f"Update {target_column} to {value}"
            if target_column
            else f"Event type {data_type} requires manual handling"
        ),
    }


def categorize_alert_level(data_type: str, value: float) -> str:
    """
    Determine the alert level for a health reading.

    Uses health-based thresholds to categorize readings as
    normal, elevated, or critical.

    Args:
        data_type: Type of health data
        value: The measured value

    Returns:
        Alert level string: "normal", "elevated", or "critical"
    """
    thresholds = {
        "heart_rate": {
            "critical_low": 50,
            "critical_high": 150,
            "elevated_low": 55,
            "elevated_high": 100,
        },
        "steps": {
            # Steps don't have critical values, just milestones
            "critical_low": None,
            "critical_high": None,
            "elevated_low": None,
            "elevated_high": None,
        },
        "sleep": {
            "critical_low": 3,  # Less than 3 hours is critical
            "critical_high": None,
            "elevated_low": 5,  # Less than 5 hours is concerning
            "elevated_high": None,
        },
        "stress": {
            "critical_low": None,
            "critical_high": 90,  # Stress level 90+ is critical
            "elevated_low": None,
            "elevated_high": 70,  # Stress level 70+ is elevated
        },
    }

    if data_type not in thresholds:
        return "normal"

    t = thresholds[data_type]

    # Check critical thresholds
    if t.get("critical_low") and value < t["critical_low"]:
        return "critical"
    if t.get("critical_high") and value > t["critical_high"]:
        return "critical"

    # Check elevated thresholds
    if t.get("elevated_low") and value < t["elevated_low"]:
        return "elevated"
    if t.get("elevated_high") and value > t["elevated_high"]:
        return "elevated"

    return "normal"


def get_automation_status(agent_context=None) -> Dict[str, Any]:
    """
    Get the status of the wearable automation features.

    Returns comprehensive information about:
    - Anomaly detection: Current baselines per data type, recent anomalies
    - Goal tracking: Today's progress toward daily health goals
    - Wearable listener: Connection and event processing status

    This is useful for:
    - Understanding what the system considers "normal" for each metric
    - Checking progress toward daily goals (steps, active minutes, sleep)
    - Diagnosing issues with the automation pipeline

    Returns:
        Dict with automation status including:
        - wearable_listener: Connection and event processing status
        - anomaly_detector: Baselines and detection history
        - goal_tracker: Today's goal progress and achievements
    """
    return _get_automation_status()
