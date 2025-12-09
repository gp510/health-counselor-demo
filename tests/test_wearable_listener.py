"""
Unit tests for Wearable Listener Agent.

These tests verify:
1. Wearable listener tools work correctly
2. Alert level categorization is accurate
3. Notification formatting produces expected output
4. Fitness update requests are properly structured
5. Lifecycle state management functions correctly

These tests run WITHOUT requiring Solace broker connection.
They test the listener's helper functions and state management.

Usage:
    pytest tests/test_wearable_listener.py -v
"""
import os
import sys
import json
import tempfile
import pytest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Add src directory to path for importing listener modules
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from wearable_listener.tools import (
    check_pending_events,
    format_alert_for_notification,
    get_listener_health,
    format_fitness_update_request,
    categorize_alert_level,
    get_current_metrics,
)
from wearable_listener.lifecycle import (
    WearableListenerState,
    process_wearable_data,
    store_pending_event,
    write_health_notification,
    get_wearable_listener_status,
    get_pending_events,
    get_latest_readings,
)


class TestAlertLevelCategorization:
    """Test alert level categorization for health readings."""

    # Heart rate tests
    @pytest.mark.asyncio
    async def test_heart_rate_normal(self):
        """Normal heart rate should return 'normal'."""
        assert await categorize_alert_level("heart_rate", 72) == "normal"
        assert await categorize_alert_level("heart_rate", 80) == "normal"
        assert await categorize_alert_level("heart_rate", 90) == "normal"

    @pytest.mark.asyncio
    async def test_heart_rate_elevated_high(self):
        """Elevated high heart rate should return 'elevated'."""
        assert await categorize_alert_level("heart_rate", 105) == "elevated"
        assert await categorize_alert_level("heart_rate", 120) == "elevated"

    @pytest.mark.asyncio
    async def test_heart_rate_elevated_low(self):
        """Elevated low heart rate should return 'elevated'."""
        assert await categorize_alert_level("heart_rate", 52) == "elevated"

    @pytest.mark.asyncio
    async def test_heart_rate_critical_high(self):
        """Critical high heart rate should return 'critical'."""
        assert await categorize_alert_level("heart_rate", 155) == "critical"
        assert await categorize_alert_level("heart_rate", 180) == "critical"

    @pytest.mark.asyncio
    async def test_heart_rate_critical_low(self):
        """Critical low heart rate should return 'critical'."""
        assert await categorize_alert_level("heart_rate", 45) == "critical"
        assert await categorize_alert_level("heart_rate", 40) == "critical"

    # Sleep tests
    @pytest.mark.asyncio
    async def test_sleep_normal(self):
        """Normal sleep duration should return 'normal'."""
        assert await categorize_alert_level("sleep", 7) == "normal"
        assert await categorize_alert_level("sleep", 8) == "normal"

    @pytest.mark.asyncio
    async def test_sleep_elevated(self):
        """Short sleep should return 'elevated'."""
        assert await categorize_alert_level("sleep", 4) == "elevated"
        assert await categorize_alert_level("sleep", 4.5) == "elevated"

    @pytest.mark.asyncio
    async def test_sleep_critical(self):
        """Very short sleep should return 'critical'."""
        assert await categorize_alert_level("sleep", 2.5) == "critical"
        assert await categorize_alert_level("sleep", 2) == "critical"

    # Stress tests
    @pytest.mark.asyncio
    async def test_stress_normal(self):
        """Normal stress should return 'normal'."""
        assert await categorize_alert_level("stress", 30) == "normal"
        assert await categorize_alert_level("stress", 50) == "normal"

    @pytest.mark.asyncio
    async def test_stress_elevated(self):
        """Elevated stress should return 'elevated'."""
        assert await categorize_alert_level("stress", 75) == "elevated"
        assert await categorize_alert_level("stress", 85) == "elevated"

    @pytest.mark.asyncio
    async def test_stress_critical(self):
        """Critical stress should return 'critical'."""
        assert await categorize_alert_level("stress", 92) == "critical"
        assert await categorize_alert_level("stress", 100) == "critical"

    # Steps tests (no critical/elevated thresholds)
    @pytest.mark.asyncio
    async def test_steps_always_normal(self):
        """Steps should always return 'normal' (no critical thresholds)."""
        assert await categorize_alert_level("steps", 100) == "normal"
        assert await categorize_alert_level("steps", 10000) == "normal"
        assert await categorize_alert_level("steps", 50000) == "normal"

    # Unknown type test
    @pytest.mark.asyncio
    async def test_unknown_type_returns_normal(self):
        """Unknown data types should return 'normal'."""
        assert await categorize_alert_level("unknown_type", 999) == "normal"


class TestAlertNotificationFormatting:
    """Test alert notification message formatting."""

    @pytest.mark.asyncio
    async def test_format_critical_alert(self):
        """Critical alerts should have urgent formatting."""
        notification = await format_alert_for_notification(
            data_type="heart_rate",
            value=160,
            unit="bpm",
            alert_level="critical",
            message="Dangerously elevated heart rate",
            source_device="Apple Watch"
        )

        assert "CRITICAL" in notification
        assert "160" in notification
        assert "bpm" in notification
        assert "Apple Watch" in notification
        assert "🚨" in notification

    @pytest.mark.asyncio
    async def test_format_elevated_alert(self):
        """Elevated alerts should have warning formatting."""
        notification = await format_alert_for_notification(
            data_type="stress",
            value=75,
            unit="level",
            alert_level="elevated",
            source_device="Fitbit"
        )

        assert "Elevated" in notification
        assert "75" in notification
        assert "⚠️" in notification

    @pytest.mark.asyncio
    async def test_format_normal_alert(self):
        """Normal readings should have positive formatting."""
        notification = await format_alert_for_notification(
            data_type="heart_rate",
            value=72,
            unit="bpm",
            alert_level="normal"
        )

        assert "Health Update" in notification or "Normal" in notification.title()
        assert "72" in notification
        assert "✅" in notification

    @pytest.mark.asyncio
    async def test_format_with_timestamp(self):
        """Notification should include timestamp if provided."""
        timestamp = "2024-12-03T15:30:00Z"
        notification = await format_alert_for_notification(
            data_type="heart_rate",
            value=72,
            unit="bpm",
            alert_level="normal",
            timestamp=timestamp
        )

        assert timestamp in notification or "Recorded" in notification

    @pytest.mark.asyncio
    async def test_format_with_message(self):
        """Notification should include details message if provided."""
        message = "Heart rate elevated during rest period"
        notification = await format_alert_for_notification(
            data_type="heart_rate",
            value=105,
            unit="bpm",
            alert_level="elevated",
            message=message
        )

        assert message in notification

    @pytest.mark.asyncio
    async def test_data_type_friendly_names(self):
        """Data types should be converted to friendly names."""
        notification = await format_alert_for_notification(
            data_type="heart_rate",
            value=72,
            unit="bpm",
            alert_level="normal"
        )
        assert "Heart Rate" in notification

        notification = await format_alert_for_notification(
            data_type="sleep",
            value=7.5,
            unit="hours",
            alert_level="normal"
        )
        assert "Sleep" in notification


class TestFitnessUpdateRequest:
    """Test fitness database update request formatting."""

    @pytest.mark.asyncio
    async def test_heart_rate_update_request(self):
        """Heart rate should map to avg_heart_rate column."""
        event = {
            "event_id": "WRB-12345678",
            "data_type": "heart_rate",
            "value": 72,
            "timestamp": "2024-12-03T15:30:00Z",
            "source_device": "Apple Watch"
        }

        result = await format_fitness_update_request(event)

        assert result["data_type"] == "heart_rate"
        assert result["value"] == 72
        assert result["target_column"] == "avg_heart_rate"
        assert result["can_update_fitness_db"] is True

    @pytest.mark.asyncio
    async def test_steps_update_request(self):
        """Steps should map to steps column."""
        event = {
            "data_type": "steps",
            "value": 8500,
            "timestamp": "2024-12-03T15:30:00Z"
        }

        result = await format_fitness_update_request(event)

        assert result["target_column"] == "steps"
        assert result["can_update_fitness_db"] is True

    @pytest.mark.asyncio
    async def test_sleep_update_request(self):
        """Sleep should map to sleep_hours column."""
        event = {
            "data_type": "sleep",
            "value": 7.5,
            "timestamp": "2024-12-03T15:30:00Z"
        }

        result = await format_fitness_update_request(event)

        assert result["target_column"] == "sleep_hours"
        assert result["can_update_fitness_db"] is True

    @pytest.mark.asyncio
    async def test_stress_no_direct_mapping(self):
        """Stress has no direct fitness DB mapping."""
        event = {
            "data_type": "stress",
            "value": 45,
            "timestamp": "2024-12-03T15:30:00Z"
        }

        result = await format_fitness_update_request(event)

        assert result["target_column"] is None
        assert result["can_update_fitness_db"] is False
        assert "manual handling" in result["message"]

    @pytest.mark.asyncio
    async def test_update_request_includes_event_id(self):
        """Update request should include original event ID."""
        event = {
            "event_id": "WRB-ABCD1234",
            "data_type": "heart_rate",
            "value": 72
        }

        result = await format_fitness_update_request(event)

        assert result["event_id"] == "WRB-ABCD1234"


class TestWearableListenerState:
    """Test wearable listener state management."""

    def test_initial_state(self):
        """New state should have correct initial values."""
        state = WearableListenerState()

        assert state.running is False
        assert state.event_count == 0
        assert state.last_event_time is None
        assert state.messaging_service is None
        assert state.receiver is None

    def test_events_by_type_initialized(self):
        """Events by type should be initialized with all types."""
        state = WearableListenerState()

        expected_types = {"heart_rate", "steps", "sleep", "workout", "stress"}
        assert set(state.events_by_type.keys()) == expected_types
        assert all(count == 0 for count in state.events_by_type.values())


class TestHealthNotificationWriting:
    """Test health notification file writing."""

    def test_write_notification_to_file(self):
        """Should write formatted notification to file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            notification_file = f.name

        try:
            # Patch environment variable
            with patch.dict(os.environ, {"HEALTH_NOTIFICATION_FILE": notification_file}):
                event = {
                    "timestamp": "2024-12-03T15:30:00Z",
                    "data_type": "heart_rate",
                    "value": 160,
                    "unit": "bpm",
                    "message": "Critical heart rate alert",
                    "source_device": "Apple Watch"
                }

                write_health_notification(event, "critical")

            # Verify file was written
            with open(notification_file, 'r') as f:
                content = f.read()

            assert "CRITICAL" in content
            assert "heart_rate" in content
            assert "160" in content
            assert "bpm" in content

        finally:
            os.unlink(notification_file)

    def test_notification_format(self):
        """Notification should follow expected format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            notification_file = f.name

        try:
            with patch.dict(os.environ, {"HEALTH_NOTIFICATION_FILE": notification_file}):
                event = {
                    "timestamp": "2024-12-03T15:30:00Z",
                    "data_type": "stress",
                    "value": 85,
                    "unit": "level",
                    "message": "High stress detected",
                    "source_device": "Fitbit"
                }

                write_health_notification(event, "elevated")

            with open(notification_file, 'r') as f:
                content = f.read()

            # Should contain timestamp, level, data type, value, unit, source, message
            assert "2024-12-03T15:30:00Z" in content
            assert "ELEVATED" in content
            assert "stress" in content
            assert "85" in content
            assert "level" in content
            assert "Fitbit" in content

        finally:
            os.unlink(notification_file)


class TestPendingEventsManagement:
    """Test pending events queue management."""

    def test_store_pending_event(self):
        """Should store event in agent context."""
        # Create mock agent context
        mock_context = MagicMock()
        mock_context.pending_events = []

        # Patch global state
        with patch('wearable_listener.lifecycle._state') as mock_state:
            mock_state.agent_context = mock_context

            event = {"data_type": "heart_rate", "value": 72}
            store_pending_event(event)

            assert len(mock_context.pending_events) == 1
            assert mock_context.pending_events[0] == event

    def test_get_pending_events_clears_queue(self):
        """Getting pending events should clear the queue."""
        # Create mock agent context with events
        mock_context = MagicMock()
        mock_context.pending_events = [
            {"data_type": "heart_rate", "value": 72},
            {"data_type": "steps", "value": 5000}
        ]

        with patch('wearable_listener.lifecycle._state') as mock_state:
            mock_state.agent_context = mock_context

            events = get_pending_events()

            assert len(events) == 2
            assert len(mock_context.pending_events) == 0  # Queue cleared


class TestListenerHealthStatus:
    """Test listener health status reporting."""

    @pytest.mark.asyncio
    async def test_get_listener_health_when_running(self):
        """Should report healthy when listener is running."""
        with patch('wearable_listener.tools.get_wearable_listener_status') as mock_status:
            mock_status.return_value = {
                "running": True,
                "event_count": 100,
                "events_by_type": {"heart_rate": 50, "steps": 30, "sleep": 20},
                "last_event_time": "2024-12-03T15:30:00Z",
                "pending_events": 2
            }

            health = await get_listener_health()

            assert health["healthy"] is True
            assert health["events_processed"] == 100
            assert "healthy" in health["message"].lower()

    @pytest.mark.asyncio
    async def test_get_listener_health_when_stopped(self):
        """Should report unhealthy when listener is not running."""
        with patch('wearable_listener.tools.get_wearable_listener_status') as mock_status:
            mock_status.return_value = {
                "running": False,
                "event_count": 0,
                "events_by_type": {},
                "last_event_time": None,
                "pending_events": 0
            }

            health = await get_listener_health()

            assert health["healthy"] is False
            assert "not running" in health["message"].lower()

    @pytest.mark.asyncio
    async def test_get_listener_health_with_backlog(self):
        """Should warn when pending events exceed threshold."""
        with patch('wearable_listener.tools.get_wearable_listener_status') as mock_status:
            mock_status.return_value = {
                "running": True,
                "event_count": 100,
                "events_by_type": {},
                "last_event_time": "2024-12-03T15:30:00Z",
                "pending_events": 15  # More than threshold (10)
            }

            health = await get_listener_health()

            assert health["healthy"] is True  # Still running
            assert "unprocessed" in health["message"].lower()


class TestCheckPendingEvents:
    """Test check_pending_events tool function."""

    @pytest.mark.asyncio
    async def test_check_pending_events_with_events(self):
        """Should return categorized pending events."""
        mock_events = [
            {"data_type": "heart_rate", "value": 72},
            {"data_type": "heart_rate", "value": 75},
            {"data_type": "steps", "value": 5000}
        ]

        with patch('wearable_listener.tools.get_pending_events', return_value=mock_events):
            with patch('wearable_listener.tools.get_wearable_listener_status', return_value={
                "running": True, "event_count": 10, "events_by_type": {}, "pending_events": 3
            }):
                result = await check_pending_events()

                assert result["count"] == 3
                assert result["events_by_type"]["heart_rate"] == 2
                assert result["events_by_type"]["steps"] == 1
                assert len(result["events"]) == 3

    @pytest.mark.asyncio
    async def test_check_pending_events_empty(self):
        """Should handle no pending events."""
        with patch('wearable_listener.tools.get_pending_events', return_value=[]):
            with patch('wearable_listener.tools.get_wearable_listener_status', return_value={
                "running": True, "event_count": 0, "events_by_type": {}, "pending_events": 0
            }):
                result = await check_pending_events()

                assert result["count"] == 0
                assert "No pending" in result["message"]


class TestEventProcessing:
    """Test wearable event processing logic."""

    def test_process_normal_event(self):
        """Normal events should be stored without notification."""
        mock_context = MagicMock()
        mock_context.pending_events = []

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            notification_file = f.name

        try:
            with patch.dict(os.environ, {"HEALTH_NOTIFICATION_FILE": notification_file}):
                with patch('wearable_listener.lifecycle._state') as mock_state:
                    mock_state.agent_context = mock_context

                    event = {
                        "data_type": "heart_rate",
                        "value": 72,
                        "unit": "bpm",
                        "alert_level": "normal",
                        "message": "Normal reading"
                    }

                    process_wearable_data(event, mock_context)

                    # Event should be stored
                    assert len(mock_context.pending_events) == 1

            # No notification for normal events
            with open(notification_file, 'r') as f:
                content = f.read()
            assert content == ""  # File should be empty

        finally:
            os.unlink(notification_file)

    def test_process_critical_event_writes_notification(self):
        """Critical events should write to notification file."""
        mock_context = MagicMock()
        mock_context.pending_events = []

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            notification_file = f.name

        try:
            with patch.dict(os.environ, {"HEALTH_NOTIFICATION_FILE": notification_file}):
                with patch('wearable_listener.lifecycle._state') as mock_state:
                    mock_state.agent_context = mock_context

                    event = {
                        "data_type": "heart_rate",
                        "value": 160,
                        "unit": "bpm",
                        "alert_level": "critical",
                        "message": "Critical heart rate",
                        "timestamp": "2024-12-03T15:30:00Z",
                        "source_device": "Apple Watch"
                    }

                    process_wearable_data(event, mock_context)

            # Notification should be written
            with open(notification_file, 'r') as f:
                content = f.read()
            assert "CRITICAL" in content

        finally:
            os.unlink(notification_file)

    def test_process_elevated_event_writes_notification(self):
        """Elevated events should write to notification file."""
        mock_context = MagicMock()
        mock_context.pending_events = []

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            notification_file = f.name

        try:
            with patch.dict(os.environ, {"HEALTH_NOTIFICATION_FILE": notification_file}):
                with patch('wearable_listener.lifecycle._state') as mock_state:
                    mock_state.agent_context = mock_context

                    event = {
                        "data_type": "stress",
                        "value": 75,
                        "unit": "level",
                        "alert_level": "elevated",
                        "message": "Elevated stress",
                        "timestamp": "2024-12-03T15:30:00Z",
                        "source_device": "Fitbit"
                    }

                    process_wearable_data(event, mock_context)

            # Notification should be written
            with open(notification_file, 'r') as f:
                content = f.read()
            assert "ELEVATED" in content

        finally:
            os.unlink(notification_file)


class TestEventPayloadValidation:
    """Test validation of event payloads from simulator."""

    def test_process_event_with_missing_fields(self):
        """Should handle events with missing optional fields gracefully."""
        mock_context = MagicMock()
        mock_context.pending_events = []

        with patch('wearable_listener.lifecycle._state') as mock_state:
            mock_state.agent_context = mock_context

            # Minimal event payload
            event = {
                "data_type": "heart_rate",
                "value": 72
            }

            # Should not raise exception
            process_wearable_data(event, mock_context)

            assert len(mock_context.pending_events) == 1


class TestGetCurrentMetrics:
    """Test get_current_metrics tool function for real-time queries."""

    @pytest.mark.asyncio
    async def test_get_current_metrics_with_readings(self):
        """Should return current metrics when readings exist."""
        mock_readings = {
            "heart_rate": {
                "value": 85,
                "unit": "bpm",
                "timestamp": "2024-12-08T15:30:00Z",
                "alert_level": "normal",
                "source_device": "Apple Watch",
                "baseline": {"mean": 72, "std_dev": 8},
                "anomaly": None,
                "goal_progress": None,
            }
        }
        mock_status = {
            "running": True,
            "event_count": 100,
            "events_by_type": {"heart_rate": 50},
            "pending_events": 2
        }

        with patch('wearable_listener.tools.get_latest_readings', return_value=mock_readings):
            with patch('wearable_listener.tools.get_wearable_listener_status', return_value=mock_status):
                result = await get_current_metrics()

                assert result["data_types"] == ["heart_rate"]
                assert result["metrics"]["heart_rate"]["value"] == 85
                assert result["listener_status"]["running"] is True
                assert "Current readings" in result["message"]

    @pytest.mark.asyncio
    async def test_get_current_metrics_empty_readings(self):
        """Should return appropriate message when no readings available."""
        mock_status = {
            "running": True,
            "event_count": 0,
            "events_by_type": {},
            "pending_events": 0
        }

        with patch('wearable_listener.tools.get_latest_readings', return_value={}):
            with patch('wearable_listener.tools.get_wearable_listener_status', return_value=mock_status):
                result = await get_current_metrics()

                assert result["metrics"] == {}
                assert result["data_types"] == []
                assert result["status"] == "waiting_for_data"
                assert "hasn't received any data yet" in result["message"]
                assert "user_guidance" in result

    @pytest.mark.asyncio
    async def test_get_current_metrics_listener_not_running(self):
        """Should indicate listener not running when stopped."""
        mock_status = {
            "running": False,
            "event_count": 0,
            "events_by_type": {},
            "pending_events": 0
        }

        with patch('wearable_listener.tools.get_latest_readings', return_value={}):
            with patch('wearable_listener.tools.get_wearable_listener_status', return_value=mock_status):
                result = await get_current_metrics()

                assert result["metrics"] == {}
                assert result["status"] == "listener_not_running"
                assert "not currently running" in result["message"]
                assert "user_guidance" in result

    @pytest.mark.asyncio
    async def test_get_current_metrics_with_elevated_alert(self):
        """Should include alerts in message for elevated readings."""
        mock_readings = {
            "heart_rate": {
                "value": 115,
                "unit": "bpm",
                "timestamp": "2024-12-08T15:30:00Z",
                "alert_level": "elevated",
                "source_device": "Apple Watch",
                "baseline": {"mean": 72, "std_dev": 8},
                "anomaly": None,
                "goal_progress": None,
            }
        }
        mock_status = {"running": True, "event_count": 50, "events_by_type": {}, "pending_events": 0}

        with patch('wearable_listener.tools.get_latest_readings', return_value=mock_readings):
            with patch('wearable_listener.tools.get_wearable_listener_status', return_value=mock_status):
                result = await get_current_metrics()

                # Should include alert in message
                assert "heart_rate" in result["message"] or "Alerts" in result["message"]
                assert result["metrics"]["heart_rate"]["alert_level"] == "elevated"

    @pytest.mark.asyncio
    async def test_get_current_metrics_baseline_comparison(self):
        """Should calculate deviation from baseline when available."""
        mock_readings = {
            "heart_rate": {
                "value": 88,
                "unit": "bpm",
                "timestamp": "2024-12-08T15:30:00Z",
                "alert_level": "normal",
                "source_device": "Apple Watch",
                "baseline": {"mean": 72, "std_dev": 8},  # 88 is 2σ above mean
                "anomaly": None,
                "goal_progress": None,
            }
        }
        mock_status = {"running": True, "event_count": 50, "events_by_type": {}, "pending_events": 0}

        with patch('wearable_listener.tools.get_latest_readings', return_value=mock_readings):
            with patch('wearable_listener.tools.get_wearable_listener_status', return_value=mock_status):
                result = await get_current_metrics()

                # Should have deviation calculated
                heart_rate = result["metrics"]["heart_rate"]
                assert "deviation_sigma" in heart_rate
                assert heart_rate["deviation_sigma"] == 2.0  # (88-72)/8 = 2.0

    @pytest.mark.asyncio
    async def test_get_current_metrics_multiple_data_types(self):
        """Should return all available data types."""
        mock_readings = {
            "heart_rate": {
                "value": 75,
                "unit": "bpm",
                "timestamp": "2024-12-08T15:30:00Z",
                "alert_level": "normal",
                "baseline": None,
            },
            "steps": {
                "value": 5000,
                "unit": "steps",
                "timestamp": "2024-12-08T15:30:00Z",
                "alert_level": "normal",
                "baseline": None,
            }
        }
        mock_status = {"running": True, "event_count": 100, "events_by_type": {}, "pending_events": 0}

        with patch('wearable_listener.tools.get_latest_readings', return_value=mock_readings):
            with patch('wearable_listener.tools.get_wearable_listener_status', return_value=mock_status):
                result = await get_current_metrics()

                assert len(result["data_types"]) == 2
                assert "heart_rate" in result["data_types"]
                assert "steps" in result["data_types"]


class TestLatestReadingsStorage:
    """Test that latest readings are stored correctly in lifecycle."""

    def test_state_has_latest_readings(self):
        """WearableListenerState should have latest_readings dict."""
        state = WearableListenerState()
        assert hasattr(state, 'latest_readings')
        assert isinstance(state.latest_readings, dict)

    def test_get_latest_readings_returns_copy(self):
        """get_latest_readings should return a copy, not the original dict."""
        # This tests that modifications don't affect the internal state
        with patch('wearable_listener.lifecycle._state') as mock_state:
            mock_state.latest_readings = {"heart_rate": {"value": 72}}

            readings = get_latest_readings()
            readings["heart_rate"]["value"] = 999  # Modify the copy

            # Original should be unchanged
            assert mock_state.latest_readings["heart_rate"]["value"] == 72


class TestIntegrationEventToCurrentMetrics:
    """Integration tests for the full flow from event processing to current metrics."""

    def test_process_event_stores_latest_reading(self):
        """Processing an event should store it in latest_readings for current queries."""
        from wearable_listener import lifecycle

        # Create a fresh state
        original_state = lifecycle._state
        lifecycle._state = WearableListenerState()

        mock_context = MagicMock()
        mock_context.pending_events = []
        lifecycle._state.agent_context = mock_context

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
                notification_file = f.name

            with patch.dict(os.environ, {"HEALTH_NOTIFICATION_FILE": notification_file}):
                # Process a heart rate event
                event = {
                    "data_type": "heart_rate",
                    "value": 85,
                    "unit": "bpm",
                    "timestamp": "2024-12-08T15:30:00Z",
                    "source_device": "Apple Watch",
                    "alert_level": "normal",
                    "message": "Normal heart rate"
                }

                process_wearable_data(event, mock_context)

                # Verify latest_readings was updated
                readings = lifecycle._state.latest_readings
                assert "heart_rate" in readings
                assert readings["heart_rate"]["value"] == 85
                assert readings["heart_rate"]["unit"] == "bpm"
                assert readings["heart_rate"]["source_device"] == "Apple Watch"

        finally:
            lifecycle._state = original_state
            os.unlink(notification_file)

    @pytest.mark.asyncio
    async def test_get_current_metrics_returns_processed_events(self):
        """get_current_metrics should return data from processed events."""
        from wearable_listener import lifecycle

        # Create a fresh state with running=True
        original_state = lifecycle._state
        lifecycle._state = WearableListenerState()
        lifecycle._state.running = True

        mock_context = MagicMock()
        mock_context.pending_events = []
        lifecycle._state.agent_context = mock_context

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
                notification_file = f.name

            with patch.dict(os.environ, {"HEALTH_NOTIFICATION_FILE": notification_file}):
                # Process multiple events
                events = [
                    {
                        "data_type": "heart_rate",
                        "value": 78,
                        "unit": "bpm",
                        "timestamp": "2024-12-08T15:30:00Z",
                        "source_device": "Apple Watch"
                    },
                    {
                        "data_type": "steps",
                        "value": 5000,
                        "unit": "steps",
                        "timestamp": "2024-12-08T15:30:00Z",
                        "source_device": "Apple Watch"
                    }
                ]

                for event in events:
                    process_wearable_data(event, mock_context)

                # Now call get_current_metrics
                result = await get_current_metrics()

                # Verify we get the data
                assert result["listener_status"]["running"] is True
                assert len(result["data_types"]) == 2
                assert "heart_rate" in result["data_types"]
                assert "steps" in result["data_types"]
                assert result["metrics"]["heart_rate"]["value"] == 78
                assert result["metrics"]["steps"]["value"] == 5000
                assert "Current readings" in result["message"]

        finally:
            lifecycle._state = original_state
            os.unlink(notification_file)
