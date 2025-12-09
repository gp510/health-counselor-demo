"""
Pytest fixtures for Health Counselor tests.
"""
import os
import sys
import csv
import sqlite3
import pytest
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

# Ensure src/ is on sys.path so tests can import wearable_listener and other modules.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Load environment variables
load_dotenv()


# ============================================================================
# Health Agent Test Fixtures
# ============================================================================

@dataclass
class HealthAgentConfig:
    """Configuration for a health agent's database."""
    name: str
    table_name: str
    csv_filename: str
    expected_columns: list


# Health agent configurations
HEALTH_AGENTS = {
    "biomarker": HealthAgentConfig(
        name="BiomarkerAgent",
        table_name="biomarker_data",
        csv_filename="biomarker_data.csv",
        expected_columns=[
            "test_id", "test_date", "test_type", "biomarker_name",
            "value", "unit", "reference_range_low", "reference_range_high",
            "status", "lab_source", "notes"
        ]
    ),
    "fitness": HealthAgentConfig(
        name="FitnessAgent",
        table_name="fitness_data",
        csv_filename="fitness_data.csv",
        expected_columns=[
            "record_id", "date", "data_source", "steps", "distance_km",
            "active_minutes", "calories_burned", "resting_heart_rate",
            "avg_heart_rate", "max_heart_rate", "sleep_hours",
            "sleep_quality_score", "workout_type", "workout_duration_min"
        ]
    ),
    "diet": HealthAgentConfig(
        name="DietAgent",
        table_name="diet_logs",
        csv_filename="diet_logs.csv",
        expected_columns=[
            "meal_id", "date", "meal_type", "food_items", "calories",
            "protein_g", "carbs_g", "fat_g", "fiber_g", "sodium_mg",
            "sugar_g", "water_ml", "notes"
        ]
    ),
    "mental_wellness": HealthAgentConfig(
        name="MentalWellnessAgent",
        table_name="mental_wellness",
        csv_filename="mental_wellness.csv",
        expected_columns=[
            "entry_id", "date", "time_of_day", "mood_score", "energy_level",
            "stress_level", "anxiety_level", "sleep_quality_rating",
            "activities", "social_interaction", "journal_entry",
            "gratitude_notes", "tags"
        ]
    ),
}


@pytest.fixture
def data_path():
    """Return the path to the CSV data directory."""
    base_path = os.environ.get("DATA_PATH", str(Path(__file__).parent.parent))
    return Path(base_path) / "CSV_Data"


@pytest.fixture
def health_agent_configs():
    """Return all health agent configurations."""
    return HEALTH_AGENTS


@pytest.fixture(params=list(HEALTH_AGENTS.keys()))
def health_agent_config(request):
    """Parametrized fixture for testing each health agent."""
    return HEALTH_AGENTS[request.param]


@pytest.fixture
def create_test_database():
    """
    Factory fixture to create an in-memory SQLite database from a CSV file.

    Returns a function that accepts a HealthAgentConfig and data_path,
    returns a (connection, cursor) tuple.
    """
    connections = []

    def _create_database(config: HealthAgentConfig, data_path: Path) -> tuple:
        csv_path = data_path / config.csv_filename

        if not csv_path.exists():
            pytest.skip(f"CSV file not found: {csv_path}")

        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        connections.append(conn)

        # Load CSV and create table
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames

            # Create table with TEXT columns (matching sam_sql_database behavior)
            create_sql = f"CREATE TABLE {config.table_name} ({', '.join(f'{col} TEXT' for col in columns)})"
            cursor.execute(create_sql)

            # Insert data
            placeholders = ', '.join('?' * len(columns))
            insert_sql = f"INSERT INTO {config.table_name} VALUES ({placeholders})"
            for row in reader:
                cursor.execute(insert_sql, [row[col] for col in columns])

        conn.commit()
        return conn, cursor

    yield _create_database

    # Cleanup
    for conn in connections:
        conn.close()


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
