"""Health summary aggregate model."""
from pydantic import BaseModel, Field, ConfigDict

from .biomarker import BiomarkerSummary
from .fitness import FitnessSummary
from .diet import DietSummary
from .wellness import WellnessSummary


class HealthSummary(BaseModel):
    """Complete health summary across all domains."""

    model_config = ConfigDict(populate_by_name=True)

    biomarkers: BiomarkerSummary
    fitness: FitnessSummary
    diet: DietSummary
    mental_wellness: WellnessSummary = Field(serialization_alias="mentalWellness")
