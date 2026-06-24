"""Pydantic schemas describing vector search requests and results."""

from pydantic import BaseModel


class Citation(BaseModel):
    """Minimal provenance for a retrieved chunk, for downstream RAG citations.

    ``filename`` is the human-readable source document name, surfaced for
    demo-friendly citations. It is optional so older/partial data without a
    resolvable document still produces a valid citation.
    """

    document_id: str
    chunk_id: str
    chunk_index: int
    filename: str | None = None


class SearchResult(BaseModel):
    """A single retrieved chunk with its similarity score and citation."""

    document_id: str
    chunk_id: str
    chunk_index: int
    score: float
    text: str
    filename: str | None = None
    citation: Citation


class SearchResponse(BaseModel):
    """Top-k retrieval results for a query. Retrieval only — no generated answer."""

    query: str
    top_k: int
    results: list[SearchResult]
