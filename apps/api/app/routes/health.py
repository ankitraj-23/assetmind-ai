"""Health check route."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for the API service."""
    return {"status": "ok", "service": settings.service_name}
