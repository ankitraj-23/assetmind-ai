"""Schemas and small data models for the Week 1 RAG pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ElementType = Literal[
    "heading",
    "paragraph",
    "list_item",
    "image",
    "table_row",
    "table_block",
    "image_caption",
    "ocr_text",
    "metadata",
]
SourceType = Literal[
    "pdf",
    "csv",
    "xlsx",
    "txt",
    "md",
    "image",
    "scanned_pdf",
    "email",
    "unknown",
]
Modality = Literal["text", "table", "image", "ocr"]
SummaryStrategy = Literal[
    "llm",
    "template",
    "passthrough",
    "vision_future",
    "visual_llm",
    "visual_template",
    "parent_llm",
    "manual_parent_llm",
    "parent_template",
    "parent_passthrough",
]


class AtomicElementSummary(BaseModel):
    """Summary for one atomic visual element before parent summarization."""

    element_id: str
    element_type: ElementType
    summary_text: str
    summary_strategy: SummaryStrategy
    asset_tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class VisualElementEvidence(BaseModel):
    """Original visual element evidence retained for answer generation."""

    element_id: str
    element_type: ElementType
    text: str
    source_type: SourceType
    file_name: str
    source_path: str
    page_number: int | None = None
    row_index: int | None = None
    section_title: str | None = None
    bbox: dict | None = None
    asset_tags: list[str] = Field(default_factory=list)
    modality: Modality = "image"
    metadata: dict = Field(default_factory=dict)


class DocumentElement(BaseModel):
    """Normalized content unit extracted from any supported source."""

    element_id: str
    document_id: str | None = None
    element_type: ElementType
    text: str
    source_type: SourceType
    file_name: str
    source_path: str
    page_number: int | None = None
    row_index: int | None = None
    section_title: str | None = None
    bbox: dict | None = None
    asset_tags: list[str] = Field(default_factory=list)
    modality: Modality = "text"
    element_summary: str | None = None
    summary_strategy: SummaryStrategy | None = None
    metadata: dict = Field(default_factory=dict)


class ParentChunkSummary(BaseModel):
    """Retrieval summary plus metadata generated for one parent chunk."""

    parent_chunk_id: str
    summary_text: str
    answerable_questions: list[str] = Field(default_factory=list)
    asset_tags: list[str] = Field(default_factory=list)
    summary_strategy: SummaryStrategy
    metadata: dict = Field(default_factory=dict)


class ExtractedTextUnit(BaseModel):
    """Backward-compatible extraction shape from the first RAG slice."""

    file_name: str
    source_path: str
    text: str
    unit_index: int
    page_number: int | None = None
    row_number: int | None = None
    metadata: dict = Field(default_factory=dict)


class ParentChunk(BaseModel):
    """Raw parent chunk sent to the final answer model as evidence."""

    document_id: str
    parent_chunk_id: str
    chunk_index: int
    raw_text: str
    source_file: str
    source_path: str
    source_type: SourceType
    page_start: int | None = None
    page_end: int | None = None
    row_start: int | None = None
    row_end: int | None = None
    section_title: str | None = None
    element_ids: list[str] = Field(default_factory=list)
    asset_tags: list[str] = Field(default_factory=list)
    modality: Modality = "text"
    element_summaries: list[AtomicElementSummary] = Field(default_factory=list)
    visual_elements: list[VisualElementEvidence] = Field(default_factory=list)
    parent_summary: ParentChunkSummary | None = None
    metadata: dict = Field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.parent_chunk_id

    @property
    def file_name(self) -> str:
        return self.source_file

    @property
    def content(self) -> str:
        return self.raw_text

    @property
    def page_number(self) -> int | None:
        return self.page_start

    @property
    def row_number(self) -> int | None:
        return self.row_start


class RetrievalUnit(BaseModel):
    """Summary-indexed retrieval unit linked to one raw parent chunk."""

    retrieval_unit_id: str
    parent_chunk_id: str
    document_id: str
    summary_text: str
    asset_tags: list[str] = Field(default_factory=list)
    modality: Modality = "text"
    source_file: str
    source_path: str
    source_type: SourceType
    page_start: int | None = None
    page_end: int | None = None
    row_start: int | None = None
    row_end: int | None = None
    section_title: str | None = None
    answerable_questions: list[str] = Field(default_factory=list)
    summary_strategy: SummaryStrategy
    metadata: dict = Field(default_factory=dict)


# Backward-compatible alias for code/tests from the first RAG slice.
RAGChunk = ParentChunk


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    parent_chunk_id: str | None = None
    retrieval_unit_id: str | None = None
    content: str
    raw_text: str | None = None
    retrieval_summary: str | None = None
    answerable_questions: list[str] = Field(default_factory=list)
    summary_strategy: SummaryStrategy | None = None
    score: float
    distance: float | None = None
    file_name: str
    source_path: str | None = None
    source_type: SourceType | None = None
    page_number: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    row_number: int | None = None
    row_index: int | None = None
    row_start: int | None = None
    row_end: int | None = None
    section_title: str | None = None
    asset_tags: list[str] = Field(default_factory=list)
    modality: Modality | None = None
    element_summaries: list[dict] = Field(default_factory=list)
    visual_elements: list[dict] = Field(default_factory=list)
    chunk_index: int
    metadata: dict = Field(default_factory=dict)


class RAGCitation(BaseModel):
    file_name: str
    page: int | None = None
    row: int | None = None
    section_title: str | None = None
    parent_chunk_id: str | None = None
    retrieval_unit_id: str | None = None
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
    elements_extracted: int = 0
    atomic_summaries_created: int = 0
    chunks_created: int
    parent_chunks_created: int = 0
    retrieval_summaries_created: int = 0
    embeddings_created: int
    template_summaries_count: int = 0
    llm_summaries_count: int = 0
    fallback_summaries_count: int = 0
    skipped: list[str] = Field(default_factory=list)

