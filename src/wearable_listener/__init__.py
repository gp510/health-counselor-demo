"""
Wearable Listener Module.

Handles real-time fitness data streaming from wearable devices via Solace event mesh.
"""

from .lifecycle import (
    initialize_wearable_listener,
    cleanup_wearable_listener,
    get_wearable_listener_status,
    get_pending_events,
)
from .tools import (
    check_pending_events,
    get_listener_health,
    format_alert_for_notification,
)

__all__ = [
    "initialize_wearable_listener",
    "cleanup_wearable_listener",
    "get_wearable_listener_status",
    "get_pending_events",
    "check_pending_events",
    "get_listener_health",
    "format_alert_for_notification",
]
