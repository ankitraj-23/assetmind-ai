"""Backward-compatible ``POST /query`` route.

This endpoint preserves the original ``QueryRequest``/``QueryResponse`` contract
(used by the frontend ``askQuestion`` helper) but is now a thin adapter over the
*canonical* RAG pipeline that backs ``/rag/chat`` and the genuine benchmark. It
reuses the same embedding provider, hybrid retrieval, asset scoping, grounded
citations and deterministic/Gemini answer path — no separate retrieval
architecture is created here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core import config
from app.models.query import QueryCitation, QueryRequest, QueryResponse
from app.rag import answer as answer_service
from app.rag.chat import _apply_asset_scope, _normalize_asset_tag
from app.rag.retrieval import retrieve_relevant_chunks
from app.rag.schemas import RAGQueryResponse
from app.routes.rag import _handle_error
from app.services.entity_extraction import extract_equipment_tags

# Intent classification only — a pure regex classifier, not a retrieval path.
from app.services.query import detect_intent

router = APIRouter(tags=["query"])

# Confidence-label thresholds preserved from the original /query contract so the
# frontend keeps receiving "high"/"medium"/"low" rather than a raw float.
HIGH_CONFIDENCE_SCORE = 0.60
MEDIUM_CONFIDENCE_SCORE = 0.30


def _confidence_label(score: float) -> str:
    if score >= HIGH_CONFIDENCE_SCORE:
        return "high"
    if score >= MEDIUM_CONFIDENCE_SCORE:
        return "medium"
    return "low"


def _related_assets(chunks, exclude_tag: str | None) -> list[str]:
    """Unique equipment tags mentioned across retrieved chunks (minus the query tag)."""
    exclude = exclude_tag.upper() if exclude_tag else None
    seen: set[str] = set()
    related: list[str] = []
    for chunk in chunks:
        text = chunk.raw_text or chunk.content or ""
        for tag in extract_equipment_tags(text):
            norm = tag.normalized_value
            if norm == exclude or norm in seen:
                continue
            seen.add(norm)
            related.append(norm)
    return related


def _to_query_citations(rag: RAGQueryResponse) -> list[QueryCitation]:
    """Adapt canonical ``RAGCitation`` objects to the legacy ``QueryCitation`` shape.

    ``document_id``/``chunk_index``/``score`` live on the retrieved chunk, so we
    enrich each citation from its originating chunk (matched by ``chunk_id``).
    """
    chunk_by_id = {chunk.chunk_id: chunk for chunk in rag.retrieved_chunks}
    citations: list[QueryCitation] = []
    for citation in rag.citations:
        chunk = chunk_by_id.get(citation.chunk_id)
        citations.append(
            QueryCitation(
                document_id=(
                    chunk.document_id
                    if chunk
                    else citation.parent_chunk_id or citation.chunk_id
                ),
                chunk_id=citation.chunk_id,
                chunk_index=chunk.chunk_index if chunk else 0,
                score=round(chunk.score, 6) if chunk else 0.0,
                text_preview=citation.snippet,
                filename=citation.file_name,
                page_number=citation.page,
            )
        )
    return citations


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    """Answer a question via the canonical RAG pipeline with citations and metadata."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="'question' must not be empty.")
    if not config.use_postgres():
        raise HTTPException(
            status_code=400,
            detail="/query requires PERSISTENCE_BACKEND=postgres.",
        )

    asset_tag = _normalize_asset_tag(request.asset_tag)
    scoped_question = _apply_asset_scope(request.question, asset_tag)

    try:
        retrieved = retrieve_relevant_chunks(scoped_question, top_k=request.top_k)
        rag_response = answer_service.answer_with_chunks(
            request.question,
            retrieved,
            standalone_question=scoped_question,
        )
    except Exception as exc:  # adapt pipeline errors to proper HTTP status codes
        raise _handle_error(exc) from exc

    return QueryResponse(
        question=request.question,
        answer=rag_response.answer,
        confidence=_confidence_label(rag_response.confidence),
        citations=_to_query_citations(rag_response),
        retrieved_count=len(rag_response.retrieved_chunks),
        query_intent=detect_intent(request.question),
        related_assets=_related_assets(rag_response.retrieved_chunks, asset_tag),
    )
