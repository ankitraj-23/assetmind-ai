"""Backfill missing ``knowledge_edges`` rows from existing ``asset_mentions``.

Asset mentions created before :func:`app.db.repository.create_asset_mention`
started materialising :class:`KnowledgeEdge` rows have no corresponding edges.
This script scans every existing ``asset_mentions`` row and idempotently creates
the same edges ``create_asset_mention`` now creates:

* ``asset -> document`` (``mentioned_in``) when the mention has a document,
* ``asset -> chunk`` (``supported_by_chunk``) when it has a chunk,
* ``asset -> entity`` (``has_entity``) when it has an entity.

It is safe to run repeatedly: :func:`repository.upsert_knowledge_edge` only
inserts an edge when an equivalent one is absent, so reruns create nothing new.
The script never deletes or mutates existing rows and needs no external APIs.

Usage
-----
    cd apps/api
    PERSISTENCE_BACKEND=postgres \
        DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind \
        python -m scripts.backfill_knowledge_edges
"""

from __future__ import annotations

import sys
from uuid import uuid4

from sqlalchemy import func, select

# Force the Postgres backend regardless of any ambient PERSISTENCE_BACKEND.
from app.core.config import settings

settings.persistence_backend = "postgres"

from app.db.models import AssetMention, KnowledgeEdge  # noqa: E402
from app.db.session import (  # noqa: E402
    DatabaseNotConfiguredError,
    get_database_url,
    session_scope,
)

# The tuple that uniquely identifies a knowledge edge, mirroring the uniqueness
# check in :func:`app.db.repository.upsert_knowledge_edge`.
_EdgeKey = tuple[str, str, str, str, str, str | None]


def main() -> int:
    try:
        get_database_url()
    except DatabaseNotConfiguredError as exc:
        print(f"ERROR: {exc}")
        print("Set DATABASE_URL and PERSISTENCE_BACKEND=postgres before running.")
        return 1

    mentions_scanned = 0
    edges_attempted = 0

    with session_scope() as session:
        edges_before = int(
            session.execute(
                select(func.count()).select_from(KnowledgeEdge)
            ).scalar_one()
            or 0
        )

        # Preload every existing edge key once, so the per-mention loop below is
        # pure in-memory set membership instead of a SELECT round-trip per edge.
        # This is what makes the backfill fast after a large CSV/XLSX ingest.
        seen_keys: set[_EdgeKey] = set(
            session.execute(
                select(
                    KnowledgeEdge.source_type,
                    KnowledgeEdge.source_id,
                    KnowledgeEdge.relation_type,
                    KnowledgeEdge.target_type,
                    KnowledgeEdge.target_id,
                    KnowledgeEdge.evidence_chunk_id,
                )
            ).all()
        )

        new_edges: list[KnowledgeEdge] = []

        def _stage_edge(
            *,
            source_id: str,
            relation_type: str,
            target_type: str,
            target_id: str,
            evidence_chunk_id: str | None,
            confidence: float | None,
        ) -> None:
            nonlocal edges_attempted
            edges_attempted += 1
            key: _EdgeKey = (
                "asset",
                source_id,
                relation_type,
                target_type,
                target_id,
                evidence_chunk_id,
            )
            # Skip both edges already in the DB and duplicates within this run.
            if key in seen_keys:
                return
            seen_keys.add(key)
            new_edges.append(
                KnowledgeEdge(
                    id=uuid4().hex,
                    source_type="asset",
                    source_id=source_id,
                    relation_type=relation_type,
                    target_type=target_type,
                    target_id=target_id,
                    evidence_chunk_id=evidence_chunk_id,
                    confidence=confidence,
                    metadata_json={},
                )
            )

        mentions = session.execute(select(AssetMention)).scalars().all()
        for mention in mentions:
            mentions_scanned += 1

            if mention.document_id is not None:
                _stage_edge(
                    source_id=mention.asset_id,
                    relation_type="mentioned_in",
                    target_type="document",
                    target_id=mention.document_id,
                    evidence_chunk_id=mention.chunk_id,
                    confidence=mention.confidence,
                )
            if mention.chunk_id is not None:
                _stage_edge(
                    source_id=mention.asset_id,
                    relation_type="supported_by_chunk",
                    target_type="chunk",
                    target_id=mention.chunk_id,
                    evidence_chunk_id=mention.chunk_id,
                    confidence=mention.confidence,
                )
            if mention.entity_id is not None:
                _stage_edge(
                    source_id=mention.asset_id,
                    relation_type="has_entity",
                    target_type="entity",
                    target_id=mention.entity_id,
                    evidence_chunk_id=mention.chunk_id,
                    confidence=mention.confidence,
                )

        if new_edges:
            session.add_all(new_edges)

        # Flush so the post-count reflects rows added in this transaction before
        # the surrounding session_scope commits.
        session.flush()
        edges_after = int(
            session.execute(
                select(func.count()).select_from(KnowledgeEdge)
            ).scalar_one()
            or 0
        )

    edges_created = edges_after - edges_before
    # Attempts that did not create a row: either an edge already existed (from a
    # prior run / live ingestion) or a duplicate tuple within this run.
    estimated_existing_skipped = edges_attempted - edges_created

    print("Knowledge edge backfill complete:")
    print(f"  asset_mentions_scanned     : {mentions_scanned}")
    print(f"  edges_attempted            : {edges_attempted}")
    print(f"  edges_created_or_existing  : {edges_attempted}")
    print(f"  edges_created (new rows)   : {edges_created}")
    print(f"  estimated_existing_skipped : {estimated_existing_skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
