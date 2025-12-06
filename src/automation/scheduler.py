"""
Health Report Scheduler.

Provides scheduled and on-demand generation of health reports
by invoking the HealthCounselorOrchestrator via the WebUI gateway.
"""

import os
import json
import uuid
import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, List, Any

import httpx

logger = logging.getLogger(__name__)


class ReportStatus(str, Enum):
    """Status of a report generation job."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CachedReport:
    """A cached health report."""

    id: str
    report_type: str
    content: str
    generated_at: datetime
    status: ReportStatus
    generation_time_seconds: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "report_type": self.report_type,
            "content": self.content,
            "generated_at": self.generated_at.isoformat(),
            "status": self.status.value,
            "generation_time_seconds": self.generation_time_seconds,
            "error": self.error,
        }


class ReportScheduler:
    """
    Manages scheduled and on-demand health report generation.

    Uses the WebUI gateway to invoke the HealthCounselorOrchestrator
    for generating comprehensive health summaries.

    Features:
    - Manual trigger for immediate report generation
    - Background scheduling for periodic reports (demo purposes)
    - In-memory caching of recent reports
    - Status tracking for long-running report generation
    """

    # Report prompts for different types
    REPORT_PROMPTS = {
        "executive_summary": """Generate an executive health summary.

Query all health agents (BiomarkerAgent, FitnessAgent, DietAgent, MentalWellnessAgent) for their trend analysis, then synthesize the findings into a comprehensive overview that includes:
- Overall health status assessment
- Top 3 strengths (what's going well)
- Top 3 areas for attention (opportunities for improvement)
- Cross-domain insights (patterns that connect different health areas)
- Specific, actionable recommendations
- When to consult a healthcare professional

Be encouraging but honest. Lead with positives.""",
        "daily_summary": """Generate a daily health summary for today.

Focus on:
- Today's activity and fitness metrics
- Today's nutrition highlights
- Today's mood and stress patterns
- Notable health events or alerts from today
- One actionable recommendation for tomorrow

Keep it concise and actionable.""",
        "weekly_trends": """Analyze health trends from the past week.

Compare this week to previous weeks and highlight:
- Key improvements in any health domain
- Areas that may need attention
- Patterns in activity, sleep, nutrition, and mood
- Correlation insights (e.g., how sleep affects mood)

Provide specific data points to support your analysis.""",
    }

    def __init__(
        self,
        gateway_url: Optional[str] = None,
        cache_size: int = 10,
        default_timeout: float = 120.0,
    ):
        """
        Initialize the report scheduler.

        Args:
            gateway_url: URL of the WebUI gateway (default from env)
            cache_size: Maximum number of reports to cache
            default_timeout: Default timeout for report generation
        """
        self.gateway_url = gateway_url or os.getenv(
            "WEBUI_GATEWAY_URL", "http://localhost:8000"
        )
        self.cache_size = cache_size
        self.default_timeout = default_timeout

        # Report cache (most recent first)
        self._reports: List[CachedReport] = []
        self._lock = threading.Lock()

        # Current generation job
        self._current_job: Optional[CachedReport] = None

        # Background scheduler
        self._scheduler_timer: Optional[threading.Timer] = None
        self._scheduler_running = False

        logger.info(
            f"[SCHEDULER] Initialized with gateway={self.gateway_url}, "
            f"cache_size={cache_size}"
        )

    async def generate_report(
        self,
        report_type: str = "executive_summary",
        custom_prompt: Optional[str] = None,
    ) -> CachedReport:
        """
        Generate a health report by invoking the orchestrator.

        Args:
            report_type: Type of report (executive_summary, daily_summary, etc.)
            custom_prompt: Optional custom prompt (overrides report_type)

        Returns:
            CachedReport with the generated content
        """
        # Get prompt
        prompt = custom_prompt or self.REPORT_PROMPTS.get(
            report_type, self.REPORT_PROMPTS["executive_summary"]
        )

        # Create report record
        report = CachedReport(
            id=str(uuid.uuid4()),
            report_type=report_type,
            content="",
            generated_at=datetime.now(timezone.utc),
            status=ReportStatus.GENERATING,
        )

        with self._lock:
            self._current_job = report

        start_time = datetime.now(timezone.utc)
        logger.info(f"[SCHEDULER] Starting report generation: {report_type}")

        try:
            content = await self._call_orchestrator(prompt)

            report.content = content
            report.status = ReportStatus.COMPLETED
            report.generation_time_seconds = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds()

            logger.info(
                f"[SCHEDULER] Report completed in {report.generation_time_seconds:.1f}s"
            )

        except Exception as e:
            report.status = ReportStatus.FAILED
            report.error = str(e)
            report.generation_time_seconds = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds()

            logger.error(f"[SCHEDULER] Report generation failed: {e}")

        finally:
            # Cache the report
            with self._lock:
                self._reports.insert(0, report)
                # Trim cache
                while len(self._reports) > self.cache_size:
                    self._reports.pop()
                self._current_job = None

        return report

    async def _call_orchestrator(self, prompt: str) -> str:
        """
        Call the WebUI gateway to invoke the orchestrator.

        Uses the same approach as the insights API: send message,
        then subscribe to SSE for the response.
        """
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.default_timeout)
        ) as client:
            # Step 1: Send message to gateway
            request_id = f"report-{uuid.uuid4()}"
            message_id = f"msg-{uuid.uuid4()}"

            response = await client.post(
                f"{self.gateway_url}/api/v1/message:send",
                json={
                    "id": request_id,
                    "jsonrpc": "2.0",
                    "method": "message/send",
                    "params": {
                        "message": {
                            "messageId": message_id,
                            "role": "user",
                            "parts": [{"kind": "text", "text": prompt}],
                            "metadata": {"agent_name": "HealthCounselorOrchestrator"},
                        }
                    },
                },
            )

            if response.status_code != 200:
                raise Exception(
                    f"Gateway returned status {response.status_code}: {response.text}"
                )

            result = response.json()
            task_id = result.get("result", {}).get("id")

            if not task_id:
                raise Exception("No task ID returned from gateway")

            # Step 2: Subscribe to SSE stream for response
            content = await self._collect_sse_response(client, task_id)

            if not content:
                raise Exception("No content received from orchestrator")

            return content

    async def _collect_sse_response(
        self, client: httpx.AsyncClient, task_id: str
    ) -> Optional[str]:
        """Subscribe to SSE stream and collect the complete response."""
        full_response = ""

        async with client.stream(
            "GET",
            f"{self.gateway_url}/api/v1/sse/subscribe/{task_id}",
            headers={"Accept": "text/event-stream"},
        ) as response:
            if response.status_code != 200:
                raise Exception(
                    f"SSE subscription failed with status {response.status_code}"
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
                    # Process event
                    try:
                        data = json.loads(event_data)

                        if event_type == "final_response":
                            state = (
                                data.get("result", {}).get("status", {}).get("state")
                            )
                            if state == "completed":
                                parts = (
                                    data.get("result", {})
                                    .get("status", {})
                                    .get("message", {})
                                    .get("parts", [])
                                )
                                for part in parts:
                                    if (
                                        part.get("kind") == "text"
                                        and part.get("text")
                                    ):
                                        return part["text"]
                            elif state == "failed":
                                error_parts = (
                                    data.get("result", {})
                                    .get("status", {})
                                    .get("message", {})
                                    .get("parts", [])
                                )
                                error_text = (
                                    error_parts[0].get("text", "Task failed")
                                    if error_parts
                                    else "Task failed"
                                )
                                raise Exception(f"Orchestrator error: {error_text}")

                        elif event_type == "task_artifact":
                            artifact = data.get("artifact", {})
                            for part in artifact.get("parts", []):
                                if part.get("kind") == "text" and part.get("text"):
                                    full_response += part["text"]

                        elif event_type == "task_status":
                            state = data.get("status", {}).get("state")
                            if state == "completed" and full_response:
                                return full_response
                            elif state == "failed":
                                error_parts = (
                                    data.get("status", {})
                                    .get("message", {})
                                    .get("parts", [])
                                )
                                error_text = (
                                    error_parts[0].get("text", "Task failed")
                                    if error_parts
                                    else "Task failed"
                                )
                                raise Exception(f"Orchestrator error: {error_text}")

                    except json.JSONDecodeError:
                        pass

                    event_type = None
                    event_data = ""

        return full_response if full_response else None

    def get_latest_report(
        self, report_type: Optional[str] = None
    ) -> Optional[CachedReport]:
        """
        Get the most recent cached report.

        Args:
            report_type: Optional filter by report type

        Returns:
            Most recent matching report, or None
        """
        with self._lock:
            for report in self._reports:
                if report_type is None or report.report_type == report_type:
                    return report
            return None

    def get_all_reports(self) -> List[Dict]:
        """Get all cached reports."""
        with self._lock:
            return [r.to_dict() for r in self._reports]

    def get_current_job(self) -> Optional[Dict]:
        """Get the currently running job, if any."""
        with self._lock:
            if self._current_job:
                return self._current_job.to_dict()
            return None

    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        with self._lock:
            return {
                "gateway_url": self.gateway_url,
                "cached_reports": len(self._reports),
                "cache_size": self.cache_size,
                "current_job": (
                    self._current_job.to_dict() if self._current_job else None
                ),
                "scheduler_running": self._scheduler_running,
                "report_types": list(self.REPORT_PROMPTS.keys()),
            }

    def start_scheduler(self, interval_hours: int = 24) -> None:
        """
        Start background report generation scheduler.

        Args:
            interval_hours: Hours between report generations
        """
        if self._scheduler_running:
            logger.warning("[SCHEDULER] Scheduler already running")
            return

        self._scheduler_running = True
        self._schedule_next(interval_hours)
        logger.info(f"[SCHEDULER] Started with interval={interval_hours}h")

    def stop_scheduler(self) -> None:
        """Stop the background scheduler."""
        self._scheduler_running = False
        if self._scheduler_timer:
            self._scheduler_timer.cancel()
            self._scheduler_timer = None
        logger.info("[SCHEDULER] Stopped")

    def _schedule_next(self, interval_hours: int) -> None:
        """Schedule the next report generation."""
        if not self._scheduler_running:
            return

        def run_and_reschedule():
            if not self._scheduler_running:
                return

            # Run async report generation in a new event loop
            try:
                asyncio.run(self.generate_report("executive_summary"))
            except Exception as e:
                logger.error(f"[SCHEDULER] Scheduled report failed: {e}")

            # Schedule next run
            self._schedule_next(interval_hours)

        interval_seconds = interval_hours * 3600
        self._scheduler_timer = threading.Timer(interval_seconds, run_and_reschedule)
        self._scheduler_timer.daemon = True
        self._scheduler_timer.start()


# Global singleton instance
report_scheduler = ReportScheduler()
