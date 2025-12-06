"""
Pytest fixtures for Solace Agent Mesh E2E tests.
"""
import os
import sys
import time
import uuid
import asyncio
import pytest
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Gateway configuration
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8000")



@pytest.fixture
def gateway_url():
    """Return the gateway URL."""
    return GATEWAY_URL


@pytest.fixture
def http_client():
    """Create a synchronous HTTP client."""
    with httpx.Client(base_url=GATEWAY_URL, timeout=120.0) as client:
        yield client


@pytest.fixture
async def async_http_client():
    """Create an async HTTP client."""
    async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=120.0) as client:
        yield client


def create_message_request(
    prompt: str,
    agent_name: str = "OrchestratorAgent",
    session_id: str = None
) -> dict:
    """
    Create a JSON-RPC message request for the agent mesh.

    Args:
        prompt: The user's query/prompt
        agent_name: Target agent name (default: OrchestratorAgent)
        session_id: Optional session ID for conversation continuity

    Returns:
        dict: JSON-RPC formatted request
    """
    message_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())

    return {
        "id": request_id,
        "jsonrpc": "2.0",
        "method": "message/stream",
        "params": {
            "message": {
                "messageId": message_id,
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": prompt
                    }
                ],
                "contextId": session_id,
                "metadata": {
                    "agent_name": agent_name
                }
            }
        }
    }


async def send_query_and_get_response(
    client: httpx.AsyncClient,
    prompt: str,
    timeout: float = 90.0
) -> str:
    """
    Send a query to the agent mesh and collect the complete response.

    Args:
        client: Async HTTP client
        prompt: The query to send
        timeout: Maximum time to wait for response

    Returns:
        str: The complete response text
    """
    import json as json_module

    # Send the streaming request
    request = create_message_request(prompt)
    response = await client.post("/api/v1/message:stream", json=request)
    response.raise_for_status()

    result = response.json()
    # Task ID is in result.id (not taskId)
    task_id = result.get("result", {}).get("id")

    if not task_id:
        raise ValueError(f"No task id in response: {result}")

    # Connect to SSE and collect response
    response_parts = []
    seen_messages = set()  # Track unique messages to avoid duplicates

    async with client.stream(
        "GET",
        f"/api/v1/sse/subscribe/{task_id}",
        timeout=timeout
    ) as sse_response:
        async for line in sse_response.aiter_lines():
            if line.startswith("data:"):
                data = line[5:].strip()
                if data:
                    try:
                        event = json_module.loads(data)
                        res = event.get("result", {})
                        final = res.get("final", False)

                        # Extract text from status.message.parts
                        status = res.get("status", {})
                        state = status.get("state")
                        message = status.get("message", {})
                        message_id = message.get("messageId")

                        # Only process each message once
                        if message_id and message_id not in seen_messages:
                            seen_messages.add(message_id)
                            parts = message.get("parts", [])
                            for part in parts:
                                if part.get("kind") == "text":
                                    text = part.get("text", "")
                                    if text:
                                        response_parts.append(text)

                        # Check if completed
                        if final or state == "completed":
                            break

                    except json_module.JSONDecodeError:
                        continue

    return "".join(response_parts)


@pytest.fixture
def send_query(async_http_client):
    """Fixture that provides a function to send queries."""
    async def _send_query(prompt: str, timeout: float = 90.0) -> str:
        return await send_query_and_get_response(async_http_client, prompt, timeout)
    return _send_query


def check_gateway_available():
    """Check if the gateway is accessible."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{GATEWAY_URL}/health")
            return response.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def verify_gateway(request):
    """
    Verify gateway is available.

    This fixture is NOT autouse - only tests that need the gateway
    should request it explicitly or use the @pytest.mark.requires_gateway marker.
    """
    if not check_gateway_available():
        pytest.skip(
            f"Gateway not available at {GATEWAY_URL}. "
            "Please ensure the system is running."
        )


@pytest.fixture(autouse=True)
def skip_if_gateway_required(request):
    """
    Auto-skip tests marked with @pytest.mark.requires_gateway if gateway is unavailable.

    Tests without this marker (like Event Listener tests) will run without gateway.
    """
    if request.node.get_closest_marker("requires_gateway"):
        if not check_gateway_available():
            pytest.skip(
                f"Gateway not available at {GATEWAY_URL}. "
                "Please ensure the system is running."
            )


# ============================================================================
# Health Agent Test Fixtures
# ============================================================================

import csv
import sqlite3
from dataclasses import dataclass


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
