"""API route modules."""
from .biomarkers import router as biomarkers_router
from .fitness import router as fitness_router
from .diet import router as diet_router
from .wellness import router as wellness_router
from .summary import router as summary_router
from .alerts import router as alerts_router

__all__ = [
    "biomarkers_router",
    "fitness_router",
    "diet_router",
    "wellness_router",
    "summary_router",
    "alerts_router",
]
