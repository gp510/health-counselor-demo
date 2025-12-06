"""AI-powered health insights API routes.

These endpoints proxy requests to the WebUI gateway to trigger
the HealthCounselorOrchestrator for AI-generated insights.
"""
import os
import json
import uuid
import asyncio
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/health", tags=["Health Insights"])

# Configuration - WebUI gateway runs on FASTAPI_PORT (default 8000)
GATEWAY_URL = os.environ.get("WEBUI_GATEWAY_URL", "http://localhost:8000")
GATEWAY_TIMEOUT = 120.0  # seconds


class InsightResponse(BaseModel):
    """Response model for health insights."""
    content: str
    generated_at: str


# Domain-specific prompts for trend analysis
DOMAIN_PROMPTS = {
    "biomarker": "Analyze my biomarker trends and provide interpretation of recent lab results. Focus on what's improving, what needs attention, and any patterns you observe.",
    "fitness": "Analyze my fitness trends including activity levels, sleep patterns, and heart rate data. Tell me what's going well and where I can improve.",
    "diet": "Analyze my nutrition trends including calories, macros, and eating patterns. Highlight positive habits and areas for improvement.",
    "wellness": "Analyze my mental wellness trends including mood, stress, and energy patterns. Be supportive and identify what activities seem to help."
}

EXECUTIVE_SUMMARY_PROMPT = """Generate an executive health summary for me.

Query all health agents (BiomarkerAgent, FitnessAgent, DietAgent, MentalWellnessAgent) for their trend analysis, then synthesize the findings into a comprehensive overview that includes:
- Overall health status assessment
- Top 3 strengths (what's going well)
- Top 3 areas for attention (opportunities for improvement)
- Cross-domain insights (patterns that connect different health areas)
- Specific, actionable recommendations
- When to consult a healthcare professional

Be encouraging but honest. Lead with positives."""


@router.get("/insights/executive-summary", response_model=InsightResponse)
async def get_executive_summary():
    """
    Generate an AI-powered executive health summary.

    Triggers the HealthCounselorOrchestrator to query all specialized
    health agents and synthesize a comprehensive health overview.

    This is an on-demand operation that may take 30-60 seconds.
    """
    return await _get_ai_insight(EXECUTIVE_SUMMARY_PROMPT)


@router.get("/insights/{domain}", response_model=InsightResponse)
async def get_domain_insights(domain: str):
    """
    Generate AI-powered insights for a specific health domain.

    Args:
        domain: One of 'biomarker', 'fitness', 'diet', 'wellness'

    Returns:
        AI-generated narrative insights for the requested domain.
    """
    if domain not in DOMAIN_PROMPTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain '{domain}'. Must be one of: {list(DOMAIN_PROMPTS.keys())}"
        )

    return await _get_ai_insight(DOMAIN_PROMPTS[domain])


async def _get_ai_insight(prompt: str) -> InsightResponse:
    """Send a prompt to the orchestrator via WebUI gateway and collect the response via SSE."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(GATEWAY_TIMEOUT)) as client:
            # Step 1: Send message to gateway and get task ID
            request_id = f"insight-{uuid.uuid4()}"
            message_id = f"msg-{uuid.uuid4()}"

            response = await client.post(
                f"{GATEWAY_URL}/api/v1/message:send",
                json={
                    "id": request_id,
                    "jsonrpc": "2.0",
                    "method": "message/send",
                    "params": {
                        "message": {
                            "messageId": message_id,
                            "role": "user",
                            "parts": [{"kind": "text", "text": prompt}],
                            "metadata": {
                                "agent_name": "HealthCounselorOrchestrator"
                            }
                        }
                    }
                }
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"Gateway returned status {response.status_code}: {response.text}"
                )

            result = response.json()

            # Extract task ID from response
            task_id = result.get("result", {}).get("id")
            if not task_id:
                raise HTTPException(
                    status_code=502,
                    detail="No task ID returned from gateway"
                )

            # Step 2: Subscribe to SSE stream for the task response
            content = await _collect_sse_response(client, task_id)

            if not content:
                raise HTTPException(
                    status_code=502,
                    detail="No content received from AI agent"
                )

            return InsightResponse(
                content=content,
                generated_at=datetime.utcnow().isoformat() + "Z"
            )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Gateway request timed out. The AI analysis is taking longer than expected."
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to gateway. Ensure the WebUI gateway is running (sam run configs/gateways/webui.yaml)."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error communicating with gateway: {str(e)}"
        )


async def _collect_sse_response(client: httpx.AsyncClient, task_id: str) -> Optional[str]:
    """Subscribe to SSE stream and collect the complete response."""
    full_response = ""

    async with client.stream(
        "GET",
        f"{GATEWAY_URL}/api/v1/sse/subscribe/{task_id}",
        headers={"Accept": "text/event-stream"},
    ) as response:
        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"SSE subscription failed with status {response.status_code}"
            )

        event_type = None
        event_data = ""

        async for line in response.aiter_lines():
            line = line.strip()

            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                event_data = line[5:].strip()
            elif line == "" and event_data:
                # End of event - process it
                try:
                    data = json.loads(event_data)

                    # Handle final_response event
                    if event_type == "final_response":
                        state = data.get("result", {}).get("status", {}).get("state")
                        if state == "completed":
                            # Extract text from status.message.parts
                            parts = data.get("result", {}).get("status", {}).get("message", {}).get("parts", [])
                            for part in parts:
                                if part.get("kind") == "text" and part.get("text"):
                                    return part["text"]
                        elif state == "failed":
                            error_parts = data.get("result", {}).get("status", {}).get("message", {}).get("parts", [])
                            error_text = error_parts[0].get("text", "Task failed") if error_parts else "Task failed"
                            raise HTTPException(status_code=502, detail=f"AI agent error: {error_text}")

                    # Handle task_artifact event (for streaming responses)
                    elif event_type == "task_artifact":
                        artifact = data.get("artifact", {})
                        for part in artifact.get("parts", []):
                            if part.get("kind") == "text" and part.get("text"):
                                full_response += part["text"]

                    # Handle task_status event
                    elif event_type == "task_status":
                        state = data.get("status", {}).get("state")
                        if state == "completed" and full_response:
                            return full_response
                        elif state == "failed":
                            error_parts = data.get("status", {}).get("message", {}).get("parts", [])
                            error_text = error_parts[0].get("text", "Task failed") if error_parts else "Task failed"
                            raise HTTPException(status_code=502, detail=f"AI agent error: {error_text}")

                except json.JSONDecodeError:
                    pass  # Ignore malformed JSON

                # Reset for next event
                event_type = None
                event_data = ""

    return full_response if full_response else None
