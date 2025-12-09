"""
Unit tests for Dashboard API routes.

Tests the row conversion functions that transform SQLite rows to Pydantic models.
"""
import pytest


class TestRowToFitnessConversion:
    """Test _row_to_fitness function handles various data types."""

    def test_row_to_fitness_with_float_strings(self):
        """
        Test that _row_to_fitness handles float strings like '103.0'.

        SQLite can return numeric values as float strings when data is
        inserted from real-time sources. The conversion must handle this.

        Bug reproduction: ValueError: invalid literal for int() with base 10: '103.0'
        """
        from server.dashboard_api.routes.summary import _row_to_fitness

        # Simulate a SQLite row with float strings (as returned by real-time wearable data)
        mock_row = {
            "record_id": "REC_2024_001",
            "date": "2024-12-08",
            "data_source": "wearable_listener",
            "steps": "8500.0",  # Float string
            "distance_km": "6.8",
            "active_minutes": "45.0",  # Float string
            "calories_burned": "420.0",  # Float string
            "resting_heart_rate": "62.0",  # Float string
            "avg_heart_rate": "103.0",  # Float string - this caused the original error
            "max_heart_rate": "145.0",  # Float string
            "sleep_hours": "7.5",
            "sleep_quality_score": "85.0",  # Float string
            "workout_type": "running",
            "workout_duration_min": "30.0",  # Float string
        }

        # This should NOT raise ValueError
        result = _row_to_fitness(mock_row)

        # Verify the conversion worked correctly
        assert result.steps == 8500
        assert result.avg_heart_rate == 103
        assert result.max_heart_rate == 145
        assert result.resting_heart_rate == 62
        assert result.active_minutes == 45
        assert result.calories_burned == 420
        assert result.sleep_quality_score == 85
        assert result.workout_duration_min == 30

    def test_row_to_fitness_with_integer_strings(self):
        """Test that _row_to_fitness still works with regular integer strings."""
        from server.dashboard_api.routes.summary import _row_to_fitness

        mock_row = {
            "record_id": "REC_2024_002",
            "date": "2024-12-08",
            "data_source": "csv_import",
            "steps": "10000",
            "distance_km": "8.2",
            "active_minutes": "60",
            "calories_burned": "500",
            "resting_heart_rate": "58",
            "avg_heart_rate": "95",
            "max_heart_rate": "160",
            "sleep_hours": "8.0",
            "sleep_quality_score": "90",
            "workout_type": "none",
            "workout_duration_min": "0",
        }

        result = _row_to_fitness(mock_row)

        assert result.steps == 10000
        assert result.avg_heart_rate == 95
        assert result.workout_type is None  # "none" should be converted to None

    def test_row_to_fitness_with_none_values(self):
        """Test that _row_to_fitness handles None/empty values gracefully."""
        from server.dashboard_api.routes.summary import _row_to_fitness

        mock_row = {
            "record_id": "REC_2024_003",
            "date": "2024-12-08",
            "data_source": "partial_data",
            "steps": None,
            "distance_km": None,
            "active_minutes": "",
            "calories_burned": "0",
            "resting_heart_rate": "65",
            "avg_heart_rate": "75",
            "max_heart_rate": "80",
            "sleep_hours": "0",
            "sleep_quality_score": "0",
            "workout_type": "",
            "workout_duration_min": None,
        }

        result = _row_to_fitness(mock_row)

        assert result.steps == 0
        assert result.active_minutes == 0
        assert result.workout_duration_min == 0
        assert result.workout_type is None


class TestRowToWellnessConversion:
    """Test _row_to_wellness function for similar issues."""

    def test_row_to_wellness_with_float_strings(self):
        """Test that _row_to_wellness handles float strings."""
        from server.dashboard_api.routes.summary import _row_to_wellness

        mock_row = {
            "entry_id": "WELL_001",
            "date": "2024-12-08",
            "time_of_day": "morning",
            "mood_score": "7.0",  # Float string
            "energy_level": "6.0",  # Float string
            "stress_level": "4.0",  # Float string
            "anxiety_level": "3.0",  # Float string
            "sleep_quality_rating": "8.0",  # Float string
            "activities": "meditation,reading",
            "social_interaction": "medium",
            "journal_entry": "Feeling good today",
            "gratitude_notes": "Grateful for health",
            "tags": "positive,productive",
        }

        result = _row_to_wellness(mock_row)

        assert result.mood_score == 7
        assert result.energy_level == 6
        assert result.stress_level == 4
        assert result.anxiety_level == 3
        assert result.sleep_quality_rating == 8


class TestFitnessAPIFiltersIncompleteRecords:
    """
    Test that fitness API excludes incomplete records.

    Bug: The wearable listener creates records with zeros for all fields
    except the one being updated. These incomplete records appear in API
    responses, showing "all zeros" to users.

    Example bad record in DB:
    LIVE-20251208 | steps=0, active_minutes=0, calories=0 (only avg_heart_rate has data)
    """

    def test_fitness_records_exclude_incomplete_wearable_records(self):
        """
        Fitness API should NOT return records where all key metrics are zero.

        This test queries the actual database and verifies that records with
        steps=0, active_minutes=0, calories_burned=0, AND sleep_hours=0 are
        filtered out. These are "incomplete" records created by the wearable
        listener when the first event of the day arrives.
        """
        import asyncio
        from server.dashboard_api.routes.fitness import get_fitness_records

        # Query fitness records from the actual database
        records = asyncio.get_event_loop().run_until_complete(
            get_fitness_records(days=30)
        )

        # Verify we got some records
        assert len(records) > 0, "Expected at least one fitness record"

        # Each record should have meaningful data (not all zeros)
        for record in records:
            # A valid record should have at least ONE of these non-zero:
            # - steps (daily activity)
            # - active_minutes (exercise time)
            # - calories_burned (energy expenditure)
            # - sleep_hours (sleep tracking)
            has_meaningful_data = (
                record.steps > 0
                or record.active_minutes > 0
                or record.calories_burned > 0
                or record.sleep_hours > 0
            )
            assert has_meaningful_data, (
                f"Record {record.record_id} has all zeros for key metrics: "
                f"steps={record.steps}, active_minutes={record.active_minutes}, "
                f"calories_burned={record.calories_burned}, sleep_hours={record.sleep_hours}"
            )

    def test_fitness_summary_today_excludes_incomplete_records(self):
        """
        Today's fitness in summary should have meaningful data, not zeros.

        The summary endpoint returns "today's" fitness. If the most recent
        record is incomplete (all zeros from wearable listener), it should
        fall back to the next valid record.
        """
        import asyncio
        from server.dashboard_api.routes.summary import get_health_summary

        # Query health summary from the actual database
        summary = asyncio.get_event_loop().run_until_complete(get_health_summary())

        # Today's fitness should exist
        today_fitness = summary.fitness.today
        assert today_fitness is not None, "Expected today's fitness data"

        # Today's fitness should have meaningful data (not all zeros)
        has_meaningful_data = (
            today_fitness.steps > 0
            or today_fitness.active_minutes > 0
            or today_fitness.calories_burned > 0
            or today_fitness.sleep_hours > 0
        )
        assert has_meaningful_data, (
            f"Today's fitness {today_fitness.record_id} has all zeros: "
            f"steps={today_fitness.steps}, active_minutes={today_fitness.active_minutes}, "
            f"calories_burned={today_fitness.calories_burned}, sleep_hours={today_fitness.sleep_hours}"
        )
