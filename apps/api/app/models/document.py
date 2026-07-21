"""Pydantic schema describing an ingested document."""

from pydantic import BaseModel, Field


class Document(BaseModel):
    """Metadata for a single ingested document."""

    id: str
    filename: str
    content_type: str
    size_bytes: int
    text_char_count: int
    status: str
    storage_path: str
    created_at: str
    chunk_count: int = 0

    # Ingestion result fields (populated on the upload response; optional so
    # documents rehydrated from storage without them remain valid).
    embedding_provider: str | None = None
    embedding_model: str | None = None
    assets_extracted: list[str] = Field(default_factory=list)
    entities_extracted: int = 0
    warnings: list[str] = Field(default_factory=list)
