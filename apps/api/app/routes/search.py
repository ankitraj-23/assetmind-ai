"""Vector search route: retrieve top-k chunks for a query."""

from fastapi import APIRouter, HTTPException, Query

from app.models.search import SearchResponse
from app.services import search as search_service

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., description="Search query text."),
    top_k: int = Query(5, ge=1, le=50, description="Number of chunks to return."),
) -> SearchResponse:
    """Embed the query and return the most similar stored chunks (retrieval only)."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query 'q' must not be empty.")
    results = search_service.search(q, top_k=top_k)
    return SearchResponse(query=q, top_k=top_k, results=results)
