"""Pydantic schemas describing vector search requests and results."""

from pydantic import BaseModel


class Citation(BaseModel):
    """Minimal provenance for a retrieved chunk, for downstream RAG citations."""

    document_id: str
    chunk_id: str
    chunk_index: int


class SearchResult(BaseModel):
    """A single retrieved chunk with its similarity score and citation."""

    document_id: str
    chunk_id: str
    chunk_index: int
    score: float
    text: str
    citation: Citation


class SearchResponse(BaseModel):
    """Top-k retrieval results for a query. Retrieval only — no generated answer."""

    query: str
    top_k: int
    results: list[SearchResult]
