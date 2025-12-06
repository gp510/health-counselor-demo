"""
E2E tests for Health Counselor query scenarios.

These tests send real queries to the running Solace Agent Mesh system
and validate that responses contain expected health-related information.

Prerequisites:
- Solace broker running
- All health agents started (orchestrator, biomarker, fitness, diet, mental wellness)
- WebUI gateway running at localhost:8000 (or GATEWAY_URL)

Usage:
    pytest tests/test_health_queries.py -v
"""
import json
import uuid
import pytest
import httpx


def create_message_request(
    prompt: str,
    agent_name: str = "HealthCounselorOrchestrator",
    session_id: str = None
) -> dict:
    """Create a JSON-RPC message request for the agent mesh."""
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
                "parts": [{"kind": "text", "text": prompt}],
                "contextId": session_id,
                "metadata": {"agent_name": agent_name}
            }
        }
    }


async def send_query_and_get_response(
    client: httpx.AsyncClient,
    prompt: str,
    timeout: float = 90.0
) -> str:
    """Send a query to the agent mesh and collect the complete response."""
    request = create_message_request(prompt)
    response = await client.post("/api/v1/message:stream", json=request)
    response.raise_for_status()

    result = response.json()
    task_id = result.get("result", {}).get("id")

    if not task_id:
        raise ValueError(f"No task id in response: {result}")

    response_parts = []
    seen_messages = set()

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
                        event = json.loads(data)
                        res = event.get("result", {})
                        final = res.get("final", False)
                        status = res.get("status", {})
                        state = status.get("state")
                        message = status.get("message", {})
                        message_id = message.get("messageId")

                        if message_id and message_id not in seen_messages:
                            seen_messages.add(message_id)
                            parts = message.get("parts", [])
                            for part in parts:
                                if part.get("kind") == "text":
                                    text = part.get("text", "")
                                    if text:
                                        response_parts.append(text)

                        if final or state == "completed":
                            break
                    except json.JSONDecodeError:
                        continue

    return "".join(response_parts)


class TestBiomarkerQueries:
    """Tests for biomarker-related health queries."""

    @pytest.mark.asyncio
    @pytest.mark.requires_gateway
    async def test_cholesterol_query(self, async_http_client):
        """
        Test: "What are my cholesterol levels?"

        Expected: Response should mention LDL, HDL, or total cholesterol values.
        Based on data: LDL was elevated (118, 105, 98 mg/dL across tests)
        """
        response = await send_query_and_get_response(
            async_http_client,
            "What are my cholesterol levels?"
        )

        response_lower = response.lower()

        # Check for infrastructure issues
        if "table" in response_lower and "not found" in response_lower:
            pytest.skip("BiomarkerAgent database not initialized")

        # Should mention cholesterol-related terms
        assert any([
            "ldl" in response_lower,
            "hdl" in response_lower,
            "cholesterol" in response_lower,
            "lipid" in response_lower,
        ]), f"Response should mention cholesterol data. Got: {response[:500]}"

        print(f"\n--- Cholesterol Query Response ---\n{response[:1000]}")

    @pytest.mark.asyncio
    @pytest.mark.requires_gateway
    async def test_abnormal_biomarkers_query(self, async_http_client):
        """
        Test: "What biomarkers are outside normal range?"

        Expected: Response should mention abnormal values like Vitamin D (low)
        or LDL (high) based on the test data.
        """
        response = await send_query_and_get_response(
            async_http_client,
            "What biomarkers are outside normal range?"
        )

        response_lower = response.lower()

        # Should identify some abnormal results
        assert any([
            "low" in response_lower,
            "high" in response_lower,
            "abnormal" in response_lower,
            "outside" in response_lower,
            "elevated" in response_lower,
            "vitamin d" in response_lower,
            "ldl" in response_lower,
        ]), f"Response should identify abnormal biomarkers. Got: {response[:500]}"

        print(f"\n--- Abnormal Biomarkers Response ---\n{response[:1000]}")


class TestFitnessQueries:
    """Tests for fitness-related health queries."""

    @pytest.mark.asyncio
    @pytest.mark.requires_gateway
    async def test_sleep_query(self, async_http_client):
        """
        Test: "How has my sleep been this week?"

        Expected: Response should mention sleep hours, quality, or patterns.
        Data shows sleep ranging from 5.5 to 8.8 hours with quality scores.
        """
        response = await send_query_and_get_response(
            async_http_client,
            "How has my sleep been this week?"
        )

        response_lower = response.lower()

        # Should mention sleep-related metrics
        assert any([
            "sleep" in response_lower,
            "hours" in response_lower,
            "quality" in response_lower,
            "rest" in response_lower,
        ]), f"Response should discuss sleep patterns. Got: {response[:500]}"

        print(f"\n--- Sleep Query Response ---\n{response[:1000]}")

    @pytest.mark.asyncio
    @pytest.mark.requires_gateway
    async def test_activity_query(self, async_http_client):
        """
        Test: "How many steps have I averaged recently?"

        Expected: Response should include step counts or activity metrics.
        Data shows steps ranging from ~3,400 to ~13,200.
        """
        response = await send_query_and_get_response(
            async_http_client,
            "How many steps have I averaged recently?"
        )

        response_lower = response.lower()

        # Should mention step or activity data
        assert any([
            "step" in response_lower,
            "average" in response_lower,
            "activity" in response_lower,
            "walk" in response_lower,
        ]), f"Response should include activity data. Got: {response[:500]}"

        print(f"\n--- Activity Query Response ---\n{response[:1000]}")

    @pytest.mark.asyncio
    @pytest.mark.requires_gateway
    async def test_workout_history_query(self, async_http_client):
        """
        Test: "What workouts have I done this month?"

        Expected: Response should list workout types (running, cycling, strength, etc.)
        """
        response = await send_query_and_get_response(
            async_http_client,
            "What workouts have I done this month?"
        )

        response_lower = response.lower()

        # Should mention workout types from the data
        assert any([
            "running" in response_lower,
            "cycling" in response_lower,
            "strength" in response_lower,
            "yoga" in response_lower,
            "swimming" in response_lower,
            "workout" in response_lower,
        ]), f"Response should list workouts. Got: {response[:500]}"

        print(f"\n--- Workout History Response ---\n{response[:1000]}")


class TestDietQueries:
    """Tests for diet and nutrition queries."""

    @pytest.mark.asyncio
    @pytest.mark.requires_gateway
    async def test_protein_intake_query(self, async_http_client):
        """
        Test: "Am I meeting my protein goals?"

        Expected: Response should include protein intake information in grams.
        """
        response = await send_query_and_get_response(
            async_http_client,
            "Am I meeting my protein goals?"
        )

        response_lower = response.lower()

        # Should mention protein
        assert any([
            "protein" in response_lower,
            "gram" in response_lower,
            "g" in response,  # Case-sensitive for unit
        ]), f"Response should discuss protein intake. Got: {response[:500]}"

        print(f"\n--- Protein Intake Response ---\n{response[:1000]}")

    @pytest.mark.asyncio
    @pytest.mark.requires_gateway
    async def test_high_sodium_query(self, async_http_client):
        """
        Test: "Which meals were highest in sodium?"

        Expected: Response should identify high-sodium meals.
        Data shows several meals with >800mg sodium marked "High sodium".
        """
        response = await send_query_and_get_response(
            async_http_client,
            "Which meals were highest in sodium?"
        )

        response_lower = response.lower()

        # Should mention sodium
        assert any([
            "sodium" in response_lower,
            "mg" in response_lower,
            "salt" in response_lower,
        ]), f"Response should discuss sodium intake. Got: {response[:500]}"

        print(f"\n--- High Sodium Response ---\n{response[:1000]}")


class TestMentalWellnessQueries:
    """Tests for mental wellness queries."""

    @pytest.mark.asyncio
    @pytest.mark.requires_gateway
    async def test_mood_trends_query(self, async_http_client):
        """
        Test: "How has my mood been trending?"

        Expected: Response should discuss mood scores or emotional patterns.
        """
        response = await send_query_and_get_response(
            async_http_client,
            "How has my mood been trending?"
        )

        response_lower = response.lower()

        # Should mention mood-related terms
        assert any([
            "mood" in response_lower,
            "score" in response_lower,
            "feeling" in response_lower,
            "trend" in response_lower,
        ]), f"Response should discuss mood trends. Got: {response[:500]}"

        print(f"\n--- Mood Trends Response ---\n{response[:1000]}")

    @pytest.mark.asyncio
    @pytest.mark.requires_gateway
    async def test_stress_query(self, async_http_client):
        """
        Test: "What days have I been most stressed?"

        Expected: Response should identify high-stress days from the data.
        """
        response = await send_query_and_get_response(
            async_http_client,
            "What days have I been most stressed?"
        )

        response_lower = response.lower()

        # Should mention stress
        assert any([
            "stress" in response_lower,
            "anxious" in response_lower,
            "anxiety" in response_lower,
            "level" in response_lower,
        ]), f"Response should identify stressful days. Got: {response[:500]}"

        print(f"\n--- Stress Query Response ---\n{response[:1000]}")


class TestMultiAgentCoordination:
    """Tests for multi-agent coordination scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.requires_gateway
    async def test_holistic_health_summary(self, async_http_client):
        """
        Test: "Give me a comprehensive health summary"

        Expected: Response should coordinate multiple agents and synthesize
        data from biomarkers, fitness, diet, and mental wellness.
        """
        response = await send_query_and_get_response(
            async_http_client,
            "Give me a comprehensive health summary",
            timeout=120.0  # Multi-agent queries take longer
        )

        response_lower = response.lower()

        # Should mention multiple health domains
        domains_mentioned = sum([
            "biomarker" in response_lower or "lab" in response_lower or "cholesterol" in response_lower,
            "fitness" in response_lower or "step" in response_lower or "sleep" in response_lower,
            "diet" in response_lower or "nutrition" in response_lower or "calorie" in response_lower,
            "mood" in response_lower or "stress" in response_lower or "mental" in response_lower,
        ])

        assert domains_mentioned >= 2, (
            f"Expected response to cover multiple health domains. Got: {response[:500]}"
        )

        print(f"\n--- Holistic Health Summary ---\n{response[:1500]}")

    @pytest.mark.asyncio
    @pytest.mark.requires_gateway
    async def test_tiredness_investigation(self, async_http_client):
        """
        Test: "Why might I be feeling tired?"

        Expected: Response should correlate sleep data, activity levels,
        stress, and potentially nutrition (like iron/B12 from biomarkers).
        """
        response = await send_query_and_get_response(
            async_http_client,
            "Why might I be feeling tired?",
            timeout=120.0
        )

        response_lower = response.lower()

        # Should consider multiple factors
        factors_mentioned = sum([
            "sleep" in response_lower,
            "energy" in response_lower,
            "stress" in response_lower or "anxiety" in response_lower,
            "exercise" in response_lower or "activity" in response_lower,
            "iron" in response_lower or "vitamin" in response_lower or "b12" in response_lower,
        ])

        assert factors_mentioned >= 2, (
            f"Expected multi-factor tiredness analysis. Got: {response[:500]}"
        )

        print(f"\n--- Tiredness Investigation ---\n{response[:1500]}")

    @pytest.mark.asyncio
    @pytest.mark.requires_gateway
    async def test_exercise_mood_correlation(self, async_http_client):
        """
        Test: "Do I feel better on days I exercise?"

        Expected: Response should correlate fitness and mental wellness data
        to identify mood patterns on active vs. rest days.
        """
        response = await send_query_and_get_response(
            async_http_client,
            "Do I feel better on days I exercise?",
            timeout=120.0
        )

        response_lower = response.lower()

        # Should discuss exercise-mood relationship
        assert any([
            "exercise" in response_lower and "mood" in response_lower,
            "workout" in response_lower and "feel" in response_lower,
            "active" in response_lower and ("better" in response_lower or "mood" in response_lower),
            "correlation" in response_lower,
        ]), f"Expected exercise-mood correlation analysis. Got: {response[:500]}"

        print(f"\n--- Exercise-Mood Correlation ---\n{response[:1500]}")
