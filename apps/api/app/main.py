"""PlantMind AI — FastAPI application entry point.

Minimal backend skeleton. Only a health check is wired up at this stage.
"""

from fastapi import FastAPI

from app.core.config import settings
from app.routes import health

app = FastAPI(title=settings.project_name, version="0.1.0")

app.include_router(health.router)
