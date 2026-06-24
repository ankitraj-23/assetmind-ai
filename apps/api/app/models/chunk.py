"""Pydantic schemas describing retrievable text chunks of a document."""

from pydantic import BaseModel


class Chunk(BaseModel):
    """A single ordered, character-bounded slice of a document's text."""

    id: str
    document_id: str
    chunk_index: int
    text: str
    char_start: int
    char_end: int


class DocumentChunks(BaseModel):
    """All chunks belonging to one document."""

    document_id: str
    chunks: list[Chunk]
