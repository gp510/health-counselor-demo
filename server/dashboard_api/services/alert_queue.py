"""Thread-safe in-memory alert queue for real-time notifications.

This module provides a publish-subscribe mechanism for automation alerts
that can be streamed to connected clients via SSE.
"""
import asyncio
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, AsyncIterator, Any


class AlertType(str, Enum):
    """Types of automation alerts."""
    ANOMALY_DETECTED = "anomaly_detected"
    GOAL_ACHIEVED = "goal_achieved"
    GOAL_REMINDER = "goal_reminder"
    CRITICAL_HEALTH = "critical_health"
    REPORT_READY = "report_ready"
    INVESTIGATION_COMPLETE = "investigation_complete"


@dataclass
class AutomationAlert:
    """Real-time automation alert from the wearable listener or scheduler."""

    alert_type: AlertType
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    severity: str = "info"  # info, warning, critical
    domain: str = "automation"

    # Additional context for specific alert types
    data_type: Optional[str] = None  # heart_rate, steps, sleep, etc.
    value: Optional[float] = None
    baseline: Optional[float] = None
    deviation: Optional[float] = None
    goal_name: Optional[str] = None
    goal_target: Optional[float] = None
    investigation_context: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "id": self.id,
            "alert_type": self.alert_type.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
            "domain": self.domain,
        }

        # Add optional fields if present
        if self.data_type:
            result["data_type"] = self.data_type
        if self.value is not None:
            result["value"] = self.value
        if self.baseline is not None:
            result["baseline"] = self.baseline
        if self.deviation is not None:
            result["deviation"] = self.deviation
        if self.goal_name:
            result["goal_name"] = self.goal_name
        if self.goal_target is not None:
            result["goal_target"] = self.goal_target
        if self.investigation_context:
            result["investigation_context"] = self.investigation_context

        return result


class AlertQueue:
    """Thread-safe in-memory queue for real-time automation alerts.

    Supports multiple SSE subscribers and maintains a history buffer
    for new connections to catch up on recent alerts.
    """

    def __init__(self, max_history: int = 100):
        """Initialize the alert queue.

        Args:
            max_history: Maximum number of alerts to keep in history buffer.
        """
        self._history: deque[AutomationAlert] = deque(maxlen=max_history)
        self._subscribers: list[asyncio.Queue] = []
        self._lock = threading.Lock()
        self._stats = {
            "total_published": 0,
            "total_subscribers": 0,
            "alerts_by_type": {},
        }

    def publish(self, alert: AutomationAlert) -> None:
        """Publish an alert to all subscribers.

        Thread-safe method that can be called from any thread.

        Args:
            alert: The automation alert to publish.
        """
        with self._lock:
            # Add to history
            self._history.append(alert)

            # Update stats
            self._stats["total_published"] += 1
            alert_type = alert.alert_type.value
            self._stats["alerts_by_type"][alert_type] = \
                self._stats["alerts_by_type"].get(alert_type, 0) + 1

            # Notify all subscribers
            dead_subscribers = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(alert)
                except asyncio.QueueFull:
                    dead_subscribers.append(queue)

            # Remove dead subscribers
            for queue in dead_subscribers:
                self._subscribers.remove(queue)

    async def subscribe(
        self,
        include_history: bool = True,
        history_count: int = 10
    ) -> AsyncIterator[AutomationAlert]:
        """Subscribe to real-time alerts via async generator.

        Args:
            include_history: Whether to yield recent alerts first.
            history_count: Number of recent alerts to include from history.

        Yields:
            AutomationAlert objects as they arrive.
        """
        queue: asyncio.Queue[AutomationAlert] = asyncio.Queue(maxsize=100)

        with self._lock:
            self._subscribers.append(queue)
            self._stats["total_subscribers"] += 1

            # Optionally send recent history
            if include_history:
                recent = list(self._history)[-history_count:]
                for alert in recent:
                    queue.put_nowait(alert)

        try:
            while True:
                alert = await queue.get()
                yield alert
        finally:
            with self._lock:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)

    def get_history(self, count: int = 50) -> list[AutomationAlert]:
        """Get recent alerts from history.

        Args:
            count: Maximum number of alerts to return.

        Returns:
            List of recent alerts, newest first.
        """
        with self._lock:
            return list(self._history)[-count:][::-1]

    def get_stats(self) -> dict:
        """Get queue statistics.

        Returns:
            Dictionary with queue statistics.
        """
        with self._lock:
            return {
                **self._stats,
                "current_subscribers": len(self._subscribers),
                "history_size": len(self._history),
            }

    def clear_history(self) -> None:
        """Clear the alert history buffer."""
        with self._lock:
            self._history.clear()


# Global singleton instance
alert_queue = AlertQueue()


# Convenience functions for publishing specific alert types

def publish_anomaly_alert(
    data_type: str,
    value: float,
    baseline: float,
    deviation: float,
    message: str,
    severity: str = "warning"
) -> AutomationAlert:
    """Publish an anomaly detection alert.

    Args:
        data_type: Type of data (heart_rate, steps, etc.)
        value: The anomalous value
        baseline: The expected baseline value
        deviation: Standard deviations from baseline
        message: Human-readable alert message
        severity: Alert severity level

    Returns:
        The published AutomationAlert
    """
    alert = AutomationAlert(
        alert_type=AlertType.ANOMALY_DETECTED,
        title=f"Anomaly Detected: {data_type.replace('_', ' ').title()}",
        message=message,
        severity=severity,
        data_type=data_type,
        value=value,
        baseline=baseline,
        deviation=deviation,
    )
    alert_queue.publish(alert)
    return alert


def publish_goal_achieved(
    goal_name: str,
    value: float,
    target: float,
    message: str
) -> AutomationAlert:
    """Publish a goal achievement alert.

    Args:
        goal_name: Name of the achieved goal
        value: The achieved value
        target: The target value
        message: Celebratory message

    Returns:
        The published AutomationAlert
    """
    alert = AutomationAlert(
        alert_type=AlertType.GOAL_ACHIEVED,
        title=f"Goal Achieved: {goal_name}!",
        message=message,
        severity="info",
        goal_name=goal_name,
        value=value,
        goal_target=target,
    )
    alert_queue.publish(alert)
    return alert


def publish_goal_reminder(
    goal_name: str,
    current: float,
    target: float,
    message: str
) -> AutomationAlert:
    """Publish a goal reminder/nudge alert.

    Args:
        goal_name: Name of the goal
        current: Current progress value
        target: The target value
        message: Encouraging reminder message

    Returns:
        The published AutomationAlert
    """
    alert = AutomationAlert(
        alert_type=AlertType.GOAL_REMINDER,
        title=f"Goal Reminder: {goal_name}",
        message=message,
        severity="info",
        goal_name=goal_name,
        value=current,
        goal_target=target,
    )
    alert_queue.publish(alert)
    return alert


def publish_critical_health_alert(
    data_type: str,
    value: float,
    message: str,
    investigation_context: Optional[dict] = None
) -> AutomationAlert:
    """Publish a critical health alert.

    Args:
        data_type: Type of data triggering the alert
        value: The concerning value
        message: Urgent alert message
        investigation_context: Results from multi-agent investigation

    Returns:
        The published AutomationAlert
    """
    alert = AutomationAlert(
        alert_type=AlertType.CRITICAL_HEALTH,
        title=f"Critical Health Alert: {data_type.replace('_', ' ').title()}",
        message=message,
        severity="critical",
        data_type=data_type,
        value=value,
        investigation_context=investigation_context,
    )
    alert_queue.publish(alert)
    return alert


def publish_report_ready(
    report_type: str,
    message: str
) -> AutomationAlert:
    """Publish a report ready notification.

    Args:
        report_type: Type of report (e.g., "executive_summary", "weekly")
        message: Description of the ready report

    Returns:
        The published AutomationAlert
    """
    alert = AutomationAlert(
        alert_type=AlertType.REPORT_READY,
        title=f"Report Ready: {report_type.replace('_', ' ').title()}",
        message=message,
        severity="info",
    )
    alert_queue.publish(alert)
    return alert


def publish_investigation_complete(
    trigger: str,
    findings: dict,
    message: str
) -> AutomationAlert:
    """Publish an investigation completion alert.

    Args:
        trigger: What triggered the investigation
        findings: Results from multi-agent investigation
        message: Summary of findings

    Returns:
        The published AutomationAlert
    """
    alert = AutomationAlert(
        alert_type=AlertType.INVESTIGATION_COMPLETE,
        title=f"Investigation Complete: {trigger}",
        message=message,
        severity="info",
        investigation_context=findings,
    )
    alert_queue.publish(alert)
    return alert
