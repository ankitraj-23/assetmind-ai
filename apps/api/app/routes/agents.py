from fastapi import APIRouter, HTTPException

from app.models.agents import RcaRequest, RcaResponse
from app.services.rca import perform_rca

router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
)


@router.post(
    "/rca",
    response_model=RcaResponse,
    summary="Perform Root Cause Analysis",
    description="""
Performs an evidence-backed Root Cause Analysis for a given asset and symptom.
This agent retrieves relevant documents, uses an LLM to analyze them, and
returns a structured response with likely causes, evidence, and recommendations.
""",
)
async def run_rca_agent(request: RcaRequest) -> RcaResponse:
    """
    Run the Root Cause Analysis agent.
    """
    try:
        return await perform_rca(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during RCA: {str(e)}")