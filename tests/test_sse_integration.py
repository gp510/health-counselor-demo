"""
Integration tests for SSE alert streaming.

Tests the full flow:
1. Alert published via POST /api/health/alerts/automation/test
2. Alert appears in SSE stream at /api/health/alerts/stream
3. Alert appears in history at /api/health/alerts/automation/history

Requires Dashboard API running on port 8082.

Usage:
    # Start the Dashboard API first:
    python -m uvicorn server.dashboard_api.main:app --port 8082

    # Run this test:
    pytest tests/test_sse_integration.py -v
"""
import asyncio
import httpx
import pytest
import json
import uuid
from datetime import datetime


# Dashboard API URL
API_BASE = "http://localhost:8082"


def is_api_running() -> bool:
    """Check if Dashboard API is running."""
    try:
        response = httpx.get(f"{API_BASE}/api/health/summary", timeout=2.0)
        return response.status_code == 200
    except (httpx.ConnectError, httpx.ReadTimeout):
        return False


@pytest.fixture(scope="module")
def api_client():
    """Create HTTP client for API requests."""
    with httpx.Client(base_url=API_BASE, timeout=10.0) as client:
        yield client


class TestSSEAlertFlow:
    """Test SSE alert streaming functionality."""

    @pytest.mark.skipif(not is_api_running(), reason="Dashboard API not running on port 8082")
    def test_publish_test_alert(self, api_client):
        """Test that we can publish a test alert."""
        unique_msg = f"Test alert {uuid.uuid4().hex[:8]}"

        response = api_client.post(
            "/api/health/alerts/automation/test",
            params={
                "alert_type": "anomaly_detected",
                "message": unique_msg,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "published"
        assert "alert_id" in data

    @pytest.mark.skipif(not is_api_running(), reason="Dashboard API not running on port 8082")
    def test_alert_appears_in_history(self, api_client):
        """Test that published alerts appear in history."""
        # Publish a unique alert
        unique_msg = f"History test {uuid.uuid4().hex[:8]}"

        response = api_client.post(
            "/api/health/alerts/automation/test",
            params={
                "alert_type": "goal_achieved",
                "message": unique_msg,
            }
        )
        assert response.status_code == 200
        published_id = response.json()["alert_id"]

        # Check history
        response = api_client.get("/api/health/alerts/automation/history")
        assert response.status_code == 200
        history = response.json()

        # Find our alert in history
        found = any(alert["id"] == published_id for alert in history)
        assert found, f"Alert {published_id} not found in history"

    @pytest.mark.skipif(not is_api_running(), reason="Dashboard API not running on port 8082")
    def test_automation_stats(self, api_client):
        """Test that automation stats endpoint works."""
        response = api_client.get("/api/health/alerts/automation/stats")
        assert response.status_code == 200
        stats = response.json()

        # Should have expected keys
        assert "total_published" in stats
        assert "current_subscribers" in stats
        assert "history_size" in stats

    @pytest.mark.skipif(not is_api_running(), reason="Dashboard API not running on port 8082")
    @pytest.mark.asyncio
    async def test_sse_stream_receives_alert(self):
        """Test that SSE stream receives published alerts in real-time."""
        unique_msg = f"SSE test {uuid.uuid4().hex[:8]}"
        received_alerts = []
        connection_ready = asyncio.Event()

        async def subscribe_and_wait():
            """Subscribe to SSE and wait for alerts."""
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                async with client.stream(
                    "GET",
                    f"{API_BASE}/api/health/alerts/stream?include_history=false"
                ) as response:
                    # Signal that connection is established
                    connection_ready.set()
                    # Read for up to 10 seconds or until we get our alert
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                alert = json.loads(line[6:])
                                received_alerts.append(alert)
                                if unique_msg in alert.get("message", ""):
                                    return True
                            except json.JSONDecodeError as e:
                                print(f"[DEBUG] Failed to parse SSE line: {line}, error: {e}")
                                continue
                        # Give up after 10 alerts if we haven't found ours
                        if len(received_alerts) >= 10:
                            break
            return False

        # Start SSE listener in background
        listener_task = asyncio.create_task(subscribe_and_wait())

        # Wait for connection to be established (not just time-based)
        try:
            await asyncio.wait_for(connection_ready.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            listener_task.cancel()
            pytest.fail("SSE connection failed to establish")

        # Small additional delay for subscriber registration
        await asyncio.sleep(0.2)

        # Publish our test alert
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/api/health/alerts/automation/test",
                params={
                    "alert_type": "anomaly_detected",
                    "message": unique_msg,
                }
            )
            assert response.status_code == 200

        # Wait for listener with timeout
        try:
            found = await asyncio.wait_for(listener_task, timeout=5.0)
            assert found, f"Alert with message '{unique_msg}' not received via SSE"
        except asyncio.TimeoutError:
            listener_task.cancel()
            pytest.fail(f"SSE stream timeout. Received alerts: {received_alerts}")


class TestViteProxySSE:
    """Test SSE through Vite proxy (port 3000)."""

    VITE_URL = "http://localhost:3000"

    def is_vite_running(self) -> bool:
        """Check if Vite dev server is running."""
        try:
            response = httpx.get(f"{self.VITE_URL}/", timeout=2.0)
            return response.status_code == 200
        except (httpx.ConnectError, httpx.ReadTimeout):
            return False

    @pytest.mark.skipif(True, reason="Run manually when Vite is running")
    @pytest.mark.asyncio
    async def test_sse_through_vite_proxy(self):
        """Test that SSE works through Vite's proxy."""
        if not self.is_vite_running():
            pytest.skip("Vite dev server not running on port 3000")

        received_alerts = []

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            # Try to connect to SSE through Vite proxy
            try:
                async with client.stream(
                    "GET",
                    f"{self.VITE_URL}/api/health/alerts/stream"
                ) as response:
                    # Check headers - SSE should have specific content type
                    content_type = response.headers.get("content-type", "")
                    assert "text/event-stream" in content_type, \
                        f"Expected text/event-stream, got {content_type}"

                    # Read a few lines
                    count = 0
                    async for line in response.aiter_lines():
                        count += 1
                        if count > 5:
                            break
                        if line.startswith("data: "):
                            alert = json.loads(line[6:])
                            received_alerts.append(alert)

            except httpx.ReadTimeout:
                pytest.fail("SSE connection timed out through Vite proxy")


if __name__ == "__main__":
    # Quick manual test
    import sys

    if not is_api_running():
        print("ERROR: Dashboard API not running on port 8082")
        print("Start it with: python -m uvicorn server.dashboard_api.main:app --port 8082")
        sys.exit(1)

    print("Dashboard API is running. Running tests...")
    pytest.main([__file__, "-v"])
