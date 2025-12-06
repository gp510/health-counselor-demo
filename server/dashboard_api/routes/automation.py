"""Automation API routes.

Provides endpoints for scheduled report generation and automation status.
"""
import asyncio
from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

from src.automation.scheduler import report_scheduler, ReportStatus

router = APIRouter(prefix="/api/automation", tags=["Automation"])


# ============================================================================
# Response Models
# ============================================================================


class ReportType(str, Enum):
    """Available report types."""

    EXECUTIVE_SUMMARY = "executive_summary"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_TRENDS = "weekly_trends"


class ReportResponse(BaseModel):
    """Response model for a generated report."""

    id: str
    report_type: str
    content: str
    generated_at: str
    status: str
    generation_time_seconds: float
    error: Optional[str] = None


class ReportStatusResponse(BaseModel):
    """Response model for report generation status."""

    id: str
    report_type: str
    status: str
    generated_at: str
    generation_time_seconds: float
    error: Optional[str] = None


class SchedulerStatusResponse(BaseModel):
    """Response model for scheduler status."""

    gateway_url: str
    cached_reports: int
    cache_size: int
    current_job: Optional[dict] = None
    scheduler_running: bool
    report_types: List[str]


class GenerateReportRequest(BaseModel):
    """Request model for generating a report."""

    report_type: ReportType = ReportType.EXECUTIVE_SUMMARY
    custom_prompt: Optional[str] = None


# ============================================================================
# Report Generation Endpoints
# ============================================================================


@router.post("/reports/generate", response_model=ReportResponse)
async def generate_report(
    report_type: ReportType = Query(
        ReportType.EXECUTIVE_SUMMARY,
        description="Type of health report to generate"
    ),
    custom_prompt: Optional[str] = Query(
        None,
        description="Custom prompt (overrides report_type)"
    ),
):
    """
    Generate a health report by invoking the orchestrator.

    This endpoint triggers the HealthCounselorOrchestrator to query all
    health agents and generate a comprehensive health summary.

    Report types:
    - executive_summary: Full health overview with recommendations
    - daily_summary: Today's health highlights and metrics
    - weekly_trends: Week-over-week analysis and patterns

    Note: Report generation can take 30-120 seconds depending on complexity.
    """
    try:
        report = await report_scheduler.generate_report(
            report_type=report_type.value,
            custom_prompt=custom_prompt,
        )
        return ReportResponse(**report.to_dict())
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Report generation failed: {str(e)}"
        )


@router.post("/reports/generate-async")
async def generate_report_async(
    background_tasks: BackgroundTasks,
    report_type: ReportType = Query(
        ReportType.EXECUTIVE_SUMMARY,
        description="Type of health report to generate"
    ),
    custom_prompt: Optional[str] = Query(
        None,
        description="Custom prompt (overrides report_type)"
    ),
):
    """
    Start asynchronous report generation.

    Returns immediately with a job ID. Use /reports/status to check progress
    and /reports/latest to retrieve the completed report.

    This is useful when you don't want to wait for the full generation time.
    """
    async def generate_in_background():
        await report_scheduler.generate_report(
            report_type=report_type.value,
            custom_prompt=custom_prompt,
        )

    background_tasks.add_task(
        lambda: asyncio.run(generate_in_background())
    )

    return {
        "status": "started",
        "report_type": report_type.value,
        "message": "Report generation started. Check /reports/status for progress.",
    }


# ============================================================================
# Report Retrieval Endpoints
# ============================================================================


@router.get("/reports/latest", response_model=Optional[ReportResponse])
async def get_latest_report(
    report_type: Optional[ReportType] = Query(
        None,
        description="Filter by report type (optional)"
    ),
):
    """
    Get the most recent cached report.

    Returns the latest completed report from the cache.
    Optionally filter by report type.
    """
    type_filter = report_type.value if report_type else None
    report = report_scheduler.get_latest_report(report_type=type_filter)

    if not report:
        return None

    return ReportResponse(**report.to_dict())


@router.get("/reports/history", response_model=List[ReportStatusResponse])
async def get_report_history():
    """
    Get all cached reports.

    Returns a list of all reports in the cache, ordered from newest to oldest.
    Only includes metadata (not full content) for efficiency.
    """
    reports = report_scheduler.get_all_reports()
    return [
        ReportStatusResponse(
            id=r["id"],
            report_type=r["report_type"],
            status=r["status"],
            generated_at=r["generated_at"],
            generation_time_seconds=r["generation_time_seconds"],
            error=r.get("error"),
        )
        for r in reports
    ]


@router.get("/reports/{report_id}", response_model=Optional[ReportResponse])
async def get_report_by_id(report_id: str):
    """
    Get a specific report by ID.

    Returns the full report content if found in cache.
    """
    for report_dict in report_scheduler.get_all_reports():
        if report_dict["id"] == report_id:
            return ReportResponse(**report_dict)

    raise HTTPException(
        status_code=404,
        detail=f"Report {report_id} not found in cache"
    )


# ============================================================================
# Status Endpoints
# ============================================================================


@router.get("/reports/status")
async def get_generation_status():
    """
    Get the current report generation status.

    Returns information about any currently running generation job
    and recent job history.
    """
    current = report_scheduler.get_current_job()
    history = report_scheduler.get_all_reports()[:5]  # Last 5 reports

    return {
        "current_job": current,
        "recent_reports": [
            {
                "id": r["id"],
                "report_type": r["report_type"],
                "status": r["status"],
                "generated_at": r["generated_at"],
                "generation_time_seconds": r["generation_time_seconds"],
            }
            for r in history
        ],
    }


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status():
    """
    Get the automation scheduler status.

    Returns information about the scheduler configuration,
    cached reports, and current job status.
    """
    status = report_scheduler.get_status()
    return SchedulerStatusResponse(**status)


# ============================================================================
# Scheduler Control Endpoints
# ============================================================================


@router.post("/scheduler/start")
async def start_scheduler(
    interval_hours: int = Query(
        24,
        ge=1,
        le=168,
        description="Hours between automatic report generations"
    ),
):
    """
    Start the background report scheduler.

    Once started, the scheduler will automatically generate executive
    summary reports at the specified interval.

    Note: For demo purposes, you might want shorter intervals (1-4 hours).
    """
    report_scheduler.start_scheduler(interval_hours=interval_hours)
    return {
        "status": "started",
        "interval_hours": interval_hours,
        "message": f"Scheduler started. Reports will be generated every {interval_hours} hours.",
    }


@router.post("/scheduler/stop")
async def stop_scheduler():
    """
    Stop the background report scheduler.

    Cancels any pending scheduled report generation.
    Does not affect currently running jobs.
    """
    report_scheduler.stop_scheduler()
    return {
        "status": "stopped",
        "message": "Scheduler stopped. No more automatic reports will be generated.",
    }


# ============================================================================
# Report Types Info
# ============================================================================


@router.get("/reports/types")
async def get_report_types():
    """
    Get available report types and their descriptions.

    Returns information about each report type including
    the prompt template used.
    """
    prompts = report_scheduler.REPORT_PROMPTS
    return {
        "types": [
            {
                "id": report_type,
                "name": report_type.replace("_", " ").title(),
                "description": prompt.split("\n")[0],  # First line as description
            }
            for report_type, prompt in prompts.items()
        ]
    }
