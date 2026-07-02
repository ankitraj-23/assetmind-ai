"""Vector search over stored chunk embeddings with optional asset scoping.

When ``asset_tag`` is provided retrieval works in two stages:
  1. All chunks are scored by cosine similarity as usual.
  2. Chunks that mention the asset tag receive a configurable boost so they
     rank above equally-scored generic chunks.
  3. Citation deduplication ensures no chunk_id appears twice in the result.
  4. Source diversity: at most ``MAX_PER_DOCUMENT`` chunks from one document.
"""

from __future__ import annotations

import re

from app.core import config
from app.models.search import Citation, SearchResult
from app.services import chunking, embeddings, ingestion

# Similarity boost applied to chunks that mention the requested asset tag.
_ASSET_BOOST = 0.15

# Maximum citations returned from a single source document (diversity guard).
MAX_PER_DOCUMENT = 3


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return cosine similarity of two equal-length vectors (0.0 on zero-mag)."""
    import math

    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _mentions_tag(text: str, tag: str) -> bool:
    """Return True if ``text`` contains ``tag`` as a whole word (case-insensitive)."""
    return bool(re.search(rf"\b{re.escape(tag)}\b", text, re.I))


def _deduplicate(results: list[SearchResult], top_k: int) -> list[SearchResult]:
    """Remove duplicate chunk_ids and enforce per-document diversity cap."""
    seen_chunks: set[str] = set()
    doc_counts: dict[str, int] = {}
    out: list[SearchResult] = []

    for r in results:
        if r.chunk_id in seen_chunks:
            continue
        if doc_counts.get(r.document_id, 0) >= MAX_PER_DOCUMENT:
            continue
        seen_chunks.add(r.chunk_id)
        doc_counts[r.document_id] = doc_counts.get(r.document_id, 0) + 1
        out.append(r)
        if len(out) >= top_k:
            break

    return out


def search(
    query: str,
    top_k: int = 5,
    asset_tag: str | None = None,
) -> list[SearchResult]:
    """Return the ``top_k`` chunks most similar to ``query``.

    When ``asset_tag`` is set, chunks mentioning that tag receive a score
    boost so they rank ahead of equally similar but unrelated chunks.
    Results are deduplicated (no repeated chunk_id) and capped per document.
    """
    top_k = max(1, top_k)
    query_vector = embeddings.embed_text(query)
    if not any(query_vector):
        return []

    # Fetch a larger pool before deduplication so diversity trimming can't
    # reduce the final list below top_k.
    pool_size = top_k * MAX_PER_DOCUMENT + 10

    if config.use_postgres():
        raw = _search_postgres(query_vector, pool_size, asset_tag)
    else:
        raw = _search_json(query_vector, pool_size, asset_tag)

    return _deduplicate(raw, top_k)


def _apply_asset_boost(
    results: list[SearchResult],
    asset_tag: str,
) -> list[SearchResult]:
    """Boost scores of chunks that mention ``asset_tag`` and re-sort."""
    boosted = []
    for r in results:
        boosted_score = r.score
        if _mentions_tag(r.text, asset_tag):
            boosted_score = min(1.0, r.score + _ASSET_BOOST)
        boosted.append(r.model_copy(update={"score": round(boosted_score, 6)}))
    boosted.sort(key=lambda r: (-r.score, r.document_id, r.chunk_index))
    return boosted


def _search_json(
    query_vector: list[float],
    pool_size: int,
    asset_tag: str | None,
) -> list[SearchResult]:
    scored: list[SearchResult] = []
    for document in ingestion.list_documents():
        chunk_text = {chunk.id: chunk.text for chunk in chunking.get_chunks(document.id)}
        for record in embeddings.get_embeddings(document.id):
            text = chunk_text.get(record.chunk_id)
            if text is None:
                continue
            score = cosine_similarity(query_vector, record.vector)
            scored.append(
                SearchResult(
                    document_id=record.document_id,
                    chunk_id=record.chunk_id,
                    chunk_index=record.chunk_index,
                    score=round(score, 6),
                    text=text,
                    filename=document.filename,
                    citation=Citation(
                        document_id=record.document_id,
                        chunk_id=record.chunk_id,
                        chunk_index=record.chunk_index,
                        filename=document.filename,
                    ),
                )
            )

    scored.sort(key=lambda r: (-r.score, r.document_id, r.chunk_index))

    if asset_tag:
        scored = _apply_asset_boost(scored, asset_tag)

    return scored[:pool_size]


def _search_postgres(
    query_vector: list[float],
    pool_size: int,
    asset_tag: str | None,
) -> list[SearchResult]:
    from app.db import repository as repo

    scored: list[SearchResult] = []
    for record in repo.get_all_chunks_with_embeddings():
        vector = record.get("embedding")
        if not vector:
            continue
        document = record.get("document") or {}
        filename = document.get("filename")
        score = cosine_similarity(query_vector, vector)
        scored.append(
            SearchResult(
                document_id=record["document_id"],
                chunk_id=record["id"],
                chunk_index=record["chunk_index"],
                score=round(score, 6),
                text=record["text"],
                filename=filename,
                citation=Citation(
                    document_id=record["document_id"],
                    chunk_id=record["id"],
                    chunk_index=record["chunk_index"],
                    filename=filename,
                ),
            )
        )

    scored.sort(key=lambda r: (-r.score, r.document_id, r.chunk_index))

    if asset_tag:
        scored = _apply_asset_boost(scored, asset_tag)

    return scored[:pool_size]
