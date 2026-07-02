"""RAG query route: answer a question from retrieved chunks with citations."""

from fastapi import APIRouter, HTTPException

from app.models.query import QueryRequest, QueryResponse
from app.services import query as query_service

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    """Answer a question from indexed context with intent detection and asset scoping."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="'question' must not be empty.")
    return query_service.answer_question(
        request.question,
        top_k=request.top_k,
        asset_tag=request.asset_tag,
    )
