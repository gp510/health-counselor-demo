"""Fitness data models."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class FitnessRecord(BaseModel):
    """Daily fitness record from wearable."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    record_id: str
    date: str
    data_source: str
    steps: int
    distance_km: float
    active_minutes: int
    calories_burned: int
    resting_heart_rate: int
    avg_heart_rate: int
    max_heart_rate: int
    sleep_hours: float
    sleep_quality_score: int
    workout_type: Optional[str] = None
    workout_duration_min: int = 0


class FitnessSummary(BaseModel):
    """Aggregated fitness summary."""

    model_config = ConfigDict(populate_by_name=True)

    today: Optional[FitnessRecord] = None
    week_avg_steps: float = Field(serialization_alias="weekAvgSteps")
    week_avg_sleep: float = Field(serialization_alias="weekAvgSleep")
    week_avg_hr: float = Field(serialization_alias="weekAvgHR")
