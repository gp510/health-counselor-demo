"""
Unit tests for Health Counselor CSV data files.

These tests verify:
1. CSV files exist in the expected location
2. CSV files have the expected columns (schema validation)
3. CSV files contain valid data rows
4. Data values meet basic integrity constraints

These tests run WITHOUT requiring any agents or gateway to be running.
They directly test the data files.

Usage:
    pytest tests/test_health_data.py -v
"""
import csv
import pytest
from pathlib import Path


def load_csv_data(csv_path: Path) -> tuple:
    """
    Load CSV file and return (columns, rows).

    Args:
        csv_path: Path to the CSV file

    Returns:
        Tuple of (column_names, list_of_row_dicts)
    """
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        rows = list(reader)
    return columns, rows


class TestCSVDataExists:
    """Verify CSV data files exist and are accessible."""

    def test_biomarker_csv_exists(self, data_path):
        """Verify biomarker_data.csv exists."""
        csv_file = data_path / "biomarker_data.csv"
        assert csv_file.exists(), f"Missing CSV: {csv_file}"

    def test_fitness_csv_exists(self, data_path):
        """Verify fitness_data.csv exists."""
        csv_file = data_path / "fitness_data.csv"
        assert csv_file.exists(), f"Missing CSV: {csv_file}"

    def test_diet_csv_exists(self, data_path):
        """Verify diet_logs.csv exists."""
        csv_file = data_path / "diet_logs.csv"
        assert csv_file.exists(), f"Missing CSV: {csv_file}"

    def test_mental_wellness_csv_exists(self, data_path):
        """Verify mental_wellness.csv exists."""
        csv_file = data_path / "mental_wellness.csv"
        assert csv_file.exists(), f"Missing CSV: {csv_file}"


class TestCSVSchemaValidation:
    """Validate CSV files have expected column schemas."""

    def test_biomarker_schema(self, data_path, health_agent_configs):
        """Verify biomarker CSV has all required columns."""
        config = health_agent_configs["biomarker"]
        csv_path = data_path / config.csv_filename

        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            actual_columns = set(reader.fieldnames)

        expected_columns = set(config.expected_columns)
        missing = expected_columns - actual_columns

        assert not missing, f"Missing columns in {config.csv_filename}: {missing}"

    def test_fitness_schema(self, data_path, health_agent_configs):
        """Verify fitness CSV has all required columns."""
        config = health_agent_configs["fitness"]
        csv_path = data_path / config.csv_filename

        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            actual_columns = set(reader.fieldnames)

        expected_columns = set(config.expected_columns)
        missing = expected_columns - actual_columns

        assert not missing, f"Missing columns in {config.csv_filename}: {missing}"

    def test_diet_schema(self, data_path, health_agent_configs):
        """Verify diet CSV has all required columns."""
        config = health_agent_configs["diet"]
        csv_path = data_path / config.csv_filename

        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            actual_columns = set(reader.fieldnames)

        expected_columns = set(config.expected_columns)
        missing = expected_columns - actual_columns

        assert not missing, f"Missing columns in {config.csv_filename}: {missing}"

    def test_mental_wellness_schema(self, data_path, health_agent_configs):
        """Verify mental wellness CSV has all required columns."""
        config = health_agent_configs["mental_wellness"]
        csv_path = data_path / config.csv_filename

        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            actual_columns = set(reader.fieldnames)

        expected_columns = set(config.expected_columns)
        missing = expected_columns - actual_columns

        assert not missing, f"Missing columns in {config.csv_filename}: {missing}"


class TestCSVDataIntegrity:
    """Validate CSV data meets basic integrity constraints."""

    def test_biomarker_has_data_rows(self, data_path, health_agent_configs):
        """Verify biomarker CSV has at least some data rows."""
        config = health_agent_configs["biomarker"]
        csv_path = data_path / config.csv_filename

        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        columns, rows = load_csv_data(csv_path)

        assert len(rows) > 0, f"No data rows in {config.csv_filename}"
        print(f"\n{config.csv_filename}: {len(rows)} records")

    def test_biomarker_status_values(self, data_path, health_agent_configs):
        """Verify biomarker status values are valid."""
        config = health_agent_configs["biomarker"]
        csv_path = data_path / config.csv_filename

        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        columns, rows = load_csv_data(csv_path)

        valid_statuses = {"normal", "low", "high", "critical"}
        for row in rows:
            status = row.get("status", "").lower()
            assert status in valid_statuses, f"Invalid status '{status}' in row {row.get('test_id')}"

    def test_fitness_has_data_rows(self, data_path, health_agent_configs):
        """Verify fitness CSV has at least some data rows."""
        config = health_agent_configs["fitness"]
        csv_path = data_path / config.csv_filename

        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        columns, rows = load_csv_data(csv_path)

        assert len(rows) > 0, f"No data rows in {config.csv_filename}"
        print(f"\n{config.csv_filename}: {len(rows)} records")

    def test_fitness_numeric_fields(self, data_path, health_agent_configs):
        """Verify fitness numeric fields can be converted to numbers."""
        config = health_agent_configs["fitness"]
        csv_path = data_path / config.csv_filename

        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        columns, rows = load_csv_data(csv_path)

        numeric_fields = ["steps", "calories_burned", "sleep_hours"]
        for row in rows:
            for field in numeric_fields:
                value = row.get(field, "0")
                try:
                    float(value)
                except ValueError:
                    pytest.fail(f"Non-numeric value '{value}' for {field} in {row.get('record_id')}")

    def test_diet_has_data_rows(self, data_path, health_agent_configs):
        """Verify diet CSV has at least some data rows."""
        config = health_agent_configs["diet"]
        csv_path = data_path / config.csv_filename

        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        columns, rows = load_csv_data(csv_path)

        assert len(rows) > 0, f"No data rows in {config.csv_filename}"
        print(f"\n{config.csv_filename}: {len(rows)} records")

    def test_diet_meal_types(self, data_path, health_agent_configs):
        """Verify diet meal_type values are valid."""
        config = health_agent_configs["diet"]
        csv_path = data_path / config.csv_filename

        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        columns, rows = load_csv_data(csv_path)

        valid_meal_types = {"breakfast", "lunch", "dinner", "snack"}
        for row in rows:
            meal_type = row.get("meal_type", "").lower()
            assert meal_type in valid_meal_types, f"Invalid meal_type '{meal_type}' in {row.get('meal_id')}"

    def test_mental_wellness_has_data_rows(self, data_path, health_agent_configs):
        """Verify mental wellness CSV has at least some data rows."""
        config = health_agent_configs["mental_wellness"]
        csv_path = data_path / config.csv_filename

        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        columns, rows = load_csv_data(csv_path)

        assert len(rows) > 0, f"No data rows in {config.csv_filename}"
        print(f"\n{config.csv_filename}: {len(rows)} records")

    def test_mental_wellness_score_ranges(self, data_path, health_agent_configs):
        """Verify mental wellness scores are within valid ranges (1-10)."""
        config = health_agent_configs["mental_wellness"]
        csv_path = data_path / config.csv_filename

        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        columns, rows = load_csv_data(csv_path)

        score_fields = ["mood_score", "energy_level", "stress_level", "anxiety_level"]
        for row in rows:
            for field in score_fields:
                value = row.get(field, "0")
                try:
                    score = int(value)
                    assert 1 <= score <= 10, f"Score {score} out of range for {field} in {row.get('entry_id')}"
                except ValueError:
                    pytest.fail(f"Non-integer score '{value}' for {field} in {row.get('entry_id')}")
