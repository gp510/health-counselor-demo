"""
Wearable Listener Lifecycle Module.

Manages Solace subscription to wearable health data events and coordinates
responses with other health agents in the mesh.

Includes:
- Anomaly detection with rolling statistics
- Goal tracking with achievement notifications
- Real-time alert publishing to dashboard SSE stream
"""

import os
import copy
import json
import logging
import httpx
import sqlite3
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from solace.messaging.messaging_service import MessagingService
from solace.messaging.resources.topic_subscription import TopicSubscription
from solace.messaging.receiver.message_receiver import MessageHandler, InboundMessage
from solace.messaging.config.transport_security_strategy import TLS

# Import anomaly detection and goal tracking
from .anomaly_detector import anomaly_detector, check_and_track_anomaly
from .goal_tracker import goal_tracker, update_goal_progress, check_goals_at_risk

logger = logging.getLogger(__name__)

# Dashboard API URL for publishing alerts
DASHBOARD_API_URL = os.getenv("DASHBOARD_API_URL", "http://localhost:8082")

# Fitness database path for real-time updates
FITNESS_DB_PATH = os.getenv("FITNESS_AGENT_DB_NAME", "")


def update_fitness_database(data_type: str, value: float, timestamp: str) -> bool:
    """
    Update the fitness database with real-time wearable data.

    Creates or updates today's record with the latest values from the wearable.
    This enables the FitnessAgent to return real-time data when queried.

    Args:
        data_type: Type of data (heart_rate, steps, sleep, etc.)
        value: The measured value
        timestamp: ISO timestamp of the reading

    Returns:
        True if update was successful
    """
    if not FITNESS_DB_PATH or FITNESS_DB_PATH == ":memory:":
        logger.debug("[FITNESS DB] No shared fitness database configured")
        return False

    # Map wearable data types to fitness_data columns
    column_mapping = {
        "heart_rate": "avg_heart_rate",
        "steps": "steps",
        "sleep": "sleep_hours",
        "workout": "workout_type",
    }

    column = column_mapping.get(data_type)
    if not column:
        logger.debug(f"[FITNESS DB] No column mapping for {data_type}")
        return False

    try:
        # Parse date from timestamp
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            today = dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            today = datetime.now().strftime("%Y-%m-%d")

        conn = sqlite3.connect(FITNESS_DB_PATH)
        cursor = conn.cursor()

        # Check if today's record exists
        cursor.execute(
            "SELECT record_id FROM fitness_data WHERE date = ?",
            (today,)
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing record with real-time data
            # For heart rate, update avg_heart_rate (we track most recent)
            # For steps, the value is cumulative so just update
            cursor.execute(
                f"UPDATE fitness_data SET {column} = ? WHERE date = ?",
                (value, today)
            )
            logger.info(f"[FITNESS DB] Updated {column}={value} for {today}")
        else:
            # No record exists for today - skip insertion
            # Wearable data supplements existing daily records, it doesn't create new ones
            # Creating records with zeros causes "all zeros" display issues in the dashboard
            logger.debug(
                f"[FITNESS DB] No record for {today}, skipping {column}={value} "
                "(wearable data supplements existing records only)"
            )
            conn.close()
            return False

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        logger.error(f"[FITNESS DB] Database error: {e}")
        return False
    except Exception as e:
        logger.error(f"[FITNESS DB] Error updating fitness database: {e}")
        return False


class WearableListenerState:
    """Holds the state of the wearable data listener."""

    def __init__(self):
        self.messaging_service: Optional[MessagingService] = None
        self.receiver = None
        self.running = False
        self.event_count = 0
        self.last_event_time: Optional[datetime] = None
        self.agent_context = None
        # Track events by type
        self.events_by_type: Dict[str, int] = {
            "heart_rate": 0,
            "steps": 0,
            "sleep": 0,
            "workout": 0,
            "stress": 0,
        }
        # Track latest reading per data type for real-time queries
        self.latest_readings: Dict[str, Dict[str, Any]] = {}


# Global state for the wearable listener
_state = WearableListenerState()


class WearableDataHandler(MessageHandler):
    """Handles incoming wearable health data messages."""

    def __init__(self, agent_context):
        self.agent_context = agent_context

    def on_message(self, message: InboundMessage):
        """Process incoming wearable data event."""
        global _state

        try:
            payload = message.get_payload_as_string()
            event = json.loads(payload)

            _state.event_count += 1
            _state.last_event_time = datetime.now(timezone.utc)

            # Track by data type
            data_type = event.get("data_type", "unknown")
            if data_type in _state.events_by_type:
                _state.events_by_type[data_type] += 1

            topic = message.get_destination_name()
            logger.info(f"[WEARABLE EVENT] Topic: {topic}")
            logger.debug(f"[WEARABLE PAYLOAD] {json.dumps(event, indent=2)}")

            # Process the event
            process_wearable_data(event, self.agent_context)

        except json.JSONDecodeError as e:
            logger.error(f"[ERROR] Failed to parse wearable event: {e}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to process wearable event: {e}")


def publish_alert_to_dashboard(
    alert_type: str,
    title: str,
    message: str,
    severity: str = "info",
    data_type: Optional[str] = None,
    value: Optional[float] = None,
    baseline: Optional[float] = None,
    deviation: Optional[float] = None,
    goal_name: Optional[str] = None,
    goal_target: Optional[float] = None,
) -> bool:
    """
    Publish an alert to the dashboard API for SSE streaming.

    Args:
        alert_type: Type of alert (anomaly_detected, goal_achieved, etc.)
        title: Alert title
        message: Alert message
        severity: Alert severity (info, warning, critical)
        data_type: Type of health data (optional)
        value: The current value (optional)
        baseline: Baseline value for anomalies (optional)
        deviation: Deviation from baseline (optional)
        goal_name: Name of goal (optional)
        goal_target: Goal target value (optional)

    Returns:
        True if alert was published successfully
    """
    try:
        # Build query params
        params = {
            "alert_type": alert_type,
            "message": message,
        }

        # POST to the test endpoint (we'll enhance this to a proper publish endpoint)
        # For now, the test endpoint works for publishing alerts
        response = httpx.post(
            f"{DASHBOARD_API_URL}/api/health/alerts/automation/test",
            params=params,
            timeout=5.0,
        )

        if response.status_code == 200:
            logger.info(f"[ALERT PUBLISHED] {alert_type}: {title}")
            return True
        else:
            logger.warning(f"[ALERT FAILED] Status {response.status_code}: {response.text}")
            return False

    except httpx.ConnectError:
        logger.debug(f"[ALERT] Dashboard API not available at {DASHBOARD_API_URL}")
        return False
    except Exception as e:
        logger.error(f"[ALERT ERROR] Failed to publish alert: {e}")
        return False


def write_health_notification(event: Dict[str, Any], alert_level: str) -> None:
    """
    Write notification to file for elevated/critical health alerts.

    Creates a visible record of health notifications that can be
    monitored via 'tail -f health_notifications.log' during demos.

    Args:
        event: The wearable health event
        alert_level: The alert level (critical, elevated, normal)
    """
    notification_file = os.getenv("HEALTH_NOTIFICATION_FILE", "health_notifications.log")

    timestamp = event.get("timestamp", datetime.now(timezone.utc).isoformat())
    data_type = event.get("data_type", "Unknown")
    value = event.get("value", "N/A")
    unit = event.get("unit", "")
    message = event.get("message", "No message")
    source = event.get("source_device", "Unknown device")

    notification_line = (
        f"[{timestamp}] [{alert_level.upper()}] "
        f"{data_type}: {value} {unit} ({source}) - {message}\n"
    )

    try:
        with open(notification_file, "a") as f:
            f.write(notification_line)
        logger.info(f"[HEALTH NOTIFICATION] Written to {notification_file}")
    except IOError as e:
        logger.error(f"[NOTIFICATION ERROR] Failed to write to {notification_file}: {e}")


def process_wearable_data(event: Dict[str, Any], agent_context) -> None:
    """
    Process a wearable health data event.

    1. Log the event for monitoring
    2. Check for anomalies using personal baseline
    3. Update goal progress
    4. Store event for agent processing (with anomaly/goal metadata)
    5. If elevated/critical/anomaly, write health notification
    6. Publish alerts to dashboard for SSE streaming

    Data types handled:
    - heart_rate: Heart rate in bpm
    - steps: Step count updates
    - sleep: Sleep session data
    - workout: Workout session events
    - stress: Stress/HRV indicators
    """
    data_type = event.get("data_type", "unknown")
    value = event.get("value", "N/A")
    unit = event.get("unit", "")
    alert_level = event.get("alert_level", "normal")
    message = event.get("message", "")

    logger.info(f"[PROCESSING] {data_type}: {value} {unit} ({alert_level})")

    # Convert value to float for analysis
    try:
        numeric_value = float(value) if value != "N/A" else None
    except (ValueError, TypeError):
        numeric_value = None

    anomaly_result = None
    goal_event = None

    # Run anomaly detection if we have a numeric value
    if numeric_value is not None:
        # Check for anomaly and track in rolling stats
        is_anomaly, anomaly_result = check_and_track_anomaly(
            data_type, numeric_value
        )

        if is_anomaly and anomaly_result:
            logger.info(
                f"[ANOMALY] {anomaly_result.message} "
                f"(baseline: {anomaly_result.baseline_mean:.1f}, "
                f"deviation: {anomaly_result.deviation_sigma:.1f}σ)"
            )

            # Publish anomaly alert to dashboard
            publish_alert_to_dashboard(
                alert_type="anomaly_detected",
                title=f"Anomaly: {data_type.replace('_', ' ').title()}",
                message=anomaly_result.message,
                severity=anomaly_result.severity,
                data_type=data_type,
                value=numeric_value,
                baseline=anomaly_result.baseline_mean,
                deviation=anomaly_result.deviation_sigma,
            )

            # Upgrade alert level if anomaly is significant
            if anomaly_result.severity == "critical" and alert_level == "normal":
                alert_level = "critical"
            elif anomaly_result.severity == "warning" and alert_level == "normal":
                alert_level = "elevated"

        # Update goal progress
        goal_event = update_goal_progress(data_type, numeric_value)

        if goal_event:
            logger.info(f"[GOAL] {goal_event.message}")

            # Publish goal achievement to dashboard
            publish_alert_to_dashboard(
                alert_type="goal_achieved",
                title=f"Goal: {goal_event.goal_name}",
                message=goal_event.message,
                severity="info",
                data_type=data_type,
                value=numeric_value,
                goal_name=goal_event.goal_name,
                goal_target=goal_event.target_value,
            )

        # Update shared fitness database with real-time data
        timestamp = event.get("timestamp", datetime.now(timezone.utc).isoformat())
        update_fitness_database(data_type, numeric_value, timestamp)

    # Enrich event with anomaly/goal metadata before storing
    enriched_event = event.copy()
    if anomaly_result and anomaly_result.detected:
        enriched_event["anomaly"] = {
            "detected": True,
            "baseline_mean": anomaly_result.baseline_mean,
            "baseline_std": anomaly_result.baseline_std,
            "deviation_sigma": anomaly_result.deviation_sigma,
            "severity": anomaly_result.severity,
            "investigation_needed": anomaly_result.severity in ("warning", "critical"),
        }
    if goal_event:
        enriched_event["goal_event"] = {
            "type": goal_event.event_type,
            "goal_name": goal_event.goal_name,
            "progress_percent": goal_event.progress_percent,
        }

    # Store latest reading for real-time queries (always update, don't clear)
    if numeric_value is not None:
        timestamp = event.get("timestamp", datetime.now(timezone.utc).isoformat())
        baseline = anomaly_detector.get_baseline(data_type)
        _state.latest_readings[data_type] = {
            "value": numeric_value,
            "unit": event.get("unit", ""),
            "timestamp": timestamp,
            "alert_level": alert_level,
            "source_device": event.get("source_device", "wearable"),
            "baseline": baseline,
            "anomaly": enriched_event.get("anomaly"),
            "goal_progress": enriched_event.get("goal_event"),
        }

    # Store enriched event for agent processing
    store_pending_event(enriched_event)

    # Handle alerts based on level
    if alert_level == "critical":
        logger.warning(f"[CRITICAL HEALTH ALERT] {data_type}: {value} {unit} - {message}")
        write_health_notification(event, alert_level)
    elif alert_level == "elevated":
        logger.info(f"[ELEVATED READING] {data_type}: {value} {unit} - {message}")
        write_health_notification(event, alert_level)
    else:
        logger.debug(f"[NORMAL] {data_type}: {value} {unit}")


def store_pending_event(event: Dict[str, Any]) -> None:
    """Store event for agent processing."""
    global _state

    # Store in agent context if available
    if _state.agent_context:
        if not hasattr(_state.agent_context, "pending_events"):
            _state.agent_context.pending_events = []
        _state.agent_context.pending_events.append(event)
        logger.debug(
            f"[STORED] Event queued for processing. "
            f"Queue size: {len(_state.agent_context.pending_events)}"
        )


def initialize_wearable_listener(agent_context, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Initialize the wearable data listener.

    Called by SAM agent_init_function to establish Solace subscription
    for real-time wearable health data.

    Args:
        agent_context: The agent context from SAM
        config: Configuration from agent YAML

    Returns:
        Dict with initialization status and metadata
    """
    global _state

    logger.info("[INIT] Initializing Wearable Listener...")

    # Store agent context
    _state.agent_context = agent_context
    agent_context.pending_events = []

    # Get connection config from environment
    broker_url = os.getenv("SOLACE_BROKER_URL", "ws://localhost:8008")
    vpn_name = os.getenv("SOLACE_BROKER_VPN", "default")
    username = os.getenv("SOLACE_BROKER_USERNAME", "default")
    password = os.getenv("SOLACE_BROKER_PASSWORD", "default")

    # Get topic config
    topic_prefix = config.get("topic_prefix", os.getenv("WEARABLE_TOPIC_PREFIX", "health/events"))
    topic_pattern = config.get("topic_pattern", f"{topic_prefix}/wearable/*/update")

    logger.info(f"[INIT] Connecting to: {broker_url}")
    logger.info(f"[INIT] Subscribing to: {topic_pattern}")

    try:
        # Build broker properties
        broker_props = {
            "solace.messaging.transport.host": broker_url,
            "solace.messaging.service.vpn-name": vpn_name,
            "solace.messaging.authentication.scheme.basic.username": username,
            "solace.messaging.authentication.scheme.basic.password": password,
        }

        # Create messaging service builder
        builder = MessagingService.builder().from_properties(broker_props)

        # For Solace Cloud (wss://), configure TLS
        if broker_url.startswith("wss://"):
            tls_strategy = TLS.create().without_certificate_validation()
            builder = builder.with_transport_security_strategy(tls_strategy)
            logger.info("[INIT] TLS enabled (development mode)")

        # Build and connect
        _state.messaging_service = builder.build()
        _state.messaging_service.connect()
        logger.info("[INIT] Connected to Solace broker")

        # Create receiver with topic subscription
        # health/events/wearable/*/update matches health/events/wearable/heart_rate/update
        subscription = TopicSubscription.of(topic_pattern)

        _state.receiver = (
            _state.messaging_service.create_direct_message_receiver_builder()
            .with_subscriptions([subscription])
            .build()
        )

        # Start receiver first, then register handler
        _state.receiver.start()

        # Set message handler
        handler = WearableDataHandler(agent_context)
        _state.receiver.receive_async(handler)
        _state.running = True

        logger.info(f"[INIT] Wearable listener started, subscribed to: {topic_pattern}")

        return {
            "status": "initialized",
            "broker_url": broker_url,
            "topic_pattern": topic_pattern,
            "message": "Wearable listener ready to receive health data events",
        }

    except Exception as e:
        logger.error(f"[INIT ERROR] Failed to initialize wearable listener: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": f"Failed to initialize wearable listener: {e}",
        }


def cleanup_wearable_listener(agent_context) -> None:
    """
    Cleanup the wearable data listener.

    Called by SAM agent_cleanup_function on shutdown.
    """
    global _state

    logger.info("[CLEANUP] Shutting down Wearable Listener...")

    _state.running = False

    try:
        if _state.receiver:
            _state.receiver.terminate()
            logger.info("[CLEANUP] Receiver terminated")

        if _state.messaging_service:
            _state.messaging_service.disconnect()
            logger.info("[CLEANUP] Disconnected from Solace broker")

    except Exception as e:
        logger.error(f"[CLEANUP ERROR] {e}")

    finally:
        _state.receiver = None
        _state.messaging_service = None
        _state.agent_context = None

    logger.info(f"[CLEANUP] Complete. Total events processed: {_state.event_count}")
    logger.info(f"[CLEANUP] Events by type: {json.dumps(_state.events_by_type)}")


def get_wearable_listener_status() -> Dict[str, Any]:
    """Get the current status of the wearable listener."""
    global _state

    return {
        "running": _state.running,
        "event_count": _state.event_count,
        "events_by_type": _state.events_by_type.copy(),
        "last_event_time": (
            _state.last_event_time.isoformat() if _state.last_event_time else None
        ),
        "pending_events": (
            len(_state.agent_context.pending_events)
            if _state.agent_context and hasattr(_state.agent_context, "pending_events")
            else 0
        ),
    }


def get_pending_events() -> list:
    """Get and clear pending events."""
    global _state

    if _state.agent_context and hasattr(_state.agent_context, "pending_events"):
        events = _state.agent_context.pending_events.copy()
        _state.agent_context.pending_events.clear()
        return events

    return []


def get_latest_readings() -> Dict[str, Dict[str, Any]]:
    """
    Get the latest reading for each data type.

    Returns a dictionary mapping data type to the most recent reading.
    Each reading includes:
    - value: The measured value
    - unit: Unit of measurement
    - timestamp: When the reading was taken
    - alert_level: normal, elevated, or critical
    - baseline: Personal baseline stats (mean, std_dev, etc.)
    - anomaly: Anomaly info if detected, otherwise None
    - goal_progress: Goal event info if applicable, otherwise None

    This does NOT clear the pending events queue.
    """
    global _state
    return copy.deepcopy(_state.latest_readings)


def get_anomaly_status() -> Dict[str, Any]:
    """
    Get current anomaly detector status.

    Returns statistics about anomaly detection including baselines
    and recent anomaly history.
    """
    return anomaly_detector.get_stats()


def get_goal_status() -> Dict[str, Any]:
    """
    Get current goal tracking status.

    Returns today's goal progress for all tracked goals.
    """
    return goal_tracker.get_summary()


def get_automation_status() -> Dict[str, Any]:
    """
    Get comprehensive automation status.

    Returns combined status of anomaly detection and goal tracking
    for monitoring and debugging.
    """
    return {
        "wearable_listener": get_wearable_listener_status(),
        "anomaly_detector": get_anomaly_status(),
        "goal_tracker": get_goal_status(),
    }
