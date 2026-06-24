"""Pydantic schemas describing vector embeddings of document chunks."""

from pydantic import BaseModel


class ChunkEmbedding(BaseModel):
    """A single chunk's embedding vector and its provenance.

    The full ``vector`` is persisted locally; API responses expose only a short
    ``preview`` (see :class:`EmbeddingPreview`) to avoid returning large arrays.
    """

    chunk_id: str
    document_id: str
    chunk_index: int
    model: str
    dimension: int
    vector: list[float]


class EmbeddingPreview(BaseModel):
    """Lightweight view of a chunk embedding for API responses."""

    chunk_id: str
    document_id: str
    chunk_index: int
    dimension: int
    preview: list[float]


class DocumentEmbeddings(BaseModel):
    """All chunk embeddings belonging to one document, in preview form."""

    document_id: str
    embedding_model: str
    dimension: int
    embeddings: list[EmbeddingPreview]
