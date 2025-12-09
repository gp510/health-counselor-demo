"""
Critical Demo Scenario 3 Test - Real-Time Wearable Data

This test MUST pass for the demo to work. It simulates the exact flow:
1. Wearable simulator sends heart rate data
2. WearableListenerAgent processes it
3. User asks "What's my current heart rate?"
4. get_current_metrics returns the live reading

If this test fails, the demo WILL fail.
"""

import pytest
import asyncio
import os
import tempfile
from unittest.mock import MagicMock

# Import the actual modules - no mocking
from wearable_listener.lifecycle import (
    WearableListenerState,
    process_wearable_data,
    get_latest_readings,
    get_wearable_listener_status,
)
from wearable_listener.tools import get_current_metrics
import wearable_listener.lifecycle as lifecycle


class TestDemoScenario3CriticalPath:
    """
    CRITICAL: These tests must pass for Demo Scenario 3 to work.

    Demo Scenario 3: Real-Time Wearable Data
    - User asks: "What's my current heart rate?"
    - System returns: Live reading from wearable (e.g., "85 bpm")
    """

    @pytest.fixture
    def demo_setup(self):
        """Set up a fresh wearable listener state for demo."""
        # Save original state
        original_state = lifecycle._state

        # Create fresh state with listener running
        lifecycle._state = WearableListenerState()
        lifecycle._state.running = True

        # Create temp notification file
        fd, notification_file = tempfile.mkstemp(suffix=".log")
        os.close(fd)
        lifecycle._state.notification_file = notification_file

        yield lifecycle._state

        # Cleanup
        lifecycle._state = original_state
        if os.path.exists(notification_file):
            os.unlink(notification_file)

    @pytest.mark.asyncio
    async def test_critical_demo_flow_heart_rate_query(self, demo_setup):
        """
        CRITICAL TEST: Simulates exact demo scenario.

        This is what happens when user asks "What's my current heart rate?"
        If this fails, the demo fails.
        """
        # Step 1: Simulate wearable sending heart rate data
        # (This is what wearable_simulator.py does)
        heart_rate_event = {
            "event_id": "DEMO-HR-001",
            "data_type": "heart_rate",
            "value": 85,
            "unit": "bpm",
            "timestamp": "2024-12-08T15:45:00Z",
            "source_device": "Apple Watch",
            "alert_level": "normal",
        }

        mock_context = MagicMock()
        mock_context.pending_events = []

        # Process the event (this stores it in latest_readings)
        process_wearable_data(heart_rate_event, mock_context)

        # Step 2: Verify get_latest_readings has the data
        readings = get_latest_readings()
        assert "heart_rate" in readings, "FATAL: Heart rate not stored in latest_readings"
        assert readings["heart_rate"]["value"] == 85, "FATAL: Heart rate value incorrect"

        # Step 3: Call get_current_metrics (this is what the agent calls)
        result = await get_current_metrics()

        # Step 4: Verify the response is what demo expects
        assert result["status"] == "success", f"FATAL: Status is '{result['status']}', expected 'success'. Message: {result.get('message')}"
        assert "heart_rate" in result["metrics"], "FATAL: heart_rate not in metrics response"
        assert result["metrics"]["heart_rate"]["value"] == 85, "FATAL: Heart rate value not returned correctly"
        assert "Current readings" in result["message"], f"FATAL: Wrong message format: {result['message']}"

        print(f"\n✅ DEMO SCENARIO 3 VERIFIED: Heart rate = {result['metrics']['heart_rate']['value']} bpm")

    @pytest.mark.asyncio
    async def test_critical_listener_must_be_running(self, demo_setup):
        """
        CRITICAL: Listener state must report running=True for demo to work.
        """
        status = get_wearable_listener_status()

        assert status["running"] is True, "FATAL: Listener not running - demo will fail"
        print("\n✅ Wearable listener is running")

    @pytest.mark.asyncio
    async def test_critical_no_data_gives_helpful_message(self, demo_setup):
        """
        CRITICAL: When no data yet, response must guide user, not show error.

        Clear latest_readings and verify we get "waiting_for_data" not an error.
        """
        # Clear any existing readings
        lifecycle._state.latest_readings = {}

        result = await get_current_metrics()

        # Must NOT be an error - should be waiting_for_data
        assert result["status"] == "waiting_for_data", f"FATAL: Expected 'waiting_for_data', got '{result['status']}'"
        assert "user_guidance" in result, "FATAL: No user_guidance in response"
        assert "hasn't received any data" in result["message"], f"FATAL: Wrong message: {result['message']}"

        print(f"\n✅ No-data state handled correctly: {result['status']}")

    @pytest.mark.asyncio
    async def test_critical_elevated_heart_rate_flagged(self, demo_setup):
        """
        CRITICAL: Elevated heart rate during workout must be flagged.

        Demo shows workout scenario where HR goes elevated.
        """
        elevated_hr_event = {
            "event_id": "DEMO-HR-002",
            "data_type": "heart_rate",
            "value": 115,
            "unit": "bpm",
            "timestamp": "2024-12-08T15:46:00Z",
            "source_device": "Apple Watch",
            "alert_level": "elevated",
        }

        mock_context = MagicMock()
        mock_context.pending_events = []

        process_wearable_data(elevated_hr_event, mock_context)

        result = await get_current_metrics()

        assert result["status"] == "success"
        assert result["metrics"]["heart_rate"]["value"] == 115
        assert result["metrics"]["heart_rate"]["alert_level"] == "elevated"
        assert "Alerts" in result["message"], f"FATAL: Elevated HR not flagged in message: {result['message']}"

        print(f"\n✅ Elevated heart rate (115 bpm) correctly flagged")

    @pytest.mark.asyncio
    async def test_critical_multiple_metrics_returned(self, demo_setup):
        """
        CRITICAL: When multiple metrics exist, all should be returned.
        """
        mock_context = MagicMock()
        mock_context.pending_events = []

        # Send heart rate
        process_wearable_data({
            "event_id": "DEMO-HR-003",
            "data_type": "heart_rate",
            "value": 78,
            "unit": "bpm",
            "timestamp": "2024-12-08T15:47:00Z",
            "source_device": "Apple Watch",
            "alert_level": "normal",
        }, mock_context)

        # Send steps
        process_wearable_data({
            "event_id": "DEMO-STEPS-001",
            "data_type": "steps",
            "value": 4532,
            "unit": "steps",
            "timestamp": "2024-12-08T15:47:00Z",
            "source_device": "Apple Watch",
            "alert_level": "normal",
        }, mock_context)

        result = await get_current_metrics()

        assert result["status"] == "success"
        assert len(result["data_types"]) == 2, f"FATAL: Expected 2 data types, got {len(result['data_types'])}"
        assert "heart_rate" in result["data_types"]
        assert "steps" in result["data_types"]

        print(f"\n✅ Multiple metrics returned: {result['data_types']}")


class TestRuntimeStateSimulation:
    """
    Tests that simulate actual runtime states.

    These tests verify behavior when the system is in various states
    that occur during actual demo execution.
    """

    @pytest.mark.asyncio
    async def test_uninitialized_state_no_crash(self):
        """
        CRITICAL: If agent not initialized, must return helpful message, not crash.

        This simulates what happens if initialize_wearable_listener wasn't called.
        """
        import wearable_listener.lifecycle as lifecycle

        # Save and create uninitalized state
        original_state = lifecycle._state
        lifecycle._state = WearableListenerState()  # Fresh state, running=False

        try:
            result = await get_current_metrics()

            # Must NOT crash
            assert result is not None, "FATAL: get_current_metrics returned None"
            assert result["status"] == "listener_not_running", f"FATAL: Wrong status: {result['status']}"
            assert "user_guidance" in result, "FATAL: No user_guidance for uninitialized state"

            print(f"\n✅ Uninitialized state handled: {result['status']}")
            print(f"   User guidance: {result['user_guidance'][:50]}...")

        finally:
            lifecycle._state = original_state

    @pytest.mark.asyncio
    async def test_initialized_but_no_events_yet(self):
        """
        CRITICAL: Right after initialization, before any events, should be waiting_for_data.

        This is the state right after sam run starts but before simulator sends data.
        """
        import wearable_listener.lifecycle as lifecycle

        original_state = lifecycle._state

        # Simulate post-init state
        lifecycle._state = WearableListenerState()
        lifecycle._state.running = True  # Agent is running
        lifecycle._state.latest_readings = {}  # But no events yet

        try:
            result = await get_current_metrics()

            assert result["status"] == "waiting_for_data", f"FATAL: Expected waiting_for_data, got {result['status']}"
            assert "user_guidance" in result
            assert "wearable simulator" in result["message"].lower() or "received" in result["message"].lower()

            print(f"\n✅ No-events state handled: {result['status']}")

        finally:
            lifecycle._state = original_state


class TestDemoConfigSafety:
    """Guardrails for demo configuration strings."""

    def test_wearable_listener_instructions_have_no_goal_placeholder(self):
        """
        CRITICAL: Wearable Listener instructions must not reference {goal_name}
        placeholder (breaks ADK session injection).
        """
        from pathlib import Path

        yaml_text = Path("configs/agents/wearable-listener-agent.yaml").read_text()
        assert "{goal_name}" not in yaml_text, "FATAL: Remove {goal_name} placeholder from wearable-listener instructions"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
