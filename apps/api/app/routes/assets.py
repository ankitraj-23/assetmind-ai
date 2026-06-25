"""Asset registry routes — read-only views over extracted equipment assets.

Assets are produced by deterministic equipment-tag extraction during ingestion
and only exist when ``PERSISTENCE_BACKEND=postgres``. In JSON mode no assets are
persisted, so these endpoints return safe, empty responses and never touch a
database.
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from app.core import config

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
def list_assets() -> list[dict[str, Any]]:
    """List extracted equipment assets (empty in JSON mode)."""
    if not config.use_postgres():
        return []
    # Imported lazily so JSON mode never touches the database layer.
    from app.db import repository as repo

    return repo.list_assets()


@router.get("/{tag}")
def get_asset(tag: str) -> dict[str, Any]:
    """Return one asset by tag (case-insensitive).

    Responds with 404 when the asset is unknown, or when running in JSON mode
    where assets are not persisted.
    """
    if not config.use_postgres():
        raise HTTPException(
            status_code=404,
            detail="Assets are only available when PERSISTENCE_BACKEND=postgres.",
        )
    from app.db import repository as repo

    record = repo.get_asset_by_tag(tag)
    if record is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return record
