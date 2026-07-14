from typing import List, Optional

from pydantic import BaseModel, Field


class RcaRequest(BaseModel):
    asset_tag: str = Field(..., description="The asset tag to analyze.", example="P-101")
    symptom: str = Field(
        ...,
        description="The observed symptom or problem.",
        example="high vibration after seal replacement",
    )


class RcaEvidence(BaseModel):
    source: str = Field(..., description="The source document of the evidence.", example="work_orders_clean.csv")
    text: str = Field(..., description="The text snippet of the evidence.")
    document_id: Optional[str] = Field(None, description="The ID of the source document.")
    chunk_id: Optional[str] = Field(None, description="The ID of the source chunk.")


class LikelyCause(BaseModel):
    cause: str = Field(..., description="A description of the likely cause.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="The confidence score for this cause (0.0 to 1.0).")
    evidence: List[RcaEvidence] = Field(..., description="A list of evidence snippets supporting this cause.")


class RcaResponse(BaseModel):
    asset_tag: str = Field(..., description="The asset tag that was analyzed.")
    symptom: str = Field(..., description="The symptom that was analyzed.")
    summary: str = Field(..., description="A high-level summary of the RCA findings.")
    likely_causes: List[LikelyCause] = Field(..., description="A list of likely root causes.")
    recommended_actions: List[str] = Field(..., description="A list of recommended next actions.")
    missing_information: List[str] = Field(..., description="A list of information that would improve the analysis.")
    citations: list = Field([], description="Legacy field, content moved into likely_causes.evidence.")


class EvidencePackageRequest(BaseModel):
    asset_tag: Optional[str] = Field(None, description="The asset tag to compile evidence for.", example="P-101")
    standard: Optional[str] = Field(None, description="The standard to compile evidence for.", example="OISD-137")


class EvidenceItem(BaseModel):
    source: str = Field(..., description="Source document or checklist section.")
    text: str = Field(..., description="Verbatim text evidence.")
    status: str = Field("Non-Compliant", description="Status of the item (e.g. Non-Compliant, At Risk, SOP Issue).")


class EvidencePackageResponse(BaseModel):
    package_id: str = Field(..., description="Unique generated package ID.")
    asset_tag: Optional[str] = Field(None, description="The asset tag compiled.")
    standard: Optional[str] = Field(None, description="The standard compiled.")
    generated_at: str = Field(..., description="ISO timestamp of generation.")
    summary: str = Field(..., description="Compiled compliance executive summary.")
    evidence_items: List[EvidenceItem] = Field(..., description="List of evidence items.")
    download_url: str = Field(..., description="Relative download URL path.")