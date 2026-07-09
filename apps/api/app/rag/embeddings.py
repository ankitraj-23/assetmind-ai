"""Gemini embedding wrapper used by the RAG pipeline."""

from __future__ import annotations

import math
import time
from collections.abc import Iterable
from typing import Callable

from app.core.config import settings
from app.db.models import EMBEDDING_DIM

EMBEDDING_MODEL = "gemini-embedding-2"
TARGET_EMBEDDING_DIMENSION = EMBEDDING_DIM
CHUNK_EMBED_DELAY_SECONDS = 3.0


class MissingGeminiApiKeyError(RuntimeError):
    """Raised when a Gemini operation is requested without GEMINI_API_KEY."""


def _api_key() -> str:
    key = (settings.gemini_api_key or "").strip()
    if not key:
        raise MissingGeminiApiKeyError(
            "GEMINI_API_KEY is not set. Set it in the environment or apps/api/.env "
            "before running RAG ingestion, retrieval, or answer generation."
        )
    return key


def ensure_configured() -> None:
    """Raise a clear error if Gemini credentials are missing."""

    _api_key()


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
    return _embed(query, "retrieval_query")
