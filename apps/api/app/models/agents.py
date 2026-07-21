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