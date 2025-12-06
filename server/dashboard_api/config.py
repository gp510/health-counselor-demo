"""Application configuration loaded from environment variables."""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Database paths
    data_path: str = os.getenv("DATA_PATH", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

    @property
    def biomarker_db_path(self) -> str:
        return os.path.join(self.data_path, "biomarker.db")

    @property
    def fitness_db_path(self) -> str:
        return os.path.join(self.data_path, "fitness.db")

    @property
    def diet_db_path(self) -> str:
        return os.path.join(self.data_path, "diet.db")

    @property
    def wellness_db_path(self) -> str:
        return os.path.join(self.data_path, "mental_wellness.db")

    # API configuration
    api_host: str = "127.0.0.1"
    api_port: int = 8082

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    class Config:
        env_prefix = "DASHBOARD_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
