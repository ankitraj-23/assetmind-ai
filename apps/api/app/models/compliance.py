"""Pydantic models for the deterministic compliance and evidence-package agents.

These schemas describe the API contract for:

* ``GET /agents/compliance/gaps`` and
  ``GET /agents/compliance/assets/{asset_tag}`` — explainable compliance gaps
  computed from persisted evidence (asset facts, timeline, chunk text), and
* ``POST /agents/evidence-package`` — a generated, citation-backed Markdown
  evidence package with a working download link.

Every gap carries at least one real supporting-evidence snippet drawn from an
ingested document/chunk; ``document_id``/``chunk_id`` may be ``None`` when the
evidence is not chunk-addressable.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ComplianceEvidence(BaseModel):
    """One piece of persisted evidence supporting a compliance gap."""

    source: str = Field(..., description="Human-readable source (filename).", example="compliance_checklist_2025.pdf")
    text: str = Field(..., description="Verbatim evidence snippet from the document.")
    document_id: Optional[str] = Field(None, description="Source document id, if known.")
    chunk_id: Optional[str] = Field(None, description="Source chunk id, if known.")


class ComplianceGap(BaseModel):
    """A single explainable compliance gap for an asset."""

    asset_tag: str = Field(..., description="Asset the gap belongs to.", example="P-101")
    gap_type: str = Field(
        ...,
        description="Canonical gap category (e.g. inspection_overdue, certificate_expired).",
        example="certificate_expired",
    )
    severity: str = Field(..., description="high | medium | low.", example="high")
    reason: str = Field(..., description="Plain-language explanation of why this is a gap.")
    standard_or_policy: Optional[str] = Field(
        None, description="Referenced standard/policy detected in the evidence.", example="PESO / Factories Act Section 31"
    )
    evidence: List[ComplianceEvidence] = Field(
        default_factory=list, description="Supporting evidence snippets from persisted content."
    )
    recommended_action: str = Field(..., description="Concrete corrective action.")


class ComplianceGapsResponse(BaseModel):
    """Response for the compliance gaps endpoints."""

    count: int = Field(..., description="Number of gaps returned.")
    filters: dict = Field(default_factory=dict, description="Echo of applied filters.")
    gaps: List[ComplianceGap] = Field(default_factory=list, description="The detected gaps.")
    mode: str = Field("postgres", description="Persistence mode used to compute results.")
    message: Optional[str] = Field(None, description="Optional note (e.g. JSON-mode fallback).")


class EvidencePackageRequest(BaseModel):
    """Request body for POST /agents/evidence-package."""

    asset_tag: str = Field(..., description="Asset to compile the package for.", example="P-101")
    package_type: str = Field("audit", description="Package type.", example="audit")


class EvidenceDocumentRef(BaseModel):
    """A source document included in an evidence package."""

    document_id: Optional[str] = None
    filename: Optional[str] = None
    chunk_count: Optional[int] = None


class EvidenceFinding(BaseModel):
    """An inspection or maintenance evidence line included in the package."""

    text: str
    source: Optional[str] = None
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    category: Optional[str] = None


class EvidencePackageResponse(BaseModel):
    """Response for POST /agents/evidence-package."""

    package_id: str
    asset_tag: str
    package_type: str
    generated_at: str
    summary: str
    included_documents: List[EvidenceDocumentRef] = Field(default_factory=list)
    compliance_gaps: List[ComplianceGap] = Field(default_factory=list)
    inspection_findings: List[EvidenceFinding] = Field(default_factory=list)
    maintenance_evidence: List[EvidenceFinding] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    download_url: str
