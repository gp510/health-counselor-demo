"""Biomarker data models."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


HealthStatus = Literal["normal", "low", "high", "critical"]


class Biomarker(BaseModel):
    """Individual biomarker test result."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    test_id: str
    test_date: str
    test_type: str
    biomarker_name: str
    value: float
    unit: str
    reference_range_low: float
    reference_range_high: float
    status: HealthStatus
    lab_source: str
    notes: Optional[str] = None


class BiomarkerSummary(BaseModel):
    """Aggregated biomarker summary."""

    model_config = ConfigDict(populate_by_name=True)

    latest: list[Biomarker]
    abnormal_count: int = Field(serialization_alias="abnormalCount")
    last_test_date: Optional[str] = Field(
        default=None, serialization_alias="lastTestDate"
    )
