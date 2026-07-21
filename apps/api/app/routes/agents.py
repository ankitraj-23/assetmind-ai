from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.models.agents import RcaRequest, RcaResponse
from app.models.compliance import (
    ComplianceGapsResponse,
    EvidencePackageRequest,
    EvidencePackageResponse,
)
from app.services import compliance as compliance_service
from app.services import evidence_package as evidence_service
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


# ---------------------------------------------------------------------------
# Compliance agent
# ---------------------------------------------------------------------------


@router.get(
    "/compliance/gaps",
    response_model=ComplianceGapsResponse,
    summary="List explainable compliance gaps",
    description="""
Returns deterministic, evidence-backed compliance gaps computed from persisted
content (asset mentions, chunk text, classified timeline). Every gap carries at
least one real supporting-evidence snippet. Supports optional ``asset_tag``,
``severity`` and ``gap_type`` filters. Returns a safe empty response in JSON mode.
""",
)
def get_compliance_gaps(
    asset_tag: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    gap_type: str | None = Query(default=None),
) -> ComplianceGapsResponse:
    result = compliance_service.evaluate_gaps(
        asset_tag=asset_tag, severity=severity, gap_type=gap_type
    )
    return ComplianceGapsResponse(**result)


@router.get(
    "/compliance/assets/{asset_tag}",
    response_model=ComplianceGapsResponse,
    summary="Compliance gaps for a single asset",
)
def get_compliance_gaps_for_asset(
    asset_tag: str,
    severity: str | None = Query(default=None),
    gap_type: str | None = Query(default=None),
) -> ComplianceGapsResponse:
    result = compliance_service.evaluate_gaps(
        asset_tag=asset_tag, severity=severity, gap_type=gap_type
    )
    return ComplianceGapsResponse(**result)


# ---------------------------------------------------------------------------
# Evidence-package agent
# ---------------------------------------------------------------------------


@router.post(
    "/evidence-package",
    response_model=EvidencePackageResponse,
    summary="Generate a citation-backed evidence package",
    description="""
Compiles a substantive Markdown evidence package for an asset from persisted
evidence and the computed compliance gaps, writes it to
``storage/exports/``, and returns a summary plus a working download URL.
""",
)
def generate_evidence_package(
    request: EvidencePackageRequest,
) -> EvidencePackageResponse:
    try:
        result = evidence_service.generate_evidence_package(
            asset_tag=request.asset_tag, package_type=request.package_type
        )
    except evidence_service.ComplianceModeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EvidencePackageResponse(**result)


@router.get(
    "/evidence-package/{package_id}/download",
    summary="Download a generated evidence package (Markdown)",
)
def download_evidence_package(package_id: str) -> FileResponse:
    path = evidence_service.resolve_package_path(package_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Evidence package not found.")
    return FileResponse(
        path,
        media_type="text/markdown",
        filename=path.name,
    )
