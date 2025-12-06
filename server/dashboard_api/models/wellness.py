"""Mental wellness data models."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal

TimeOfDay = Literal["morning", "afternoon", "evening"]
SocialLevel = Literal["low", "medium", "high", "none"]


class MentalWellnessEntry(BaseModel):
    """Mental wellness journal entry."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    entry_id: str
    date: str
    time_of_day: TimeOfDay
    mood_score: int = Field(ge=1, le=10)
    energy_level: int = Field(ge=1, le=10)
    stress_level: int = Field(ge=1, le=10)
    anxiety_level: int = Field(ge=1, le=10)
    sleep_quality_rating: int = Field(ge=1, le=10)
    activities: str
    social_interaction: SocialLevel
    journal_entry: Optional[str] = None
    gratitude_notes: Optional[str] = None
    tags: str


class WellnessSummary(BaseModel):
    """Aggregated mental wellness summary."""

    model_config = ConfigDict(populate_by_name=True)

    latest: Optional[MentalWellnessEntry] = None
    week_avg_mood: float = Field(serialization_alias="weekAvgMood")
    week_avg_stress: float = Field(serialization_alias="weekAvgStress")
    week_avg_energy: float = Field(serialization_alias="weekAvgEnergy")
