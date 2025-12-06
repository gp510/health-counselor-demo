"""
Unit tests for Wearable Health Data Simulator.

These tests verify:
1. Health event generation functions produce valid data
2. Alert level determination works correctly for all data types
3. Event payloads have the correct structure
4. Scenario generators produce expected event sequences

These tests run WITHOUT requiring Solace broker connection.
They import and test the simulator's data generation logic.

Usage:
    pytest tests/test_wearable_simulator.py -v
"""
import sys
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add scripts directory to path for importing simulator
scripts_path = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_path))

from wearable_simulator import (
    HEALTH_DATA_SPECS,
    ALERT_MESSAGES,
    WEARABLE_DEVICES,
    determine_alert_level,
    get_alert_message,
    create_health_event,
    generate_heart_rate,
    generate_steps_update,
    generate_stress_reading,
    generate_sleep_event,
    generate_workout_event,
)


class TestHealthDataSpecs:
    """Verify health data specifications are properly defined."""

    def test_all_data_types_defined(self):
        """Verify all expected data types have specifications."""
        expected_types = {"heart_rate", "steps", "sleep", "workout", "stress"}
        actual_types = set(HEALTH_DATA_SPECS.keys())

        assert expected_types == actual_types, (
            f"Missing data types: {expected_types - actual_types}"
        )

    def test_heart_rate_specs(self):
        """Verify heart rate specifications are valid."""
        specs = HEALTH_DATA_SPECS["heart_rate"]

        assert "unit" in specs
        assert specs["unit"] == "bpm"
        assert "normal_range" in specs
        assert "critical_low" in specs
        assert "critical_high" in specs
        assert specs["critical_low"] < specs["normal_range"][0]
        assert specs["critical_high"] > specs["normal_range"][1]

    def test_stress_specs(self):
        """Verify stress specifications are valid."""
        specs = HEALTH_DATA_SPECS["stress"]

        assert specs["unit"] == "level"
        assert specs["scale"] == (1, 100)
        assert specs["normal_range"][1] <= specs["elevated_range"][0]
        assert specs["elevated_range"][1] <= specs["critical_range"][0]

    def test_sleep_specs(self):
        """Verify sleep specifications are valid."""
        specs = HEALTH_DATA_SPECS["sleep"]

        assert specs["unit"] == "hours"
        assert "normal_duration" in specs
        assert specs["normal_duration"][0] >= 0
        assert specs["normal_duration"][1] <= 24

    def test_workout_specs(self):
        """Verify workout specifications are valid."""
        specs = HEALTH_DATA_SPECS["workout"]

        assert "types" in specs
        assert len(specs["types"]) > 0
        assert "running" in specs["types"]
        assert "duration_range" in specs
        assert specs["duration_range"][0] > 0


class TestAlertLevelDetermination:
    """Test alert level determination for different data types and values."""

    # Heart rate tests
    def test_heart_rate_normal(self):
        """Normal resting heart rate should return 'normal'."""
        assert determine_alert_level("heart_rate", 72) == "normal"
        assert determine_alert_level("heart_rate", 85) == "normal"

    def test_heart_rate_elevated(self):
        """Elevated heart rate should return 'elevated'."""
        assert determine_alert_level("heart_rate", 105) == "elevated"
        assert determine_alert_level("heart_rate", 115) == "elevated"

    def test_heart_rate_critical_high(self):
        """Critically high heart rate should return 'critical'."""
        assert determine_alert_level("heart_rate", 155) == "critical"
        assert determine_alert_level("heart_rate", 180) == "critical"

    def test_heart_rate_critical_low(self):
        """Critically low heart rate should return 'critical'."""
        assert determine_alert_level("heart_rate", 45) == "critical"
        assert determine_alert_level("heart_rate", 40) == "critical"

    # Stress tests
    def test_stress_normal(self):
        """Normal stress levels should return 'normal'."""
        assert determine_alert_level("stress", 30) == "normal"
        assert determine_alert_level("stress", 45) == "normal"

    def test_stress_elevated(self):
        """Elevated stress levels should return 'elevated'."""
        assert determine_alert_level("stress", 55) == "elevated"
        assert determine_alert_level("stress", 65) == "elevated"

    def test_stress_critical(self):
        """Critical stress levels should return 'critical'."""
        assert determine_alert_level("stress", 75) == "critical"
        assert determine_alert_level("stress", 90) == "critical"

    # Sleep tests
    def test_sleep_normal(self):
        """Normal sleep duration should return 'normal'."""
        assert determine_alert_level("sleep", 7.5) == "normal"
        assert determine_alert_level("sleep", 8) == "normal"

    def test_sleep_poor(self):
        """Poor sleep duration should return 'elevated'."""
        assert determine_alert_level("sleep", 4.5) == "elevated"
        assert determine_alert_level("sleep", 3) == "elevated"

    # Unknown type test
    def test_unknown_type_returns_normal(self):
        """Unknown data types should default to 'normal'."""
        assert determine_alert_level("unknown_type", 100) == "normal"


class TestAlertMessages:
    """Test alert message generation."""

    def test_heart_rate_messages_exist(self):
        """Verify heart rate alert messages are defined."""
        assert "heart_rate" in ALERT_MESSAGES
        assert "critical" in ALERT_MESSAGES["heart_rate"]
        assert "elevated" in ALERT_MESSAGES["heart_rate"]
        assert "normal" in ALERT_MESSAGES["heart_rate"]

    def test_stress_messages_exist(self):
        """Verify stress alert messages are defined."""
        assert "stress" in ALERT_MESSAGES
        assert len(ALERT_MESSAGES["stress"]["critical"]) > 0
        assert len(ALERT_MESSAGES["stress"]["elevated"]) > 0

    def test_get_alert_message_returns_string(self):
        """get_alert_message should always return a string."""
        msg = get_alert_message("heart_rate", "normal")
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_get_alert_message_with_context(self):
        """get_alert_message with context should use specific messages."""
        msg = get_alert_message("steps", "normal", "goal_reached")
        assert isinstance(msg, str)
        # Should get goal-specific message when available

    def test_get_alert_message_fallback(self):
        """get_alert_message should handle unknown types gracefully."""
        msg = get_alert_message("unknown", "normal")
        assert isinstance(msg, str)
        assert "unknown" in msg.lower() or "reading recorded" in msg.lower()


class TestEventCreation:
    """Test health event creation and payload structure."""

    def test_create_health_event_structure(self):
        """Verify event has all required fields."""
        event = create_health_event("heart_rate", 72)

        required_fields = [
            "event_id", "event_type", "data_type", "value", "unit",
            "timestamp", "alert_level", "message", "source_device", "source"
        ]

        for field in required_fields:
            assert field in event, f"Missing field: {field}"

    def test_create_health_event_values(self):
        """Verify event values are correct."""
        event = create_health_event("heart_rate", 72, unit="bpm")

        assert event["event_type"] == "wearable_data"
        assert event["data_type"] == "heart_rate"
        assert event["value"] == 72
        assert event["unit"] == "bpm"
        assert event["source"] == "simulator"

    def test_create_health_event_auto_unit(self):
        """Unit should be auto-detected from data type specs."""
        event = create_health_event("heart_rate", 72)
        assert event["unit"] == "bpm"

        event = create_health_event("stress", 50)
        assert event["unit"] == "level"

    def test_create_health_event_auto_alert_level(self):
        """Alert level should be auto-determined from value."""
        event = create_health_event("heart_rate", 160)
        assert event["alert_level"] == "critical"

        event = create_health_event("heart_rate", 72)
        assert event["alert_level"] == "normal"

    def test_create_health_event_with_metadata(self):
        """Event should include optional metadata."""
        metadata = {"context": "exercise", "workout_type": "running"}
        event = create_health_event("heart_rate", 140, metadata=metadata)

        assert "metadata" in event
        assert event["metadata"]["context"] == "exercise"

    def test_event_id_format(self):
        """Event ID should follow WRB-XXXXXXXX format."""
        event = create_health_event("heart_rate", 72)

        assert event["event_id"].startswith("WRB-")
        assert len(event["event_id"]) == 12  # WRB- + 8 hex chars

    def test_event_timestamp_format(self):
        """Timestamp should be ISO 8601 format with Z suffix."""
        event = create_health_event("heart_rate", 72)

        assert event["timestamp"].endswith("Z")
        # Should be parseable
        datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))

    def test_source_device_from_list(self):
        """Source device should be from valid device list."""
        event = create_health_event("heart_rate", 72)

        assert event["source_device"] in WEARABLE_DEVICES


class TestHeartRateGeneration:
    """Test heart rate event generation."""

    def test_generate_resting_heart_rate(self):
        """Resting heart rate should be in resting range."""
        specs = HEALTH_DATA_SPECS["heart_rate"]

        for _ in range(10):
            event = generate_heart_rate("resting")
            hr = event["value"]
            assert specs["resting_range"][0] <= hr <= specs["resting_range"][1], (
                f"Resting HR {hr} outside range {specs['resting_range']}"
            )

    def test_generate_exercise_heart_rate(self):
        """Exercise heart rate should be in exercise range."""
        specs = HEALTH_DATA_SPECS["heart_rate"]

        for _ in range(10):
            event = generate_heart_rate("exercise")
            hr = event["value"]
            assert specs["exercise_range"][0] <= hr <= specs["exercise_range"][1], (
                f"Exercise HR {hr} outside range {specs['exercise_range']}"
            )

    def test_generate_elevated_heart_rate(self):
        """Elevated heart rate should trigger elevated alert."""
        event = generate_heart_rate("elevated")
        hr = event["value"]

        specs = HEALTH_DATA_SPECS["heart_rate"]
        assert specs["elevated_range"][0] <= hr <= specs["elevated_range"][1]

    def test_generate_critical_high_heart_rate(self):
        """Critical high heart rate should exceed critical threshold."""
        specs = HEALTH_DATA_SPECS["heart_rate"]

        event = generate_heart_rate("critical_high")
        hr = event["value"]
        assert hr >= specs["critical_high"]

    def test_heart_rate_includes_context_metadata(self):
        """Generated heart rate should include context in metadata."""
        event = generate_heart_rate("resting")

        assert "metadata" in event
        assert event["metadata"]["context"] == "resting"


class TestStepsGeneration:
    """Test step count event generation."""

    def test_generate_steps_update(self):
        """Steps update should increment from current total."""
        event = generate_steps_update(current_total=5000)

        assert event["data_type"] == "steps"
        assert event["value"] > 5000  # Should be incremented
        assert "metadata" in event
        assert "increment" in event["metadata"]

    def test_steps_increment_range(self):
        """Step increment should be within defined range."""
        specs = HEALTH_DATA_SPECS["steps"]

        for _ in range(10):
            event = generate_steps_update(current_total=0)
            increment = event["metadata"]["increment"]
            assert specs["increment_range"][0] <= increment <= specs["increment_range"][1]

    def test_steps_daily_goal_in_metadata(self):
        """Steps metadata should include daily goal."""
        specs = HEALTH_DATA_SPECS["steps"]
        event = generate_steps_update(current_total=0)

        assert event["metadata"]["daily_goal"] == specs["daily_goal"]


class TestStressGeneration:
    """Test stress level event generation."""

    def test_generate_stress_reading_valid_range(self):
        """Stress reading should be within scale."""
        specs = HEALTH_DATA_SPECS["stress"]

        for _ in range(20):
            event = generate_stress_reading()
            value = event["value"]
            assert specs["scale"][0] <= value <= specs["scale"][1]

    def test_stress_reading_has_correct_type(self):
        """Stress event should have correct data type."""
        event = generate_stress_reading()

        assert event["data_type"] == "stress"
        assert event["unit"] == "level"


class TestSleepGeneration:
    """Test sleep event generation."""

    def test_generate_sleep_event_defaults(self):
        """Sleep event with defaults should have valid values."""
        event = generate_sleep_event()

        assert event["data_type"] == "sleep"
        assert event["unit"] == "hours"
        assert event["value"] >= 0
        assert event["value"] <= 24

    def test_generate_sleep_event_with_hours(self):
        """Sleep event with specified hours."""
        event = generate_sleep_event(hours=7.5)

        assert event["value"] == 7.5

    def test_generate_sleep_event_with_quality(self):
        """Sleep event should include quality score."""
        event = generate_sleep_event(hours=7, quality=85)

        assert event["metadata"]["quality_score"] == 85

    def test_poor_sleep_alert_level(self):
        """Poor sleep duration should have elevated alert level."""
        event = generate_sleep_event(hours=4)

        assert event["alert_level"] == "elevated"
        assert event["metadata"]["context"] == "poor"

    def test_good_sleep_alert_level(self):
        """Good sleep duration should have normal alert level."""
        event = generate_sleep_event(hours=7.5)

        assert event["alert_level"] == "normal"
        assert event["metadata"]["context"] == "good"


class TestWorkoutGeneration:
    """Test workout event generation."""

    def test_generate_workout_event_defaults(self):
        """Workout event with defaults should have valid structure."""
        event = generate_workout_event()

        assert event["data_type"] == "workout"
        assert event["unit"] == "minutes"
        assert event["value"] > 0
        assert "metadata" in event
        assert "workout_type" in event["metadata"]
        assert "calories_burned" in event["metadata"]

    def test_generate_workout_event_with_type(self):
        """Workout event with specified type."""
        event = generate_workout_event(workout_type="running")

        assert event["metadata"]["workout_type"] == "running"

    def test_generate_workout_event_with_duration(self):
        """Workout event with specified duration."""
        event = generate_workout_event(duration=45)

        assert event["value"] == 45

    def test_workout_type_valid(self):
        """Workout type should be from valid types list."""
        specs = HEALTH_DATA_SPECS["workout"]

        for _ in range(10):
            event = generate_workout_event()
            workout_type = event["metadata"]["workout_type"]
            assert workout_type in specs["types"]

    def test_workout_started_event(self):
        """Workout started event should have correct event_type."""
        event = generate_workout_event(event_type="started")

        assert event["metadata"]["event_type"] == "started"

    def test_workout_completed_event(self):
        """Workout completed event should have correct event_type."""
        event = generate_workout_event(event_type="completed")

        assert event["metadata"]["event_type"] == "completed"

    def test_workout_calories_calculation(self):
        """Calories should be calculated from duration."""
        specs = HEALTH_DATA_SPECS["workout"]

        event = generate_workout_event(duration=30)
        calories = event["metadata"]["calories_burned"]

        min_expected = 30 * specs["calories_per_minute"][0]
        max_expected = 30 * specs["calories_per_minute"][1]

        assert min_expected <= calories <= max_expected


class TestEventPayloadCompatibility:
    """Test that generated events match expected wearable listener format."""

    def test_event_matches_listener_expected_format(self):
        """Event should have all fields expected by wearable listener."""
        event = create_health_event("heart_rate", 72)

        # Fields expected by wearable listener's process_wearable_data
        required_by_listener = [
            "data_type", "value", "unit", "alert_level", "message"
        ]

        for field in required_by_listener:
            assert field in event, f"Listener expects field: {field}"

    def test_event_topic_derivation(self):
        """Event should allow topic derivation for publishing."""
        event = create_health_event("heart_rate", 72)

        # Topic pattern used in simulator: {prefix}/wearable/{data_type}/update
        data_type = event["data_type"]
        expected_topic = f"health/events/wearable/{data_type}/update"

        assert data_type in ["heart_rate", "steps", "sleep", "workout", "stress"]
