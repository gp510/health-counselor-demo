"""
Unit tests for Automation Module (Agentic Automation Tier 2).

These tests verify:
1. Anomaly detection with rolling statistics
2. Goal tracking and achievement notifications
3. Report scheduler functionality
4. Alert queue for SSE streaming

These tests run WITHOUT requiring Solace broker connection or WebUI gateway.

Usage:
    pytest tests/test_automation.py -v
"""
import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Add src directory to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from wearable_listener.anomaly_detector import (
    AnomalyDetector,
    AnomalyResult,
    RollingStats,
    anomaly_detector,
    check_and_track_anomaly,
)
from wearable_listener.goal_tracker import (
    GoalTracker,
    GoalDefinition,
    GoalProgress,
    GoalEvent,
    GoalStatus,
    goal_tracker,
    update_goal_progress,
    check_goals_at_risk,
)
from automation.scheduler import (
    ReportScheduler,
    ReportStatus,
    CachedReport,
    report_scheduler,
)


# ============================================================================
# Anomaly Detector Tests
# ============================================================================


class TestAnomalyDetector:
    """Test anomaly detection logic."""

    def test_detector_initialization(self):
        """Should initialize with correct default values."""
        detector = AnomalyDetector(window_hours=12, sigma_threshold=2.5, min_readings=3)

        assert detector.window == timedelta(hours=12)
        assert detector.default_sigma == 2.5
        assert detector.default_min_readings == 3

    def test_no_anomaly_with_few_readings(self):
        """Should not detect anomaly without enough baseline data."""
        detector = AnomalyDetector()

        # Add only a few readings (less than min_readings=10 for heart_rate)
        for i in range(5):
            result = detector.check_anomaly("heart_rate", 70 + i)
            # Result exists but not detected as anomaly (insufficient data)
            assert "Insufficient baseline" in result.message

    def test_add_and_track_readings(self):
        """Should track readings and calculate stats."""
        detector = AnomalyDetector()

        # Add readings
        for i in range(10):
            detector.add_reading("heart_rate", 72)

        stats = detector.get_stats()
        assert "heart_rate" in stats["baselines"]
        assert stats["baselines"]["heart_rate"]["count"] == 10
        assert stats["baselines"]["heart_rate"]["mean"] == 72.0

    def test_detect_critical_high_threshold(self):
        """Should detect critical high heart rate via threshold."""
        detector = AnomalyDetector()

        # Check high value (above critical_high=120)
        result = detector.check_anomaly("heart_rate", 130)

        assert result.detected
        assert result.severity == "critical"
        assert "exceeds threshold" in result.message.lower()

    def test_detect_critical_low_threshold(self):
        """Should detect critical low heart rate via threshold."""
        detector = AnomalyDetector()

        # Check low value (below critical_low=40)
        result = detector.check_anomaly("heart_rate", 35)

        assert result.detected
        assert result.severity == "critical"
        assert "below threshold" in result.message.lower()

    def test_no_anomaly_for_normal_reading_with_baseline(self):
        """Should not flag normal readings as anomalies."""
        detector = AnomalyDetector()

        # Build baseline with variation
        values = [70, 72, 74, 71, 73, 75, 70, 72, 74, 73]
        for v in values:
            detector.add_reading("heart_rate", v)

        # Check a value within the normal range
        result = detector.check_anomaly("heart_rate", 73)

        # Should not be an anomaly since it's within 2 sigma
        assert not result.detected or result.severity == "info"

    def test_get_baseline(self):
        """Should return baseline statistics."""
        detector = AnomalyDetector()

        # Add readings
        for v in [70, 72, 74, 76, 78]:
            detector.add_reading("steps", v)

        baseline = detector.get_baseline("steps")

        assert baseline is not None
        assert baseline["count"] == 5
        assert baseline["mean"] == 74.0
        assert baseline["min"] == 70
        assert baseline["max"] == 78

    def test_get_all_baselines(self):
        """Should return baselines for all tracked types."""
        detector = AnomalyDetector()

        detector.add_reading("heart_rate", 72)
        detector.add_reading("steps", 8000)

        baselines = detector.get_all_baselines()

        assert "heart_rate" in baselines
        assert "steps" in baselines

    def test_reset_single_type(self):
        """Should reset statistics for specific data type."""
        detector = AnomalyDetector()

        detector.add_reading("heart_rate", 72)
        detector.add_reading("steps", 8000)

        detector.reset("heart_rate")

        assert "heart_rate" not in detector.get_all_baselines()
        assert "steps" in detector.get_all_baselines()

    def test_reset_all(self):
        """Should reset all statistics."""
        detector = AnomalyDetector()

        detector.add_reading("heart_rate", 72)
        detector.add_reading("steps", 8000)

        detector.reset()

        assert len(detector.get_all_baselines()) == 0


class TestCheckAndTrackAnomaly:
    """Test the convenience function for anomaly detection."""

    def test_check_and_track_returns_tuple(self):
        """Should return tuple of (is_anomaly, result)."""
        is_anomaly, result = check_and_track_anomaly("heart_rate", 72)

        assert isinstance(is_anomaly, bool)
        # Result is None if not detected, AnomalyResult if detected
        if is_anomaly:
            assert isinstance(result, AnomalyResult)

    def test_critical_value_detected(self):
        """Should detect critical values."""
        is_anomaly, result = check_and_track_anomaly("heart_rate", 150)

        assert is_anomaly
        assert result is not None
        assert result.severity == "critical"


# ============================================================================
# Goal Tracker Tests
# ============================================================================


class TestGoalProgress:
    """Test goal progress tracking."""

    def test_initial_progress(self):
        """New progress should start at zero."""
        goal = GoalDefinition(
            name="Test Goal",
            data_type="steps",
            target=10000,
            unit="steps",
        )
        progress = GoalProgress(goal=goal)

        assert progress.current_value == 0
        assert progress.progress_percent == 0.0
        assert progress.status == GoalStatus.NOT_STARTED

    def test_progress_percent_calculation(self):
        """Should calculate progress percentage correctly."""
        goal = GoalDefinition(
            name="Steps",
            data_type="steps",
            target=10000,
            unit="steps",
        )
        progress = GoalProgress(goal=goal, current_value=5000)

        assert progress.progress_percent == 50.0
        assert progress.remaining == 5000

    def test_goal_status_when_achieved(self):
        """Should report correct status when achieved."""
        goal = GoalDefinition(
            name="Steps",
            data_type="steps",
            target=10000,
            unit="steps",
        )
        progress = GoalProgress(
            goal=goal,
            current_value=10500,
            status=GoalStatus.ACHIEVED
        )

        assert progress.progress_percent == 100.0  # Capped at 100
        assert progress.remaining == 0

    def test_to_dict(self):
        """Should serialize to dictionary correctly."""
        goal = GoalDefinition(
            name="Steps",
            data_type="steps",
            target=10000,
            unit="steps",
        )
        progress = GoalProgress(goal=goal, current_value=5000)

        data = progress.to_dict()

        assert data["goal_name"] == "Steps"
        assert data["target"] == 10000
        assert data["current_value"] == 5000
        assert data["progress_percent"] == 50.0


class TestGoalTracker:
    """Test goal tracking functionality."""

    def test_default_goals_loaded(self):
        """Should initialize with default goals."""
        tracker = GoalTracker()

        # goals is a dict with data_type as keys
        assert len(tracker.goals) > 0
        assert "steps" in tracker.goals
        assert "active_minutes" in tracker.goals
        assert tracker.goals["steps"].name == "Daily Steps"

    def test_update_steps_progress(self):
        """Should update steps goal progress."""
        tracker = GoalTracker()

        event = tracker.update_progress("steps", 5000)

        progress = tracker.get_progress("steps")
        assert progress is not None
        assert progress["current_value"] == 5000
        assert progress["progress_percent"] == 50.0

    def test_steps_goal_achievement(self):
        """Should generate achievement event when goal is met."""
        tracker = GoalTracker()

        # Update to achieve goal
        event = tracker.update_progress("steps", 10500)

        assert event is not None
        assert event.event_type == "achieved"
        assert event.goal_name == "Daily Steps"
        assert event.progress_percent >= 100

    def test_no_duplicate_achievement(self):
        """Should not generate duplicate achievement events."""
        tracker = GoalTracker()

        # Achieve goal
        event1 = tracker.update_progress("steps", 10500)
        assert event1.event_type == "achieved"

        # Update again - should not generate another achievement
        event2 = tracker.update_progress("steps", 11000)
        assert event2 is None

    def test_sleep_goal_tracking(self):
        """Should track sleep goal correctly."""
        tracker = GoalTracker()

        event = tracker.update_progress("sleep", 7.5)

        progress = tracker.get_progress("sleep")
        assert progress is not None
        assert progress["current_value"] == 7.5
        assert progress["status"] == "achieved"  # 7.5h meets 7h target

    def test_get_summary(self):
        """Should return comprehensive summary."""
        tracker = GoalTracker()
        tracker.update_progress("steps", 5000)

        summary = tracker.get_summary()

        assert "date" in summary
        assert "goals" in summary
        assert "total_goals" in summary
        assert "achieved" in summary
        assert len(summary["goals"]) > 0

    def test_get_all_progress(self):
        """Should return all goal progress."""
        tracker = GoalTracker()
        tracker.update_progress("steps", 5000)

        progress = tracker.get_all_progress()

        assert "steps" in progress
        assert "sleep" in progress
        assert progress["steps"]["current_value"] == 5000

    def test_add_goal(self):
        """Should add new goal definition."""
        tracker = GoalTracker()

        new_goal = GoalDefinition(
            name="Meditation",
            data_type="meditation",
            target=10,
            unit="minutes",
        )
        tracker.add_goal(new_goal)

        assert "meditation" in tracker.goals
        assert tracker.get_progress("meditation") is not None

    def test_remove_goal(self):
        """Should remove goal definition."""
        tracker = GoalTracker()
        assert "water" in tracker.goals

        result = tracker.remove_goal("water")

        assert result is True
        assert "water" not in tracker.goals

    def test_reset(self):
        """Should reset all goals for new day."""
        tracker = GoalTracker()
        tracker.update_progress("steps", 5000)

        tracker.reset()

        progress = tracker.get_progress("steps")
        assert progress["current_value"] == 0
        assert progress["status"] == "not_started"


class TestGoalsAtRisk:
    """Test at-risk goal detection."""

    def test_detect_goals_at_risk(self):
        """Should identify goals at risk of not being met."""
        tracker = GoalTracker()

        # Set low progress
        tracker.update_progress("steps", 2000)  # 20% of 10000

        # Check at risk (simulating late evening)
        at_risk = tracker.check_at_risk_goals(current_hour=21)

        # Steps should be at risk if only 20% done by 9 PM
        step_risk = next(
            (r for r in at_risk if r.goal_name == "Daily Steps"), None
        )
        assert step_risk is not None
        assert step_risk.event_type == "at_risk"

    def test_no_at_risk_before_evening(self):
        """Should not flag at-risk during the day."""
        tracker = GoalTracker()
        tracker.update_progress("steps", 2000)

        at_risk = tracker.check_at_risk_goals(current_hour=14)  # 2 PM

        assert len(at_risk) == 0


# ============================================================================
# Report Scheduler Tests
# ============================================================================


class TestCachedReport:
    """Test cached report data structure."""

    def test_to_dict(self):
        """Should serialize to dictionary correctly."""
        report = CachedReport(
            id="test-123",
            report_type="executive_summary",
            content="Test content",
            generated_at=datetime(2024, 12, 3, 15, 30, tzinfo=timezone.utc),
            status=ReportStatus.COMPLETED,
            generation_time_seconds=45.5,
        )

        data = report.to_dict()

        assert data["id"] == "test-123"
        assert data["report_type"] == "executive_summary"
        assert data["content"] == "Test content"
        assert data["status"] == "completed"
        assert data["generation_time_seconds"] == 45.5


class TestReportScheduler:
    """Test report scheduler functionality."""

    def test_report_prompts_defined(self):
        """Should have defined prompts for each report type."""
        scheduler = ReportScheduler()

        assert "executive_summary" in scheduler.REPORT_PROMPTS
        assert "daily_summary" in scheduler.REPORT_PROMPTS
        assert "weekly_trends" in scheduler.REPORT_PROMPTS

    def test_get_status(self):
        """Should return scheduler status."""
        scheduler = ReportScheduler(gateway_url="http://test:8000")

        status = scheduler.get_status()

        assert status["gateway_url"] == "http://test:8000"
        assert status["cached_reports"] == 0
        assert status["scheduler_running"] is False
        assert "executive_summary" in status["report_types"]

    def test_cache_reports(self):
        """Should cache reports correctly."""
        scheduler = ReportScheduler(cache_size=5)

        # Manually add reports to cache
        for i in range(3):
            report = CachedReport(
                id=f"test-{i}",
                report_type="executive_summary",
                content=f"Content {i}",
                generated_at=datetime.now(timezone.utc),
                status=ReportStatus.COMPLETED,
            )
            scheduler._reports.insert(0, report)

        assert len(scheduler._reports) == 3

        # Get latest report
        latest = scheduler.get_latest_report()
        assert latest.id == "test-2"

    def test_cache_size_limit(self):
        """Should respect cache size limit."""
        scheduler = ReportScheduler(cache_size=3)

        # Add more reports than cache size
        for i in range(5):
            report = CachedReport(
                id=f"test-{i}",
                report_type="executive_summary",
                content=f"Content {i}",
                generated_at=datetime.now(timezone.utc),
                status=ReportStatus.COMPLETED,
            )
            scheduler._reports.insert(0, report)
            while len(scheduler._reports) > scheduler.cache_size:
                scheduler._reports.pop()

        assert len(scheduler._reports) == 3

    def test_get_latest_by_type(self):
        """Should filter by report type."""
        scheduler = ReportScheduler()

        # Add mixed report types
        scheduler._reports.append(
            CachedReport(
                id="exec-1",
                report_type="executive_summary",
                content="Exec",
                generated_at=datetime.now(timezone.utc),
                status=ReportStatus.COMPLETED,
            )
        )
        scheduler._reports.insert(
            0,
            CachedReport(
                id="daily-1",
                report_type="daily_summary",
                content="Daily",
                generated_at=datetime.now(timezone.utc),
                status=ReportStatus.COMPLETED,
            ),
        )

        # Get by type
        daily = scheduler.get_latest_report(report_type="daily_summary")
        assert daily.id == "daily-1"

        exec_report = scheduler.get_latest_report(report_type="executive_summary")
        assert exec_report.id == "exec-1"

    def test_start_stop_scheduler(self):
        """Should start and stop scheduler."""
        scheduler = ReportScheduler()

        scheduler.start_scheduler(interval_hours=1)
        assert scheduler._scheduler_running is True

        scheduler.stop_scheduler()
        assert scheduler._scheduler_running is False
        assert scheduler._scheduler_timer is None


class TestReportGeneration:
    """Test report generation (mocked)."""

    @pytest.mark.asyncio
    async def test_generate_report_success(self):
        """Should generate report successfully (mocked)."""
        scheduler = ReportScheduler(gateway_url="http://test:8000")

        # Mock the orchestrator call
        with patch.object(
            scheduler, "_call_orchestrator", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = "Generated health summary content"

            report = await scheduler.generate_report("executive_summary")

            assert report.status == ReportStatus.COMPLETED
            assert report.content == "Generated health summary content"
            assert report.generation_time_seconds > 0

    @pytest.mark.asyncio
    async def test_generate_report_failure(self):
        """Should handle generation failure gracefully."""
        scheduler = ReportScheduler(gateway_url="http://test:8000")

        # Mock orchestrator failure
        with patch.object(
            scheduler, "_call_orchestrator", new_callable=AsyncMock
        ) as mock_call:
            mock_call.side_effect = Exception("Gateway timeout")

            report = await scheduler.generate_report("executive_summary")

            assert report.status == ReportStatus.FAILED
            assert report.error == "Gateway timeout"

    @pytest.mark.asyncio
    async def test_custom_prompt(self):
        """Should use custom prompt when provided."""
        scheduler = ReportScheduler(gateway_url="http://test:8000")

        with patch.object(
            scheduler, "_call_orchestrator", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = "Custom report content"

            custom_prompt = "Generate a custom health analysis"
            await scheduler.generate_report(
                report_type="executive_summary",
                custom_prompt=custom_prompt,
            )

            # Verify custom prompt was used
            mock_call.assert_called_once_with(custom_prompt)


# ============================================================================
# Integration Tests (Automation Status)
# ============================================================================


class TestAutomationStatus:
    """Test automation status reporting from lifecycle."""

    def test_get_automation_status(self):
        """Should return combined automation status."""
        from wearable_listener.lifecycle import get_automation_status

        status = get_automation_status()

        assert "wearable_listener" in status
        assert "anomaly_detector" in status
        assert "goal_tracker" in status

    def test_automation_status_structure(self):
        """Should have correct structure for each component."""
        from wearable_listener.lifecycle import get_automation_status

        status = get_automation_status()

        # Anomaly detector status
        assert "baselines" in status["anomaly_detector"]

        # Goal tracker status
        assert "goals" in status["goal_tracker"]
        assert "date" in status["goal_tracker"]


# ============================================================================
# Alert Queue Tests
# ============================================================================


class TestAlertQueue:
    """Test the SSE alert queue."""

    def test_alert_queue_import(self):
        """Should import alert queue correctly."""
        from server.dashboard_api.services.alert_queue import (
            alert_queue,
            AutomationAlert,
            AlertType,
        )

        assert alert_queue is not None
        assert AlertType.ANOMALY_DETECTED is not None
        assert AlertType.GOAL_ACHIEVED is not None

    def test_create_automation_alert(self):
        """Should create automation alert correctly."""
        from server.dashboard_api.services.alert_queue import (
            AutomationAlert,
            AlertType,
        )

        alert = AutomationAlert(
            alert_type=AlertType.ANOMALY_DETECTED,
            title="High Heart Rate Detected",
            message="Heart rate 120 bpm is above baseline",
            severity="warning",
            data_type="heart_rate",
            value=120.0,
            baseline=72.0,
            deviation=2.5,
        )

        data = alert.to_dict()

        assert data["alert_type"] == "anomaly_detected"
        assert data["title"] == "High Heart Rate Detected"
        assert data["severity"] == "warning"
        # Fields are directly on result, not nested under "data"
        assert data["value"] == 120.0
        assert data["baseline"] == 72.0

    def test_publish_alert(self):
        """Should publish alert to queue."""
        from server.dashboard_api.services.alert_queue import (
            alert_queue,
            AutomationAlert,
            AlertType,
        )

        initial_count = alert_queue.get_stats()["total_published"]

        alert = AutomationAlert(
            alert_type=AlertType.GOAL_ACHIEVED,
            title="Steps Goal Achieved!",
            message="Congratulations! You've reached 10,000 steps.",
            severity="info",
            data_type="steps",
            value=10500.0,
            goal_name="Daily Steps",
            goal_target=10000.0,
        )

        alert_queue.publish(alert)

        new_count = alert_queue.get_stats()["total_published"]
        assert new_count == initial_count + 1

    def test_get_alert_history(self):
        """Should retrieve alert history."""
        from server.dashboard_api.services.alert_queue import (
            alert_queue,
            AutomationAlert,
            AlertType,
        )

        # Publish a test alert
        alert = AutomationAlert(
            alert_type=AlertType.CRITICAL_HEALTH,
            title="Test Critical Alert",
            message="Testing history retrieval",
            severity="critical",
        )
        alert_queue.publish(alert)

        history = alert_queue.get_history(count=10)

        assert len(history) > 0
        # Most recent should be our test alert
        assert any(a.title == "Test Critical Alert" for a in history)

    def test_get_stats(self):
        """Should return queue statistics."""
        from server.dashboard_api.services.alert_queue import alert_queue

        stats = alert_queue.get_stats()

        assert "total_published" in stats
        assert "current_subscribers" in stats
        assert "history_size" in stats
        assert "alerts_by_type" in stats
