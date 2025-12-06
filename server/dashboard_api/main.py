"""Health Counselor Dashboard API - FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routes import biomarkers, fitness, diet, wellness, summary, alerts, insights

settings = get_settings()

app = FastAPI(
    title="Health Counselor Dashboard API",
    description="Read-only API for health metrics visualization",
    version="1.0.0",
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Include routers
app.include_router(summary.router)
app.include_router(biomarkers.router)
app.include_router(fitness.router)
app.include_router(diet.router)
app.include_router(wellness.router)
app.include_router(alerts.router)
app.include_router(insights.router)


@app.get("/health")
async def health_check():
    """Health check endpoint for the API."""
    return {"status": "healthy", "service": "dashboard-api"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server.dashboard_api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
