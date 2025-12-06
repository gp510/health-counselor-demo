"""Health alert models."""
from pydantic import BaseModel
from typing import Literal, Optional

AlertLevel = Literal["info", "warning", "critical"]
AlertDomain = Literal["biomarkers", "fitness", "diet", "wellness", "system"]


class HealthAlert(BaseModel):
    """Health alert notification."""

    id: str
    level: AlertLevel
    title: str
    message: str
    domain: AlertDomain
    timestamp: str
    dismissed: bool = False
    data: Optional[dict] = None
