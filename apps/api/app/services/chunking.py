"""Deterministic character-based text chunking and local persistence.

This is a Week 1 foundation slice ahead of embeddings and RAG. Chunking is a
simple fixed-size sliding window over the extracted text — no tokenization,
sentence splitting, or model calls. Chunks are persisted to a flat JSON file
keyed by document id so they can be retrieved per document.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core import config
from app.core.config import settings
from app.models.chunk import Chunk

# Fixed, deterministic chunking parameters. Overlap preserves context across
# boundaries so retrieval does not miss spans that straddle a cut.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
_STRIDE = CHUNK_SIZE - CHUNK_OVERLAP

_CHUNKS_FILENAME = "chunks.json"


def _storage_dir() -> Path:
    """Return the storage directory, creating it if necessary."""
    path = Path(settings.storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _chunks_path() -> Path:
    return _storage_dir() / _CHUNKS_FILENAME


def chunk_text(document_id: str, text: str) -> list[Chunk]:
    """Split ``text`` into ordered, overlapping fixed-size chunks.

    Returns an empty list for empty text. Chunk ids are stable, derived from
    the document id and the chunk index.
    """
    if not text:
        return []

    chunks: list[Chunk] = []
    length = len(text)
    start = 0
    index = 0
    while start < length:
        end = min(start + CHUNK_SIZE, length)
        chunks.append(
            Chunk(
                id=f"{document_id}-{index}",
                document_id=document_id,
                chunk_index=index,
                text=text[start:end],
                char_start=start,
                char_end=end,
            )
        )
        if end == length:
            break
        start += _STRIDE
        index += 1

    return chunks


def _load_all() -> dict[str, list[dict]]:
    path = _chunks_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_chunks(document_id: str, chunks: list[Chunk]) -> None:
    """Persist a document's chunks, replacing any existing entry."""
    store = _load_all()
    store[document_id] = [chunk.model_dump() for chunk in chunks]
    _chunks_path().write_text(json.dumps(store, indent=2), encoding="utf-8")


def get_chunks(document_id: str) -> list[Chunk]:
    """Return the persisted chunks for a document, or an empty list."""
    if config.use_postgres():
        from app.db import repository as repo

        return [
            Chunk(
                id=record["id"],
                document_id=record["document_id"],
                chunk_index=record["chunk_index"],
                text=record["text"],
                char_start=record["char_start"] or 0,
                char_end=record["char_end"] or 0,
            )
            for record in repo.list_document_chunks(document_id)
        ]
    records = _load_all().get(document_id, [])
    return [Chunk(**record) for record in records]
