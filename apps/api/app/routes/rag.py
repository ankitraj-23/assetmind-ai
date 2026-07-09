"""Gemini-backed RAG endpoints for dataset ingestion, retrieval, and Q&A."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.core import config
from app.db.session import DatabaseNotConfiguredError
from app.rag import answer as answer_service
from app.rag import chat as chat_service
from app.rag import retrieval, storage
from app.rag.embeddings import MissingGeminiApiKeyError
from app.rag.schemas import (
    RAGChatHistoryResponse,
    RAGChatRequest,
    RAGChatResponse,
    RAGChatSessionsResponse,
    RAGIngestRequest,
    RAGIngestResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSearchResponse,
)

router = APIRouter(prefix="/rag", tags=["rag"])


def _require_postgres() -> None:
    if not config.use_postgres():
        raise HTTPException(
            status_code=400,
            detail="RAG endpoints require PERSISTENCE_BACKEND=postgres.",
        )


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MissingGeminiApiKeyError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, DatabaseNotConfiguredError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, (FileNotFoundError, NotADirectoryError, ValueError)):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, SQLAlchemyError):
        return HTTPException(status_code=503, detail=f"Database operation failed: {exc}")
    return HTTPException(status_code=500, detail=str(exc))


@router.post("/ingest-dataset", response_model=RAGIngestResponse)
def ingest_dataset(request: RAGIngestRequest) -> RAGIngestResponse:
    _require_postgres()
    try:
        return storage.ingest_dataset(
            request.path,
            force_reingest=request.force_reingest,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/query", response_model=RAGQueryResponse)
def query(request: RAGQueryRequest) -> RAGQueryResponse:
    _require_postgres()
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="'question' must not be empty.")
    try:
        return answer_service.answer_question(request.question, top_k=request.top_k)
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/chat", response_model=RAGChatResponse)
def chat(request: RAGChatRequest) -> RAGChatResponse:
    _require_postgres()
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="'message' must not be empty.")
    try:
        return chat_service.answer_chat_message(
            request.message,
            session_id=request.session_id,
            user_id=request.user_id,
            top_k=request.top_k,
            asset_tag=request.asset_tag,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/chat/sessions", response_model=RAGChatSessionsResponse)
def chat_sessions(user_id: str | None = None) -> RAGChatSessionsResponse:
    _require_postgres()
    try:
        return chat_service.list_chat_sessions(user_id=user_id)
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/chat/sessions/{session_id}", response_model=RAGChatHistoryResponse)
def chat_history(
    session_id: str,
    user_id: str | None = None,
) -> RAGChatHistoryResponse:
    _require_postgres()
    try:
        return chat_service.get_chat_history(session_id, user_id=user_id)
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/search", response_model=RAGSearchResponse)
def search(
    q: str = Query(..., description="Search query text."),
    top_k: int = Query(5, ge=1, le=20, description="Number of chunks to return."),
) -> RAGSearchResponse:
    _require_postgres()
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query 'q' must not be empty.")
    try:
        return RAGSearchResponse(
            query=q,
            results=retrieval.retrieve_relevant_chunks(q, top_k=top_k),
        )
    except Exception as exc:
        raise _handle_error(exc) from exc

