"""Health Counselor Automation Module.

Provides scheduled and triggered automation for health report generation
and proactive health monitoring.
"""

from .scheduler import ReportScheduler, report_scheduler

__all__ = ["ReportScheduler", "report_scheduler"]
