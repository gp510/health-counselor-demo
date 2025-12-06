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
)
from wearable_listener.lifecycle import (
    WearableListenerState,
    process_wearable_data,
    store_pending_event,
    write_health_notification,
    get_wearable_listener_status,
    get_pending_events,
)


class TestAlertLevelCategorization:
    """Test alert level categorization for health readings."""

    # Heart rate tests
    def test_heart_rate_normal(self):
        """Normal heart rate should return 'normal'."""
        assert categorize_alert_level("heart_rate", 72) == "normal"
        assert categorize_alert_level("heart_rate", 80) == "normal"
        assert categorize_alert_level("heart_rate", 90) == "normal"

    def test_heart_rate_elevated_high(self):
        """Elevated high heart rate should return 'elevated'."""
        assert categorize_alert_level("heart_rate", 105) == "elevated"
        assert categorize_alert_level("heart_rate", 120) == "elevated"

    def test_heart_rate_elevated_low(self):
        """Elevated low heart rate should return 'elevated'."""
        assert categorize_alert_level("heart_rate", 52) == "elevated"

    def test_heart_rate_critical_high(self):
        """Critical high heart rate should return 'critical'."""
        assert categorize_alert_level("heart_rate", 155) == "critical"
        assert categorize_alert_level("heart_rate", 180) == "critical"

    def test_heart_rate_critical_low(self):
        """Critical low heart rate should return 'critical'."""
        assert categorize_alert_level("heart_rate", 45) == "critical"
        assert categorize_alert_level("heart_rate", 40) == "critical"

    # Sleep tests
    def test_sleep_normal(self):
        """Normal sleep duration should return 'normal'."""
        assert categorize_alert_level("sleep", 7) == "normal"
        assert categorize_alert_level("sleep", 8) == "normal"

    def test_sleep_elevated(self):
        """Short sleep should return 'elevated'."""
        assert categorize_alert_level("sleep", 4) == "elevated"
        assert categorize_alert_level("sleep", 4.5) == "elevated"

    def test_sleep_critical(self):
        """Very short sleep should return 'critical'."""
        assert categorize_alert_level("sleep", 2.5) == "critical"
        assert categorize_alert_level("sleep", 2) == "critical"

    # Stress tests
    def test_stress_normal(self):
        """Normal stress should return 'normal'."""
        assert categorize_alert_level("stress", 30) == "normal"
        assert categorize_alert_level("stress", 50) == "normal"

    def test_stress_elevated(self):
        """Elevated stress should return 'elevated'."""
        assert categorize_alert_level("stress", 75) == "elevated"
        assert categorize_alert_level("stress", 85) == "elevated"

    def test_stress_critical(self):
        """Critical stress should return 'critical'."""
        assert categorize_alert_level("stress", 92) == "critical"
        assert categorize_alert_level("stress", 100) == "critical"

    # Steps tests (no critical/elevated thresholds)
    def test_steps_always_normal(self):
        """Steps should always return 'normal' (no critical thresholds)."""
        assert categorize_alert_level("steps", 100) == "normal"
        assert categorize_alert_level("steps", 10000) == "normal"
        assert categorize_alert_level("steps", 50000) == "normal"

    # Unknown type test
    def test_unknown_type_returns_normal(self):
        """Unknown data types should return 'normal'."""
        assert categorize_alert_level("unknown_type", 999) == "normal"


class TestAlertNotificationFormatting:
    """Test alert notification message formatting."""

    def test_format_critical_alert(self):
        """Critical alerts should have urgent formatting."""
        notification = format_alert_for_notification(
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

    def test_format_elevated_alert(self):
        """Elevated alerts should have warning formatting."""
        notification = format_alert_for_notification(
            data_type="stress",
            value=75,
            unit="level",
            alert_level="elevated",
            source_device="Fitbit"
        )

        assert "Elevated" in notification
        assert "75" in notification
        assert "⚠️" in notification

    def test_format_normal_alert(self):
        """Normal readings should have positive formatting."""
        notification = format_alert_for_notification(
            data_type="heart_rate",
            value=72,
            unit="bpm",
            alert_level="normal"
        )

        assert "Health Update" in notification or "Normal" in notification.title()
        assert "72" in notification
        assert "✅" in notification

    def test_format_with_timestamp(self):
        """Notification should include timestamp if provided."""
        timestamp = "2024-12-03T15:30:00Z"
        notification = format_alert_for_notification(
            data_type="heart_rate",
            value=72,
            unit="bpm",
            alert_level="normal",
            timestamp=timestamp
        )

        assert timestamp in notification or "Recorded" in notification

    def test_format_with_message(self):
        """Notification should include details message if provided."""
        message = "Heart rate elevated during rest period"
        notification = format_alert_for_notification(
            data_type="heart_rate",
            value=105,
            unit="bpm",
            alert_level="elevated",
            message=message
        )

        assert message in notification

    def test_data_type_friendly_names(self):
        """Data types should be converted to friendly names."""
        notification = format_alert_for_notification(
            data_type="heart_rate",
            value=72,
            unit="bpm",
            alert_level="normal"
        )
        assert "Heart Rate" in notification

        notification = format_alert_for_notification(
            data_type="sleep",
            value=7.5,
            unit="hours",
            alert_level="normal"
        )
        assert "Sleep" in notification


class TestFitnessUpdateRequest:
    """Test fitness database update request formatting."""

    def test_heart_rate_update_request(self):
        """Heart rate should map to avg_heart_rate column."""
        event = {
            "event_id": "WRB-12345678",
            "data_type": "heart_rate",
            "value": 72,
            "timestamp": "2024-12-03T15:30:00Z",
            "source_device": "Apple Watch"
        }

        result = format_fitness_update_request(event)

        assert result["data_type"] == "heart_rate"
        assert result["value"] == 72
        assert result["target_column"] == "avg_heart_rate"
        assert result["can_update_fitness_db"] is True

    def test_steps_update_request(self):
        """Steps should map to steps column."""
        event = {
            "data_type": "steps",
            "value": 8500,
            "timestamp": "2024-12-03T15:30:00Z"
        }

        result = format_fitness_update_request(event)

        assert result["target_column"] == "steps"
        assert result["can_update_fitness_db"] is True

    def test_sleep_update_request(self):
        """Sleep should map to sleep_hours column."""
        event = {
            "data_type": "sleep",
            "value": 7.5,
            "timestamp": "2024-12-03T15:30:00Z"
        }

        result = format_fitness_update_request(event)

        assert result["target_column"] == "sleep_hours"
        assert result["can_update_fitness_db"] is True

    def test_stress_no_direct_mapping(self):
        """Stress has no direct fitness DB mapping."""
        event = {
            "data_type": "stress",
            "value": 45,
            "timestamp": "2024-12-03T15:30:00Z"
        }

        result = format_fitness_update_request(event)

        assert result["target_column"] is None
        assert result["can_update_fitness_db"] is False
        assert "manual handling" in result["message"]

    def test_update_request_includes_event_id(self):
        """Update request should include original event ID."""
        event = {
            "event_id": "WRB-ABCD1234",
            "data_type": "heart_rate",
            "value": 72
        }

        result = format_fitness_update_request(event)

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

    def test_get_listener_health_when_running(self):
        """Should report healthy when listener is running."""
        with patch('wearable_listener.tools.get_wearable_listener_status') as mock_status:
            mock_status.return_value = {
                "running": True,
                "event_count": 100,
                "events_by_type": {"heart_rate": 50, "steps": 30, "sleep": 20},
                "last_event_time": "2024-12-03T15:30:00Z",
                "pending_events": 2
            }

            health = get_listener_health()

            assert health["healthy"] is True
            assert health["events_processed"] == 100
            assert "healthy" in health["message"].lower()

    def test_get_listener_health_when_stopped(self):
        """Should report unhealthy when listener is not running."""
        with patch('wearable_listener.tools.get_wearable_listener_status') as mock_status:
            mock_status.return_value = {
                "running": False,
                "event_count": 0,
                "events_by_type": {},
                "last_event_time": None,
                "pending_events": 0
            }

            health = get_listener_health()

            assert health["healthy"] is False
            assert "not running" in health["message"].lower()

    def test_get_listener_health_with_backlog(self):
        """Should warn when pending events exceed threshold."""
        with patch('wearable_listener.tools.get_wearable_listener_status') as mock_status:
            mock_status.return_value = {
                "running": True,
                "event_count": 100,
                "events_by_type": {},
                "last_event_time": "2024-12-03T15:30:00Z",
                "pending_events": 15  # More than threshold (10)
            }

            health = get_listener_health()

            assert health["healthy"] is True  # Still running
            assert "unprocessed" in health["message"].lower()


class TestCheckPendingEvents:
    """Test check_pending_events tool function."""

    def test_check_pending_events_with_events(self):
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
                result = check_pending_events()

                assert result["count"] == 3
                assert result["events_by_type"]["heart_rate"] == 2
                assert result["events_by_type"]["steps"] == 1
                assert len(result["events"]) == 3

    def test_check_pending_events_empty(self):
        """Should handle no pending events."""
        with patch('wearable_listener.tools.get_pending_events', return_value=[]):
            with patch('wearable_listener.tools.get_wearable_listener_status', return_value={
                "running": True, "event_count": 0, "events_by_type": {}, "pending_events": 0
            }):
                result = check_pending_events()

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
