"""Pydantic schema describing an ingested document."""

from pydantic import BaseModel


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
