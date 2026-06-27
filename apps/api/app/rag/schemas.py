"""Schemas and small data models for the Week 1 RAG pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedTextUnit(BaseModel):
    file_name: str
    source_path: str
    text: str
    unit_index: int
    page_number: int | None = None
    row_number: int | None = None
    metadata: dict = Field(default_factory=dict)


class RAGChunk(BaseModel):
    document_id: str
    file_name: str
    source_path: str
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    token_count: int
    page_number: int | None = None
    row_number: int | None = None
    metadata: dict = Field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.document_id}-{self.chunk_index}"


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    score: float
    distance: float | None = None
    file_name: str
    source_path: str | None = None
    page_number: int | None = None
    row_number: int | None = None
    chunk_index: int
    metadata: dict = Field(default_factory=dict)


class RAGCitation(BaseModel):
    file_name: str
    page: int | None = None
    row: int | None = None
    chunk_id: str
    source_path: str | None = None
    snippet: str


class RAGQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=20)


class RAGQueryResponse(BaseModel):
    answer: str
    citations: list[RAGCitation]
    confidence: float = Field(..., ge=0.0, le=1.0)
    missing_info: list[str] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk]


class RAGSearchResponse(BaseModel):
    query: str
    results: list[RetrievedChunk]


class RAGIngestRequest(BaseModel):
    path: str = "data/documents"
    force_reingest: bool = False


class RAGIngestResponse(BaseModel):
    documents_ingested: int
    chunks_created: int
    embeddings_created: int
    skipped: list[str] = Field(default_factory=list)

