"""RAG-style query answering over retrieved chunks.

This module turns a question into a citation-backed answer by:

1. retrieving the most relevant chunks via the existing vector ``search``
   service (no vector logic is duplicated here), and
2. composing an answer from those chunks.

The answer generator is a **temporary, deterministic placeholder**. It performs
no LLM or external API calls; it simply frames and surfaces the top retrieved
evidence extractively. It is designed to be replaced by a real LLM later
without changing the request/response contract in ``app.models.query``.
"""

from __future__ import annotations

from app.models.query import QueryCitation, QueryResponse
from app.models.search import SearchResult
from app.services import search as search_service

# Cosine-similarity thresholds (stored/query vectors are L2-normalized) used to
# map the best retrieved score onto a coarse confidence label.
HIGH_CONFIDENCE_SCORE = 0.60
MEDIUM_CONFIDENCE_SCORE = 0.30

# How much chunk text to surface as evidence / citation preview.
PREVIEW_CHARS = 280


def _confidence_for(score: float) -> str:
    """Map the best retrieval score onto a coarse confidence label."""
    if score >= HIGH_CONFIDENCE_SCORE:
        return "high"
    if score >= MEDIUM_CONFIDENCE_SCORE:
        return "medium"
    return "low"


def _preview(text: str) -> str:
    """Return a single-line, length-capped preview of chunk text."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= PREVIEW_CHARS:
        return collapsed
    return collapsed[:PREVIEW_CHARS].rstrip() + "..."


def _compose_answer(question: str, results: list[SearchResult]) -> str:
    """Build a deterministic, extractive answer from retrieved chunks.

    TEMPORARY: this is a stand-in for a real LLM. It does not reason or
    paraphrase; it states that the answer is grounded in the top retrieved
    chunks and surfaces the strongest evidence verbatim.
    """
    top = results[0]
    evidence = _preview(top.text)
    return (
        f"Based on {len(results)} retrieved document chunk(s), the most relevant "
        f'evidence for "{question}" is: "{evidence}" '
        "(This is a temporary extractive answer generated without an LLM; see "
        "the citations for full provenance.)"
    )


NO_CONTEXT_ANSWER = (
    "Not enough indexed context to answer this question. No relevant chunks were "
    "found — ingest related documents via POST /documents and try again."
)


def answer_question(question: str, top_k: int = 5) -> QueryResponse:
    """Answer ``question`` from indexed context with citations and confidence.

    Callers are responsible for rejecting empty questions. When nothing relevant
    is retrieved, returns a ``low``-confidence "not enough indexed context"
    answer with no citations.
    """
    results = search_service.search(question, top_k=top_k)

    if not results:
        return QueryResponse(
            question=question,
            answer=NO_CONTEXT_ANSWER,
            confidence="low",
            citations=[],
            retrieved_count=0,
        )

    citations = [
        QueryCitation(
            document_id=result.document_id,
            chunk_id=result.chunk_id,
            chunk_index=result.chunk_index,
            score=result.score,
            text_preview=_preview(result.text),
            filename=result.filename,
        )
        for result in results
    ]

    return QueryResponse(
        question=question,
        answer=_compose_answer(question, results),
        confidence=_confidence_for(results[0].score),
        citations=citations,
        retrieved_count=len(results),
    )
