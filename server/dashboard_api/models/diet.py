"""Diet data models."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal

MealType = Literal["breakfast", "morning_coffee", "lunch", "afternoon_coffee", "snack", "dinner"]


class DietEntry(BaseModel):
    """Meal log entry."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    meal_id: str
    date: str
    meal_type: MealType
    food_items: str
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    sodium_mg: int
    sugar_g: float
    water_ml: int
    notes: Optional[str] = None


class DietSummary(BaseModel):
    """Aggregated diet summary."""

    model_config = ConfigDict(populate_by_name=True)

    today_calories: int = Field(serialization_alias="todayCalories")
    today_protein: float = Field(serialization_alias="todayProtein")
    today_carbs: float = Field(serialization_alias="todayCarbs")
    today_fat: float = Field(serialization_alias="todayFat")
    today_water: int = Field(serialization_alias="todayWater")
    week_avg_calories: float = Field(serialization_alias="weekAvgCalories")
