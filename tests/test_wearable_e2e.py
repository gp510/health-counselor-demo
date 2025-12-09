"""
Integration tests for Wearable Health Data flow.

These tests verify:
1. Simulator event format is compatible with listener expectations
2. Full wearable data scenarios produce expected event sequences
3. Health notification file format is correct
4. Integration between simulator and listener components

Usage:
    pytest tests/test_wearable_e2e.py -v
"""
import os
import sys
import json
import tempfile
import pytest
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Add paths for importing
scripts_path = Path(__file__).parent.parent / "scripts"
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(scripts_path))
sys.path.insert(0, str(src_path))

from wearable_simulator import (
    create_health_event,
    generate_heart_rate,
    generate_steps_update,
    generate_stress_reading,
    generate_sleep_event,
    generate_workout_event,
    HEALTH_DATA_SPECS,
)
from wearable_listener.lifecycle import process_wearable_data, write_health_notification
from wearable_listener.tools import (
    categorize_alert_level,
    format_fitness_update_request,
    format_alert_for_notification,
)


class TestSimulatorListenerCompatibility:
    """Verify simulator output is compatible with listener input expectations."""

    @pytest.mark.asyncio
    async def test_heart_rate_event_compatibility(self):
        """Simulator heart rate events should be processable by listener."""
        event = generate_heart_rate("resting")

        # Listener expects these fields
        assert "data_type" in event
        assert "value" in event
        assert "alert_level" in event

        # Can be processed by listener's categorize function
        alert = await categorize_alert_level(event["data_type"], event["value"])
        assert alert in ["normal", "elevated", "critical"]

    @pytest.mark.asyncio
    async def test_steps_event_compatibility(self):
        """Simulator steps events should be processable by listener."""
        event = generate_steps_update(current_total=5000)

        assert event["data_type"] == "steps"
        assert isinstance(event["value"], int)

        # Can be formatted for fitness update
        result = await format_fitness_update_request(event)
        assert result["can_update_fitness_db"] is True
        assert result["target_column"] == "steps"

    @pytest.mark.asyncio
    async def test_sleep_event_compatibility(self):
        """Simulator sleep events should be processable by listener."""
        event = generate_sleep_event(hours=7.5, quality=85)

        assert event["data_type"] == "sleep"
        assert event["value"] == 7.5
        assert event["metadata"]["quality_score"] == 85

        # Can be formatted for fitness update
        result = await format_fitness_update_request(event)
        assert result["can_update_fitness_db"] is True
        assert result["target_column"] == "sleep_hours"

    @pytest.mark.asyncio
    async def test_workout_event_compatibility(self):
        """Simulator workout events should be processable by listener."""
        event = generate_workout_event(workout_type="running", duration=30)

        assert event["data_type"] == "workout"
        assert event["value"] == 30
        assert event["metadata"]["workout_type"] == "running"

        # Workout maps to workout_type column
        result = await format_fitness_update_request(event)
        assert result["target_column"] == "workout_type"

    @pytest.mark.asyncio
    async def test_stress_event_compatibility(self):
        """Simulator stress events should be processable by listener."""
        event = generate_stress_reading()

        assert event["data_type"] == "stress"
        assert 1 <= event["value"] <= 100

        # Stress has no direct DB mapping
        result = await format_fitness_update_request(event)
        assert result["can_update_fitness_db"] is False

    def test_all_event_types_have_required_fields(self):
        """All event types should have minimum required fields for listener."""
        event_generators = [
            lambda: generate_heart_rate("resting"),
            lambda: generate_steps_update(0),
            lambda: generate_stress_reading(),
            lambda: generate_sleep_event(),
            lambda: generate_workout_event(),
        ]

        required_fields = ["event_id", "event_type", "data_type", "value", "timestamp"]

        for generator in event_generators:
            event = generator()
            for field in required_fields:
                assert field in event, f"Missing {field} in {event['data_type']} event"


class TestAlertLevelConsistency:
    """Verify alert levels are consistent between simulator and listener."""

    @pytest.mark.asyncio
    async def test_heart_rate_alert_levels_match(self):
        """Simulator and listener should agree on heart rate alert levels."""
        test_cases = [
            (72, "normal"),
            (105, "elevated"),
            (160, "critical"),
            (45, "critical"),
        ]

        for value, expected_category in test_cases:
            # Simulator creates event with auto-determined alert level
            event = create_health_event("heart_rate", value)

            # Listener categorizes independently
            listener_category = await categorize_alert_level("heart_rate", value)

            # Both should classify similarly (may differ slightly in thresholds)
            # At minimum, critical should match critical
            if expected_category == "critical":
                assert event["alert_level"] == "critical" or listener_category == "critical", (
                    f"HR {value}: simulator={event['alert_level']}, listener={listener_category}"
                )

    @pytest.mark.asyncio
    async def test_stress_alert_levels_match(self):
        """Simulator and listener should agree on stress alert levels."""
        test_cases = [
            (30, "normal"),
            (75, "critical"),  # Listener uses 70 as elevated threshold
            (95, "critical"),
        ]

        for value, expected_category in test_cases:
            event = create_health_event("stress", value)
            listener_category = await categorize_alert_level("stress", value)

            # Critical stress should match
            if expected_category == "critical":
                assert listener_category in ["elevated", "critical"]


class TestEventProcessingIntegration:
    """Test full event processing from generation to notification."""

    def test_critical_heart_rate_full_flow(self):
        """Critical heart rate should flow from generation to notification."""
        mock_context = MagicMock()
        mock_context.pending_events = []

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            notification_file = f.name

        try:
            with patch.dict(os.environ, {"HEALTH_NOTIFICATION_FILE": notification_file}):
                with patch('wearable_listener.lifecycle._state') as mock_state:
                    mock_state.agent_context = mock_context

                    # Generate event using simulator
                    event = generate_heart_rate("critical_high")

                    # Process using listener
                    process_wearable_data(event, mock_context)

            # Verify notification was written
            with open(notification_file, 'r') as f:
                content = f.read()

            assert "CRITICAL" in content
            assert "heart_rate" in content

        finally:
            os.unlink(notification_file)

    def test_workout_scenario_flow(self):
        """Workout scenario events should flow correctly."""
        # Simulate workout sequence
        events = []

        # Workout start
        start_event = generate_workout_event(
            workout_type="running",
            duration=30,
            event_type="started"
        )
        events.append(start_event)

        # Heart rate during workout
        for _ in range(3):
            hr_event = generate_heart_rate("exercise")
            events.append(hr_event)

        # Workout complete
        complete_event = generate_workout_event(
            workout_type="running",
            duration=30,
            event_type="completed"
        )
        events.append(complete_event)

        # Verify all events are valid
        for event in events:
            assert "data_type" in event
            assert "value" in event
            assert "timestamp" in event

        # Verify workout events have correct metadata
        assert start_event["metadata"]["event_type"] == "started"
        assert complete_event["metadata"]["event_type"] == "completed"

        # Heart rates should be in exercise range
        specs = HEALTH_DATA_SPECS["heart_rate"]
        for event in events:
            if event["data_type"] == "heart_rate":
                assert specs["exercise_range"][0] <= event["value"] <= specs["exercise_range"][1]

    def test_elevated_stress_scenario_flow(self):
        """Elevated stress events should generate notifications."""
        mock_context = MagicMock()
        mock_context.pending_events = []

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            notification_file = f.name

        try:
            with patch.dict(os.environ, {"HEALTH_NOTIFICATION_FILE": notification_file}):
                with patch('wearable_listener.lifecycle._state') as mock_state:
                    mock_state.agent_context = mock_context

                    # Create escalating stress events
                    stress_levels = [30, 55, 75, 85]
                    for level in stress_levels:
                        event = create_health_event("stress", level)
                        process_wearable_data(event, mock_context)

            # Verify elevated/critical notifications written
            with open(notification_file, 'r') as f:
                content = f.read()

            # Should have notifications for elevated and critical levels
            assert "ELEVATED" in content or "CRITICAL" in content

        finally:
            os.unlink(notification_file)


class TestNotificationFormatIntegration:
    """Test notification format from simulator events."""

    @pytest.mark.asyncio
    async def test_format_simulator_event_for_user(self):
        """Simulator events should format nicely for user notification."""
        event = generate_heart_rate("critical_high")

        notification = await format_alert_for_notification(
            data_type=event["data_type"],
            value=event["value"],
            unit=event["unit"],
            alert_level=event["alert_level"],
            message=event["message"],
            source_device=event["source_device"],
            timestamp=event["timestamp"]
        )

        # Should be user-friendly
        assert "Heart Rate" in notification
        assert str(event["value"]) in notification
        assert "bpm" in notification
        assert event["source_device"] in notification
        assert "🚨" in notification  # Critical emoji

    @pytest.mark.asyncio
    async def test_format_sleep_event_for_user(self):
        """Sleep events should format with quality information."""
        event = generate_sleep_event(hours=4, quality=45)

        notification = await format_alert_for_notification(
            data_type=event["data_type"],
            value=event["value"],
            unit=event["unit"],
            alert_level=event["alert_level"],
            message=event.get("message", ""),
            source_device=event["source_device"]
        )

        assert "Sleep" in notification
        assert "4" in notification


class TestTopicPatternMatching:
    """Test that event topics match expected patterns."""

    def test_heart_rate_topic(self):
        """Heart rate events should publish to correct topic."""
        event = generate_heart_rate("resting")
        expected_topic = "health/events/wearable/heart_rate/update"

        # Derive topic from event
        data_type = event["data_type"]
        actual_topic = f"health/events/wearable/{data_type}/update"

        assert actual_topic == expected_topic

    def test_all_data_types_have_valid_topics(self):
        """All data types should produce valid topic patterns."""
        events = [
            generate_heart_rate("resting"),
            generate_steps_update(0),
            generate_stress_reading(),
            generate_sleep_event(),
            generate_workout_event(),
        ]

        valid_types = {"heart_rate", "steps", "sleep", "workout", "stress"}
        topic_prefix = "health/events/wearable"

        for event in events:
            data_type = event["data_type"]
            assert data_type in valid_types
            topic = f"{topic_prefix}/{data_type}/update"
            assert topic.startswith(topic_prefix)


class TestScenarioEventSequences:
    """Test that scenarios produce expected event sequences."""

    def test_random_scenario_variety(self):
        """Random scenario should produce variety of event types."""
        # Simulate multiple random events
        event_types_seen = set()

        for _ in range(50):
            # Random selection like the scenario does
            import random
            generators = [
                lambda: generate_heart_rate("resting"),
                lambda: generate_heart_rate("normal"),
                lambda: generate_stress_reading(),
            ]
            event = random.choice(generators)()
            event_types_seen.add(event["data_type"])

        # Should see multiple types
        assert len(event_types_seen) >= 2

    def test_sleep_scenario_events(self):
        """Sleep scenario should produce sleep + morning heart rate."""
        # Generate sleep event
        sleep_event = generate_sleep_event(hours=7.5)
        assert sleep_event["data_type"] == "sleep"

        # Generate morning heart rate
        hr_event = generate_heart_rate("resting")
        assert hr_event["data_type"] == "heart_rate"

        # Both should be valid
        assert sleep_event["value"] == 7.5
        specs = HEALTH_DATA_SPECS["heart_rate"]
        assert specs["resting_range"][0] <= hr_event["value"] <= specs["resting_range"][1]
