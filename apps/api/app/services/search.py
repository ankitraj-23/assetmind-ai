"""Vector search over stored chunk embeddings.

Retrieval only: a query is embedded with the existing local embedding function
and compared against every stored chunk embedding using cosine similarity. The
top-k chunks are returned with their text and citation metadata. No LLM answer
is generated here.

The chunk *text* lives in the chunking store and the *vectors* live in the
embeddings store, so results are assembled by joining the two per document on
``chunk_id``. Both stores are reached through their public service functions, so
this module owns no persistence of its own.
"""

from __future__ import annotations

import math

from app.models.search import Citation, SearchResult
from app.services import chunking, embeddings, ingestion


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return the cosine similarity of two equal-length vectors.

    Returns ``0.0`` when either vector has zero magnitude. Stored and query
    vectors are already L2-normalized, so this reduces to a dot product, but the
    guarded form keeps it correct if normalization ever changes.
    """
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def search(query: str, top_k: int = 5) -> list[SearchResult]:
    """Return the ``top_k`` chunks most similar to ``query``, best first.

    Returns an empty list when nothing is indexed or when the query embeds to a
    zero vector (no known tokens). Callers are responsible for rejecting empty
    queries.
    """
    top_k = max(1, top_k)
    query_vector = embeddings.embed_text(query)
    if not any(query_vector):
        return []

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
    return scored[:top_k]
