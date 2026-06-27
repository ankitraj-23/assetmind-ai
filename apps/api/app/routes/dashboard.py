"""Dashboard routes — live counts over the ingested knowledge base.

Live summary counts (documents, chunks, assets, entities, mentions, knowledge
edges) only exist when ``PERSISTENCE_BACKEND=postgres``. In JSON mode nothing is
persisted, so this endpoint returns a safe, empty response and never touches a
database.
"""

from typing import Any

from fastapi import APIRouter

from app.core import config

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary() -> dict[str, Any]:
    """Return live dashboard counts (empty, DB-free response in JSON mode)."""
    if not config.use_postgres():
        return {
            "documents_indexed": 0,
            "chunks_created": 0,
            "assets_discovered": 0,
            "entities_extracted": 0,
            "asset_mentions": 0,
            "knowledge_edges": 0,
            "recent_documents": [],
            "mode": "json",
            "message": "Live dashboard summary is available in Postgres mode.",
        }
    # Imported lazily so JSON mode never touches the database layer.
    from app.db import repository as repo

    summary = repo.get_dashboard_summary()
    summary["mode"] = "postgres"
    return summary
