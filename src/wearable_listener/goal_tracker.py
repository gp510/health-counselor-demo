"""
Goal Tracking Module for Health Data.

Tracks daily fitness goals and provides notifications when goals
are achieved or at risk of being missed.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date, time, timezone, timedelta
from typing import Optional, Dict, List
from enum import Enum

logger = logging.getLogger(__name__)


class GoalStatus(str, Enum):
    """Status of a goal."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    AT_RISK = "at_risk"
    ACHIEVED = "achieved"
    MISSED = "missed"


@dataclass
class GoalDefinition:
    """Definition of a health goal."""

    name: str
    data_type: str  # steps, active_minutes, sleep, etc.
    target: float
    unit: str
    is_cumulative: bool = True  # True for steps/minutes, False for sleep
    reminder_threshold: float = 0.5  # Remind at 50% progress if time is running out
    celebration_message: str = "Goal achieved!"


@dataclass
class GoalProgress:
    """Current progress toward a goal."""

    goal: GoalDefinition
    current_value: float = 0.0
    status: GoalStatus = GoalStatus.NOT_STARTED
    achieved_at: Optional[datetime] = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notified_achieved: bool = False
    notified_at_risk: bool = False

    @property
    def progress_percent(self) -> float:
        """Calculate progress as a percentage."""
        if self.goal.target == 0:
            return 100.0
        return min((self.current_value / self.goal.target) * 100, 100.0)

    @property
    def remaining(self) -> float:
        """Calculate remaining amount to reach goal."""
        return max(self.goal.target - self.current_value, 0)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "goal_name": self.goal.name,
            "data_type": self.goal.data_type,
            "target": self.goal.target,
            "unit": self.goal.unit,
            "current_value": self.current_value,
            "progress_percent": self.progress_percent,
            "remaining": self.remaining,
            "status": self.status.value,
            "achieved_at": self.achieved_at.isoformat() if self.achieved_at else None,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class GoalEvent:
    """Event generated when goal status changes."""

    event_type: str  # achieved, at_risk, progress
    goal_name: str
    data_type: str
    current_value: float
    target_value: float
    progress_percent: float
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "goal_name": self.goal_name,
            "data_type": self.data_type,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "progress_percent": self.progress_percent,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


class GoalTracker:
    """
    Tracks daily health goals and generates notifications.

    Maintains current progress toward each goal, detects when goals
    are achieved, and identifies goals at risk of being missed.

    Goals reset daily at midnight (or configurable time).
    """

    # Default goal definitions
    DEFAULT_GOALS = [
        GoalDefinition(
            name="Daily Steps",
            data_type="steps",
            target=10000,
            unit="steps",
            is_cumulative=True,
            reminder_threshold=0.6,
            celebration_message="You hit your step goal! Great job staying active today!",
        ),
        GoalDefinition(
            name="Active Minutes",
            data_type="active_minutes",
            target=30,
            unit="minutes",
            is_cumulative=True,
            reminder_threshold=0.5,
            celebration_message="You've been active for 30+ minutes today!",
        ),
        GoalDefinition(
            name="Sleep Duration",
            data_type="sleep",
            target=7.0,
            unit="hours",
            is_cumulative=False,  # Sleep is a single value per night
            reminder_threshold=0.8,  # Not really used for sleep
            celebration_message="Great sleep! You got the recommended 7+ hours.",
        ),
        GoalDefinition(
            name="Water Intake",
            data_type="water",
            target=8,
            unit="glasses",
            is_cumulative=True,
            reminder_threshold=0.5,
            celebration_message="You've stayed hydrated today!",
        ),
    ]

    def __init__(
        self,
        goals: Optional[List[GoalDefinition]] = None,
        reset_hour: int = 0,  # Midnight
    ):
        """
        Initialize the goal tracker.

        Args:
            goals: List of goal definitions (defaults to DEFAULT_GOALS)
            reset_hour: Hour of day to reset goals (0-23)
        """
        self.goals = {g.data_type: g for g in (goals or self.DEFAULT_GOALS)}
        self.reset_hour = reset_hour

        # Current day's progress
        self._current_date: Optional[date] = None
        self._progress: Dict[str, GoalProgress] = {}

        # Event history
        self._event_history: List[GoalEvent] = []

        # Initialize for today
        self._ensure_current_day()

        logger.info(
            f"[GOALS] Initialized tracker with {len(self.goals)} goals: "
            f"{list(self.goals.keys())}"
        )

    def _ensure_current_day(self) -> bool:
        """
        Ensure we're tracking for the current day.

        Returns:
            True if day changed (goals were reset)
        """
        today = date.today()

        if self._current_date != today:
            # Archive previous day if exists
            if self._current_date:
                self._archive_day()

            # Reset for new day
            self._current_date = today
            self._progress = {
                data_type: GoalProgress(goal=goal)
                for data_type, goal in self.goals.items()
            }
            logger.info(f"[GOALS] Reset goals for {today}")
            return True

        return False

    def _archive_day(self) -> None:
        """Archive the previous day's results."""
        # Check for missed goals
        for data_type, progress in self._progress.items():
            if progress.status != GoalStatus.ACHIEVED:
                progress.status = GoalStatus.MISSED
                logger.info(
                    f"[GOALS] {progress.goal.name} missed: "
                    f"{progress.current_value}/{progress.goal.target}"
                )

    def update_progress(
        self,
        data_type: str,
        value: float,
        is_cumulative_update: bool = True,
        timestamp: Optional[datetime] = None
    ) -> Optional[GoalEvent]:
        """
        Update progress toward a goal.

        Args:
            data_type: Type of data (steps, sleep, etc.)
            value: The new value or increment
            is_cumulative_update: If True, add to current. If False, replace.
            timestamp: When the update occurred

        Returns:
            GoalEvent if goal status changed, None otherwise
        """
        self._ensure_current_day()

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Check if we track this data type
        if data_type not in self.goals:
            logger.debug(f"[GOALS] No goal defined for {data_type}")
            return None

        progress = self._progress[data_type]
        goal = progress.goal

        # Update value
        if goal.is_cumulative and is_cumulative_update:
            progress.current_value = value  # Wearable sends total, not delta
        else:
            progress.current_value = value

        progress.last_updated = timestamp

        # Update status
        old_status = progress.status

        if progress.current_value >= goal.target:
            progress.status = GoalStatus.ACHIEVED
            if not progress.achieved_at:
                progress.achieved_at = timestamp
        elif progress.current_value > 0:
            progress.status = GoalStatus.IN_PROGRESS
        else:
            progress.status = GoalStatus.NOT_STARTED

        # Generate events based on status changes
        event = None

        # Goal achieved!
        if progress.status == GoalStatus.ACHIEVED and not progress.notified_achieved:
            progress.notified_achieved = True
            event = GoalEvent(
                event_type="achieved",
                goal_name=goal.name,
                data_type=data_type,
                current_value=progress.current_value,
                target_value=goal.target,
                progress_percent=progress.progress_percent,
                message=goal.celebration_message,
                timestamp=timestamp,
            )
            self._event_history.append(event)
            logger.info(f"[GOALS] {goal.name} ACHIEVED! {progress.current_value}/{goal.target}")

        # Log progress
        logger.debug(
            f"[GOALS] {goal.name}: {progress.current_value}/{goal.target} "
            f"({progress.progress_percent:.0f}%) - {progress.status.value}"
        )

        return event

    def check_at_risk_goals(self, current_hour: Optional[int] = None) -> List[GoalEvent]:
        """
        Check for goals at risk of being missed.

        This should be called periodically (e.g., evening) to remind
        users about goals they haven't reached yet.

        Args:
            current_hour: Current hour (0-23), defaults to now

        Returns:
            List of GoalEvents for at-risk goals
        """
        self._ensure_current_day()

        if current_hour is None:
            current_hour = datetime.now().hour

        events = []

        # Check for at-risk goals in the evening (after 6 PM)
        if current_hour < 18:
            return events

        hours_remaining = 24 - current_hour

        for data_type, progress in self._progress.items():
            goal = progress.goal

            # Skip already achieved or already notified
            if progress.status == GoalStatus.ACHIEVED:
                continue
            if progress.notified_at_risk:
                continue

            # Check if at risk (less than threshold progress with limited time)
            if progress.progress_percent < (goal.reminder_threshold * 100):
                progress.status = GoalStatus.AT_RISK
                progress.notified_at_risk = True

                remaining = progress.remaining
                message = (
                    f"You're at {progress.progress_percent:.0f}% of your "
                    f"{goal.name} goal. {remaining:.0f} {goal.unit} to go! "
                    f"You have {hours_remaining} hours left today."
                )

                event = GoalEvent(
                    event_type="at_risk",
                    goal_name=goal.name,
                    data_type=data_type,
                    current_value=progress.current_value,
                    target_value=goal.target,
                    progress_percent=progress.progress_percent,
                    message=message,
                )
                events.append(event)
                self._event_history.append(event)

                logger.info(f"[GOALS] {goal.name} AT RISK: {message}")

        return events

    def get_progress(self, data_type: str) -> Optional[Dict]:
        """
        Get current progress for a specific goal.

        Args:
            data_type: The data type to check

        Returns:
            Progress dict or None if not tracked
        """
        self._ensure_current_day()

        progress = self._progress.get(data_type)
        if progress:
            return progress.to_dict()
        return None

    def get_all_progress(self) -> Dict[str, Dict]:
        """Get progress for all goals."""
        self._ensure_current_day()

        return {
            data_type: progress.to_dict()
            for data_type, progress in self._progress.items()
        }

    def get_summary(self) -> Dict:
        """Get a summary of today's goal progress."""
        self._ensure_current_day()

        achieved = sum(
            1 for p in self._progress.values()
            if p.status == GoalStatus.ACHIEVED
        )
        in_progress = sum(
            1 for p in self._progress.values()
            if p.status == GoalStatus.IN_PROGRESS
        )
        at_risk = sum(
            1 for p in self._progress.values()
            if p.status == GoalStatus.AT_RISK
        )

        return {
            "date": self._current_date.isoformat() if self._current_date else None,
            "total_goals": len(self.goals),
            "achieved": achieved,
            "in_progress": in_progress,
            "at_risk": at_risk,
            "not_started": len(self.goals) - achieved - in_progress - at_risk,
            "goals": self.get_all_progress(),
        }

    def get_event_history(self, count: int = 10) -> List[Dict]:
        """Get recent goal events."""
        return [e.to_dict() for e in self._event_history[-count:]]

    def add_goal(self, goal: GoalDefinition) -> None:
        """Add a new goal definition."""
        self.goals[goal.data_type] = goal
        # Initialize progress if for current day
        if self._current_date:
            self._progress[goal.data_type] = GoalProgress(goal=goal)
        logger.info(f"[GOALS] Added goal: {goal.name} ({goal.target} {goal.unit})")

    def remove_goal(self, data_type: str) -> bool:
        """Remove a goal definition."""
        if data_type in self.goals:
            del self.goals[data_type]
            if data_type in self._progress:
                del self._progress[data_type]
            logger.info(f"[GOALS] Removed goal for {data_type}")
            return True
        return False

    def reset(self) -> None:
        """Reset all goals for a new day."""
        self._current_date = None
        self._progress.clear()
        self._ensure_current_day()
        logger.info("[GOALS] Reset all goals")


# Global singleton instance
goal_tracker = GoalTracker()


def update_goal_progress(
    data_type: str,
    value: float,
    timestamp: Optional[datetime] = None
) -> Optional[GoalEvent]:
    """
    Convenience function to update goal progress.

    Args:
        data_type: Type of health data
        value: The current value
        timestamp: When update occurred

    Returns:
        GoalEvent if goal status changed
    """
    return goal_tracker.update_progress(data_type, value, timestamp=timestamp)


def check_goals_at_risk() -> List[GoalEvent]:
    """Convenience function to check for at-risk goals."""
    return goal_tracker.check_at_risk_goals()
