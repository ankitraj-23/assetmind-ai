"""Canonical embedding provider shared by ingestion, retrieval, and querying.

This is the *single embedding contract* for the whole system. Both indexing
(document ingestion, dataset ingestion, re-indexing) and querying (RAG chat /
query / search, hybrid retrieval, benchmarks) must obtain their vectors here so
that indexed and queried vectors are always produced by the *same* provider and
model — never a Gemini query against a locally-hashed index or vice versa.

Two providers are supported:

* **gemini** — used whenever ``GEMINI_API_KEY`` is configured. Dense semantic
  embeddings via ``gemini-embedding-2`` (or the configured model), fitted to
  :data:`app.db.models.EMBEDDING_DIM`.
* **local** — a deterministic, dependency-free ``local-hashing-v1`` fallback
  (:func:`app.services.embeddings.embed_text`) used when Gemini is unavailable.
  The *exact same* algorithm and model metadata are used for both indexing and
  querying, so the local index stays internally comparable.

:func:`active_provider` / :func:`active_model` report which is in effect so
callers can tag stored vectors and filter retrieval to compatible vectors only.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterable
from typing import Callable

from app.core.config import settings
from app.db.models import EMBEDDING_DIM
from app.services import embeddings as local_embeddings

EMBEDDING_MODEL = "gemini-embedding-2"
TARGET_EMBEDDING_DIMENSION = EMBEDDING_DIM
CHUNK_EMBED_DELAY_SECONDS = 3.0

# Metadata for the deterministic fallback. Kept identical to the algorithm in
# app.services.embeddings so a vector's ``embedding_model`` unambiguously
# identifies how it was produced.
LOCAL_EMBEDDING_MODEL = local_embeddings.EMBEDDING_MODEL
LOCAL_EMBEDDING_PROVIDER = "local"
GEMINI_EMBEDDING_PROVIDER = "gemini"


class MissingGeminiApiKeyError(RuntimeError):
    """Raised when a Gemini operation is requested without GEMINI_API_KEY."""


def gemini_available() -> bool:
    """Return True when a non-empty ``GEMINI_API_KEY`` is configured."""

    return bool((settings.gemini_api_key or "").strip())


def active_provider() -> str:
    """Return the provider currently used for both indexing and querying."""

    return GEMINI_EMBEDDING_PROVIDER if gemini_available() else LOCAL_EMBEDDING_PROVIDER


def active_model() -> str:
    """Return the model identifier stored alongside vectors from this provider."""

    return _embedding_model() if gemini_available() else LOCAL_EMBEDDING_MODEL


def _api_key() -> str:
    key = (settings.gemini_api_key or "").strip()
    if not key:
        raise MissingGeminiApiKeyError(
            "GEMINI_API_KEY is not set. Set it in the environment or apps/api/.env "
            "before running RAG ingestion, retrieval, or answer generation."
        )
    return key


def ensure_configured() -> None:
    """No-op compatibility hook.

    A deterministic local fallback is always available, so ingestion and
    retrieval never hard-require Gemini. Retained for callers that used to gate
    on Gemini configuration.
    """

    return None


def _embedding_model() -> str:
    return (settings.gemini_embedding_model or EMBEDDING_MODEL).strip()


def _client():
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is required for Gemini embeddings. "
            "Run 'pip install -r requirements.txt' from apps/api."
        ) from exc

    return genai.Client(api_key=_api_key())


def _fit_dimension(vector: Iterable[float]) -> list[float]:
    values = [float(value) for value in vector]
    if len(values) > TARGET_EMBEDDING_DIMENSION:
        values = values[:TARGET_EMBEDDING_DIMENSION]
    elif len(values) < TARGET_EMBEDDING_DIMENSION:
        values.extend([0.0] * (TARGET_EMBEDDING_DIMENSION - len(values)))

    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        return values
    return [value / norm for value in values]


def _embed(text: str, task_type: str) -> list[float]:
    try:
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is required for Gemini embeddings. "
            "Run 'pip install -r requirements.txt' from apps/api."
        ) from exc

    client = _client()
    result = client.models.embed_content(
        model=_embedding_model(),
        contents=text,
        config=types.EmbedContentConfig(
            task_type=task_type.upper(),
            output_dimensionality=TARGET_EMBEDDING_DIMENSION,
        ),
    )

    embeddings = getattr(result, "embeddings", None) or []
    embedding = embeddings[0].values if embeddings else None
    if embedding is None and getattr(result, "embedding", None) is not None:
        embedding = result.embedding.values
    if embedding is None:
        raise RuntimeError("Gemini embedding response did not include an embedding.")
    return _fit_dimension(embedding)


def embed_text(text: str) -> list[float]:
    """Embed a document/chunk for indexing with the active provider."""

    if not gemini_available():
        return local_embeddings.embed_text(text)
    return _embed(text, "retrieval_document")


def embed_texts(
    texts: list[str],
    *,
    delay_seconds: float = CHUNK_EMBED_DELAY_SECONDS,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[list[float]]:
    """Embed chunks one at a time, pausing before each Gemini request."""

    vectors: list[list[float]] = []
    total = len(texts)
    for index, text in enumerate(texts, start=1):
        if progress_callback is not None:
            progress_callback(index, total)
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        vectors.append(embed_text(text))
    return vectors


def embed_query(query: str) -> list[float]:
    """Embed a query for retrieval with the active provider.

    The provider and model must match those used at indexing time; the local
    fallback uses the identical ``local-hashing-v1`` algorithm as the index.
    """

    if not gemini_available():
        return local_embeddings.embed_text(query)
    return _embed(query, "retrieval_query")
