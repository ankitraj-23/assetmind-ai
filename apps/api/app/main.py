"""PlantMind AI — FastAPI application entry point.

Minimal backend skeleton. Only a health check is implemented at this stage.
"""

from fastapi import FastAPI

app = FastAPI(title="PlantMind AI API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for the API service."""
    return {"status": "ok", "service": "plantmind-ai-api"}
