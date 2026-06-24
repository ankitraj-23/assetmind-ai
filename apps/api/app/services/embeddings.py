"""Deterministic local chunk embeddings and local persistence.

This is a Week 1 foundation slice. Embeddings are produced with a dependency-free
feature-hashing ("hashing trick") method so the backend can build and query a
vector representation of every chunk without any external API, API key, or heavy
model download.

The method is intentionally simple and temporary:

* Tokenize the chunk text into lowercase word tokens.
* Hash each token with :mod:`hashlib` (stable across processes, unlike the
  salted built-in ``hash``) into one of ``EMBEDDING_DIMENSION`` buckets, with a
  per-token sign bit, and accumulate ``+/-1`` per bucket.
* L2-normalize the vector so values are bounded floats.

Everything is hidden behind :func:`embed_text` plus the ``EMBEDDING_MODEL`` /
``EMBEDDING_DIMENSION`` constants, so this can later be swapped for OpenAI,
Gemini, or SentenceTransformers embeddings without changing callers or the
stored JSON shape.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.embedding import ChunkEmbedding

# Identifier and size of the current (development) embedding scheme. Bump the
# version suffix whenever the vectorization changes so stored vectors stay
# traceable to the method that produced them.
EMBEDDING_MODEL = "local-hashing-v1"
EMBEDDING_DIMENSION = 384

# Number of decimals retained when persisting/serving vectors. Keeps the local
# JSON readable without meaningfully affecting the values.
_ROUND_NDIGITS = 6
# Length of the debugging preview returned by the API.
PREVIEW_LENGTH = 3

_EMBEDDINGS_FILENAME = "embeddings.json"
_TOKEN_RE = re.compile(r"\w+")


def _storage_dir() -> Path:
    """Return the storage directory, creating it if necessary."""
    path = Path(settings.storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _embeddings_path() -> Path:
    return _storage_dir() / _EMBEDDINGS_FILENAME


def embed_text(text: str) -> list[float]:
    """Return a deterministic ``EMBEDDING_DIMENSION``-length vector for ``text``.

    Empty or whitespace-only text yields an all-zero vector of the correct
    dimension. This is the single seam to replace with a real embedding model.
    """
    vector = [0.0] * EMBEDDING_DIMENSION
    tokens = _TOKEN_RE.findall(text.lower())
    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [round(value / norm, _ROUND_NDIGITS) for value in vector]


def embed_chunks(document_id: str, chunks: list[Chunk]) -> list[ChunkEmbedding]:
    """Build embeddings for every chunk of a document (order preserved)."""
    return [
        ChunkEmbedding(
            chunk_id=chunk.id,
            document_id=document_id,
            chunk_index=chunk.chunk_index,
            model=EMBEDDING_MODEL,
            dimension=EMBEDDING_DIMENSION,
            vector=embed_text(chunk.text),
        )
        for chunk in chunks
    ]


def _load_all() -> dict[str, list[dict]]:
    path = _embeddings_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_embeddings(document_id: str, embeddings: list[ChunkEmbedding]) -> None:
    """Persist a document's embeddings, replacing any existing entry."""
    store = _load_all()
    store[document_id] = [embedding.model_dump() for embedding in embeddings]
    _embeddings_path().write_text(json.dumps(store, indent=2), encoding="utf-8")


def get_embeddings(document_id: str) -> list[ChunkEmbedding]:
    """Return the persisted embeddings for a document, or an empty list."""
    records = _load_all().get(document_id, [])
    return [ChunkEmbedding(**record) for record in records]
