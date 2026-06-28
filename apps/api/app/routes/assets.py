"""Asset registry routes — read-only views over extracted equipment assets.

Assets are produced by deterministic equipment-tag extraction during ingestion
and only exist when ``PERSISTENCE_BACKEND=postgres``. In JSON mode no assets are
persisted, so these endpoints return safe, empty responses and never touch a
database.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

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


@router.get("/{tag}/mentions")
def get_asset_mentions(tag: str) -> dict[str, Any]:
    """Return evidence-rich mentions of an asset (case-insensitive tag).

    Each mention carries the source document/chunk text plus a ``citation``
    object matching the existing search citation style, so the backend can show
    where an asset is discussed with the same provenance rendering as search.

    In JSON mode no assets are persisted, so this returns an empty, DB-free
    response (``count`` 0) rather than a 404.
    """
    if not config.use_postgres():
        return {"tag": tag, "count": 0, "mentions": []}
    from app.db import repository as repo

    mentions = repo.list_asset_mentions_by_tag(tag)
    return {"tag": tag, "count": len(mentions), "mentions": mentions}


@router.get("/{tag}/documents")
def get_asset_documents(tag: str) -> dict[str, Any]:
    """Return the unique documents that mention an asset (case-insensitive tag).

    In JSON mode no asset/document links are persisted, so this returns a safe,
    empty, DB-free response rather than touching a database.
    """
    if not config.use_postgres():
        return {
            "tag": tag,
            "count": 0,
            "documents": [],
            "mode": "json",
            "message": "Asset document links are available in Postgres mode.",
        }
    from app.db import repository as repo

    documents = repo.list_asset_documents_by_tag(tag)
    return {"tag": tag, "count": len(documents), "documents": documents}


@router.get("/{tag}/timeline")
def get_asset_timeline(tag: str) -> dict[str, Any]:
    """Return derived timeline events for an asset (case-insensitive tag).

    In JSON mode no asset mentions are persisted, so this returns a safe, empty,
    DB-free response rather than touching a database.
    """
    if not config.use_postgres():
        return {
            "tag": tag,
            "count": 0,
            "events": [],
            "mode": "json",
            "message": "Asset timeline is available in Postgres mode.",
        }
    from app.db import repository as repo

    events = repo.list_asset_timeline_by_tag(tag)
    return {"tag": tag, "count": len(events), "events": events}


@router.get("/{tag}/facts")
def get_asset_facts(tag: str) -> dict[str, Any]:
    """Return a compact fact sheet for an asset (case-insensitive tag).

    Responds with 404 when the asset is unknown, or when running in JSON mode
    where assets are not persisted (mirrors ``GET /assets/{tag}``).
    """
    if not config.use_postgres():
        raise HTTPException(
            status_code=404,
            detail="Assets are only available when PERSISTENCE_BACKEND=postgres.",
        )
    from app.db import repository as repo

    facts = repo.get_asset_facts_by_tag(tag)
    if facts is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return facts


# Declared before ``/{tag}/graph`` so the extra ``/summary`` segment is matched
# explicitly and never shadowed by the broader graph (or ``/{tag}``) route.
@router.get("/{tag}/graph/summary")
def get_asset_graph_summary(tag: str) -> dict[str, Any]:
    """Return aggregate counts for an asset's derived knowledge graph.

    Responds with 404 when the asset is unknown. In JSON mode no asset mentions
    are persisted, so this returns a safe, empty, DB-free response.
    """
    if not config.use_postgres():
        return {
            "asset": None,
            "asset_tag": tag,
            "document_count": 0,
            "chunk_count": 0,
            "entity_count": 0,
            "edge_count": 0,
            "relation_type_counts": {},
            "top_documents": [],
            "mode": "json",
            "message": "Asset graph summary is available in Postgres mode.",
        }
    from app.db import repository as repo

    summary = repo.get_asset_graph_summary_by_tag(tag)
    if summary is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return summary


@router.get("/{tag}/graph")
def get_asset_graph(
    tag: str,
    include_chunks: bool = True,
    relation_type: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return a derived knowledge graph for an asset (case-insensitive tag).

    Optional query params filter the graph: ``include_chunks=false`` drops chunk
    nodes/edges, and ``relation_type`` keeps only edges of that relation. Responds
    with 404 when the asset is unknown. In JSON mode no asset mentions are
    persisted, so this returns a safe, empty, DB-free graph response.
    """
    if not config.use_postgres():
        return {
            "asset": None,
            "nodes": [],
            "edges": [],
            "counts": {"nodes": 0, "edges": 0},
            "mode": "json",
            "message": "Asset graph is available in Postgres mode.",
        }
    from app.db import repository as repo

    graph = repo.get_asset_graph_by_tag(
        tag, include_chunks=include_chunks, relation_type=relation_type
    )
    if graph is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return graph
